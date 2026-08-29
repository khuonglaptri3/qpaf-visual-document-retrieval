from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from oracle_study.io import dataframe_sha256, read_table, sha256_file, write_json
from oracle_study.metrics import evaluate_scores


SCORE_COLUMNS = ["bm25_score", "dense_score", "stage1_score", "visual_score"]
FUSION_COLUMNS = ["bm25_score", "dense_score", "visual_score"]
KEY_COLUMNS = ["dataset", "query_id", "page_id"]
REQUIRED_ARTIFACTS = [
    "artifacts/baseline_test_output.txt",
    "data/raw_scores.parquet",
    "data/cache/retrieval_scores.parquet",
    "data/cache/candidate_audit.parquet",
    "data/cache/coverage_report.json",
    "artifacts/extraction_manifest.json",
    "artifacts/_EXTRACTION_SUCCESS.json",
    "artifacts/preflight.json",
    "artifacts/baseline_metrics.json",
    "artifacts/run_manifest.json",
]


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _read_text_preserving_legacy_encoding(path: Path) -> str:
    value = path.read_bytes()
    if value.startswith((b"\xff\xfe", b"\xfe\xff")):
        return value.decode("utf-16")
    return value.decode("utf-8")


def _validate_remote_hashes(root: Path, manifest: dict[str, Any]) -> dict[str, bool]:
    paths = {
        "candidate_raw_scores.parquet": root / "data" / "raw_scores.parquet",
        "retrieval_scores.parquet": root / "data" / "cache" / "retrieval_scores.parquet",
        "candidate_audit.parquet": root / "data" / "cache" / "candidate_audit.parquet",
        "coverage_report.json": root / "data" / "cache" / "coverage_report.json",
    }
    checks = {}
    for name, path in paths.items():
        _require(path.is_file(), f"Missing imported extraction artifact: {path}")
        expected = manifest["artifacts"][name]["sha256"]
        checks[name] = sha256_file(path) == expected
    _require(all(checks.values()), f"Imported extraction artifact hash mismatch: {checks}")
    return checks


def _rank_contract(frame: pd.DataFrame) -> bool:
    parsed = frame["branch_ranks"].map(json.loads)
    for branch in ["bm25", "dense", "stage1", "visual"]:
        ranks = parsed.map(lambda value: value[branch]).astype(int)
        for indices in frame.groupby(["dataset", "query_id"], sort=False).indices.values():
            values = ranks.iloc[indices].to_numpy()
            if values.min() != 1 or values.max() != len(values) or len(np.unique(values)) != len(values):
                return False
    return True


