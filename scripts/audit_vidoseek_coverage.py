from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from scripts.extract_vidore_baseline import (
    EXPANDED_DEPTHS,
    INITIAL_DEPTHS,
    MINIMUM_COVERAGE,
    _coverage,
    make_candidate_indices,
)
from scripts.vidoseek_dataset import parse_annotations


DATASET_KEY = "vidoseek"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SCORE_CACHE_FILES = {
    "bm25": "bm25_scores.pt",
    "dense": "bge_m3_scores.pt",
    "stage1": "dse_scores.pt",
}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _annotation_query_ids(payload: dict[str, Any]) -> np.ndarray:
    examples = payload.get("examples")
    if not isinstance(examples, list) or not examples:
        raise ValueError("ViDoSeek annotations require a non-empty top-level examples list")
    query_ids = sorted(str(example.get("uid", "")) for example in examples)
    if not all(query_ids) or len(set(query_ids)) != len(query_ids):
        raise ValueError("ViDoSeek audit query IDs must be non-empty and unique")
    return np.asarray(query_ids)


def build_candidate_pools(
    query_ids: np.ndarray,
    page_ids: np.ndarray,
    bm25_scores: np.ndarray,
    dense_scores: np.ndarray,
    stage1_scores: np.ndarray,
) -> dict[str, list[np.ndarray]]:
    """Build both frozen score-only pools without accepting relevance data."""
    expected_shape = (len(query_ids), len(page_ids))
    scores = {
        "bm25": np.asarray(bm25_scores, dtype=float),
        "dense": np.asarray(dense_scores, dtype=float),
        "stage1": np.asarray(stage1_scores, dtype=float),
    }
    for name, values in scores.items():
        if values.shape != expected_shape:
            raise ValueError(f"{name} score shape {values.shape} != {expected_shape}")
        if not np.isfinite(values).all():
            raise ValueError(f"{name} scores contain NaN or Inf")

    initial = make_candidate_indices(
        scores["stage1"], scores["bm25"], scores["dense"], page_ids, INITIAL_DEPTHS
    )
    expanded = make_candidate_indices(
        scores["stage1"], scores["bm25"], scores["dense"], page_ids, EXPANDED_DEPTHS
    )
    for query_index, initial_pages in enumerate(initial):
        if not np.isin(initial_pages, expanded[query_index]).all():
            raise RuntimeError("Frozen expanded candidate pool is not a superset of initial pool")
    return {"initial": initial, "expanded": expanded}


def compare_candidate_coverage(
    query_ids: np.ndarray,
    page_ids: np.ndarray,
    candidate_pools: dict[str, list[np.ndarray]],
    qrel_lookup: dict[tuple[Any, Any], float],
    dataset_id: str,
) -> dict[str, Any]:
    """Evaluate already-built candidate pools against qrels for audit only."""
    summaries: dict[str, dict[str, Any]] = {}
    zero_query_ids: dict[str, list[str]] = {}
    for name in ["initial", "expanded"]:
        coverage, audit = _coverage(
            query_ids,
            page_ids,
            candidate_pools[name],
            qrel_lookup,
            dataset_id=dataset_id,
        )
        zero_ids = sorted(audit.loc[audit["relevant_selected"].eq(0), "query_id"].tolist())
        zero_query_ids[name] = zero_ids
        summaries[name] = {
            "depths": INITIAL_DEPTHS if name == "initial" else EXPANDED_DEPTHS,
            "coverage": coverage,
            "queries_with_zero_relevant_candidates": len(zero_ids),
            "zero_relevant_query_ids": zero_ids,
            "mean_candidates": float(audit["candidate_count"].mean()),
        }

    rescued = sorted(set(zero_query_ids["initial"]) - set(zero_query_ids["expanded"]))
    still_uncovered = zero_query_ids["expanded"]
    expanded_gate_passes = (
        summaries["expanded"]["coverage"] >= MINIMUM_COVERAGE and not still_uncovered
    )
    return {
        "minimum_coverage": MINIMUM_COVERAGE,
        "initial": summaries["initial"],
        "expanded": summaries["expanded"],
        "rescued_query_ids": rescued,
        "still_uncovered_query_ids": still_uncovered,
        "decision": (
            "expanded_depths_satisfy_existing_gate"
            if expanded_gate_passes
            else "expanded_depths_still_fail_existing_gate"
        ),
        "candidate_generation_used_qrels": False,
        "qrels_use": "post_candidate_coverage_audit_only",
    }


