from __future__ import annotations

import gc
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import time
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd
import torch
from PIL import Image


DATASET_KEY = "vidore_v3_finance_en"
DATASET_ID = "vidore/vidore_v3_finance_en"
EXPECTED_ENGLISH_QUERIES = 309
EXPECTED_PAGES = 2_942
MINIMUM_COVERAGE = 0.95
INITIAL_DEPTHS = {"stage1": 200, "bm25": 100, "dense": 100}
EXPANDED_DEPTHS = {"stage1": 300, "bm25": 200, "dense": 200}


def _atomic_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _atomic_torch_save(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(value, temporary)
    temporary.replace(path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dataframe_sha256(frame: pd.DataFrame, sort_by: list[str]) -> str:
    ordered = frame.sort_values(sort_by, kind="stable").reset_index(drop=True)
    digest = hashlib.sha256()
    digest.update(json.dumps(list(ordered.columns), separators=(",", ":")).encode("utf-8"))
    digest.update(
        json.dumps([str(dtype) for dtype in ordered.dtypes], separators=(",", ":")).encode("utf-8")
    )
    digest.update(pd.util.hash_pandas_object(ordered, index=False, categorize=True).values.tobytes())
    return digest.hexdigest()


def _source_label(value: Any) -> str:
    if isinstance(value, np.ndarray):
        values = value.tolist()
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        values = [value]
    return "|".join(sorted({str(item) for item in values if item is not None})) or "unknown"


def _minmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    low, high = float(values.min()), float(values.max())
    if abs(high - low) <= 1e-15:
        return np.zeros_like(values)
    return (values - low) / (high - low)


def stable_top_indices(scores: np.ndarray, page_ids: np.ndarray, k: int) -> np.ndarray:
    limit = min(int(k), len(scores))
    return np.lexsort((page_ids.astype(str), -np.asarray(scores, dtype=float)))[:limit]


def make_candidate_indices(
    stage1_scores: np.ndarray,
    bm25_scores: np.ndarray,
    dense_scores: np.ndarray,
    page_ids: np.ndarray,
    depths: dict[str, int],
) -> list[np.ndarray]:
    return [
        np.unique(
            np.concatenate(
                [
                    stable_top_indices(stage1_scores[index], page_ids, depths["stage1"]),
                    stable_top_indices(bm25_scores[index], page_ids, depths["bm25"]),
                    stable_top_indices(dense_scores[index], page_ids, depths["dense"]),
                ]
            )
        )
        for index in range(stage1_scores.shape[0])
    ]


def _coverage(
    query_ids: np.ndarray,
    page_ids: np.ndarray,
    candidates: list[np.ndarray],
    qrel_lookup: dict[tuple[Any, Any], float],
) -> tuple[float, pd.DataFrame]:
    selected = {
        (query_ids[query_index], page_ids[page_index])
        for query_index, pages in enumerate(candidates)
        for page_index in pages
    }
    relevant = {key for key, score in qrel_lookup.items() if score > 0}
    overall = 1.0 if not relevant else len(selected & relevant) / len(relevant)
    rows = []
    for query_index, query_id in enumerate(query_ids):
        query_relevant = {page_id for qid, page_id in relevant if qid == query_id}
        query_selected = {page_ids[index] for index in candidates[query_index]}
        selected_count = len(query_relevant & query_selected)
        rows.append(
            {
                "dataset": DATASET_ID,
                "query_id": str(query_id),
                "relevant_total": len(query_relevant),
                "relevant_selected": selected_count,
                "coverage": np.nan if not query_relevant else selected_count / len(query_relevant),
                "candidate_count": len(candidates[query_index]),
            }
        )
    return float(overall), pd.DataFrame(rows)


def _clear_cuda() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _load_torch(path: Path) -> Any:
    return torch.load(path, map_location="cpu", weights_only=False)


def _valid_score_cache(path: Path, shape: tuple[int, int]) -> bool:
    if not path.is_file():
        return False
    try:
        value = _load_torch(path)
        return tuple(value.shape) == shape and bool(torch.isfinite(value).all())
    except (AttributeError, OSError, RuntimeError, ValueError):
        return False


def _valid_embedding_cache(path: Path, expected_length: int) -> bool:
    if not path.is_file():
        return False
    try:
        value = _load_torch(path)
        return len(value) == expected_length and all(bool(torch.isfinite(item).all()) for item in value)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return False


def _encode_with_backoff(
    label: str,
    function: Callable[..., Any],
    values: Sequence[Any],
    cache_path: Path,
    batch_candidates: list[int],
    batch_sizes: dict[str, Any],
    commit: Callable[[], None],
) -> Any:
    if _valid_embedding_cache(cache_path, len(values)):
        batch_sizes[label] = "cache"
        print(f"{label}: using validated cache", flush=True)
        return _load_torch(cache_path)
    last_error: BaseException | None = None
    for batch_size in batch_candidates:
        try:
            started = time.perf_counter()
            output = function(values, batch_size=batch_size)
            _atomic_torch_save(output, cache_path)
            commit()
            batch_sizes[label] = batch_size
            print(
                f"{label}: encoded {len(values)} items at batch {batch_size} "
                f"in {time.perf_counter() - started:.1f}s",
                flush=True,
            )
            return output
        except (torch.cuda.OutOfMemoryError, RuntimeError) as error:
            if "out of memory" not in str(error).lower():
                raise
            last_error = error
            _clear_cuda()
            print(f"{label}: OOM at batch {batch_size}; retrying", flush=True)
    raise RuntimeError(f"{label}: all frozen batch sizes failed") from last_error


class LazyCorpusImages:
    def __init__(self, dataset: Any):
        self.dataset = dataset

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, index: int | slice) -> Image.Image | list[Image.Image]:
        if isinstance(index, slice):
            return [self[position] for position in range(*index.indices(len(self)))]
        value = self.dataset[int(index)]["image"]
        if isinstance(value, Image.Image):
            return value.convert("RGB")
        if isinstance(value, dict) and value.get("bytes") is not None:
            return Image.open(io.BytesIO(value["bytes"])).convert("RGB")
        if isinstance(value, dict) and value.get("path"):
            return Image.open(value["path"]).convert("RGB")
        raise TypeError(f"Unsupported image payload: {type(value).__name__}")

    def __iter__(self):
        for index in range(len(self)):
            yield self[index]


def _build_frames(
    query_ids: np.ndarray,
    page_ids: np.ndarray,
    query_sources: list[str],
    candidates: list[np.ndarray],
    qrel_lookup: dict[tuple[Any, Any], float],
    bm25_scores: np.ndarray,
    dense_scores: np.ndarray,
    stage1_scores: np.ndarray,
    visual_scores: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_rows = []
    normalized_rows = []
    page_keys = page_ids.astype(str)
    for query_index, pages_value in enumerate(candidates):
        pages = np.asarray(pages_value, dtype=int)
        raw_values = {
            "bm25_score": bm25_scores[query_index, pages].astype(float),
            "dense_score": dense_scores[query_index, pages].astype(float),
            "stage1_score": stage1_scores[query_index, pages].astype(float),
            "visual_score": visual_scores[query_index, pages].astype(float),
        }
        normalized = {name: _minmax(values) for name, values in raw_values.items()}
        ranks = {}
        for name, values in normalized.items():
            order = np.lexsort((page_keys[pages], -values))
            branch_ranks = np.empty(len(pages), dtype=int)
            branch_ranks[order] = np.arange(1, len(pages) + 1)
            ranks[name] = branch_ranks
        for local_index, page_index in enumerate(pages):
            common = {
                "dataset": DATASET_ID,
                "query_id": str(query_ids[query_index]),
                "page_id": str(page_ids[page_index]),
                "source": query_sources[query_index],
                "relevance": float(
                    qrel_lookup.get((query_ids[query_index], page_ids[page_index]), 0.0)
                ),
            }
            raw_rows.append(
                {
                    **common,
                    **{name: float(values[local_index]) for name, values in raw_values.items()},
                    "candidate_provenance": "union_dse_bm25_bge",
                }
            )
            normalized_rows.append(
                {
                    **common,
                    **{name: float(values[local_index]) for name, values in normalized.items()},
                    "branch_ranks": json.dumps(
                        {
                            "bm25": int(ranks["bm25_score"][local_index]),
                            "dense": int(ranks["dense_score"][local_index]),
                            "stage1": int(ranks["stage1_score"][local_index]),
                            "visual": int(ranks["visual_score"][local_index]),
                        },
                        separators=(",", ":"),
                    ),
                }
            )
    keys = ["dataset", "query_id", "page_id"]
    raw = pd.DataFrame(raw_rows).sort_values(keys, kind="stable").reset_index(drop=True)
    normalized = pd.DataFrame(normalized_rows).sort_values(keys, kind="stable").reset_index(drop=True)
    return raw, normalized


def run_extraction(
    dataset_config: dict[str, Any],
    environment: dict[str, Any],
    volume_root: Path,
    source_commit: str,
    image_definition_sha256: str,
    extractor_sha256: str,
    function_call_id: str,
    gpu_metadata: dict[str, Any],
    commit: Callable[[], None],
    query_limit: int = 0,
    page_limit: int = 0,
    calibration: bool = False,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    dataset = next(item for item in dataset_config["datasets"] if item["key"] == DATASET_KEY)
    if dataset["revision"] != "7f432c176d82e27546501ad8064a713ac3071809":
        raise RuntimeError("ViDoRe V3 dataset revision drifted")
    models = environment["models"]
    protocol = {
        "name": "vidore_v3_frozen_baseline_extraction_v1",
        "dataset_revision": dataset["revision"],
        "models": models,
        "initial_depths": INITIAL_DEPTHS,
        "expanded_depths": EXPANDED_DEPTHS,
        "minimum_coverage": MINIMUM_COVERAGE,
        "full_score": "intentionally_unavailable",
        "extractor_sha256": extractor_sha256,
    }
    protocol_sha256 = hashlib.sha256(
        json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    scope = f"calibration_q{query_limit}_p{page_limit}" if calibration else "full"
    run_root = volume_root / "score_extraction" / DATASET_KEY / protocol_sha256 / scope
    cache_dir = run_root / "cache"
    output_dir = run_root / "output"
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ["HF_HOME"] = str(volume_root / "hf_cache")
    os.environ["HF_HUB_CACHE"] = str(volume_root / "hf_cache" / "hub")
    os.environ["HF_DATASETS_CACHE"] = str(volume_root / "hf_cache" / "datasets")
    os.environ["NLTK_DATA"] = str(volume_root / "nltk_data")

    from datasets import load_dataset
    from huggingface_hub import snapshot_download
    from vidore_benchmark.retrievers.bm25_retriever import BM25Retriever
    from vidore_benchmark.retrievers.dse_qwen2_retriever import DSEQwen2Retriever

    from scripts.bge_m3_dense_retriever import BGEM3DenseRetriever
    from scripts.colqwen25_retriever import ColQwen25Retriever

    root = Path(dataset["local_dir"])
    corpus_files = sorted((root / "corpus").glob("*.parquet"))
    corpus = load_dataset("parquet", data_files=[str(path) for path in corpus_files], split="train")
    if page_limit:
        corpus = corpus.select(range(min(page_limit, len(corpus))))
    query_frame = pd.read_parquet(root / "queries" / "test-00000-of-00001.parquet")
    query_frame = query_frame.loc[query_frame["language"].eq("english")].sort_values(
        "query_id", kind="stable"
    ).reset_index(drop=True)
    if query_limit:
        query_frame = query_frame.iloc[:query_limit].copy()

    page_ids = np.asarray(corpus["corpus_id"])
    query_ids = query_frame["query_id"].to_numpy()
    query_texts = query_frame["query"].astype(str).tolist()
    corpus_texts = ["" if value is None else str(value) for value in corpus["markdown"]]
    query_sources = [_source_label(value) for value in query_frame["content_type"]]
    if not calibration:
        if len(page_ids) != EXPECTED_PAGES or len(query_ids) != EXPECTED_ENGLISH_QUERIES:
            raise RuntimeError(
                f"Frozen shape mismatch: queries={len(query_ids)}, pages={len(page_ids)}"
            )
    if len(set(page_ids.tolist())) != len(page_ids) or len(set(query_ids.tolist())) != len(query_ids):
        raise RuntimeError("Duplicate query or page identifiers")
    expected_shape = (len(query_ids), len(page_ids))
    images = LazyCorpusImages(corpus)
    timings: dict[str, float] = {}
    batch_sizes: dict[str, Any] = {}
    peaks: dict[str, int] = {}

    import nltk

    Path(os.environ["NLTK_DATA"]).mkdir(parents=True, exist_ok=True)
    for resource in ["punkt", "punkt_tab", "stopwords"]:
        nltk.download(resource, download_dir=os.environ["NLTK_DATA"], quiet=True)
    bm25_path = cache_dir / "bm25_scores.pt"
    stage_started = time.perf_counter()
    if _valid_score_cache(bm25_path, expected_shape):
        bm25_tensor = _load_torch(bm25_path)
    else:
        bm25 = BM25Retriever(device="cpu")
        bm25_tensor = bm25.get_scores_bm25(query_texts, corpus_texts)
        _atomic_torch_save(bm25_tensor, bm25_path)
        commit()
        del bm25
    bm25_scores = bm25_tensor.float().numpy()
    timings["bm25_seconds"] = time.perf_counter() - stage_started
    print(f"BM25 ready {expected_shape} in {timings['bm25_seconds']:.1f}s", flush=True)

    bge_score_path = cache_dir / "bge_m3_scores.pt"
    stage_started = time.perf_counter()
    if _valid_score_cache(bge_score_path, expected_shape):
        dense_tensor = _load_torch(bge_score_path)
    else:
        bge = models["bge_m3"]
        checkpoint_started = time.perf_counter()
        print("BGE-M3: resolving pinned snapshot", flush=True)
        bge_snapshot = snapshot_download(repo_id=bge["id"], revision=bge["revision"])
        print(
            f"BGE-M3: snapshot ready in {time.perf_counter() - checkpoint_started:.1f}s; committing",
            flush=True,
        )
        commit()
        torch.cuda.reset_peak_memory_stats()
        print("BGE-M3: loading model", flush=True)
        retriever = BGEM3DenseRetriever(model_path=bge_snapshot, device="cuda")
        print("BGE-M3: model loaded", flush=True)
        passage_embeddings = _encode_with_backoff(
            "bge_passages",
            retriever.forward_passages,
            corpus_texts,
            cache_dir / "bge_m3_passage_embeddings.pt",
            [32, 16, 8],
            batch_sizes,
            commit,
        )
        query_embeddings = _encode_with_backoff(
            "bge_queries",
            retriever.forward_queries,
            query_texts,
            cache_dir / "bge_m3_query_embeddings.pt",
            [64, 32, 16],
            batch_sizes,
            commit,
        )
        dense_tensor = retriever.get_scores(query_embeddings, passage_embeddings)
        _atomic_torch_save(dense_tensor, bge_score_path)
        commit()
        peaks["bge_m3"] = int(torch.cuda.max_memory_allocated())
        del retriever, passage_embeddings, query_embeddings
        _clear_cuda()
    dense_scores = dense_tensor.float().numpy()
    timings["bge_m3_seconds"] = time.perf_counter() - stage_started
    print(f"BGE-M3 ready {expected_shape} in {timings['bge_m3_seconds']:.1f}s", flush=True)

    dse_score_path = cache_dir / "dse_scores.pt"
    stage_started = time.perf_counter()
    if _valid_score_cache(dse_score_path, expected_shape):
        stage1_tensor = _load_torch(dse_score_path)
    else:
        dse = models["dse"]
        checkpoint_started = time.perf_counter()
        print("DSE: resolving pinned snapshot", flush=True)
        dse_snapshot = snapshot_download(repo_id=dse["id"], revision=dse["revision"])
        print(
            f"DSE: snapshot ready in {time.perf_counter() - checkpoint_started:.1f}s; committing",
            flush=True,
        )
        commit()
        torch.cuda.reset_peak_memory_stats()
        print("DSE: loading model", flush=True)
        retriever = DSEQwen2Retriever(
            pretrained_model_name_or_path=dse_snapshot,
            num_image_tokens=1024,
            device="cuda",
        )
        print("DSE: model loaded", flush=True)
        passage_embeddings = _encode_with_backoff(
            "dse_passages",
            retriever.forward_passages,
            images,
            cache_dir / "dse_passage_embeddings.pt",
            [4, 2, 1],
            batch_sizes,
            commit,
        )
        query_embeddings = _encode_with_backoff(
            "dse_queries",
            retriever.forward_queries,
            query_texts,
            cache_dir / "dse_query_embeddings.pt",
            [16, 8, 4],
            batch_sizes,
            commit,
        )
        stage1_tensor = retriever.get_scores(query_embeddings, passage_embeddings)
        _atomic_torch_save(stage1_tensor, dse_score_path)
        commit()
        peaks["dse"] = int(torch.cuda.max_memory_allocated())
        del retriever, passage_embeddings, query_embeddings
        _clear_cuda()
    stage1_scores = stage1_tensor.float().numpy()
    timings["dse_seconds"] = time.perf_counter() - stage_started
    print(f"DSE ready {expected_shape} in {timings['dse_seconds']:.1f}s", flush=True)

    initial_candidates = make_candidate_indices(
        stage1_scores, bm25_scores, dense_scores, page_ids, INITIAL_DEPTHS
    )
    # The frozen notebook uses qrels only for this coverage audit/one-time expansion gate.
    qrel_frame = pd.read_parquet(root / "qrels" / "test-00000-of-00001.parquet")
    qrel_frame = qrel_frame.loc[
        qrel_frame["query_id"].isin(query_ids)
        & qrel_frame["corpus_id"].isin(page_ids)
        & qrel_frame["score"].gt(0)
    ].copy()
    qrel_lookup = {
        (row.query_id, row.corpus_id): float(row.score)
        for row in qrel_frame.itertuples(index=False)
    }
    initial_coverage, _ = _coverage(query_ids, page_ids, initial_candidates, qrel_lookup)
    expanded_once = initial_coverage < MINIMUM_COVERAGE
    candidates = (
        make_candidate_indices(stage1_scores, bm25_scores, dense_scores, page_ids, EXPANDED_DEPTHS)
        if expanded_once
        else initial_candidates
    )
    final_coverage, candidate_audit = _coverage(query_ids, page_ids, candidates, qrel_lookup)
    zero_relevant_candidates = int(candidate_audit["relevant_selected"].eq(0).sum())
    coverage_report = {
        "dataset": DATASET_ID,
        "minimum_required": MINIMUM_COVERAGE,
        "initial_coverage": initial_coverage,
        "final_coverage": final_coverage,
        "expanded_once": expanded_once,
        "queries": len(query_ids),
        "corpus_pages": len(page_ids),
        "mean_candidates": float(np.mean([len(value) for value in candidates])),
        "queries_with_zero_relevant_candidates": zero_relevant_candidates,
        "qrels_use": "coverage_audit_and_frozen_one_time_expansion_only",
    }
    _atomic_json(coverage_report, output_dir / "coverage_report.json")
    candidate_audit.to_parquet(output_dir / "candidate_audit.parquet", index=False)
    commit()
    if not calibration and (
        final_coverage < MINIMUM_COVERAGE or zero_relevant_candidates > 0
    ):
        raise RuntimeError(f"Candidate coverage gate failed: {coverage_report}")
    print(f"Coverage ready: {coverage_report}", flush=True)

    stage_started = time.perf_counter()
    visual_score_path = cache_dir / "colqwen25_candidate_scores.pt"
    if visual_score_path.is_file():
        visual_tensor = _load_torch(visual_score_path)
        visual_scores = visual_tensor.float().numpy()
        if visual_scores.shape != expected_shape:
            visual_scores = np.full(expected_shape, np.nan, dtype=np.float32)
    else:
        visual_scores = np.full(expected_shape, np.nan, dtype=np.float32)
    colqwen = models["colqwen25"]
    torch.cuda.reset_peak_memory_stats()
    print("ColQwen2.5: loading pinned base and adapter", flush=True)
    retriever = ColQwen25Retriever(
        base_model_id=colqwen["base_id"],
        base_revision=colqwen["base_revision"],
        adapter_model_id=colqwen["id"],
        adapter_revision=colqwen["revision"],
        device="cuda",
        num_workers=0,
    )
    print("ColQwen2.5: model and processor loaded", flush=True)
    passage_embeddings = _encode_with_backoff(
        "colqwen25_passages",
        retriever.forward_passages,
        images,
        cache_dir / "colqwen25_passage_embeddings.pt",
        [2, 1],
        batch_sizes,
        commit,
    )
    query_embeddings = _encode_with_backoff(
        "colqwen25_queries",
        retriever.forward_queries,
        query_texts,
        cache_dir / "colqwen25_query_embeddings.pt",
        [8, 4, 2],
        batch_sizes,
        commit,
    )
    for query_index, pages in enumerate(candidates):
        if np.isfinite(visual_scores[query_index, pages]).all():
            continue
        selected_embeddings = [passage_embeddings[int(index)] for index in pages]
        scores = retriever.get_scores(
            [query_embeddings[query_index]], selected_embeddings, batch_size=128
        )[0].float().numpy()
        visual_scores[query_index, pages] = scores
        if (query_index + 1) % 10 == 0:
            _atomic_torch_save(torch.from_numpy(visual_scores), visual_score_path)
            commit()
            print(f"ColQwen candidate scores: {query_index + 1}/{len(query_ids)}", flush=True)
    _atomic_torch_save(torch.from_numpy(visual_scores), visual_score_path)
    commit()
    if not all(
        np.isfinite(visual_scores[index, pages]).all()
        for index, pages in enumerate(candidates)
    ):
        raise RuntimeError("ColQwen candidate score cache is incomplete")
    peaks["colqwen25"] = int(torch.cuda.max_memory_allocated())
    del retriever, passage_embeddings, query_embeddings
    _clear_cuda()
    timings["colqwen25_seconds"] = time.perf_counter() - stage_started
    print(f"ColQwen2.5 ready in {timings['colqwen25_seconds']:.1f}s", flush=True)

    raw_scores, retrieval_scores = _build_frames(
        query_ids,
        page_ids,
        query_sources,
        candidates,
        qrel_lookup,
        bm25_scores,
        dense_scores,
        stage1_scores,
        visual_scores,
    )
    keys = ["dataset", "query_id", "page_id"]
    if raw_scores.duplicated(keys).any() or retrieval_scores.duplicated(keys).any():
        raise RuntimeError("Duplicate candidate score keys")
    numeric = ["relevance", "bm25_score", "dense_score", "stage1_score", "visual_score"]
    if not np.isfinite(raw_scores[numeric].to_numpy(float)).all():
        raise RuntimeError("Non-finite raw candidate score")
    raw_path = output_dir / "candidate_raw_scores.parquet"
    retrieval_path = output_dir / "retrieval_scores.parquet"
    raw_scores.to_parquet(raw_path, index=False)
    retrieval_scores.to_parquet(retrieval_path, index=False)

    total_seconds = time.perf_counter() - started_at
    manifest = {
        "schema_version": 1,
        "status": "PASS",
        "scope": scope,
        "scientific_scope": "frozen_vidore_baseline_no_heaven_full_score",
        "source_commit": source_commit,
        "image_definition_sha256": image_definition_sha256,
        "extractor_sha256": extractor_sha256,
        "function_call_id": function_call_id,
        "protocol_sha256": protocol_sha256,
        "protocol": protocol,
        "dataset": {
            "id": dataset["id"],
            "revision": dataset["revision"],
            "queries": len(query_ids),
            "pages": len(page_ids),
        },
        "hardware": gpu_metadata,
        "packages": {
            name: importlib.metadata.version(name)
            for name in [
                "colpali-engine",
                "datasets",
                "torch",
                "transformers",
                "vidore-benchmark",
            ]
        },
        "python": platform.python_version(),
        "batch_sizes": batch_sizes,
        "max_memory_allocated_bytes": peaks,
        "timings_seconds": {**timings, "total": total_seconds},
        "coverage": coverage_report,
        "artifacts": {
            "candidate_raw_scores.parquet": {
                "bytes": raw_path.stat().st_size,
                "sha256": _file_sha256(raw_path),
                "content_sha256": _dataframe_sha256(raw_scores, keys),
            },
            "retrieval_scores.parquet": {
                "bytes": retrieval_path.stat().st_size,
                "sha256": _file_sha256(retrieval_path),
                "content_sha256": _dataframe_sha256(retrieval_scores, keys),
            },
            "candidate_audit.parquet": {
                "bytes": (output_dir / "candidate_audit.parquet").stat().st_size,
                "sha256": _file_sha256(output_dir / "candidate_audit.parquet"),
            },
            "coverage_report.json": {
                "bytes": (output_dir / "coverage_report.json").stat().st_size,
                "sha256": _file_sha256(output_dir / "coverage_report.json"),
            },
        },
        "full_score_status": "not_produced_by_human_approved_protocol",
        "score_extraction_started": True,
    }
    manifest_path = output_dir / "extraction_manifest.json"
    _atomic_json(manifest, manifest_path)
    success = {
        "schema_version": 1,
        "status": "complete",
        "scope": scope,
        "protocol_sha256": protocol_sha256,
        "manifest_sha256": _file_sha256(manifest_path),
        "artifact_count": len(manifest["artifacts"]),
        "full_score_produced": False,
    }
    _atomic_json(success, output_dir / "_EXTRACTION_SUCCESS.json")
    commit()
    print(f"Extraction complete in {total_seconds:.1f}s: {output_dir}", flush=True)
    return {
        **success,
        "function_call_id": function_call_id,
        "volume_output_dir": str(output_dir),
        "total_seconds": total_seconds,
        "coverage": final_coverage,
        "queries_with_zero_relevant_candidates": zero_relevant_candidates,
    }
