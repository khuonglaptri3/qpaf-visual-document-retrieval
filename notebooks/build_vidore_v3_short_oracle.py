from __future__ import annotations

import json
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "vidore_v3_short_oracle.ipynb"


def source(value: str) -> list[str]:
    return textwrap.dedent(value).lstrip("\n").splitlines(keepends=True)


def markdown(value: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source(value)}


def code(value: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source(value),
    }


def embedded_package_cell() -> str:
    names = [
        "__init__.py",
        "bootstrap.py",
        "constants.py",
        "feasibility.py",
        "io.py",
        "metrics.py",
        "profiles.py",
        "qpaf.py",
        "report.py",
    ]
    files = {
        name: (ROOT / "src" / "oracle_study" / name).read_text(encoding="utf-8")
        for name in names
    }
    return f"""
    # Install the exact local oracle implementation into this Colab runtime.
    import sys
    from pathlib import Path

    package_root = Path("/content/oracle_study")
    package_root.mkdir(parents=True, exist_ok=True)
    embedded_files = {json.dumps(files, ensure_ascii=False)}
    for filename, content in embedded_files.items():
        (package_root / filename).write_text(content, encoding="utf-8")
    if "/content" not in sys.path:
        sys.path.insert(0, "/content")

    from oracle_study.feasibility import assess_short_pilot, feasibility_markdown
    from oracle_study.io import dataframe_sha256, write_json, write_jsonl
    from oracle_study.qpaf import run_qpaf_oracle
    from oracle_study.report import plot_qpaf
    """


