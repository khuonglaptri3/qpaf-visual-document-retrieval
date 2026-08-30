from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from scripts.vidoseek_p1_02r import (
    CANDIDATE_METHOD,
    DATASET_KEY,
    HEX40,
    HEX64,
    PROTOCOL_ID,
    _file_sha256,
    _query_records_without_qrels,
    audit_all_corpus_coverage,
    require_full_extraction_execution_approval,
    validate_recorded_cost_calibration,
    validate_recorded_cpu_audit,
)


DATASET_ID = "Qiuchen-Wang/ViDoSeek"


def chunk_bounds(total: int, chunk_size: int) -> list[tuple[int, int]]:
    """Return contiguous half-open chunks with a fixed maximum working set."""
    if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
        raise ValueError("total must be a positive integer")
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or chunk_size <= 0
    ):
        raise ValueError("chunk_size must be a positive integer")
    return [
        (start, min(start + chunk_size, total)) for start in range(0, total, chunk_size)
    ]


def _ids_sha256(values: list[str] | np.ndarray) -> str:
    payload = json.dumps(
        [str(value) for value in list(values)],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validated_score_tensor(path: Path, shape: tuple[int, int], label: str) -> Any:
    import torch

    from scripts.extract_vidore_baseline import _load_torch

    if not path.is_file():
        raise FileNotFoundError(f"Missing {label} score cache: {path}")
    try:
        tensor = _load_torch(path)
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise RuntimeError(f"Unreadable {label} score cache: {path}") from error
    if tuple(getattr(tensor, "shape", ())) != shape:
        raise RuntimeError(f"{label} score cache shape is not {shape}")
    if not bool(torch.isfinite(tensor).all()):
        raise RuntimeError(f"{label} score cache contains non-finite values")
    return tensor.float().cpu()


def _build_query_frames(
    dataset_id: str,
    query_id: str,
    query_source: str,
    page_ids: np.ndarray,
    qrel_lookup: dict[tuple[str, str], float],
    bm25_scores: np.ndarray,
    dense_scores: np.ndarray,
    stage1_scores: np.ndarray,
    visual_scores: np.ndarray,
    candidate_provenance: str,
) -> tuple[Any, Any]:
    import pandas as pd

    from scripts.extract_vidore_baseline import _minmax

    page_keys = page_ids.astype(str)
    raw_values = {
        "bm25_score": np.asarray(bm25_scores, dtype=float),
        "dense_score": np.asarray(dense_scores, dtype=float),
        "stage1_score": np.asarray(stage1_scores, dtype=float),
        "visual_score": np.asarray(visual_scores, dtype=float),
    }
    if any(values.shape != (len(page_keys),) for values in raw_values.values()):
        raise ValueError("Every score row must contain every all-corpus page")
    if not all(np.isfinite(values).all() for values in raw_values.values()):
        raise ValueError("All-corpus score rows must be finite")

    normalized = {name: _minmax(values) for name, values in raw_values.items()}
    ranks: dict[str, np.ndarray] = {}
    for name, values in normalized.items():
        order = np.lexsort((page_keys, -values))
        branch_ranks = np.empty(len(page_keys), dtype=np.int64)
        branch_ranks[order] = np.arange(1, len(page_keys) + 1, dtype=np.int64)
        ranks[name] = branch_ranks

    relevance = np.asarray(
        [float(qrel_lookup.get((query_id, page_id), 0.0)) for page_id in page_keys],
        dtype=float,
    )
    common = {
        "dataset": dataset_id,
        "query_id": query_id,
        "page_id": page_keys,
        "source": query_source,
        "relevance": relevance,
    }
    raw = pd.DataFrame(
        {
            **common,
            **raw_values,
            "candidate_provenance": candidate_provenance,
        }
    )
    retrieval = pd.DataFrame(
        {
            **common,
            **normalized,
            "branch_ranks": [
                json.dumps(
                    {
                        "bm25": int(ranks["bm25_score"][index]),
                        "dense": int(ranks["dense_score"][index]),
                        "stage1": int(ranks["stage1_score"][index]),
                        "visual": int(ranks["visual_score"][index]),
                    },
                    separators=(",", ":"),
                )
                for index in range(len(page_keys))
            ],
        }
    )
    return raw, retrieval


def _update_frame_digest(digest: Any, frame: Any, include_schema: bool) -> None:
    import pandas as pd

    if include_schema:
        digest.update(
            json.dumps(list(frame.columns), separators=(",", ":")).encode("utf-8")
        )
        digest.update(
            json.dumps(
                [str(dtype) for dtype in frame.dtypes], separators=(",", ":")
            ).encode("utf-8")
        )
    digest.update(
        pd.util.hash_pandas_object(frame, index=False, categorize=True).values.tobytes()
    )


def stream_all_corpus_outputs(
    output_dir: Path,
    dataset_id: str,
    query_ids: np.ndarray,
    page_ids: np.ndarray,
    query_sources: list[str],
    qrel_lookup: dict[tuple[str, str], float],
    source_scores: dict[str, Any],
    visual_score_chunks: list[tuple[int, int, Path]],
    query_chunk_size: int,
    candidate_provenance: str,
) -> dict[str, Any]:
    """Stream deterministic Parquet row groups without a full 6.1M-row DataFrame."""
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    query_ids = np.asarray(query_ids).astype(str)
    page_ids = np.asarray(page_ids).astype(str)
    expected_shape = (len(query_ids), len(page_ids))
    if len(query_sources) != len(query_ids):
        raise ValueError("query_sources must align with query_ids")
    if query_ids.tolist() != sorted(query_ids.tolist()):
        raise ValueError("query_ids must retain frozen ascending order")
    if set(source_scores) != {"bm25_score", "dense_score", "stage1_score"}:
        raise ValueError(
            "Source scores must contain exactly BM25, dense, and stage-1 channels"
        )
    for name, tensor in source_scores.items():
        if tuple(getattr(tensor, "shape", ())) != expected_shape:
            raise ValueError(f"{name} source score shape drifted")

    expected_page_start = 0
    visual_tensors = []
    for start, end, path in visual_score_chunks:
        if start != expected_page_start or end <= start or end > len(page_ids):
            raise ValueError(
                "Visual score chunks must cover pages contiguously in frozen order"
            )
        visual_tensors.append(
            _validated_score_tensor(path, (len(query_ids), end - start), "visual chunk")
        )
        expected_page_start = end
    if expected_page_start != len(page_ids):
        raise ValueError("Visual score chunks do not cover the full page corpus")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "candidate_raw_scores.parquet"
    retrieval_path = output_dir / "retrieval_scores.parquet"
    raw_temporary = raw_path.with_suffix(raw_path.suffix + ".tmp")
    retrieval_temporary = retrieval_path.with_suffix(retrieval_path.suffix + ".tmp")
    for temporary in [raw_temporary, retrieval_temporary]:
        if temporary.exists():
            temporary.unlink()

    raw_writer = None
    retrieval_writer = None
    raw_schema = None
    retrieval_schema = None
    raw_digest = hashlib.sha256()
    retrieval_digest = hashlib.sha256()
    row_count = 0
    keys = ["dataset", "query_id", "page_id"]
    try:
        for query_start, query_end in chunk_bounds(len(query_ids), query_chunk_size):
            visual = np.concatenate(
                [tensor[query_start:query_end].numpy() for tensor in visual_tensors],
                axis=1,
            )
            raw_parts = []
            retrieval_parts = []
            for local_index, query_index in enumerate(range(query_start, query_end)):
                raw, retrieval = _build_query_frames(
                    dataset_id=dataset_id,
                    query_id=str(query_ids[query_index]),
                    query_source=query_sources[query_index],
                    page_ids=page_ids,
                    qrel_lookup=qrel_lookup,
                    bm25_scores=source_scores["bm25_score"][query_index].numpy(),
                    dense_scores=source_scores["dense_score"][query_index].numpy(),
                    stage1_scores=source_scores["stage1_score"][query_index].numpy(),
                    visual_scores=visual[local_index],
                    candidate_provenance=candidate_provenance,
                )
                raw_parts.append(raw)
                retrieval_parts.append(retrieval)
            raw_frame = (
                pd.concat(raw_parts, ignore_index=True)
                .sort_values(keys, kind="stable")
                .reset_index(drop=True)
            )
            retrieval_frame = (
                pd.concat(retrieval_parts, ignore_index=True)
                .sort_values(keys, kind="stable")
                .reset_index(drop=True)
            )
            if (
                raw_frame.duplicated(keys).any()
                or retrieval_frame.duplicated(keys).any()
            ):
                raise RuntimeError("Duplicate all-corpus score keys")

            first_chunk = row_count == 0
            _update_frame_digest(raw_digest, raw_frame, include_schema=first_chunk)
            _update_frame_digest(
                retrieval_digest, retrieval_frame, include_schema=first_chunk
            )
            raw_table = pa.Table.from_pandas(raw_frame, preserve_index=False)
            retrieval_table = pa.Table.from_pandas(
                retrieval_frame, preserve_index=False
            )
            if raw_writer is None:
                raw_schema = raw_table.schema
                retrieval_schema = retrieval_table.schema
                raw_writer = pq.ParquetWriter(
                    raw_temporary, raw_schema, compression="snappy"
                )
                retrieval_writer = pq.ParquetWriter(
                    retrieval_temporary,
                    retrieval_schema,
                    compression="snappy",
                )
            if (
                raw_table.schema != raw_schema
                or retrieval_table.schema != retrieval_schema
            ):
                raise RuntimeError(
                    "Streamed all-corpus Parquet schema drifted between chunks"
                )
            raw_writer.write_table(raw_table)
            retrieval_writer.write_table(retrieval_table)
            row_count += len(raw_frame)
    finally:
        if raw_writer is not None:
            raw_writer.close()
        if retrieval_writer is not None:
            retrieval_writer.close()

    expected_rows = len(query_ids) * len(page_ids)
    if row_count != expected_rows:
        raise RuntimeError(f"Streamed {row_count} rows; expected {expected_rows}")
    raw_temporary.replace(raw_path)
    retrieval_temporary.replace(retrieval_path)
    return {
        "candidate_raw_scores.parquet": {
            "bytes": raw_path.stat().st_size,
            "sha256": _file_sha256(raw_path),
            "content_sha256": raw_digest.hexdigest(),
            "rows": row_count,
        },
        "retrieval_scores.parquet": {
            "bytes": retrieval_path.stat().st_size,
            "sha256": _file_sha256(retrieval_path),
            "content_sha256": retrieval_digest.hexdigest(),
            "rows": row_count,
        },
    }


def _candidate_audit(
    dataset_id: str,
    query_ids: np.ndarray,
    page_ids: np.ndarray,
    qrel_lookup: dict[tuple[str, str], float],
) -> Any:
    import pandas as pd

    page_keys = set(page_ids.astype(str).tolist())
    rows = []
    for query_id in query_ids.astype(str):
        relevant = {
            str(page_id)
            for (candidate_query_id, page_id), relevance in qrel_lookup.items()
            if str(candidate_query_id) == query_id and float(relevance) > 0
        }
        selected = len(relevant & page_keys)
        rows.append(
            {
                "dataset": dataset_id,
                "query_id": query_id,
                "relevant_total": len(relevant),
                "relevant_selected": selected,
                "coverage": np.nan if not relevant else selected / len(relevant),
                "candidate_count": len(page_ids),
            }
        )
    return pd.DataFrame(rows)


def _chunk_artifact_records(
    run_root: Path,
    bounds: list[tuple[int, int]],
    paths: list[Path],
    ids: np.ndarray,
) -> list[dict[str, Any]]:
    return [
        {
            "start": start,
            "end": end,
            "items": end - start,
            "ids_sha256": _ids_sha256(ids[start:end]),
            "path": path.relative_to(run_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        }
        for (start, end), path in zip(bounds, paths)
    ]


def run_chunked_full_extraction(
    dataset_config: dict[str, Any],
    environment: dict[str, Any],
    protocol: dict[str, Any],
    audit_artifact_path: Path,
    calibration_artifact_path: Path,
    volume_root: Path,
    source_commit: str,
    image_definition_sha256: str,
    extractor_sha256: str,
    protocol_config_sha256: str,
    function_call_id: str,
    gpu_metadata: dict[str, Any],
    commit: Callable[[], None],
) -> dict[str, Any]:
    """Compute a resumable P1-02R bundle with fixed query/page working sets."""
    total_started = time.perf_counter()
    require_full_extraction_execution_approval(protocol)
    audit = validate_recorded_cpu_audit(protocol, audit_artifact_path)
    calibration_artifact = validate_recorded_cost_calibration(
        protocol, calibration_artifact_path
    )
    for label, value in {
        "image_definition_sha256": image_definition_sha256,
        "extractor_sha256": extractor_sha256,
        "protocol_config_sha256": protocol_config_sha256,
    }.items():
        if not isinstance(value, str) or not HEX64.fullmatch(value):
            raise ValueError(f"{label} must be a SHA-256")
    if not isinstance(source_commit, str) or not HEX40.fullmatch(source_commit):
        raise ValueError("source_commit must be a Git SHA")
    if not isinstance(function_call_id, str) or not function_call_id:
        raise ValueError("function_call_id must be non-empty")
    if "L4" not in str(gpu_metadata.get("actual_gpu", "")):
        raise RuntimeError("P1-02R full extraction requires an actual NVIDIA L4")

    dataset = next(
        item for item in dataset_config["datasets"] if item["key"] == DATASET_KEY
    )
    if dataset["id"] != protocol["dataset"]["id"]:
        raise RuntimeError("P1-02R full-extraction dataset ID drifted")
    if dataset["revision"] != protocol["dataset"]["revision"]:
        raise RuntimeError("P1-02R full-extraction dataset revision drifted")
    retriever_contract = {
        name: environment[name] for name in protocol["retrievers"]["contract_fields"]
    }
    retriever_contract_sha256 = hashlib.sha256(
        json.dumps(retriever_contract, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    if retriever_contract_sha256 != protocol["retrievers"]["contract_sha256"]:
        raise RuntimeError("P1-02R frozen retriever contract drifted")

    source_protocol_sha256 = protocol["frozen_parent"]["extraction_protocol_sha256"]
    source_run_root = (
        volume_root / "score_extraction" / DATASET_KEY / source_protocol_sha256 / "full"
    )
    preparation_path = source_run_root / "prepared_corpus" / "_PREPARED.json"
    if (
        _file_sha256(preparation_path)
        != audit["dataset_contract"]["preparation_marker_sha256"]
    ):
        raise RuntimeError("P1-02R prepared-corpus marker drifted after calibration")
    preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
    page_records = preparation.get("pages")
    if preparation.get("status") != "complete" or not isinstance(page_records, list):
        raise RuntimeError("P1-02R prepared corpus is incomplete")
    if len(page_records) != protocol["dataset"]["expected_pages"]:
        raise RuntimeError("P1-02R prepared page count drifted")
    image_paths = [Path(record["image"]) for record in page_records]
    if not all(path.is_file() for path in image_paths):
        raise FileNotFoundError(
            "P1-02R full extraction has missing prepared page images"
        )
    page_ids = np.asarray([str(record["page_id"]) for record in page_records])

    annotation_path = (
        Path(dataset["local_dir"]) / dataset["discovery_extraction"]["annotation_file"]
    )
    if _file_sha256(annotation_path) != audit["dataset_contract"]["annotation_sha256"]:
        raise RuntimeError("P1-02R annotation file drifted after calibration")
    annotation_payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    query_records = _query_records_without_qrels(annotation_payload)
    if len(query_records) != protocol["dataset"]["expected_queries"]:
        raise RuntimeError("P1-02R query count drifted")
    query_ids = np.asarray([row["query_id"] for row in query_records])
    query_texts = [row["query_text"] for row in query_records]
    query_sources = [row["source"] for row in query_records]
    expected_shape = (len(query_ids), len(page_ids))

    full_contract = protocol["full_extraction"]
    source_scores = {
        output_name: _validated_score_tensor(
            source_run_root / relative_path,
            expected_shape,
            output_name,
        )
        for output_name, relative_path in {
            "bm25_score": full_contract["required_source_score_caches"]["bm25"],
            "dense_score": full_contract["required_source_score_caches"]["bge_m3"],
            "stage1_score": full_contract["required_source_score_caches"]["dse"],
        }.items()
    }
    source_score_artifacts = {
        name: {
            "path": str(source_run_root / relative_path),
            "bytes": (source_run_root / relative_path).stat().st_size,
            "sha256": _file_sha256(source_run_root / relative_path),
            "shape": list(expected_shape),
        }
        for name, relative_path in {
            "bm25_score": full_contract["required_source_score_caches"]["bm25"],
            "dense_score": full_contract["required_source_score_caches"]["bge_m3"],
            "stage1_score": full_contract["required_source_score_caches"]["dse"],
        }.items()
    }

    run_root = (
        volume_root
        / "score_extraction"
        / DATASET_KEY
        / PROTOCOL_ID
        / protocol_config_sha256
        / "full"
    )
    cache_dir = run_root / "cache"
    output_dir = run_root / "output"
    query_cache_dir = cache_dir / "query_embeddings"
    passage_cache_dir = cache_dir / "passage_embeddings"
    visual_cache_dir = cache_dir / "visual_scores"
    for path in [output_dir, query_cache_dir, passage_cache_dir, visual_cache_dir]:
        path.mkdir(parents=True, exist_ok=True)

    ephemeral_hf_root = Path("/tmp/qpaf_hf_cache")
    os.environ["HF_HOME"] = str(ephemeral_hf_root)
    os.environ["HF_HUB_CACHE"] = str(ephemeral_hf_root / "hub")

    import torch

    from scripts.colqwen25_retriever import ColQwen25Retriever
    from scripts.extract_vidore_baseline import (
        _atomic_json,
        _atomic_torch_save,
        _clear_cuda,
        _encode_with_backoff,
        _valid_embedding_cache,
        _valid_score_cache,
    )
    from scripts.vidoseek_dataset import LazyPageImages, parse_annotations

    query_bounds = chunk_bounds(len(query_ids), full_contract["query_chunk_size"])
    page_bounds = chunk_bounds(len(page_ids), full_contract["page_chunk_size"])
    if len(query_bounds) != full_contract["expected_query_chunks"]:
        raise RuntimeError("P1-02R query chunk count does not match the protocol")
    if len(page_bounds) != full_contract["expected_page_chunks"]:
        raise RuntimeError("P1-02R page chunk count does not match the protocol")

    query_cache_paths = [
        query_cache_dir / f"query_{start:06d}_{end:06d}.pt"
        for start, end in query_bounds
    ]
    passage_cache_paths = [
        passage_cache_dir / f"page_{start:06d}_{end:06d}.pt"
        for start, end in page_bounds
    ]
    visual_cache_paths = [
        visual_cache_dir / f"page_{start:06d}_{end:06d}.pt"
        for start, end in page_bounds
    ]
    timings = {
        "model_load_seconds": 0.0,
        "query_encoding_seconds": 0.0,
        "passage_encoding_seconds": 0.0,
        "visual_scoring_seconds": 0.0,
        "output_materialization_seconds": 0.0,
    }
    observed_batches: dict[str, set[int]] = {"queries": set(), "passages": set()}
    resumed = {
        "query_embedding_chunks": 0,
        "passage_embedding_chunks": 0,
        "visual_score_chunks": 0,
    }

    torch.cuda.reset_peak_memory_stats()
    model_started = time.perf_counter()
    colqwen = environment["models"]["colqwen25"]
    retriever = ColQwen25Retriever(
        base_model_id=colqwen["base_id"],
        base_revision=colqwen["base_revision"],
        adapter_model_id=colqwen["id"],
        adapter_revision=colqwen["revision"],
        device="cuda",
        num_workers=0,
    )
    timings["model_load_seconds"] = time.perf_counter() - model_started

    query_stage_started = time.perf_counter()
    query_cache_changed = False
    for (start, end), cache_path in zip(query_bounds, query_cache_paths):
        was_valid = _valid_embedding_cache(cache_path, end - start)
        batch_sizes: dict[str, Any] = {}
        embeddings = _encode_with_backoff(
            "p1_02r_full_query_chunk",
            retriever.forward_queries,
            query_texts[start:end],
            cache_path,
            full_contract["query_encode_batch_candidates"],
            batch_sizes,
            lambda: None,
        )
        if was_valid:
            resumed["query_embedding_chunks"] += 1
        else:
            query_cache_changed = True
            observed_batches["queries"].add(int(batch_sizes["p1_02r_full_query_chunk"]))
        del embeddings
    if query_cache_changed:
        commit()
    timings["query_encoding_seconds"] = time.perf_counter() - query_stage_started

    for chunk_index, ((start, end), passage_path, score_path) in enumerate(
        zip(page_bounds, passage_cache_paths, visual_cache_paths),
        start=1,
    ):
        if _valid_score_cache(score_path, (len(query_ids), end - start)):
            resumed["visual_score_chunks"] += 1
            print(
                f"P1-02R visual chunk {chunk_index}/{len(page_bounds)}: validated cache",
                flush=True,
            )
            continue

        passage_stage_started = time.perf_counter()
        passage_was_valid = _valid_embedding_cache(passage_path, end - start)
        batch_sizes = {}
        passage_embeddings = _encode_with_backoff(
            "p1_02r_full_passage_chunk",
            retriever.forward_passages,
            LazyPageImages(image_paths[start:end]),
            passage_path,
            full_contract["passage_encode_batch_candidates"],
            batch_sizes,
            commit,
        )
        if passage_was_valid:
            resumed["passage_embedding_chunks"] += 1
        else:
            observed_batches["passages"].add(
                int(batch_sizes["p1_02r_full_passage_chunk"])
            )
        timings["passage_encoding_seconds"] += (
            time.perf_counter() - passage_stage_started
        )

        scoring_started = time.perf_counter()
        score_tensor = torch.empty((len(query_ids), end - start), dtype=torch.float32)
        for (query_start, query_end), query_path in zip(
            query_bounds, query_cache_paths
        ):
            from scripts.extract_vidore_baseline import _load_torch

            query_embeddings = _load_torch(query_path)
            if len(query_embeddings) != query_end - query_start:
                raise RuntimeError("P1-02R query embedding chunk length drifted")
            for local_index, query_embedding in enumerate(query_embeddings):
                scores = (
                    retriever.get_scores(
                        [query_embedding],
                        passage_embeddings,
                        batch_size=full_contract["visual_score_batch_size"],
                    )[0]
                    .float()
                    .cpu()
                )
                if len(scores) != end - start or not bool(torch.isfinite(scores).all()):
                    raise RuntimeError(
                        "P1-02R chunked visual scoring produced invalid values"
                    )
                score_tensor[query_start + local_index] = scores
            del query_embeddings
        _atomic_torch_save(score_tensor, score_path)
        commit()
        timings["visual_scoring_seconds"] += time.perf_counter() - scoring_started
        del passage_embeddings, score_tensor
        _clear_cuda()
        print(
            f"P1-02R visual chunk {chunk_index}/{len(page_bounds)}: committed",
            flush=True,
        )

    peak_memory_allocated_bytes = int(torch.cuda.max_memory_allocated())
    del retriever
    _clear_cuda()

    annotations = parse_annotations(annotation_payload)
    if annotations.query_ids.astype(str).tolist() != query_ids.astype(str).tolist():
        raise RuntimeError(
            "P1-02R query ordering changed when qrels entered evaluation"
        )
    coverage = audit_all_corpus_coverage(
        query_ids,
        page_ids,
        annotations.qrel_lookup,
        dataset_id=dataset["id"],
    )
    if coverage["decision"] != "p1_02r_coverage_gate_passes":
        raise RuntimeError("P1-02R all-corpus coverage gate no longer passes")

    output_started = time.perf_counter()
    output_artifacts = stream_all_corpus_outputs(
        output_dir=output_dir,
        dataset_id=dataset["id"],
        query_ids=query_ids,
        page_ids=page_ids,
        query_sources=query_sources,
        qrel_lookup=annotations.qrel_lookup,
        source_scores=source_scores,
        visual_score_chunks=[
            (start, end, path)
            for (start, end), path in zip(page_bounds, visual_cache_paths)
        ],
        query_chunk_size=full_contract["query_chunk_size"],
        candidate_provenance=full_contract["candidate_provenance"],
    )
    candidate_audit = _candidate_audit(
        dataset["id"], query_ids, page_ids, annotations.qrel_lookup
    )
    candidate_audit_path = output_dir / "candidate_audit.parquet"
    candidate_audit.to_parquet(candidate_audit_path, index=False)
    coverage_path = output_dir / "coverage_report.json"
    coverage_report = {
        **coverage,
        "candidate_pool_method": CANDIDATE_METHOD,
        "candidate_provenance": full_contract["candidate_provenance"],
        "qrels_use": full_contract["qrels_use"],
    }
    _atomic_json(coverage_report, coverage_path)
    output_artifacts.update(
        {
            "candidate_audit.parquet": {
                "bytes": candidate_audit_path.stat().st_size,
                "sha256": _file_sha256(candidate_audit_path),
                "rows": len(candidate_audit),
            },
            "coverage_report.json": {
                "bytes": coverage_path.stat().st_size,
                "sha256": _file_sha256(coverage_path),
            },
        }
    )
    timings["output_materialization_seconds"] = time.perf_counter() - output_started
    timings["total_seconds"] = time.perf_counter() - total_started

    cache_artifacts = {
        "query_embeddings": _chunk_artifact_records(
            run_root, query_bounds, query_cache_paths, query_ids
        ),
        "passage_embeddings": _chunk_artifact_records(
            run_root, page_bounds, passage_cache_paths, page_ids
        ),
        "visual_scores": _chunk_artifact_records(
            run_root, page_bounds, visual_cache_paths, page_ids
        ),
    }
    manifest = {
        "schema_version": 1,
        "status": "PASS",
        "scope": "full",
        "scientific_scope": full_contract["result_scope"],
        "protocol_id": PROTOCOL_ID,
        "protocol_status": protocol["status"],
        "protocol_config_sha256": protocol_config_sha256,
        "source_commit": source_commit,
        "image_definition_sha256": image_definition_sha256,
        "extractor_sha256": extractor_sha256,
        "function_call_id": function_call_id,
        "source_protocol_sha256": source_protocol_sha256,
        "retriever_contract_sha256": retriever_contract_sha256,
        "retrievers_changed": False,
        "dataset": {
            "id": dataset["id"],
            "revision": dataset["revision"],
            "queries": len(query_ids),
            "pages": len(page_ids),
            "candidate_pairs": len(query_ids) * len(page_ids),
            "annotation_sha256": audit["dataset_contract"]["annotation_sha256"],
            "preparation_marker_sha256": audit["dataset_contract"][
                "preparation_marker_sha256"
            ],
        },
        "candidate_pool": {
            "method": CANDIDATE_METHOD,
            "membership_rule": protocol["candidate_pool"]["membership_rule"],
            "ordering": protocol["candidate_pool"]["ordering"],
            "candidate_provenance": full_contract["candidate_provenance"],
            "qrels_used_for_construction": False,
        },
        "chunking": {
            "query_chunk_size": full_contract["query_chunk_size"],
            "page_chunk_size": full_contract["page_chunk_size"],
            "query_chunks": len(query_bounds),
            "page_chunks": len(page_bounds),
            "passage_encode_batch_candidates": full_contract[
                "passage_encode_batch_candidates"
            ],
            "query_encode_batch_candidates": full_contract[
                "query_encode_batch_candidates"
            ],
            "visual_score_batch_size": full_contract["visual_score_batch_size"],
            "observed_encode_batches": {
                name: sorted(values) for name, values in observed_batches.items()
            },
            "resumed_chunks": resumed,
        },
        "source_score_caches": source_score_artifacts,
        "cache_chunks": cache_artifacts,
        "calibration_evidence": {
            "artifact_sha256": protocol["cost_calibration_result"]["artifact_sha256"],
            "function_call_id": calibration_artifact["function_call_id"],
            "projected_total_gpu_seconds": calibration_artifact["projection"][
                "projected_total_gpu_seconds"
            ],
            "interpretation": calibration_artifact["projection"]["interpretation"],
        },
        "hardware": gpu_metadata,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["colpali-engine", "pandas", "pyarrow", "torch", "transformers"]
        },
        "python": platform.python_version(),
        "max_memory_allocated_bytes": peak_memory_allocated_bytes,
        "timings_seconds": timings,
        "coverage": coverage_report,
        "artifacts": output_artifacts,
        "full_score_status": "not_produced_by_human_approved_protocol",
        "score_extraction_started": True,
    }
    manifest_path = output_dir / "extraction_manifest.json"
    _atomic_json(manifest, manifest_path)
    success = {
        "schema_version": 1,
        "status": "complete",
        "scope": "full",
        "protocol_id": PROTOCOL_ID,
        "protocol_config_sha256": protocol_config_sha256,
        "manifest_sha256": _file_sha256(manifest_path),
        "artifact_count": len(output_artifacts),
        "candidate_pairs": len(query_ids) * len(page_ids),
        "full_score_produced": False,
    }
    _atomic_json(success, output_dir / "_EXTRACTION_SUCCESS.json")
    commit()
    return {
        **success,
        "function_call_id": function_call_id,
        "volume_output_dir": str(output_dir),
        "total_seconds": timings["total_seconds"],
        "coverage": coverage["coverage"],
        "queries_with_zero_relevant_candidates": coverage[
            "queries_with_zero_relevant_candidates"
        ],
    }