def audit_persisted_vidoseek_coverage(
    dataset_config: dict[str, Any],
    volume_root: Path,
    source_protocol_sha256: str,
) -> dict[str, Any]:
    if not HEX64.fullmatch(source_protocol_sha256):
        raise ValueError("source_protocol_sha256 must be 64 lowercase hex characters")

    dataset = next(
        item for item in dataset_config["datasets"] if item["key"] == DATASET_KEY
    )
    run_root = (
        volume_root
        / "score_extraction"
        / DATASET_KEY
        / source_protocol_sha256
        / "full"
    )
    cache_dir = run_root / "cache"
    preparation_path = run_root / "prepared_corpus" / "_PREPARED.json"
    if not preparation_path.is_file():
        raise FileNotFoundError(f"Missing preparation marker: {preparation_path}")
    preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
    if preparation.get("status") != "complete" or not isinstance(preparation.get("pages"), list):
        raise RuntimeError("Persisted ViDoSeek preparation marker is incomplete")
    page_ids = np.asarray([str(row["page_id"]) for row in preparation["pages"]])
    if len(page_ids) != int(preparation["page_count"]) or len(set(page_ids)) != len(page_ids):
        raise RuntimeError("Persisted ViDoSeek page IDs are incomplete or duplicated")

    annotation_path = Path(dataset["local_dir"]) / dataset["discovery_extraction"]["annotation_file"]
    expected_annotation_sha256 = dataset["qrels_metadata"]["annotation_file_sha256"]
    if _file_sha256(annotation_path) != expected_annotation_sha256:
        raise RuntimeError("ViDoSeek annotation hash does not match the frozen contract")
    annotation_payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    query_ids = _annotation_query_ids(annotation_payload)

    import torch

    loaded_scores: dict[str, np.ndarray] = {}
    cache_sha256: dict[str, str] = {}
    for name, filename in SCORE_CACHE_FILES.items():
        path = cache_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing persisted score cache: {path}")
        value = torch.load(path, map_location="cpu", weights_only=False)
        loaded_scores[name] = value.detach().float().numpy()
        cache_sha256[filename] = _file_sha256(path)

    candidate_pools = build_candidate_pools(
        query_ids,
        page_ids,
        loaded_scores["bm25"],
        loaded_scores["dense"],
        loaded_scores["stage1"],
    )
    annotations = parse_annotations(annotation_payload)
    if not np.array_equal(query_ids, annotations.query_ids):
        raise RuntimeError("Audit query order does not match the frozen annotation order")
    comparison = compare_candidate_coverage(
        query_ids,
        page_ids,
        candidate_pools,
        annotations.qrel_lookup,
        dataset_id=dataset["id"],
    )
    return {
        "schema_version": 1,
        "status": "complete",
        "audit_type": "vidoseek_frozen_expanded_candidate_coverage",
        "audit_only": True,
        "gpu_used": False,
        "source_protocol_sha256": source_protocol_sha256,
        "source_run_root": str(run_root),
        "dataset": {
            "id": dataset["id"],
            "revision": dataset["revision"],
            "queries": len(query_ids),
            "pages": len(page_ids),
            "annotation_sha256": expected_annotation_sha256,
            "preparation_marker_sha256": _file_sha256(preparation_path),
        },
        "score_cache_sha256": cache_sha256,
        **comparison,
    }