cells = [
    markdown(
        r"""
        # ViDoRe V3 Finance EN — Short QARF/QPAF Oracle

        This notebook runs the exploratory **Global Fusion → QARF → QPAF** oracle on all
        309 English queries and the full 2,942-page `vidore_v3_finance_en` corpus.

        - Dataset revision is pinned.
        - Qrels are used only for metric/oracle selection and coverage auditing.
        - Candidate construction uses DSE, BM25 and BGE-M3 scores only.
        - The run stops on GPUs with less than 24 GB VRAM.
        - Results are exploratory and must not be reported as a full ViDoRe V3 result.

        Run every cell in order. The only interactive step is authorizing Google Drive.
        """
    ),
    code(
        r"""
        %pip install -q \
          "vidore-benchmark[all-retrievers]==5.0.0" \
          "colpali-engine==0.3.12" \
          "transformers==4.53.3" \
          "datasets>=2.19,<4" \
          "pyarrow>=15" \
          "PyYAML>=6"
        """
    ),
    code(
        r"""
        import gc
        import hashlib
        import importlib.metadata
        import json
        import os
        import random
        import time
        from pathlib import Path

        import numpy as np
        import pandas as pd
        import torch
        import yaml
        from google.colab import drive

        SEED = 20260820
        DATASET = "vidore/vidore_v3_finance_en"
        DATASET_REVISION = "7f432c176d82e27546501ad8064a713ac3071809"
        MODEL_NAMES = {
            "bge_m3": "BAAI/bge-m3",
            "dse": "MrLight/dse-qwen2-2b-mrl-v1",
            "colqwen25": "vidore/colqwen2.5-v0.2",
        }

        if not torch.cuda.is_available():
            raise RuntimeError("A CUDA GPU with at least 24 GB VRAM is required")
        gpu = torch.cuda.get_device_properties(0)
        gpu_gb = gpu.total_memory / 1024**3
        if gpu_gb < 23.5:
            raise RuntimeError(f"GPU preflight failed: {gpu.name} has only {gpu_gb:.1f} GB VRAM")

        drive.mount("/content/drive")
        RUN_ROOT = Path("/content/drive/MyDrive/vidore_v3_finance_en_short_oracle")
        CACHE_DIR = RUN_ROOT / "cache"
        OUTPUT_DIR = RUN_ROOT / "output"
        HF_HOME = RUN_ROOT / "hf_cache"
        HF_HUB_CACHE = HF_HOME / "hub"
        HF_DATASETS_CACHE = HF_HOME / "datasets"
        for directory in [CACHE_DIR, OUTPUT_DIR, HF_HOME, HF_HUB_CACHE, HF_DATASETS_CACHE]:
            directory.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(HF_HOME)
        os.environ["HF_HUB_CACHE"] = str(HF_HUB_CACHE)
        os.environ["HF_DATASETS_CACHE"] = str(HF_DATASETS_CACHE)

        # Import after cache variables are frozen so model and dataset downloads persist on Drive.
        from huggingface_hub import model_info

        random.seed(SEED)
        np.random.seed(SEED)
        torch.manual_seed(SEED)
        torch.cuda.manual_seed_all(SEED)
        print(f"GPU preflight passed: {gpu.name}, {gpu_gb:.1f} GB")
        print(f"Persistent run directory: {RUN_ROOT}")
        """
    ),
    code(embedded_package_cell()),
    code(
        r"""
        from datasets import load_dataset

        corpus = load_dataset(DATASET, "corpus", split="test", revision=DATASET_REVISION)
        query_dataset = load_dataset(DATASET, "queries", split="test", revision=DATASET_REVISION)
        qrel_dataset = load_dataset(DATASET, "qrels", split="test", revision=DATASET_REVISION)

        query_frame = query_dataset.to_pandas()
        query_frame = query_frame.loc[query_frame["language"].eq("english")].copy()
        query_frame = query_frame.sort_values("query_id", kind="stable").reset_index(drop=True)
        qrel_frame = qrel_dataset.to_pandas()
        qrel_frame = qrel_frame.loc[
            qrel_frame["query_id"].isin(query_frame["query_id"]) & qrel_frame["score"].gt(0)
        ].copy()

        corpus_ids = np.asarray(corpus["corpus_id"])
        query_ids = query_frame["query_id"].to_numpy()
        query_texts = query_frame["query"].astype(str).tolist()
        corpus_texts = ["" if value is None else str(value) for value in corpus["markdown"]]

        assert len(corpus_ids) == 2942, len(corpus_ids)
        assert len(query_ids) == 309, len(query_ids)
        assert len(set(corpus_ids.tolist())) == len(corpus_ids)
        assert len(set(query_ids.tolist())) == len(query_ids)
        assert set(qrel_frame["query_id"]).issubset(set(query_ids))
        assert set(qrel_frame["corpus_id"]).issubset(set(corpus_ids))
        assert qrel_frame.groupby("query_id")["corpus_id"].nunique().reindex(query_ids).notna().all()

        qrel_lookup = {
            (row.query_id, row.corpus_id): float(row.score)
            for row in qrel_frame.itertuples(index=False)
        }
        relevant_count = qrel_frame.groupby("query_id")["corpus_id"].nunique().to_dict()

        def source_label(value):
            if isinstance(value, np.ndarray):
                values = value.tolist()
            elif isinstance(value, (list, tuple)):
                values = list(value)
            else:
                values = [value]
            return "|".join(sorted({str(item) for item in values if item is not None})) or "unknown"

        query_sources = [source_label(value) for value in query_frame["content_type"]]
        print(f"Mapping smoke test passed: {len(query_ids)} English queries, {len(corpus_ids)} pages")
        print(f"Positive qrels: {len(qrel_frame)}; mean relevant pages/query: {np.mean(list(relevant_count.values())):.2f}")
        """
    ),
    code(
        r"""
        BATCH_SIZES = {}

        def load_torch(path):
            return torch.load(path, map_location="cpu", weights_only=False)

        def encode_with_backoff(label, function, values, cache_path, batch_candidates):
            cache_path = Path(cache_path)
            if cache_path.exists():
                BATCH_SIZES[label] = "cache"
                return load_torch(cache_path)
            last_error = None
            for batch_size in batch_candidates:
                try:
                    output = function(values, batch_size=batch_size)
                    torch.save(output, cache_path)
                    BATCH_SIZES[label] = batch_size
                    return output
                except (torch.cuda.OutOfMemoryError, RuntimeError) as error:
                    if "out of memory" not in str(error).lower():
                        raise
                    last_error = error
                    gc.collect()
                    torch.cuda.empty_cache()
                    print(f"{label}: OOM at batch {batch_size}; retrying smaller batch")
            raise RuntimeError(f"{label}: all approved batch sizes failed") from last_error

        def checkpoint_sha(model_name):
            return model_info(model_name).sha

        def stable_top_indices(scores, k):
            page_keys = corpus_ids.astype(str)
            return np.lexsort((page_keys, -np.asarray(scores, dtype=float)))[:k]

        def minmax(values):
            values = np.asarray(values, dtype=float)
            low, high = float(values.min()), float(values.max())
            return np.zeros_like(values) if abs(high - low) <= 1e-15 else (values - low) / (high - low)

        class LazyCorpusImages:
            # Decode only the page images requested by the current model batch.

            def __init__(self, dataset):
                self.dataset = dataset

            def __len__(self):
                return len(self.dataset)

            def __getitem__(self, index):
                if isinstance(index, slice):
                    return [self[position] for position in range(*index.indices(len(self)))]
                return self.dataset[int(index)]["image"].convert("RGB")

            def __iter__(self):
                for index in range(len(self)):
                    yield self[index]

        # The first ten queries form the fixed model smoke set.
        smoke_queries = query_texts[:10]
        """
    ),
    markdown("## 1. BM25 over the provided OCR markdown"),
    code(
        r"""
        import nltk
        from vidore_benchmark.retrievers.bm25_retriever import BM25Retriever

        nltk.download("punkt", quiet=True)
        nltk.download("punkt_tab", quiet=True)
        nltk.download("stopwords", quiet=True)
        bm25_path = CACHE_DIR / "bm25_scores.pt"
        if bm25_path.exists():
            bm25_scores = load_torch(bm25_path)
        else:
            retriever = BM25Retriever(device="cpu")
            smoke = retriever.get_scores_bm25(smoke_queries, corpus_texts[:32])
            assert smoke.shape == (10, 32)
            bm25_scores = retriever.get_scores_bm25(query_texts, corpus_texts)
            torch.save(bm25_scores, bm25_path)
            del retriever, smoke
        bm25_scores = bm25_scores.float().numpy()
        assert bm25_scores.shape == (309, 2942)
        print("BM25 scores ready", bm25_scores.shape)
        """
    ),
    markdown("## 2. BGE-M3 dense OCR retrieval"),
    code(
        r"""
        from vidore_benchmark.retrievers.bge_m3_retriever import BGEM3Retriever

        bge_score_path = CACHE_DIR / "bge_m3_scores.pt"
        if bge_score_path.exists():
            dense_scores = load_torch(bge_score_path)
        else:
            retriever = BGEM3Retriever(pretrained_model_name_or_path=MODEL_NAMES["bge_m3"], device="cuda")
            smoke_q = retriever.forward_queries(smoke_queries, batch_size=8)
            smoke_p = retriever.forward_passages(corpus_texts[:32], batch_size=8)
            assert retriever.get_scores(smoke_q, smoke_p).shape == (10, 32)
            passage_embeddings = encode_with_backoff(
                "bge_passages", retriever.forward_passages, corpus_texts,
                CACHE_DIR / "bge_m3_passage_embeddings.pt", [32, 16, 8]
            )
            query_embeddings = encode_with_backoff(
                "bge_queries", retriever.forward_queries, query_texts,
                CACHE_DIR / "bge_m3_query_embeddings.pt", [64, 32, 16]
            )
            dense_scores = retriever.get_scores(query_embeddings, passage_embeddings)
            torch.save(dense_scores, bge_score_path)
            del retriever, smoke_q, smoke_p, passage_embeddings, query_embeddings
            gc.collect()
            torch.cuda.empty_cache()
        dense_scores = dense_scores.float().numpy()
        assert dense_scores.shape == (309, 2942)
        print("BGE-M3 scores ready", dense_scores.shape)
        """
    ),
    markdown("## 3. DSE single-vector visual retrieval and candidate construction"),
    code(
        r"""
        from vidore_benchmark.retrievers.dse_qwen2_retriever import DSEQwen2Retriever

        dse_score_path = CACHE_DIR / "dse_scores.pt"
        if dse_score_path.exists():
            stage1_scores = load_torch(dse_score_path)
        else:
            retriever = DSEQwen2Retriever(
                pretrained_model_name_or_path=MODEL_NAMES["dse"], num_image_tokens=1024, device="cuda"
            )
            smoke_images = [corpus[index]["image"].convert("RGB") for index in range(8)]
            smoke_q = retriever.forward_queries(smoke_queries, batch_size=4)
            smoke_p = retriever.forward_passages(smoke_images, batch_size=2)
            assert retriever.get_scores(smoke_q, smoke_p).shape == (10, 8)
            corpus_images = LazyCorpusImages(corpus)
            passage_embeddings = encode_with_backoff(
                "dse_passages", retriever.forward_passages, corpus_images,
                CACHE_DIR / "dse_passage_embeddings.pt", [4, 2, 1]
            )
            query_embeddings = encode_with_backoff(
                "dse_queries", retriever.forward_queries, query_texts,
                CACHE_DIR / "dse_query_embeddings.pt", [16, 8, 4]
            )
            stage1_scores = retriever.get_scores(query_embeddings, passage_embeddings)
            torch.save(stage1_scores, dse_score_path)
            del (
                retriever, smoke_q, smoke_p, smoke_images, corpus_images,
                passage_embeddings, query_embeddings
            )
            gc.collect()
            torch.cuda.empty_cache()
        stage1_scores = stage1_scores.float().numpy()
        assert stage1_scores.shape == (309, 2942)

        def make_candidate_indices(stage1_k, bm25_k, dense_k):
            return [
                np.unique(np.concatenate([
                    stable_top_indices(stage1_scores[index], stage1_k),
                    stable_top_indices(bm25_scores[index], bm25_k),
                    stable_top_indices(dense_scores[index], dense_k),
                ]))
                for index in range(len(query_ids))
            ]

        def candidate_coverage(candidate_indices):
            selected = {
                (query_ids[index], corpus_ids[page_index])
                for index, pages in enumerate(candidate_indices)
                for page_index in pages
            }
            relevant = set(qrel_lookup)
            return len(selected & relevant) / len(relevant)

        initial_candidates = make_candidate_indices(200, 100, 100)
        initial_coverage = candidate_coverage(initial_candidates)
        expanded_once = initial_coverage < 0.95
        candidate_indices = make_candidate_indices(300, 200, 200) if expanded_once else initial_candidates
        final_coverage = candidate_coverage(candidate_indices)
        coverage_report = {
            "dataset": DATASET,
            "minimum_required": 0.95,
            "initial_coverage": initial_coverage,
            "final_coverage": final_coverage,
            "expanded_once": expanded_once,
            "queries": len(query_ids),
            "corpus_pages": len(corpus_ids),
            "mean_candidates": float(np.mean([len(value) for value in candidate_indices])),
        }
        write_json(coverage_report, OUTPUT_DIR / "coverage_report.json")
        if final_coverage < 0.95:
            raise RuntimeError(f"Candidate coverage gate failed: {final_coverage:.4f}")
        print(coverage_report)
        """
    ),
    markdown("## 4. ColQwen2.5 multi-vector candidate scoring"),
    code(
        r"""
        from colpali_engine.models import ColQwen2_5_Processor
        from vidore_benchmark.retrievers.colqwen2_5_retriever import ColQwen2_5_Retriever

        colqwen_passage_path = CACHE_DIR / "colqwen25_passage_embeddings.pt"
        colqwen_query_path = CACHE_DIR / "colqwen25_query_embeddings.pt"
        if not colqwen_passage_path.exists() or not colqwen_query_path.exists():
            retriever = ColQwen2_5_Retriever(
                pretrained_model_name_or_path=MODEL_NAMES["colqwen25"], device="cuda", num_workers=0
            )
            smoke_images = [corpus[index]["image"].convert("RGB") for index in range(4)]
            smoke_q = retriever.forward_queries(smoke_queries, batch_size=2)
            smoke_p = retriever.forward_passages(smoke_images, batch_size=1)
            assert retriever.get_scores(smoke_q, smoke_p, batch_size=8).shape == (10, 4)
            corpus_images = LazyCorpusImages(corpus)
            passage_embeddings = encode_with_backoff(
                "colqwen25_passages", retriever.forward_passages, corpus_images,
                colqwen_passage_path, [2, 1]
            )
            query_embeddings = encode_with_backoff(
                "colqwen25_queries", retriever.forward_queries, query_texts,
                colqwen_query_path, [8, 4, 2]
            )
            del retriever, smoke_q, smoke_p, smoke_images, corpus_images
            gc.collect()
            torch.cuda.empty_cache()
        else:
            passage_embeddings = load_torch(colqwen_passage_path)
            query_embeddings = load_torch(colqwen_query_path)

        processor = ColQwen2_5_Processor.from_pretrained(MODEL_NAMES["colqwen25"])
        visual_score_path = CACHE_DIR / "colqwen25_candidate_scores.pt"
        if visual_score_path.exists():
            visual_scores = load_torch(visual_score_path).numpy()
        else:
            visual_scores = np.full((len(query_ids), len(corpus_ids)), np.nan, dtype=np.float32)

        for query_index, pages in enumerate(candidate_indices):
            if np.isfinite(visual_scores[query_index, pages]).all():
                continue
            selected_embeddings = [passage_embeddings[int(index)] for index in pages]
            score = processor.score(
                [query_embeddings[query_index]], selected_embeddings, batch_size=128, device="cpu"
            )[0].float().numpy()
            visual_scores[query_index, pages] = score
            if (query_index + 1) % 10 == 0:
                torch.save(torch.from_numpy(visual_scores), visual_score_path)
                print(f"ColQwen candidate scores: {query_index + 1}/{len(query_ids)}")
        torch.save(torch.from_numpy(visual_scores), visual_score_path)
        assert all(np.isfinite(visual_scores[index, pages]).all() for index, pages in enumerate(candidate_indices))
        del processor, passage_embeddings, query_embeddings
        gc.collect()
        print("ColQwen2.5 candidate scores ready")
        """
    ),
    markdown("## 5. Build the normalized oracle cache"),
    code(
        r"""
        rows = []
        page_key = corpus_ids.astype(str)
        for query_index, pages in enumerate(candidate_indices):
            pages = np.asarray(pages, dtype=int)
            branch_values = {
                "bm25_score": minmax(bm25_scores[query_index, pages]),
                "dense_score": minmax(dense_scores[query_index, pages]),
                "stage1_score": minmax(stage1_scores[query_index, pages]),
                "visual_score": minmax(visual_scores[query_index, pages]),
            }
            branch_ranks = {}
            for branch, values in branch_values.items():
                order = np.lexsort((page_key[pages], -values))
                ranks = np.empty(len(pages), dtype=int)
                ranks[order] = np.arange(1, len(pages) + 1)
                branch_ranks[branch] = ranks
            for local_index, page_index in enumerate(pages):
                rows.append({
                    "dataset": DATASET,
                    "query_id": str(query_ids[query_index]),
                    "page_id": str(corpus_ids[page_index]),
                    "relevance": qrel_lookup.get((query_ids[query_index], corpus_ids[page_index]), 0.0),
                    "bm25_score": float(branch_values["bm25_score"][local_index]),
                    "dense_score": float(branch_values["dense_score"][local_index]),
                    "stage1_score": float(branch_values["stage1_score"][local_index]),
                    "visual_score": float(branch_values["visual_score"][local_index]),
                    "branch_ranks": json.dumps({
                        "bm25": int(branch_ranks["bm25_score"][local_index]),
                        "dense": int(branch_ranks["dense_score"][local_index]),
                        "stage1": int(branch_ranks["stage1_score"][local_index]),
                        "visual": int(branch_ranks["visual_score"][local_index]),
                    }, separators=(",", ":")),
                    "source": query_sources[query_index],
                })

        retrieval_scores = pd.DataFrame(rows).sort_values(
            ["dataset", "query_id", "page_id"], kind="stable"
        ).reset_index(drop=True)
        score_path = OUTPUT_DIR / "retrieval_scores.parquet"
        retrieval_scores.to_parquet(score_path, index=False)
        score_hash = dataframe_sha256(retrieval_scores, ["dataset", "query_id", "page_id"])
        assert retrieval_scores[["dataset", "query_id", "page_id"]].duplicated().sum() == 0
        assert retrieval_scores[["bm25_score", "dense_score", "stage1_score", "visual_score"]].notna().all().all()
        print(f"Oracle cache ready: {len(retrieval_scores):,} rows, content hash {score_hash}")
        """
    ),
    markdown("## 6. Global Fusion, QARF and QPAF oracles"),
    code(
        r"""
        oracle_rows, oracle_summary, subgroup = run_qpaf_oracle(
            retrieval_scores, grids=("w7",), n_bootstrap=2_000
        )
        for row in oracle_rows:
            assert row["qarf_metrics"]["ndcg10"] + 1e-12 >= row["global_metrics"]["ndcg10"]
            assert row["qpaf_metrics"]["ndcg10"] + 1e-12 >= row["qarf_metrics"]["ndcg10"]

        write_jsonl(oracle_rows, OUTPUT_DIR / "fusion_oracle_results.jsonl")
        write_json(oracle_summary, OUTPUT_DIR / "fusion_oracle_summary.json")
        subgroup.to_csv(OUTPUT_DIR / "fusion_oracle_subgroups.csv", index=False)
        result_frame = pd.DataFrame([
            {
                "dataset": row["dataset"],
                "query_id": row["query_id"],
                "grid": row["grid"],
                "global_ndcg10": row["global_metrics"]["ndcg10"],
                "qarf_ndcg10": row["qarf_metrics"]["ndcg10"],
                "qpaf_ndcg10": row["qpaf_metrics"]["ndcg10"],
                "delta_qarf_vs_global": row["delta_qarf_vs_global"],
                "delta_qpaf_vs_qarf": row["delta_qpaf_vs_qarf"],
            }
            for row in oracle_rows
        ])
        result_frame.to_parquet(OUTPUT_DIR / "fusion_oracle_query_summary.parquet", index=False)
        plot_qpaf(result_frame, OUTPUT_DIR / "global_qarf_qpaf_oracle.png")

        feasibility = assess_short_pilot(oracle_summary, coverage_report, grid="w7")
        write_json(feasibility, OUTPUT_DIR / "pilot_feasibility.json")
        (OUTPUT_DIR / "pilot_feasibility.md").write_text(
            feasibility_markdown(feasibility), encoding="utf-8"
        )

        previous_manifest = None
        manifest_path = OUTPUT_DIR / "run_manifest.yaml"
        if manifest_path.exists():
            previous_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest = {
            "study": "vidore_v3_finance_en_short_oracle",
            "scope": "exploratory_feasibility_not_formal_go_no_go",
            "seed": SEED,
            "dataset": {"id": DATASET, "revision": DATASET_REVISION, "queries": 309, "pages": 2942},
            "models": {
                name: {"id": model_name, "revision": checkpoint_sha(model_name)}
                for name, model_name in MODEL_NAMES.items()
            },
            "weights": "w7",
            "bootstrap_resamples": 2_000,
            "candidate_pool": {
                "initial": {"dse": 200, "bm25": 100, "bge_m3": 100},
                "expanded": {"dse": 300, "bm25": 200, "bge_m3": 200},
                "expanded_once": expanded_once,
                "coverage": final_coverage,
            },
            "hardware": {
                "gpu": gpu.name,
                "vram_gb": round(gpu_gb, 2),
                "cuda": torch.version.cuda,
                "torch": torch.__version__,
            },
            "packages": {
                name: importlib.metadata.version(name)
                for name in ["vidore-benchmark", "colpali-engine", "transformers", "datasets"]
            },
            "batch_sizes": BATCH_SIZES,
            "artifacts": {
                "retrieval_score_content_sha256": score_hash,
                "oracle_result_sha256": hashlib.sha256(
                    (OUTPUT_DIR / "fusion_oracle_results.jsonl").read_bytes()
                ).hexdigest(),
            },
        }
        if previous_manifest:
            manifest["reproducibility"] = {
                "previous_score_hash_matches": previous_manifest.get("artifacts", {}).get(
                    "retrieval_score_content_sha256"
                ) == score_hash,
                "previous_oracle_hash_matches": previous_manifest.get("artifacts", {}).get(
                    "oracle_result_sha256"
                ) == manifest["artifacts"]["oracle_result_sha256"],
            }
        else:
            manifest["reproducibility"] = "first_run_rerun_not_yet_checked"
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        print(feasibility_markdown(feasibility))
        print(f"All outputs written to {OUTPUT_DIR}")
        """
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"name": "vidore_v3_short_oracle.ipynb", "provenance": []},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.x"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(OUTPUT)
