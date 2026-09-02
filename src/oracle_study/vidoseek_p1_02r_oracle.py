from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import queue
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml

from .qpaf import run_qpaf_oracle


PROTOCOL_ID = "vidoseek_p1_02r_oracle_w7_v1"
PREPARED_STATUS = "preexecution_safeguards_prepared_review_required"
APPROVED_STATUS = "bounded_cpu_performance_probe_execution_approved"
PROBE_SCOPE = "one_local_cpu_non_result_performance_probe"
APPROVED_SAFEGUARD_COMMIT = "024f2f0a0998f0c781ac738d259603c6bbf29ba9"
EXECUTION_COMMIT_RULE = "single_non_merge_direct_child_with_exact_changed_paths"
APPROVAL_COMMIT_PATHS = [
    "Context.md",
    "Tasks.md",
    "configs/vidoseek_p1_02r_oracle_w7_v1.yaml",
    "experiments/CHANGELOG.md",
    "src/oracle_study/vidoseek_p1_02r_oracle.py",
    "tests/test_vidoseek_p1_02r_oracle_protocol.py",
    "tests/test_vidoseek_p1_02r_oracle_safeguards.py",
]
CPU_THREAD_ENV = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
PROBE_SCORE_COLUMNS = [
    "dataset",
    "query_id",
    "page_id",
    "source",
    "bm25_score",
    "dense_score",
    "visual_score",
]
PREPARATION_APPROVAL_TEXT = (
    "Approve local preparation and commit of the P1-02R-O1 pre-execution safeguards: "
    "add a protocol-bound input preflight, an immutable run-manifest writer, and a "
    "bounded CPU performance-probe entry point with tests. Do not execute the "
    "performance probe or W7 oracle, do not write oracle results, do not run Modal/GPU "
    "or P1-03, and do not relabel P1-02. Return the complete diff, proposed probe "
    "limits, runtime stop condition, and exact future command for review."
)
EXECUTION_APPROVAL_TEXT = (
    "Approve preparing and committing the execution-guard/provenance amendment for "
    "exactly one human-run P1-02R-O1 bounded CPU performance probe from commit "
    "024f2f0a0998f0c781ac738d259603c6bbf29ba9. Keep the fixed limits and no-retry "
    "rule. Do not execute the probe yourself, W7 oracle, Modal/GPU, or P1-03, and "
    "do not relabel P1-02."
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_protocol(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("P1-02R-O1 protocol must be a mapping")
    return value


def _repo_path(repo_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise ValueError(f"Protocol path must be repository-relative: {relative}")
    root = repo_root.resolve()
    resolved = (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Protocol path escapes the repository: {relative}")
    return resolved


def validate_protocol(protocol: dict[str, Any], repo_root: Path) -> None:
    if (
        protocol.get("schema_version") != 1
        or protocol.get("protocol_id") != PROTOCOL_ID
    ):
        raise ValueError("Unsupported P1-02R-O1 protocol identity")
    status = protocol.get("status")
    if status not in {PREPARED_STATUS, APPROVED_STATUS}:
        raise ValueError("Unsupported P1-02R-O1 protocol status")
    if (
        protocol.get("authorization", {})
        .get("preexecution_preparation", {})
        .get("approval_text")
        != PREPARATION_APPROVAL_TEXT
    ):
        raise ValueError("P1-02R-O1 pre-execution preparation approval drifted")

    graph = protocol.get("parent_task_graph", {})
    if graph.get("frozen_p1_02", {}).get("status") != "BLOCKED":
        raise ValueError("P1-02 must remain BLOCKED")
    if graph.get("frozen_p1_02", {}).get("relabel_allowed") is not False:
        raise ValueError("P1-02 relabeling must remain forbidden")
    if graph.get("verified_recovery", {}).get("status") != "PASS":
        raise ValueError("P1-02R recovery must remain a verified PASS")
    if graph.get("frozen_p1_03", {}).get("status") != "BLOCKED":
        raise ValueError("P1-03 must remain BLOCKED")
    if graph.get("frozen_p1_03", {}).get("execution_authorized") is not False:
        raise ValueError("P1-03 execution must remain unauthorized")

    probe = protocol.get("performance_probe", {})
    query_indices = probe.get("query_indices")
    page_limits = probe.get("page_limits")
    if query_indices != [0, 570, 1141]:
        raise ValueError("Performance probe query indices must remain [0, 570, 1141]")
    if page_limits != [128, 256, 512]:
        raise ValueError("Performance probe page limits must remain [128, 256, 512]")
    if probe.get("bootstrap_resamples") != 100 or probe.get("repetitions") != 1:
        raise ValueError("Performance probe repetition/bootstrap limits drifted")
    if probe.get("per_case_timeout_seconds") != 120:
        raise ValueError("Performance probe per-case timeout must remain 120 seconds")
    if probe.get("ladder_timeout_seconds") != 300:
        raise ValueError("Performance probe ladder timeout must remain 300 seconds")
    if probe.get("actual_relevance_loaded") is not False:
        raise ValueError("Performance probe must not load actual relevance")
    if probe.get("device") != "cpu" or probe.get("grid") != "w7":
        raise ValueError("Performance probe must remain CPU-only W7 timing")
    if probe.get("classification") != "engineering_performance_probe_not_result":
        raise ValueError("Performance probe must remain classified as a non-result")
    if probe.get("max_case_candidate_rows") != 1536:
        raise ValueError("Performance probe must remain bounded to 1,536 rows per case")
    if probe.get("max_concurrent_cases") != 1 or probe.get("cpu_thread_limit") != 1:
        raise ValueError("Performance probe must remain single-process/single-threaded")
    if probe.get("automatic_retry_allowed") is not False:
        raise ValueError("Performance probe automatic retry must remain forbidden")
    if probe.get("query_selection") != (
        "systematic_floor_indices_over_candidate_audit_order"
    ):
        raise ValueError("Performance probe query selection drifted")
    if probe.get("page_selection") != "systematic_floor_indices_over_ascending_page_id":
        raise ValueError("Performance probe page selection drifted")
    if probe.get("unused_required_columns_rule") != (
        "deterministic_stage1_and_branch_rank_placeholders"
    ):
        raise ValueError("Performance probe placeholder rule drifted")
    if probe.get("output_manifest_produced") is not False:
        raise ValueError(
            "Performance-probe manifest must remain unproduced in the protocol"
        )
    if probe.get("attempt_marker_produced") is not False:
        raise ValueError("Performance-probe attempt marker must remain unproduced")

    preflight = protocol.get("preflight_contract", {})
    if preflight.get("mode") != "read_only":
        raise ValueError("P1-02R-O1 preflight must remain read-only")
    for field in [
        "actual_relevance_values_loaded",
        "report_persisted",
        "oracle_executed",
    ]:
        if preflight.get(field) is not False:
            raise ValueError(f"P1-02R-O1 preflight boundary drifted: {field}")
    if (
        preflight.get(
            "verifies_input_bytes_hashes_parquet_metadata_and_evidence_cross_links"
        )
        is not True
    ):
        raise ValueError("P1-02R-O1 preflight verification contract is incomplete")

    manifest_contract = protocol.get("run_manifest_contract", {})
    if manifest_contract.get("write_mode") != "atomic_create_once_no_overwrite":
        raise ValueError("P1-02R-O1 run manifest must remain immutable")
    if manifest_contract.get("classification") != probe.get("classification"):
        raise ValueError("P1-02R-O1 run-manifest classification drifted")
    if manifest_contract.get("path") != probe.get("output_manifest_path"):
        raise ValueError("P1-02R-O1 run-manifest path drifted")
    if manifest_contract.get("attempt_marker_sha256_required") is not True:
        raise ValueError("P1-02R-O1 run manifest must link the consumed attempt")
    for field in ["actual_relevance_values_allowed", "oracle_result_fields_allowed"]:
        if manifest_contract.get(field) is not False:
            raise ValueError(f"P1-02R-O1 run-manifest boundary drifted: {field}")

    attempt_contract = protocol.get("attempt_marker_contract", {})
    if attempt_contract.get("write_mode") != "atomic_create_once_no_overwrite":
        raise ValueError("P1-02R-O1 attempt marker must remain immutable")
    if attempt_contract.get("classification") != "engineering_probe_attempt_not_result":
        raise ValueError("P1-02R-O1 attempt-marker classification drifted")
    if attempt_contract.get("path") != probe.get("attempt_marker_path"):
        raise ValueError("P1-02R-O1 attempt-marker path drifted")
    if attempt_contract.get("consumes_authorization_before_preflight") is not True:
        raise ValueError("P1-02R-O1 attempt marker must consume before preflight")
    if attempt_contract.get("automatic_retry_allowed") is not False:
        raise ValueError("P1-02R-O1 attempt marker must forbid retry")

    readiness = protocol.get("execution_readiness", {})
    for field in [
        "protocol_bound_preflight_exists",
        "immutable_run_manifest_writer_exists",
        "performance_probe_entrypoint_exists",
    ]:
        if readiness.get(field) is not True:
            raise ValueError(f"P1-02R-O1 readiness field must be true: {field}")
    if readiness.get("all_corpus_runtime_measured") is not False:
        raise ValueError("All-corpus runtime must remain unmeasured")
    if readiness.get("ready_for_execution_approval") is not False:
        raise ValueError("Full W7 execution must remain unready")

    execution = protocol.get("execution", {})
    if status == PREPARED_STATUS:
        if readiness.get("ready_for_performance_probe_execution_approval") is not True:
            raise ValueError("Prepared performance probe must be ready for approval")
        if probe.get("command_currently_authorized") is not False:
            raise ValueError("Reviewed future command must remain unauthorized")
        if readiness.get("performance_probe_authorized") is not False:
            raise ValueError("Prepared performance probe must remain unauthorized")
        if not execution or any(value is not False for value in execution.values()):
            raise ValueError(
                "Prepared P1-02R-O1 execution guards must all remain closed"
            )
        if "performance_probe_execution" in protocol.get("authorization", {}):
            raise ValueError(
                "Prepared protocol must not claim probe execution approval"
            )
    else:
        if readiness.get("ready_for_performance_probe_execution_approval") is not False:
            raise ValueError("Approved performance probe must not await approval")
        if probe.get("command_currently_authorized") is not True:
            raise ValueError(
                "Approved performance-probe command must be marked authorized"
            )
        if readiness.get("performance_probe_authorized") is not True:
            raise ValueError("Approved performance probe must be authorized")
        if readiness.get("performance_probe_executed") is not False:
            raise ValueError("Approved performance probe must remain unexecuted")
        if execution.get("performance_probe_allowed") is not True:
            raise ValueError("Approved performance-probe execution guard is closed")
        if execution.get("performance_probe_output_write_allowed") is not True:
            raise ValueError("Approved performance-probe output guard is closed")
        for field in [
            "local_cpu_oracle_allowed",
            "modal_allowed",
            "gpu_allowed",
            "oracle_analysis_allowed",
            "p1_03_allowed",
            "learned_qpaf_allowed",
            "output_writes_allowed",
        ]:
            if execution.get(field) is not False:
                raise ValueError(f"Approved protocol opened forbidden guard: {field}")
        approval = protocol.get("authorization", {}).get(
            "performance_probe_execution", {}
        )
        if approval.get("approval_text") != EXECUTION_APPROVAL_TEXT:
            raise ValueError("P1-02R-O1 execution approval text drifted")

    source_contract = protocol.get("implementation_contract", {})
    if source_contract.get("source_sha256_basis") != "utf8_lf_bytes":
        raise ValueError("Source hashes must use UTF-8/LF-normalized bytes")
    sources = source_contract.get("source_files")
    if not isinstance(sources, list) or not sources:
        raise ValueError("P1-02R-O1 must pin its source files")
    for source in sources:
        path = _repo_path(repo_root, source["path"])
        if not path.is_file() or text_sha256(path) != source["sha256"]:
            raise RuntimeError(f"P1-02R-O1 source hash mismatch: {source['path']}")


def _parquet_shape(path: Path) -> dict[str, Any]:
    parquet = pq.ParquetFile(path)
    return {
        "rows": parquet.metadata.num_rows,
        "row_groups": parquet.metadata.num_row_groups,
        "columns": [field.name for field in parquet.schema_arrow],
        "column_types": {field.name: str(field.type) for field in parquet.schema_arrow},
    }


def _check_file(
    path: Path, expected_bytes: int, expected_sha256: str, label: str
) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    if path.stat().st_size != expected_bytes:
        raise RuntimeError(f"{label} byte count does not match the protocol")
    if file_sha256(path) != expected_sha256:
        raise RuntimeError(f"{label} SHA-256 does not match the protocol")


def protocol_bound_preflight(
    protocol_path: Path,
    repo_root: Path | None = None,
    *,
    allow_consumed_attempt: bool = False,
) -> dict[str, Any]:
    protocol_path = protocol_path.resolve()
    root = (repo_root or protocol_path.parents[1]).resolve()
    protocol = load_protocol(protocol_path)
    validate_protocol(protocol, root)

    bundle = protocol["input_bundle"]
    scores = bundle["retrieval_scores"]
    audit = bundle["candidate_audit"]
    score_path = _repo_path(root, scores["path"])
    audit_path = _repo_path(root, audit["path"])
    manifest_path = _repo_path(root, scores["manifest_path"])
    review_path = _repo_path(root, scores["integrity_review_path"])

    _check_file(score_path, scores["bytes"], scores["byte_sha256"], "retrieval scores")
    _check_file(audit_path, audit["bytes"], audit["byte_sha256"], "candidate audit")
    _check_file(
        manifest_path,
        scores["manifest_bytes"],
        scores["manifest_sha256"],
        "extraction manifest",
    )
    _check_file(
        review_path,
        scores["integrity_review_bytes"],
        scores["integrity_review_sha256"],
        "integrity review",
    )

    score_shape = _parquet_shape(score_path)
    audit_shape = _parquet_shape(audit_path)
    for field in ["rows", "row_groups", "columns", "column_types"]:
        if score_shape[field] != scores[field]:
            raise RuntimeError(f"Retrieval-score {field} does not match the protocol")
        if audit_shape[field] != audit[field]:
            raise RuntimeError(f"Candidate-audit {field} does not match the protocol")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    for name, expected in [
        ("retrieval_scores.parquet", scores),
        ("candidate_audit.parquet", audit),
    ]:
        recorded = manifest.get("artifacts", {}).get(name, {})
        if recorded.get("bytes") != expected["bytes"]:
            raise RuntimeError(f"Manifest {name} byte count mismatch")
        if recorded.get("rows") != expected["rows"]:
            raise RuntimeError(f"Manifest {name} row count mismatch")
        if recorded.get("sha256") != expected["byte_sha256"]:
            raise RuntimeError(f"Manifest {name} SHA-256 mismatch")
        reviewed = review.get("payloads", {}).get(name, {})
        for field, key in [
            ("bytes", "bytes"),
            ("rows", "rows"),
            ("sha256", "byte_sha256"),
        ]:
            if reviewed.get(field) != expected[key]:
                raise RuntimeError(f"Integrity-review {name} {field} mismatch")
    if (
        manifest["artifacts"]["retrieval_scores.parquet"].get("content_sha256")
        != scores["content_sha256"]
    ):
        raise RuntimeError("Manifest retrieval-score content SHA-256 mismatch")
    checks = review.get("checks")
    if (
        review.get("status") != "PASS"
        or not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise RuntimeError("P1-02R integrity review is not a complete PASS")
    contract = review.get("contract", {})
    expected_contract = {
        "rows_checked_each_score_file": scores["rows"],
        "queries": scores["queries"],
        "pages_per_query": scores["pages_per_query"],
        "coverage": scores["coverage"],
        "missing_relevant_pairs": scores["missing_relevant_pairs"],
        "queries_with_zero_relevant_candidates": scores[
            "queries_with_zero_relevant_candidates"
        ],
        "full_score_produced": False,
    }
    for field, expected in expected_contract.items():
        if contract.get(field) != expected:
            raise RuntimeError(f"Integrity-review contract mismatch: {field}")
    boundaries = review.get("boundaries", {})
    if boundaries.get("frozen_p1_02_status") != "BLOCKED":
        raise RuntimeError("Integrity review relabeled frozen P1-02")
    if boundaries.get("p1_03_authorized") is not False:
        raise RuntimeError("Integrity review authorized P1-03")

    oracle_output = _repo_path(
        root, protocol["planned_outputs"]["immutable_output_dir"]
    )
    probe_manifest = _repo_path(
        root, protocol["performance_probe"]["output_manifest_path"]
    )
    attempt_marker = _repo_path(
        root, protocol["performance_probe"]["attempt_marker_path"]
    )
    if oracle_output.exists():
        raise FileExistsError(
            f"Oracle output directory already exists: {oracle_output}"
        )
    if probe_manifest.exists():
        raise FileExistsError(
            f"Performance-probe manifest already exists: {probe_manifest}"
        )
    if attempt_marker.exists() and not allow_consumed_attempt:
        raise FileExistsError(
            f"Performance-probe authorization is already consumed: {attempt_marker}"
        )
    if allow_consumed_attempt and not attempt_marker.is_file():
        raise FileNotFoundError("Performance-probe attempt marker was not created")

    return {
        "schema_version": 1,
        "status": "PASS",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": text_sha256(protocol_path),
        "retrieval_score_sha256": scores["byte_sha256"],
        "retrieval_score_content_sha256": scores["content_sha256"],
        "rows": scores["rows"],
        "queries": scores["queries"],
        "pages_per_query": scores["pages_per_query"],
        "coverage": scores["coverage"],
        "semantic_integrity_inherited_from_hash_pinned_review": True,
        "actual_relevance_loaded": False,
        "oracle_executed": False,
        "scientific_result_produced": False,
        "authorization_attempt_consumed": allow_consumed_attempt,
    }


def require_performance_probe_execution_approval(
    protocol: dict[str, Any],
    repo_root: Path,
) -> str:
    validate_protocol(protocol, repo_root)
    readiness = protocol["execution_readiness"]
    execution = protocol["execution"]
    if readiness.get("performance_probe_authorized") is not True:
        raise RuntimeError("P1-02R-O1 performance probe is prepared but not authorized")
    if execution.get("performance_probe_allowed") is not True:
        raise RuntimeError("P1-02R-O1 performance-probe execution guard is closed")
    for field in [
        "local_cpu_oracle_allowed",
        "modal_allowed",
        "gpu_allowed",
        "oracle_analysis_allowed",
        "p1_03_allowed",
        "learned_qpaf_allowed",
        "output_writes_allowed",
    ]:
        if execution.get(field) is not False:
            raise RuntimeError(f"P1-02R-O1 forbidden execution flag opened: {field}")
    if execution.get("performance_probe_output_write_allowed") is not True:
        raise RuntimeError("P1-02R-O1 performance-probe output guard is closed")

    approval = protocol.get("authorization", {}).get("performance_probe_execution")
    required = {
        "scope": PROBE_SCOPE,
        "approved_by": "user",
        "approved_on": "2026-09-02",
        "approval_text": EXECUTION_APPROVAL_TEXT,
        "authorized_invocations": 1,
        "consumed_invocations": 0,
        "remaining_authorized_invocations": 1,
        "automatic_retry_allowed": False,
        "execution_actor": "human",
        "approved_safeguard_commit": APPROVED_SAFEGUARD_COMMIT,
        "execution_commit_rule": EXECUTION_COMMIT_RULE,
        "approval_commit_changed_paths": APPROVAL_COMMIT_PATHS,
    }
    if not isinstance(approval, dict) or any(
        approval.get(field) != expected for field, expected in required.items()
    ):
        raise RuntimeError(
            "P1-02R-O1 performance-probe approval provenance is incomplete"
        )
    if any(os.environ.get(name) != "1" for name in CPU_THREAD_ENV):
        raise RuntimeError("P1-02R-O1 CPU thread limits are not pinned to one")
    live_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    commit_and_parents = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.split()
    if commit_and_parents != [live_commit, APPROVED_SAFEGUARD_COMMIT]:
        raise RuntimeError(
            "P1-02R-O1 execution checkout must be one non-merge direct child of the "
            "approved safeguard commit"
        )
    changed_paths = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            APPROVED_SAFEGUARD_COMMIT,
            "HEAD",
            "--",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.splitlines()
    if changed_paths != APPROVAL_COMMIT_PATHS:
        raise RuntimeError("P1-02R-O1 approval commit changed-path allowlist drifted")
    tracked_status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    if tracked_status:
        raise RuntimeError(
            "P1-02R-O1 performance probe requires a clean tracked checkout"
        )
    return live_commit


def _systematic_positions(total: int, count: int) -> np.ndarray:
    if count < 2 or count > total:
        raise ValueError("Systematic probe size must be between 2 and the full size")
    return np.floor(np.linspace(0, total - 1, count)).astype(int)


def load_probe_candidates(
    protocol: dict[str, Any],
    repo_root: Path,
) -> tuple[pd.DataFrame, list[str]]:
    scores = protocol["input_bundle"]["retrieval_scores"]
    audit = protocol["input_bundle"]["candidate_audit"]
    probe = protocol["performance_probe"]
    audit_frame = pd.read_parquet(
        _repo_path(repo_root, audit["path"]), columns=["query_id"]
    )
    if (
        audit_frame["query_id"].duplicated().any()
        or len(audit_frame) != scores["queries"]
    ):
        raise RuntimeError("Candidate-audit query order is invalid")
    query_ids = (
        audit_frame.iloc[probe["query_indices"]]["query_id"].astype(str).tolist()
    )
    frame = pd.read_parquet(
        _repo_path(repo_root, scores["path"]),
        columns=PROBE_SCORE_COLUMNS,
        filters=[("query_id", "in", query_ids)],
    )
    counts = frame.groupby("query_id", sort=False).size().to_dict()
    if any(counts.get(query_id) != scores["pages_per_query"] for query_id in query_ids):
        raise RuntimeError("Probe queries do not contain the full frozen page set")
    return frame, query_ids


def build_probe_case(
    candidates: pd.DataFrame,
    query_ids: list[str],
    page_limit: int,
) -> pd.DataFrame:
    if "relevance" in candidates.columns:
        raise ValueError(
            "Performance probe candidates must not contain actual relevance"
        )
    parts = []
    for query_id in query_ids:
        group = candidates.loc[
            candidates["query_id"].astype(str).eq(query_id)
        ].sort_values("page_id", kind="stable")
        selected = group.iloc[_systematic_positions(len(group), page_limit)].copy()
        selected["stage1_score"] = 0.0
        selected["branch_ranks"] = "synthetic_probe_placeholder"
        selected["relevance"] = 0.0
        selected.iloc[0, selected.columns.get_loc("relevance")] = 1.0
        selected.iloc[len(selected) // 2, selected.columns.get_loc("relevance")] = 1.0
        parts.append(selected)
    return pd.concat(parts, ignore_index=True)


def _probe_case_worker(
    frame: pd.DataFrame,
    bootstrap_resamples: int,
    result_queue: Any,
) -> None:
    try:
        started = time.perf_counter()
        run_qpaf_oracle(frame, grids=("w7",), n_bootstrap=bootstrap_resamples)
        result_queue.put({"elapsed_seconds": time.perf_counter() - started})
    except (
        BaseException
    ) as error:  # pragma: no cover - exercised through parent failure
        result_queue.put({"error": f"{type(error).__name__}: {error}"})


def complete_process_with_timeout(process: Any, timeout_seconds: float) -> None:
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        raise TimeoutError(f"Performance-probe case exceeded {timeout_seconds} seconds")
    if process.exitcode != 0:
        raise RuntimeError(
            f"Performance-probe worker exited with code {process.exitcode}"
        )


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def validate_probe_run_manifest(manifest: dict[str, Any]) -> None:
    expected_boundaries = {
        "actual_relevance_loaded": False,
        "scientific_oracle_analysis_executed": False,
        "oracle_results_persisted": False,
        "full_w7_oracle_executed": False,
        "modal_or_gpu_used": False,
        "p1_03_authorized": False,
        "learned_qpaf_executed": False,
        "frozen_p1_02_status": "BLOCKED",
    }
    expected_top_level = {
        "schema_version",
        "status",
        "classification",
        "protocol_id",
        "protocol_sha256",
        "source_commit",
        "attempt_marker_sha256",
        "completed_at",
        "environment",
        "preflight",
        "probe_contract",
        "timings",
        "boundaries",
    }
    if set(manifest) != expected_top_level:
        unexpected = sorted(set(manifest) - expected_top_level)
        missing = sorted(expected_top_level - set(manifest))
        raise ValueError(
            f"Run manifest fields drifted; missing={missing}, unexpected={unexpected}"
        )
    if manifest.get("schema_version") != 1 or manifest.get("status") != "PASS":
        raise ValueError("Run manifest identity/status is invalid")
    if manifest.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("Run manifest protocol identity is invalid")
    if (
        not isinstance(manifest.get("protocol_sha256"), str)
        or len(manifest["protocol_sha256"]) != 64
    ):
        raise ValueError("Run manifest protocol SHA-256 is invalid")
    if (
        not isinstance(manifest.get("source_commit"), str)
        or len(manifest["source_commit"]) != 40
    ):
        raise ValueError("Run manifest source commit is invalid")
    if (
        not isinstance(manifest.get("attempt_marker_sha256"), str)
        or len(manifest["attempt_marker_sha256"]) != 64
    ):
        raise ValueError("Run manifest attempt-marker SHA-256 is invalid")
    if not isinstance(manifest.get("completed_at"), str):
        raise ValueError("Run manifest completion time is invalid")
    if manifest.get("classification") != "engineering_performance_probe_not_result":
        raise ValueError("Run manifest classification is not a non-result probe")
    if manifest.get("boundaries") != expected_boundaries:
        raise ValueError("Run manifest scientific boundaries are incomplete")
    environment = manifest.get("environment")
    if not isinstance(environment, dict) or environment.get("device") != "cpu":
        raise ValueError("Run manifest environment is not CPU-only")
    if environment.get("thread_limits") != {name: "1" for name in CPU_THREAD_ENV}:
        raise ValueError("Run manifest CPU thread limits are invalid")
    preflight = manifest.get("preflight")
    if not isinstance(preflight, dict) or any(
        preflight.get(field) is not False
        for field in [
            "actual_relevance_loaded",
            "oracle_executed",
            "scientific_result_produced",
        ]
    ):
        raise ValueError("Run manifest preflight boundaries are invalid")
    expected_probe_contract = {
        "query_indices": [0, 570, 1141],
        "page_limits": [128, 256, 512],
        "bootstrap_resamples": 100,
        "repetitions": 1,
        "max_case_candidate_rows": 1536,
        "max_concurrent_cases": 1,
        "cpu_thread_limit": 1,
        "per_case_timeout_seconds": 120,
        "ladder_timeout_seconds": 300,
        "actual_relevance_loaded": False,
        "synthetic_relevance_rule": "first_and_middle_sampled_page_binary_relevant",
    }
    if manifest.get("probe_contract") != expected_probe_contract:
        raise ValueError("Run manifest probe contract drifted")
    timings = manifest.get("timings")
    if not isinstance(timings, list) or len(timings) != 3:
        raise ValueError("Run manifest must contain exactly three probe timings")
    for timing, page_limit in zip(timings, [128, 256, 512]):
        if set(timing) != {
            "queries",
            "pages_per_query",
            "candidate_rows",
            "elapsed_seconds",
        }:
            raise ValueError("Run manifest timing fields drifted")
        if timing.get("queries") != 3 or timing.get("pages_per_query") != page_limit:
            raise ValueError("Run manifest timing dimensions drifted")
        if timing.get("candidate_rows") != 3 * page_limit:
            raise ValueError("Run manifest timing row count drifted")
        if (
            not isinstance(timing.get("elapsed_seconds"), (int, float))
            or timing["elapsed_seconds"] < 0
        ):
            raise ValueError("Run manifest timing value is invalid")

    def collect_keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return {str(key).lower() for key in value} | set().union(
                *(collect_keys(item) for item in value.values())
            )
        if isinstance(value, list):
            return set().union(*(collect_keys(item) for item in value))
        return set()

    forbidden_result_keys = {
        "accepted_updates",
        "changed_candidates",
        "changed_pages",
        "global_metrics",
        "mrr10",
        "ndcg10",
        "profile_counts",
        "qpaf_metrics",
        "qarf_metrics",
        "recall1",
        "recall3",
        "relevant_count",
    }
    keys = collect_keys(manifest)
    present = (keys & forbidden_result_keys) | {
        key
        for key in keys
        if any(metric in key for metric in ["ndcg", "recall", "mrr"])
    }
    if present:
        raise ValueError(
            "Run manifest contains forbidden result fields: "
            + ", ".join(sorted(present))
        )


def validate_probe_attempt_marker(marker: dict[str, Any]) -> None:
    expected_boundaries = {
        "authorization_attempt_consumed": True,
        "automatic_retry_allowed": False,
        "actual_relevance_loaded": False,
        "scientific_oracle_analysis_executed": False,
        "oracle_results_persisted": False,
        "full_w7_oracle_executed": False,
        "modal_or_gpu_used": False,
        "p1_03_authorized": False,
        "learned_qpaf_executed": False,
        "frozen_p1_02_status": "BLOCKED",
    }
    expected_fields = {
        "schema_version",
        "status",
        "classification",
        "protocol_id",
        "protocol_sha256",
        "approval_commit",
        "started_at",
        "authorization",
        "boundaries",
    }
    if set(marker) != expected_fields:
        raise ValueError("Performance-probe attempt-marker fields drifted")
    if marker.get("schema_version") != 1 or marker.get("status") != "STARTED":
        raise ValueError("Performance-probe attempt-marker identity/status is invalid")
    if marker.get("classification") != "engineering_probe_attempt_not_result":
        raise ValueError("Performance-probe attempt-marker classification is invalid")
    if marker.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("Performance-probe attempt-marker protocol is invalid")
    if (
        not isinstance(marker.get("protocol_sha256"), str)
        or len(marker["protocol_sha256"]) != 64
    ):
        raise ValueError("Performance-probe attempt-marker protocol hash is invalid")
    if (
        not isinstance(marker.get("approval_commit"), str)
        or len(marker["approval_commit"]) != 40
    ):
        raise ValueError("Performance-probe attempt-marker approval commit is invalid")
    if not isinstance(marker.get("started_at"), str):
        raise ValueError("Performance-probe attempt-marker start time is invalid")
    if marker.get("authorization") != {
        "authorized_invocations": 1,
        "attempt_number": 1,
        "remaining_authorized_invocations_after_start": 0,
    }:
        raise ValueError("Performance-probe attempt-marker authorization drifted")
    if marker.get("boundaries") != expected_boundaries:
        raise ValueError("Performance-probe attempt-marker boundaries drifted")


def _write_json_atomic_create_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_immutable_run_manifest(path: Path, manifest: dict[str, Any]) -> None:
    validate_probe_run_manifest(manifest)
    _write_json_atomic_create_once(path, manifest)


def write_immutable_attempt_marker(path: Path, marker: dict[str, Any]) -> None:
    validate_probe_attempt_marker(marker)
    _write_json_atomic_create_once(path, marker)


def consume_performance_probe_authorization(
    protocol_path: Path,
    protocol: dict[str, Any],
    repo_root: Path,
    approval_commit: str,
) -> Path:
    marker = {
        "schema_version": 1,
        "status": "STARTED",
        "classification": "engineering_probe_attempt_not_result",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": text_sha256(protocol_path),
        "approval_commit": approval_commit,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "authorization": {
            "authorized_invocations": 1,
            "attempt_number": 1,
            "remaining_authorized_invocations_after_start": 0,
        },
        "boundaries": {
            "authorization_attempt_consumed": True,
            "automatic_retry_allowed": False,
            "actual_relevance_loaded": False,
            "scientific_oracle_analysis_executed": False,
            "oracle_results_persisted": False,
            "full_w7_oracle_executed": False,
            "modal_or_gpu_used": False,
            "p1_03_authorized": False,
            "learned_qpaf_executed": False,
            "frozen_p1_02_status": "BLOCKED",
        },
    }
    path = _repo_path(repo_root, protocol["performance_probe"]["attempt_marker_path"])
    write_immutable_attempt_marker(path, marker)
    return path


def run_bounded_performance_probe(protocol_path: Path) -> Path:
    protocol_path = protocol_path.resolve()
    repo_root = protocol_path.parents[1]
    protocol = load_protocol(protocol_path)
    source_commit = require_performance_probe_execution_approval(protocol, repo_root)
    attempt_marker = consume_performance_probe_authorization(
        protocol_path,
        protocol,
        repo_root,
        source_commit,
    )
    preflight = protocol_bound_preflight(
        protocol_path,
        repo_root,
        allow_consumed_attempt=True,
    )
    probe = protocol["performance_probe"]
    candidates, query_ids = load_probe_candidates(protocol, repo_root)

    context = mp.get_context("spawn")
    ladder_started = time.perf_counter()
    timings = []
    for page_limit in probe["page_limits"]:
        elapsed = time.perf_counter() - ladder_started
        remaining = probe["ladder_timeout_seconds"] - elapsed
        if remaining <= 0:
            raise TimeoutError("Performance-probe ladder exceeded its 300-second limit")
        case = build_probe_case(candidates, query_ids, page_limit)
        if len(case) > probe["max_case_candidate_rows"]:
            raise RuntimeError("Performance-probe case exceeds its row cap")
        result_queue = context.Queue()
        process = context.Process(
            target=_probe_case_worker,
            args=(case, probe["bootstrap_resamples"], result_queue),
        )
        complete_process_with_timeout(
            process,
            min(float(probe["per_case_timeout_seconds"]), remaining),
        )
        try:
            result = result_queue.get(timeout=5)
        except queue.Empty as error:
            raise RuntimeError("Performance-probe worker returned no timing") from error
        finally:
            result_queue.close()
        if "error" in result:
            raise RuntimeError(f"Performance-probe worker failed: {result['error']}")
        if time.perf_counter() - ladder_started > probe["ladder_timeout_seconds"]:
            raise TimeoutError("Performance-probe ladder exceeded its 300-second limit")
        timings.append(
            {
                "queries": len(query_ids),
                "pages_per_query": page_limit,
                "candidate_rows": len(query_ids) * page_limit,
                "elapsed_seconds": result["elapsed_seconds"],
            }
        )

    completed = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": 1,
        "status": "PASS",
        "classification": "engineering_performance_probe_not_result",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": preflight["protocol_sha256"],
        "source_commit": source_commit,
        "attempt_marker_sha256": file_sha256(attempt_marker),
        "completed_at": completed,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "device": "cpu",
            "thread_limits": {name: os.environ[name] for name in CPU_THREAD_ENV},
            "packages": {
                name: _package_version(name)
                for name in ["numpy", "pandas", "pyarrow", "PyYAML"]
            },
        },
        "preflight": preflight,
        "probe_contract": {
            "query_indices": probe["query_indices"],
            "page_limits": probe["page_limits"],
            "bootstrap_resamples": probe["bootstrap_resamples"],
            "repetitions": probe["repetitions"],
            "max_case_candidate_rows": probe["max_case_candidate_rows"],
            "max_concurrent_cases": probe["max_concurrent_cases"],
            "cpu_thread_limit": probe["cpu_thread_limit"],
            "per_case_timeout_seconds": probe["per_case_timeout_seconds"],
            "ladder_timeout_seconds": probe["ladder_timeout_seconds"],
            "actual_relevance_loaded": probe["actual_relevance_loaded"],
            "synthetic_relevance_rule": probe["synthetic_relevance_rule"],
        },
        "timings": timings,
        "boundaries": {
            "actual_relevance_loaded": False,
            "scientific_oracle_analysis_executed": False,
            "oracle_results_persisted": False,
            "full_w7_oracle_executed": False,
            "modal_or_gpu_used": False,
            "p1_03_authorized": False,
            "learned_qpaf_executed": False,
            "frozen_p1_02_status": "BLOCKED",
        },
    }
    output = _repo_path(repo_root, probe["output_manifest_path"])
    write_immutable_run_manifest(output, manifest)
    return output


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="p1-02r-o1-safeguards")
    commands = root.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser(
        "preflight", help="Validate the frozen bundle without W7"
    )
    preflight.add_argument("--protocol", type=Path, required=True)
    probe = commands.add_parser(
        "performance-probe",
        help="Run the separately approved CPU-only non-result timing ladder",
    )
    probe.add_argument("--protocol", type=Path, required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "preflight":
        print(
            json.dumps(
                protocol_bound_preflight(args.protocol), indent=2, sort_keys=True
            )
        )
    else:
        print(run_bounded_performance_probe(args.protocol))


if __name__ == "__main__":
    main()
