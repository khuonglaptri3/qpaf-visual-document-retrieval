"""Read-only local M3 review; no network, retriever, GPU, or optimizer imports.

This is intentionally NOT an execution launcher. Even a successful review cannot
start extraction or training. Helpers operate on supplied IDs/synthetic scores.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path


CONFIG = "configs/vimdoc_m3_local_v1.json"
MANIFEST = "docs/04_data_protocol/manifests/vimdoc_m3_local_v1.json"
INVENTORY = (
    CONFIG,
    "configs/vimdoc_ocr_page_identity_v1.json",
    "configs/vimdoc_archive_content_audit_v1.json",
    "scripts/prepare_vimdoc_m3.py",
    "scripts/prepare_vimdoc_archive_content_audit.py",
    "scripts/run_vimdoc_archive_content_audit.py",
    "scripts/validate_vimdoc_ocr_page_identity.py",
    "vimdoc_archive_audit_modal.py",
    "tests/test_vimdoc_m3_preparation.py",
    "tests/test_vimdoc_archive_content_audit.py",
    "tests/test_vimdoc_ocr_page_identity.py",
    "docs/04_data_protocol/VIMDOC_M3_LOCAL_PACKAGE.md",
    "docs/04_data_protocol/VIMDOC_ARCHIVE_CONTENT_AUDIT_EXECUTION_REVIEW.md",
    "docs/04_data_protocol/VIMDOC_OCR_PAGE_IDENTITY_SPEC.md",
    "configs/datasets.yaml",
    "configs/environment.yaml",
    "configs/preregistered.yaml",
    "requirements-lock.txt",
    "requirements-learned-local.txt",
    "artifacts/dataset_materialization_vimdoc.json",
    "docs/04_data_protocol/manifests/vimdoc_archive_content_audit_v1_preparation.json",
    "artifacts/score_input_probe_vimdoc.json",
    "scripts/materialize_datasets.py",
    "scripts/extract_vidore_baseline.py",
    "src/oracle_study/learned/__init__.py",
    "src/oracle_study/learned/features.py",
    "src/oracle_study/learned/models.py",
    "src/oracle_study/learned/losses.py",
    "tests/test_features.py",
    "tests/test_models.py",
    "tests/test_losses.py",
    "tests/test_gradients.py",
)
CHANNELS = ("bm25", "dense", "visual")
CLOSED_AUTHORIZATION = {
    "local_preparation_approved": True,
    "protocol_proposals_adopted": False,
    "modal_execution_approved": False,
    "gpu_execution_approved": False,
    "score_extraction_approved": False,
    "training_approved": False,
    "optimizer_steps_approved": False,
    "approved_invocations": 0,
    "approved_timeout_seconds": 0,
    "approved_retries": 0,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_ids(values: list[str]) -> list[str]:
    if not values or any(
        not isinstance(value, str) or not value or any(c in value for c in "\r\n\t")
        for value in values
    ):
        raise ValueError("IDs must be nonempty strings without line/tab delimiters")
    if len(set(values)) != len(values):
        raise ValueError("Duplicate IDs are not permitted")
    return list(values)


def ids_sha256(values: list[str]) -> str:
    return hashlib.sha256(("\n".join(checked_ids(values)) + "\n").encode()).hexdigest()


def propose_split(ids: list[str], namespace: str, train_count: int) -> dict:
    """ID-only proposal; never reads query text, qrels, documents or scores."""
    ids = checked_ids(ids)
    if type(train_count) is not int or not 0 < train_count < len(ids):
        raise ValueError("Both splits must be nonempty")
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("A split namespace is required")
    ordered = sorted(ids, key=lambda q: (hashlib.sha256(f"{namespace}:{q}".encode()).digest(), q))
    train, validation = ordered[:train_count], ordered[train_count:]
    return {
        "status": "PROPOSED_NOT_ADOPTED",
        "train_ids": train,
        "validation_ids": validation,
        "train_ids_sha256": ids_sha256(train),
        "validation_ids_sha256": ids_sha256(validation),
    }


def candidate_union(channel_scores: dict[str, dict[str, float]], top_k: int = 200) -> list[str]:
    """Reference union from complete supplied scores, not a retriever runner.

    All channels must cover the same page universe. This API has no label input.
    Production extraction must provide equivalent top-K/re-score audit evidence.
    """
    if set(channel_scores) != set(CHANNELS):
        raise ValueError("Exactly BM25/dense/visual are required; DSE is not a substitute")
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    pages = checked_ids(list(channel_scores[CHANNELS[0]]))
    selected: set[str] = set()
    for channel in CHANNELS:
        scores = channel_scores[channel]
        if set(scores) != set(pages):
            raise ValueError("All channels must cover the same page universe")
        if any(type(s) not in (float, int) or not math.isfinite(s) for s in scores.values()):
            raise ValueError("Scores must be finite numeric values")
        selected.update(sorted(pages, key=lambda p: (-scores[p], p))[:top_k])
    return sorted(selected)


def normalized_union(channel_scores: dict[str, dict[str, float]], top_k: int = 200) -> list[dict]:
    """Float64 reference for Eq. 2, normalized only AFTER union construction."""
    pages = candidate_union(channel_scores, top_k)
    values = {p: [] for p in pages}
    for channel in CHANNELS:
        scores = channel_scores[channel]
        lo, hi = min(scores[p] for p in pages), max(scores[p] for p in pages)
        span = hi - lo
        if not math.isfinite(span):
            raise ValueError("Score range overflow")
        for page in pages:
            values[page].append((scores[page] - lo) / span if span > 1e-15 else 0.0)
    return [{"page_id": p, "scores": values[p]} for p in pages]


def document_layout(page_ids: list[str]) -> dict:
    """Sort pages before max aggregation so first-tie gradients are stable."""
    pages = sorted(checked_ids(page_ids))
    mapping = {}
    for page in pages:
        document, separator, suffix = page.rpartition("_")
        if not separator or not document or not suffix:
            raise ValueError("Page ID must have a final underscore-delimited segment")
        mapping[page] = document
    documents = sorted(set(mapping.values()))
    indices = {d: i for i, d in enumerate(documents)}
    return {"page_ids": pages, "document_ids": documents,
            "page_to_unit_groups": [indices[mapping[p]] for p in pages]}


def resolve_matched(config: dict, split: dict) -> dict:
    expected = {"QARF": {"gate_granularity": "query_masked_mean"},
                "QPAF": {"gate_granularity": "page"}}
    if config["matched_methods"] != expected:
        raise ValueError("Only the declared gate granularity may differ")
    shared = {k: copy.deepcopy(config[k]) for k in (
        "dataset", "retrievers", "score_contract", "shared_training",
        "evaluation_contract", "future_execution", "authorization")}
    shared["split_hashes"] = {k: split[k] for k in ("train_ids_sha256", "validation_ids_sha256")}
    return {method: {**copy.deepcopy(shared), **override} for method, override in expected.items()}


def preflight(root: Path, include_ids: bool = False) -> dict:
    root = root.resolve()
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    entries = manifest["files"]
    if len(entries) != len(INVENTORY) or {e["path"] for e in entries} != set(INVENTORY):
        raise ValueError("Manifest inventory differs from the exact local package")
    for entry in entries:
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root) or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"Source/input hash drift: {entry['path']}")
    config = json.loads((root / CONFIG).read_text(encoding="utf-8"))
    # JSON equality also distinguishes false from 0, unlike Python dict equality.
    if json.dumps(config["authorization"], sort_keys=True) != json.dumps(CLOSED_AUTHORIZATION, sort_keys=True):
        raise ValueError("This package supports local preparation ONLY")
    future = config["future_execution"]
    if future["runner_implemented"] is not False or future["run_commands"] != []:
        raise ValueError("No live runner/command belongs in this preparation package")
    receipt = json.loads((root / config["dataset"]["materialization_receipt"]).read_text(encoding="utf-8"))
    dataset = config["dataset"]
    sample = receipt["validation"]["confirmation_sample"]
    ids = checked_ids(sample["selected_query_ids"])
    if len(ids) != dataset["sample_count"] or ids_sha256(ids) != dataset["sample_ids_sha256"]:
        raise ValueError("Frozen development sample mismatch")
    if receipt["id"] != dataset["id"] or receipt["revision"] != dataset["revision"]:
        raise ValueError("Dataset identity/revision mismatch")
    if receipt["qrels_sha256"] != dataset["document_qrels_sha256"]:
        raise ValueError("Document-qrels hash mismatch")
    for name, key in (("ViMDoc_pages.tar.gz", "archive_sha256"),
                      ("data/ViMDoc-00000-of-00001.parquet", "query_parquet_sha256")):
        if receipt["file_sha256"][name] != dataset[key]:
            raise ValueError("Historical payload hash mismatch")
    proposal = config["split_proposal"]
    split = propose_split(ids, proposal["namespace"], proposal["train_count"])
    if len(split["validation_ids"]) != proposal["validation_count"]:
        raise ValueError("Validation split count mismatch")
    resolved = resolve_matched(config, split)
    split["train_count"] = len(split["train_ids"])
    split["validation_count"] = len(split["validation_ids"])
    if not include_ids:
        del split["train_ids"], split["validation_ids"]
    return {
        "local_package_integrity": "PASS",
        "ready_for_execution": False,
        "m3_execution_readiness": "BLOCKED",
        "files_verified": len(entries),
        "sample_count": len(ids),
        "split_proposal": split,
        "matched_configs": resolved,
        "unresolved_before_execution": config["unresolved_before_execution"],
        "verification_scope": "local_bytes_and_historical_metadata_only",
        "remote_state_verified": False,
        "real_score_cache_verified": False,
        "scientific_metrics_computed": False,
        "writes_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-proposed-ids", action="store_true")
    args = parser.parse_args()
    try:
        report = preflight(Path(__file__).resolve().parents[1], args.include_proposed_ids)
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.exit(2, f"LOCAL_PREPARATION_REFUSED: {error}\n")
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0  # Integrity success, explicitly NOT execution readiness.


if __name__ == "__main__":
    raise SystemExit(main())
