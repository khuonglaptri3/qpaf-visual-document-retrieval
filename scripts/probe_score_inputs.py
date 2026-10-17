from __future__ import annotations

import collections
import importlib
import inspect
import json
import pkgutil
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def _parquet_schema(path: Path) -> dict[str, Any]:
    parquet = pq.ParquetFile(path)
    return {
        "kind": "parquet",
        "rows": parquet.metadata.num_rows,
        "row_groups": parquet.metadata.num_row_groups,
        "columns": [
            {"name": field.name, "type": str(field.type)}
            for field in parquet.schema_arrow
        ],
    }


def _json_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, Any] = {"kind": "json", "top_level_type": type(value).__name__}
    if isinstance(value, dict):
        result["top_level_keys"] = sorted(map(str, value))
    elif isinstance(value, list):
        result["items"] = len(value)
        if value and isinstance(value[0], dict):
            result["item_keys"] = sorted(map(str, value[0]))
    return result


def _archive_schema(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [info.filename for info in archive.infolist() if not info.is_dir()]
        kind = "zip"
    elif path.name.lower().endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as archive:
            names = [member.name for member in archive.getmembers() if member.isfile()]
        kind = "tar.gz"
    else:
        raise ValueError(f"Unsupported archive: {path}")

    suffix_counts = collections.Counter(Path(name).suffix.lower() or "<none>" for name in names)
    return {
        "kind": kind,
        "files": len(names),
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "sample_names": sorted(names)[:10],
    }


def inspect_path(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".parquet":
        detail = _parquet_schema(path)
    elif path.suffix.lower() == ".json":
        detail = _json_schema(path)
    elif path.suffix.lower() == ".zip" or path.name.lower().endswith((".tar.gz", ".tgz")):
        detail = _archive_schema(path)
    else:
        detail = {"kind": "opaque"}
    return {"bytes": path.stat().st_size, **detail}


def _retriever_signatures() -> dict[str, Any]:
    import vidore_benchmark.retrievers as retrievers

    available_modules = sorted(module.name for module in pkgutil.iter_modules(retrievers.__path__))
    targets = {
        "bm25": ("vidore_benchmark.retrievers.bm25_retriever", "BM25Retriever"),
        "bge_m3": ("vidore_benchmark.retrievers.bge_m3_retriever", "BGEM3Retriever"),
        "dse": ("vidore_benchmark.retrievers.dse_qwen2_retriever", "DSEQwen2Retriever"),
        "colqwen25": (
            "vidore_benchmark.retrievers.colqwen2_5_retriever",
            "ColQwen2_5_Retriever",
        ),
        "colqwen25_processor": ("colpali_engine.models", "ColQwen2_5_Processor"),
        "local_colqwen25_adapter": ("scripts.colqwen25_retriever", "ColQwen25Retriever"),
        "local_bge_m3_adapter": ("scripts.bge_m3_dense_retriever", "BGEM3DenseRetriever"),
    }
    imports: dict[str, Any] = {}
    for name, (module_name, class_name) in targets.items():
        try:
            value = getattr(importlib.import_module(module_name), class_name)
            imports[name] = {
                "status": "available",
                "module": module_name,
                "class": class_name,
                "signature": str(inspect.signature(value)),
            }
        except (AttributeError, ImportError) as error:
            imports[name] = {
                "status": "missing",
                "module": module_name,
                "class": class_name,
                "error": f"{type(error).__name__}: {error}",
            }
    return {"available_modules": available_modules, "imports": imports}


def _adapter_readiness(
    dataset_key: str,
    files: dict[str, dict[str, Any]],
    retrievers: dict[str, Any],
) -> dict[str, Any]:
    imports = retrievers["imports"]
    blockers = []
    if imports["local_colqwen25_adapter"]["status"] != "available":
        blockers.append("local_colqwen25_adapter_unavailable")
    if dataset_key == "vidore_v3_finance_en":
        corpus_columns = {
            column["name"]
            for name, detail in files.items()
            if name.startswith("corpus/")
            for column in detail.get("columns", [])
        }
        missing = sorted({"corpus_id", "image", "markdown"} - corpus_columns)
        blockers.extend(f"missing_corpus_column:{name}" for name in missing)
    elif dataset_key == "vidoseek":
        blockers.append("page_rendering_and_ocr_protocol_not_declared")
    elif dataset_key == "vimdoc":
        blockers.append("ocr_text_source_not_declared")
    else:
        blockers.append("dataset_adapter_not_implemented")
    return {
        "status": "ready_for_gpu_smoke" if not blockers else "blocked",
        "blockers": blockers,
    }


def probe_score_inputs(
    config: dict[str, Any],
    dataset_key: str,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    datasets = {item["key"]: item for item in config["datasets"]}
    if dataset_key not in datasets:
        raise ValueError(f"Unknown dataset key: {dataset_key}")
    dataset = datasets[dataset_key]
    root = Path(dataset["local_dir"])
    files = {
        relative: inspect_path(root / relative)
        for relative in dataset["required_files"]
    }
    retrievers = _retriever_signatures()
    result = {
        "schema_version": 1,
        "dataset_key": dataset_key,
        "dataset_id": dataset["id"],
        "dataset_revision": dataset["revision"],
        "dataset_root": str(root),
        "qrels_contract": dataset["qrels_contract"],
        "required_file_count": len(files),
        "files": files,
        "retriever_signatures": retrievers,
        "read_only": True,
        "score_extraction_started": False,
    }
    if environment is not None:
        result["models"] = environment["models"]
    result["adapter_readiness"] = _adapter_readiness(dataset_key, files, retrievers)
    return result