def validate_bundle(root: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    raw_path = root / "data" / "raw_scores.parquet"
    scores_path = root / "data" / "cache" / "retrieval_scores.parquet"
    audit_path = root / "data" / "cache" / "candidate_audit.parquet"
    coverage_path = root / "data" / "cache" / "coverage_report.json"
    manifest_path = root / "artifacts" / "extraction_manifest.json"
    extraction_success_path = root / "artifacts" / "_EXTRACTION_SUCCESS.json"
    recorded_run_path = root / "artifacts" / "score_extraction_full.json"

    manifest = _json(manifest_path)
    extraction_success = _json(extraction_success_path)
    recorded_run = _json(recorded_run_path)
    coverage = _json(coverage_path)
    raw = read_table(raw_path).sort_values(KEY_COLUMNS, kind="stable").reset_index(drop=True)
    scores = read_table(scores_path).sort_values(KEY_COLUMNS, kind="stable").reset_index(drop=True)
    audit = read_table(audit_path)

    raw_required = set(KEY_COLUMNS + ["source", "relevance", *SCORE_COLUMNS, "candidate_provenance"])
    score_required = set(KEY_COLUMNS + ["source", "relevance", *SCORE_COLUMNS, "branch_ranks"])
    checks: dict[str, bool] = {
        "manifest_status_pass": manifest.get("status") == "PASS" and manifest.get("scope") == "full",
        "extraction_success_complete": extraction_success.get("status") == "complete",
        "protocol_matches": extraction_success.get("protocol_sha256") == manifest.get("protocol_sha256"),
        "manifest_hash_matches_record": sha256_file(manifest_path)
        == recorded_run.get("remote_manifest_sha256"),
        "raw_columns_complete": raw_required <= set(raw.columns),
        "score_columns_complete": score_required <= set(scores.columns),
        "row_count_matches": len(raw) == len(scores) == 140_083,
        "query_count_matches": raw[["dataset", "query_id"]].drop_duplicates().shape[0] == 309,
        "raw_keys_unique": not raw.duplicated(KEY_COLUMNS).any(),
        "score_keys_unique": not scores.duplicated(KEY_COLUMNS).any(),
        "key_sets_match": raw[KEY_COLUMNS].equals(scores[KEY_COLUMNS]),
        "common_values_match": raw[["source", "relevance"]].equals(scores[["source", "relevance"]]),
        "candidate_provenance_matches": raw["candidate_provenance"].eq("union_dse_bm25_bge").all(),
        "raw_numeric_finite": np.isfinite(raw[["relevance", *SCORE_COLUMNS]].to_numpy(float)).all(),
        "score_numeric_finite": np.isfinite(scores[["relevance", *SCORE_COLUMNS]].to_numpy(float)).all(),
        "relevance_nonnegative": raw["relevance"].ge(0).all(),
        "normalized_scores_bounded": scores[SCORE_COLUMNS].ge(0).all().all()
        and scores[SCORE_COLUMNS].le(1).all().all(),
        "branch_rank_contract": _rank_contract(scores),
        "coverage_gate": float(coverage["final_coverage"]) >= float(coverage["minimum_required"]),
        "no_query_without_relevant_candidate": int(coverage["queries_with_zero_relevant_candidates"])
        == 0,
        "audit_query_count_matches": len(audit) == 309,
        "audit_has_relevant_candidates": audit["relevant_selected"].gt(0).all(),
    }
    checks.update(
        {f"remote_hash_{name}": matched for name, matched in _validate_remote_hashes(root, manifest).items()}
    )

    grouped = raw.groupby(["dataset", "query_id"], sort=False)[SCORE_COLUMNS]
    low = grouped.transform("min")
    high = grouped.transform("max")
    span = high - low
    expected = (raw[SCORE_COLUMNS] - low).div(span.where(span.abs().gt(1e-15), 1.0))
    expected = expected.mask(span.abs().le(1e-15), 0.0)
    checks["normalization_matches_raw"] = bool(
        np.allclose(expected.to_numpy(float), scores[SCORE_COLUMNS].to_numpy(float), atol=1e-12, rtol=0)
    )

    baseline_text = _read_text_preserving_legacy_encoding(
        root / "artifacts" / "baseline_test_output.txt"
    )
    checks["frozen_baseline_29_passed"] = bool(
        any(re.fullmatch(r"29 passed in [0-9.]+s", line) for line in baseline_text.splitlines())
        and " failed" not in baseline_text
        and " error" not in baseline_text.lower()
    )

    failed = sorted(name for name, passed in checks.items() if not bool(passed))
    report = {
        "schema_version": 1,
        "status": "PASS" if not failed else "FAIL",
        "passed": not failed,
        "scope": "qpaf_candidate_score_bundle_not_heaven_full_score",
        "dataset": manifest["dataset"],
        "score_rows": int(len(scores)),
        "query_rows": int(scores[["dataset", "query_id"]].drop_duplicates().shape[0]),
        "coverage": coverage,
        "checks": {name: bool(value) for name, value in checks.items()},
        "failed_checks": failed,
        "retrieval_score_content_sha256": dataframe_sha256(scores, KEY_COLUMNS),
        "raw_score_file_sha256": sha256_file(raw_path),
        "retrieval_score_file_sha256": sha256_file(scores_path),
        "protocol_sha256": manifest["protocol_sha256"],
        "full_score_status": manifest["full_score_status"],
    }
    _require(not failed, f"P0-03 preflight failed: {failed}")
    return report, scores


def summarize_baselines(scores: pd.DataFrame) -> dict[str, Any]:
    query_metrics: dict[str, list[list[float]]] = {
        name: [] for name in ["bm25", "dense", "visual", "rrf", "fixed_equal"]
    }
    for _, group in scores.groupby(["dataset", "query_id"], sort=False):
        page_ids = group["page_id"].astype(str).to_numpy()
        relevance = group["relevance"].to_numpy(float)
        ranks = group["branch_ranks"].map(json.loads)
        method_scores = {
            "bm25": group["bm25_score"].to_numpy(float),
            "dense": group["dense_score"].to_numpy(float),
            "visual": group["visual_score"].to_numpy(float),
            "rrf": sum(
                1.0 / (60.0 + ranks.map(lambda value, key=key: value[key]).to_numpy(float))
                for key in ["bm25", "dense", "visual"]
            ),
            "fixed_equal": group[FUSION_COLUMNS].mean(axis=1).to_numpy(float),
        }
        for name, values in method_scores.items():
            metric = evaluate_scores(values, relevance, page_ids)
            query_metrics[name].append([metric.ndcg10, metric.recall1, metric.recall3, metric.mrr10])

    methods = {}
    for name, rows in query_metrics.items():
        means = np.asarray(rows, dtype=float).mean(axis=0)
        methods[name] = {
            "ndcg_at_10": float(means[0]),
            "recall_at_1": float(means[1]),
            "recall_at_3": float(means[2]),
            "mrr_at_10": float(means[3]),
        }
    return {
        "schema_version": 1,
        "status": "PASS",
        "scope": "candidate_pool_metrics_not_official_full_corpus_metrics",
        "warning": "Use for bundle validation only; do not report as full-corpus benchmark metrics.",
        "queries": int(scores[["dataset", "query_id"]].drop_duplicates().shape[0]),
        "methods": methods,
        "rrf_k": 60,
        "fixed_equal_channels": FUSION_COLUMNS,
    }


def _package_versions() -> dict[str, str]:
    return {
        name: importlib.metadata.version(name)
        for name in ["numpy", "pandas", "pyarrow", "PyYAML", "torch"]
    }


def finalize(root: Path) -> dict[str, Any]:
    root = root.resolve()
    _require(_git(root, "status", "--porcelain") == "", "Refusing to finalize a dirty worktree")
    source_commit = _git(root, "rev-parse", "HEAD")
    preflight, scores = validate_bundle(root)
    baseline_metrics = summarize_baselines(scores)
    extraction_manifest = _json(root / "artifacts" / "extraction_manifest.json")

    write_json(preflight, root / "artifacts" / "preflight.json")
    write_json(baseline_metrics, root / "artifacts" / "baseline_metrics.json")
    run_manifest = {
        "schema_version": 1,
        "status": "PASS",
        "phase": "P0-03",
        "scope": preflight["scope"],
        "source_commit": source_commit,
        "source_tree_clean_before_outputs": True,
        "extraction_source_commit": extraction_manifest["source_commit"],
        "extraction_function_call_id": extraction_manifest["function_call_id"],
        "protocol_sha256": extraction_manifest["protocol_sha256"],
        "dataset": extraction_manifest["dataset"],
        "hardware": extraction_manifest["hardware"],
        "python": sys.version,
        "platform": platform.platform(),
        "packages": _package_versions(),
        "config_sha256": {
            path: sha256_file(root / path)
            for path in [
                "configs/datasets.yaml",
                "configs/environment.yaml",
                "configs/preregistered.yaml",
            ]
        },
    }
    write_json(run_manifest, root / "artifacts" / "run_manifest.json")

    artifacts = {}
    for relative in REQUIRED_ARTIFACTS:
        path = root / relative
        _require(path.is_file(), f"Missing required P0-03 artifact: {relative}")
        artifacts[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    artifact_manifest = {
        "schema_version": 1,
        "status": "PASS",
        "phase": "P0-03",
        "source_commit": source_commit,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    write_json(artifact_manifest, root / "artifacts" / "artifact_manifest.json")
    success = {
        "schema_version": 1,
        "status": "PASS",
        "phase": "P0-03",
        "scope": preflight["scope"],
        "source_commit": source_commit,
        "protocol_sha256": extraction_manifest["protocol_sha256"],
        "artifact_count": len(artifacts),
        "artifact_manifest_sha256": sha256_file(root / "artifacts" / "artifact_manifest.json"),
        "relevant_page_coverage": float(preflight["coverage"]["final_coverage"]),
        "queries_with_zero_relevant_candidates": int(
            preflight["coverage"]["queries_with_zero_relevant_candidates"]
        ),
    }
    write_json(success, root / "artifacts" / "_SUCCESS.json")
    return success


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize the imported P0-03 QPAF score bundle")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(finalize(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
