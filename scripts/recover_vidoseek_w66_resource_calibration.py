"""Guard and run one fresh optimized recovery of the W66 resource calibration."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psutil
import pyarrow.parquet as pq

from oracle_study.metrics import RankingMetrics
from oracle_study.profiles import get_profiles
from oracle_study.qpaf import _query_oracle

if __package__:
    from . import calibrate_vidoseek_w66_resources as base
    from .qpaf_candidate_oracle_optimized import candidate_oracle_exact_fast
    from . import run_vidoseek_exploratory24_w66 as w66
else:
    import calibrate_vidoseek_w66_resources as base
    import run_vidoseek_exploratory24_w66 as w66
    from qpaf_candidate_oracle_optimized import candidate_oracle_exact_fast


PROTOCOL_ID = "vidoseek_w66_resource_calibration_recovery_v1"
CLASSIFICATION = "synthetic_w66_engineering_recovery_not_retrieval_result"
CONFIG_PATH = "configs/vidoseek_w66_resource_calibration_recovery_v1.json"
PROPOSAL_PATH = "docs/05_oracle_experiments/w66/vidoseek_w66_resource_calibration_recovery_proposal.json"
EXECUTION_REVIEW_PATH = (
    "docs/05_oracle_experiments/w66/QPAF_W66_RESOURCE_CALIBRATION_RECOVERY_EXECUTION_REVIEW.md"
)
INTERRUPTION_REVIEW_PATH = (
    "artifacts/vidoseek_w66_resource_calibration_interruption_review/review.json"
)
BENCHMARK_PATH = (
    "artifacts/vidoseek_w66_resource_calibration_recovery_preparation/"
    "bounded_equivalence_benchmark.json"
)
SCRIPT_PATH = "scripts/recover_vidoseek_w66_resource_calibration.py"
OPTIMIZED_PATH = "scripts/qpaf_candidate_oracle_optimized.py"
TEST_PATH = "tests/test_vidoseek_w66_resource_calibration_recovery.py"
OUTPUT_PATH = "runs/vidoseek_w66_resource_calibration_recovery_v1"
GRID_NAME = base.GRID_NAME
PROFILE_COUNT = base.PROFILE_COUNT
PROFILES_SHA256 = base.PROFILES_SHA256
QUERY_LIST_SHA256 = base.QUERY_LIST_SHA256
CALIBRATION_AUDIT_INDEX = base.CALIBRATION_AUDIT_INDEX
CALIBRATION_QUERY_ID = base.CALIBRATION_QUERY_ID
PAGES_PER_QUERY = base.PAGES_PER_QUERY
SYNTHETIC_RELEVANT_INDEX = base.SYNTHETIC_RELEVANT_INDEX
LOAD_QUERY_COUNT = base.LOAD_QUERY_COUNT
LOAD_PAIR_COUNT = base.LOAD_PAIR_COUNT
LOAD_COLUMNS = base.LOAD_COLUMNS
BOOTSTRAP_SAMPLE_SIZE = base.BOOTSTRAP_SAMPLE_SIZE
BOOTSTRAP_RESAMPLES = base.BOOTSTRAP_RESAMPLES
SEED = base.SEED
PROPOSED_TIMEOUT_SECONDS = 3_600
MAX_TELEMETRY_GAP_SECONDS = 5.0
PROCESS_TREE_PRIVATE_BYTES_LIMIT = base.PROCESS_TREE_PRIVATE_BYTES_LIMIT
PRESTART_FREE_PHYSICAL_BYTES_MIN = base.PRESTART_FREE_PHYSICAL_BYTES_MIN
ABORT_FREE_PHYSICAL_BYTES_BELOW = base.ABORT_FREE_PHYSICAL_BYTES_BELOW
PRESTART_DISK_FREE_BYTES_MIN = base.PRESTART_DISK_FREE_BYTES_MIN
OUTPUT_BYTE_LIMIT = base.OUTPUT_BYTE_LIMIT
SAMPLE_INTERVAL_SECONDS = base.SAMPLE_INTERVAL_SECONDS
PACKAGES = base.PACKAGES
PREPARATION_STATUS = "PREPARED_RECOVERY_EXECUTION_CLOSED"
APPROVED_STATUS = "APPROVED_FOR_ONE_RECOVERY_INVOCATION"
GIT_RULE = base.GIT_RULE


def read_json(path: Path) -> dict[str, Any]:
    return base.read_json(path)


def value_sha256(value: Any) -> str:
    return base.value_sha256(value)


def file_sha256(path: Path) -> str:
    return base.file_sha256(path)


def git_head(root: Path) -> str:
    return base.git_head(root)


def source_paths(root: Path) -> list[str]:
    return sorted(
        [
            path.relative_to(root).as_posix()
            for path in (root / "src/oracle_study").glob("*.py")
        ]
        + [
            SCRIPT_PATH,
            OPTIMIZED_PATH,
            base.SCRIPT_PATH,
            base.W66_SCRIPT_PATH,
            PROPOSAL_PATH,
            EXECUTION_REVIEW_PATH,
            INTERRUPTION_REVIEW_PATH,
            BENCHMARK_PATH,
            base.RESOURCE_REVIEW_JSON,
            base.RESOURCE_REVIEW_MD,
            base.PARENT_W7_PROPOSAL_PATH,
            base.PARENT_W7_REVIEW_PATH,
            base.BASE_PROTOCOL_PATH,
            "configs/vidoseek_p1_02r.yaml",
        ]
    )


def _approval_state(config: dict[str, Any]) -> str:
    approval = config["authorization"]
    closed = (
        config["resource_budget_status"] == PREPARATION_STATUS
        and config["approved_wall_timeout_seconds"] == 0
        and config["invocations"] == 0
        and approval
        == {
            "protocol_adopted": False,
            "resource_budget_approved": False,
            "execution_authorized": False,
            "approved_by": None,
            "execution_actor": None,
            "approval_text": None,
            "approved_at": None,
        }
    )
    approved = (
        config["resource_budget_status"] == APPROVED_STATUS
        and config["approved_wall_timeout_seconds"] == PROPOSED_TIMEOUT_SECONDS
        and config["invocations"] == 1
        and approval.get("protocol_adopted") is True
        and approval.get("resource_budget_approved") is True
        and approval.get("execution_authorized") is True
        and approval.get("approved_by") == "user"
        and approval.get("execution_actor") in {"human", "codex"}
        and bool(approval.get("approval_text"))
        and bool(approval.get("approved_at"))
    )
    if closed == approved:
        raise ValueError("Recovery authorization/resource state drift")
    return "approved" if approved else "closed"


def require_git_provenance(root: Path, config: dict[str, Any], state: str) -> str:
    if state == "closed":
        record = config["preparation_git"]
        if (
            set(record)
            != {
                "prepared_parent_commit",
                "preparation_commit_rule",
                "preparation_commit_changed_paths",
            }
            or record["preparation_commit_rule"] != GIT_RULE
        ):
            raise ValueError("Recovery preparation Git fields drift")
        return base.pilot.safeguards.require_exact_git_execution_checkout(
            root,
            approved_parent_commit=record["prepared_parent_commit"],
            approval_commit_changed_paths=record["preparation_commit_changed_paths"],
            execution_label="W66 calibration-recovery preparation",
        )

    record = config["approval_git"]
    if (
        set(record)
        != {
            "approved_parent_commit",
            "approval_commit_rule",
            "approval_commit_changed_paths",
        }
        or record["approval_commit_rule"] != GIT_RULE
        or not isinstance(record["approved_parent_commit"], str)
    ):
        raise ValueError("Recovery approval Git fields drift")
    return base.pilot.safeguards.require_exact_git_execution_checkout(
        root,
        approved_parent_commit=record["approved_parent_commit"],
        approval_commit_changed_paths=record["approval_commit_changed_paths"],
        execution_label="W66 calibration-recovery approval",
    )


def validate_config(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "protocol_id": PROTOCOL_ID,
        "classification": CLASSIFICATION,
        "proposal_path": PROPOSAL_PATH,
        "execution_review_path": EXECUTION_REVIEW_PATH,
        "interruption_review_path": INTERRUPTION_REVIEW_PATH,
        "benchmark_path": BENCHMARK_PATH,
        "base_calibration_protocol_id": base.PROTOCOL_ID,
        "base_protocol_path": base.BASE_PROTOCOL_PATH,
        "parent_w7_proposal_path": base.PARENT_W7_PROPOSAL_PATH,
        "parent_w7_result_review_path": base.PARENT_W7_REVIEW_PATH,
        "w66_runner_path": base.W66_SCRIPT_PATH,
        "base_calibration_runner_path": base.SCRIPT_PATH,
        "optimized_candidate_oracle_path": OPTIMIZED_PATH,
        "output_path": OUTPUT_PATH,
        "grid": GRID_NAME,
        "profile_count": PROFILE_COUNT,
        "profiles_canonical_sha256": PROFILES_SHA256,
        "query_list_sha256": QUERY_LIST_SHA256,
        "calibration_audit_index": CALIBRATION_AUDIT_INDEX,
        "calibration_query_id": CALIBRATION_QUERY_ID,
        "pages_per_query": PAGES_PER_QUERY,
        "synthetic_relevant_page_sorted_index": SYNTHETIC_RELEVANT_INDEX,
        "load_query_count": LOAD_QUERY_COUNT,
        "load_pair_count": LOAD_PAIR_COUNT,
        "load_columns": list(LOAD_COLUMNS),
        "bootstrap_sample_size": BOOTSTRAP_SAMPLE_SIZE,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "seed": SEED,
        "proposed_wall_timeout_seconds": PROPOSED_TIMEOUT_SECONDS,
        "workers": 1,
        "threads_per_library": 1,
        "arrow_cpu_threads": 1,
        "arrow_io_threads": 1,
        "automatic_retries": 0,
        "process_tree_private_bytes_limit": PROCESS_TREE_PRIVATE_BYTES_LIMIT,
        "prestart_free_physical_bytes_min": PRESTART_FREE_PHYSICAL_BYTES_MIN,
        "abort_free_physical_bytes_below": ABORT_FREE_PHYSICAL_BYTES_BELOW,
        "prestart_disk_free_bytes_min": PRESTART_DISK_FREE_BYTES_MIN,
        "output_byte_limit": OUTPUT_BYTE_LIMIT,
        "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
        "maximum_telemetry_gap_seconds": MAX_TELEMETRY_GAP_SECONDS,
        "previous_checkpoint_reuse_allowed": False,
        "actual_relevance_column_allowed": False,
        "checkpoint_reuse_into_scientific_run_allowed": False,
        "formal_p1_03_allowed": False,
        "training_allowed": False,
        "modal_gpu_allowed": False,
    }
    variable = {
        "resource_budget_status",
        "approved_wall_timeout_seconds",
        "invocations",
        "preparation_git",
        "approval_git",
        "source_sha256",
        "environment",
        "authorization",
    }
    if set(config) != set(expected) | variable:
        raise ValueError("Recovery config fields drift")
    for key, expected_value in expected.items():
        if config.get(key) != expected_value or type(config.get(key)) is not type(
            expected_value
        ):
            raise ValueError(f"Recovery scope drift: {key}")
    if set(config["authorization"]) != {
        "protocol_adopted",
        "resource_budget_approved",
        "execution_authorized",
        "approved_by",
        "execution_actor",
        "approval_text",
        "approved_at",
    }:
        raise ValueError("Recovery authorization fields drift")
    state = _approval_state(config)
    live_commit = require_git_provenance(root, config, state)

    if state == "closed" and config["approval_git"] != {
        "approved_parent_commit": None,
        "approval_commit_rule": GIT_RULE,
        "approval_commit_changed_paths": [
            CONFIG_PATH,
            EXECUTION_REVIEW_PATH,
            TEST_PATH,
        ],
    }:
        raise ValueError("Closed recovery approval Git state drift")
    if sorted(config["source_sha256"]) != source_paths(root):
        raise ValueError("Recovery source inventory drift")
    for relative, expected_hash in config["source_sha256"].items():
        if file_sha256(root / relative) != expected_hash:
            raise ValueError(f"Recovery source hash drift: {relative}")
    environment = {
        "python": platform.python_version(),
        "packages": {name: version(name) for name in PACKAGES},
    }
    if config["environment"] != environment:
        raise ValueError("Recovery Python/package environment drift")

    proposal = read_json(root / PROPOSAL_PATH)
    if (
        proposal.get("protocol_id") != PROTOCOL_ID
        or proposal.get("status") != "PREPARED_EXECUTION_CLOSED"
        or proposal.get("execution_authorized") is not False
        or proposal["selection"]["audit_index"] != CALIBRATION_AUDIT_INDEX
        or proposal["selection"]["query_id"] != CALIBRATION_QUERY_ID
        or proposal["resources"]["proposed_wall_timeout_seconds"]
        != PROPOSED_TIMEOUT_SECONDS
        or proposal["resources"]["maximum_telemetry_gap_seconds"]
        != MAX_TELEMETRY_GAP_SECONDS
    ):
        raise ValueError("Recovery proposal drift")
    interruption = read_json(root / INTERRUPTION_REVIEW_PATH)
    if (
        interruption.get("status") != "FAIL_CONSUMED_TELEMETRY_GAP_NO_RESULT"
        or interruption.get("protocol_id") != base.PROTOCOL_ID
        or interruption["attempt"]["remaining_authorized_invocations"] != 0
        or interruption["boundaries"]["scientific_result_produced"] is not False
    ):
        raise ValueError("Recovery interruption evidence drift")
    benchmark = read_json(root / BENCHMARK_PATH)
    if (
        benchmark.get("classification")
        != "bounded_synthetic_engineering_benchmark_not_w66_result"
        or benchmark["result"]["exact_assignments_scores_metrics_changes"] is not True
        or benchmark["fixture"]["size"] != 512
        or benchmark["fixture"]["seed"] != 20260909
        or benchmark["fixture"]["profiles"] != PROFILE_COUNT
        or benchmark["conditional_timeout_reasoning"]["proposed_cost_cap_seconds"]
        != PROPOSED_TIMEOUT_SECONDS
        or benchmark["conditional_timeout_reasoning"]["is_runtime_guarantee"]
        is not False
    ):
        raise ValueError("Recovery equivalence benchmark drift")
    base.selected_queries(root)
    profiles = get_profiles(GRID_NAME)
    if (
        profiles.shape != (PROFILE_COUNT, 3)
        or value_sha256(profiles.tolist()) != PROFILES_SHA256
    ):
        raise ValueError("W66 profile grid drift")
    return {
        "state": state,
        "live_commit": live_commit,
        "proposal": proposal,
        "interruption": interruption,
        "benchmark": benchmark,
    }


def require_approval(config: dict[str, Any], actor: str) -> None:
    try:
        state = _approval_state(config)
    except (KeyError, TypeError, ValueError):
        state = "closed"
    approval = config.get("authorization", {})
    if state != "approved" or approval.get("execution_actor") != actor:
        raise PermissionError(
            "Separate synthetic W66 calibration-recovery approval pending; "
            "no attempt consumed"
        )
    if actor not in {"human", "codex"}:
        raise PermissionError("Invalid synthetic W66 calibration-recovery actor")
    if any(
        os.environ.get(name) != "1" for name in base.pilot.safeguards.CPU_THREAD_ENV
    ):
        raise RuntimeError("W66 recovery requires one numeric-library thread")


def preflight(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    validated = validate_config(root, config)
    evidence = base.pilot.safeguards.protocol_bound_preflight(
        root / base.BASE_PROTOCOL_PATH,
        repo_root=root,
        allow_recorded_probe_evidence=True,
    )
    parent = read_json(root / base.PARENT_W7_PROPOSAL_PATH)
    score_path = root / parent["input"]["retrieval_scores_path"]
    schema_names = pq.ParquetFile(score_path).schema_arrow.names
    if (
        evidence["retrieval_score_sha256"]
        != parent["input"]["retrieval_scores_byte_sha256"]
        or any(column not in schema_names for column in LOAD_COLUMNS)
        or "relevance" in LOAD_COLUMNS
    ):
        raise ValueError("Recovery score input/schema drift")
    output = root / OUTPUT_PATH
    snapshot = base.host_snapshot(root, output)
    return {
        "status": "PASS",
        "classification": "read_only_synthetic_recovery_preflight_not_result",
        "base_preflight": evidence,
        "source_commit": validated["live_commit"],
        "prior_attempt_status": validated["interruption"]["status"],
        "prior_attempt_remaining_authorized_invocations": 0,
        "previous_checkpoint_reuse_allowed": False,
        "query_list_sha256": QUERY_LIST_SHA256,
        "calibration_audit_index": CALIBRATION_AUDIT_INDEX,
        "calibration_query_id": CALIBRATION_QUERY_ID,
        "load_query_count": LOAD_QUERY_COUNT,
        "load_pair_count": LOAD_PAIR_COUNT,
        "load_columns": list(LOAD_COLUMNS),
        "actual_relevance_loaded": False,
        "synthetic_relevance_created": False,
        "w66_oracle_executed": False,
        "scientific_result_produced": False,
        "resource_budget_status": config["resource_budget_status"],
        "approved_wall_timeout_seconds": config["approved_wall_timeout_seconds"],
        "authorized_invocations": config["invocations"],
        "execution_authorized": config["authorization"]["execution_authorized"],
        "maximum_telemetry_gap_seconds": MAX_TELEMETRY_GAP_SECONDS,
        "host_snapshot": snapshot,
        "admission_thresholds_currently_met": (
            not snapshot["output_exists"]
            and snapshot["free_physical_bytes"]
            >= config["prestart_free_physical_bytes_min"]
            and snapshot["disk_free_bytes"] >= config["prestart_disk_free_bytes_min"]
        ),
        "attempt_exists": output.exists(),
    }


def build_identity(
    config: dict[str, Any], evidence: dict[str, Any], source_commit: str
) -> dict[str, Any]:
    return {
        "schema_version": base.pilot.sharded.CHECKPOINT_SCHEMA_VERSION,
        "classification": CLASSIFICATION,
        "protocol_id": PROTOCOL_ID,
        "config_sha256": value_sha256(config),
        "source_commit": source_commit,
        "retrieval_score_sha256": evidence["base_preflight"]["retrieval_score_sha256"],
        "retrieval_score_content_sha256": evidence["base_preflight"][
            "retrieval_score_content_sha256"
        ],
        "parent_query_list_sha256": QUERY_LIST_SHA256,
        "calibration_query": ["Qiuchen-Wang/ViDoSeek", CALIBRATION_QUERY_ID],
        "pages_per_query": PAGES_PER_QUERY,
        "synthetic_relevance_rule": {
            "sort": "ascending_page_id",
            "relevant_page_sorted_index": SYNTHETIC_RELEVANT_INDEX,
            "relevance": 1.0,
            "all_other_relevance": 0.0,
            "actual_relevance_decoded": False,
        },
        "grid": GRID_NAME,
        "profiles": get_profiles(GRID_NAME).tolist(),
        "candidate_oracle": "candidate_oracle_exact_fast",
        "candidate_oracle_source_sha256": config["source_sha256"][OPTIMIZED_PATH],
        "candidate_oracle_equivalence_benchmark_sha256": config["source_sha256"][
            BENCHMARK_PATH
        ],
        "previous_checkpoint_reuse_allowed": False,
        "channel_order": ["bm25_score", "dense_score", "visual_score"],
        "profile_selection_tie_break": ["ndcg10", "recall3", "mrr10"],
        "ranking_tie_break": "ascending_page_id",
        "qpaf_max_sweeps": 2,
        "strict_improvement_tolerance": 1e-12,
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "checkpoint_reuse_into_scientific_run_allowed": False,
    }


def query_result_row_optimized(
    frame: pd.DataFrame,
    profiles: np.ndarray,
    global_profile_index: int,
    global_query_metrics: RankingMetrics,
) -> dict[str, Any]:
    item = base.pilot.sharded._query_item(frame)
    score_matrix = item["score_matrix"]
    relevance = item["relevance"]
    page_ids = item["page_ids"]
    query_profile, query_scores, query_metrics = _query_oracle(
        score_matrix, relevance, page_ids, profiles
    )
    assignments, _, candidate_metrics, changes = candidate_oracle_exact_fast(
        score_matrix,
        relevance,
        page_ids,
        profiles,
        query_profile,
        query_scores,
        query_metrics,
    )
    changed_mask = assignments != query_profile
    return {
        "dataset": item["dataset"],
        "query_id": item["query_id"],
        "source": item["source"],
        "relevant_count": int(np.count_nonzero(relevance > 0)),
        "grid": GRID_NAME,
        "global_profile": profiles[global_profile_index].astype(float).tolist(),
        "global_metrics": asdict(global_query_metrics),
        "qarf_profile": profiles[query_profile].astype(float).tolist(),
        "qarf_metrics": asdict(query_metrics),
        "qpaf_metrics": asdict(candidate_metrics),
        "delta_qarf_vs_global": query_metrics.ndcg10 - global_query_metrics.ndcg10,
        "delta_qpaf_vs_qarf": candidate_metrics.ndcg10 - query_metrics.ndcg10,
        "delta_qpaf_vs_global": (
            candidate_metrics.ndcg10 - global_query_metrics.ndcg10
        ),
        "delta_ndcg10": candidate_metrics.ndcg10 - query_metrics.ndcg10,
        "changed_candidates": int(np.count_nonzero(changed_mask)),
        "accepted_updates": int(changes),
        "profile_counts": np.bincount(assignments, minlength=len(profiles))
        .astype(int)
        .tolist(),
        "changed_pages": {
            str(page_ids[index]): profiles[assignments[index]].astype(float).tolist()
            for index in np.flatnonzero(changed_mask)
        },
    }


def query_checkpoint(
    path: Path,
    *,
    run_identity_sha256: str,
    query_index: int,
    query_key: tuple[str, str],
    frame: pd.DataFrame,
    profiles: np.ndarray,
    global_profile_index: int,
    global_query_metrics: RankingMetrics,
    global_selection_sha256: str,
) -> tuple[dict[str, Any], str, bool]:
    input_sha256 = base.pilot.sharded.dataframe_sha256(
        frame, sort_by=["dataset", "query_id", "page_id"]
    )
    if path.exists():
        payload, content_sha256 = base.pilot.sharded._read_checkpoint(
            path,
            kind="w66_optimized_recovery_query_oracle_result",
            run_identity_sha256=run_identity_sha256,
        )
        reused = True
    else:
        payload = {
            "query_index": query_index,
            "dataset": query_key[0],
            "query_id": query_key[1],
            "input_query_sha256": input_sha256,
            "global_selection_sha256": global_selection_sha256,
            "row": query_result_row_optimized(
                frame,
                profiles,
                global_profile_index,
                global_query_metrics,
            ),
        }
        content_sha256 = base.pilot.sharded._write_checkpoint(
            path,
            kind="w66_optimized_recovery_query_oracle_result",
            run_identity_sha256=run_identity_sha256,
            payload=payload,
        )
        reused = False
    expected = {
        "query_index": query_index,
        "dataset": query_key[0],
        "query_id": query_key[1],
        "input_query_sha256": input_sha256,
        "global_selection_sha256": global_selection_sha256,
    }
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise ValueError(f"W66 recovery query checkpoint {field} mismatch")
    row = payload.get("row")
    if not isinstance(row, dict):
        raise ValueError("W66 recovery query checkpoint row is invalid")
    if (
        row.get("dataset") != query_key[0]
        or row.get("query_id") != query_key[1]
        or row.get("grid") != GRID_NAME
    ):
        raise ValueError("W66 recovery query checkpoint identity mismatch")
    for name in ("global_metrics", "qarf_metrics", "qpaf_metrics"):
        base.pilot.sharded._validate_metric_dict(row.get(name), name)
    return row, content_sha256, reused


def run_checkpointed_search(
    frame: pd.DataFrame, identity: dict[str, Any], checkpoint_root: Path
) -> dict[str, Any]:
    profiles = get_profiles(GRID_NAME)
    identity_sha256 = value_sha256(identity)
    key = ("Qiuchen-Wang/ViDoSeek", CALIBRATION_QUERY_ID)

    global_started = time.monotonic()
    global_payload, global_hash, global_reused = w66.global_checkpoint(
        checkpoint_root / "global" / "000000.json",
        run_identity_sha256=identity_sha256,
        query_index=0,
        query_key=key,
        frame=frame,
        profiles=profiles,
    )
    global_seconds = time.monotonic() - global_started
    if global_reused:
        raise ValueError("Recovery Global checkpoint unexpectedly pre-existed")
    global_index, global_metrics = w66.select_global_profile([global_payload], profiles)
    selection = {
        "profile_index": global_index,
        "profile": profiles[global_index].astype(float).tolist(),
        "global_checkpoint_content_sha256": global_hash,
        "scope": "one_synthetic_recovery_query_only",
    }
    selection_hash = base.pilot.sharded._write_checkpoint(
        checkpoint_root / "global_selection.json",
        kind="w66_synthetic_recovery_global_selection",
        run_identity_sha256=identity_sha256,
        payload=selection,
    )

    query_started = time.monotonic()
    row, query_hash, query_reused = query_checkpoint(
        checkpoint_root / "queries" / "000000.json",
        run_identity_sha256=identity_sha256,
        query_index=0,
        query_key=key,
        frame=frame,
        profiles=profiles,
        global_profile_index=global_index,
        global_query_metrics=global_metrics[0],
        global_selection_sha256=selection_hash,
    )
    query_seconds = time.monotonic() - query_started
    if query_reused:
        raise ValueError("Recovery query checkpoint unexpectedly pre-existed")

    replay_started = time.monotonic()
    _, replay_global_hash, replay_global_reused = w66.global_checkpoint(
        checkpoint_root / "global" / "000000.json",
        run_identity_sha256=identity_sha256,
        query_index=0,
        query_key=key,
        frame=frame,
        profiles=profiles,
    )
    replay_selection, replay_selection_hash = base.pilot.sharded._read_checkpoint(
        checkpoint_root / "global_selection.json",
        kind="w66_synthetic_recovery_global_selection",
        run_identity_sha256=identity_sha256,
    )
    replay_row, replay_query_hash, replay_query_reused = query_checkpoint(
        checkpoint_root / "queries" / "000000.json",
        run_identity_sha256=identity_sha256,
        query_index=0,
        query_key=key,
        frame=frame,
        profiles=profiles,
        global_profile_index=global_index,
        global_query_metrics=global_metrics[0],
        global_selection_sha256=selection_hash,
    )
    replay_seconds = time.monotonic() - replay_started
    if (
        not replay_global_reused
        or not replay_query_reused
        or replay_global_hash != global_hash
        or replay_selection != selection
        or replay_selection_hash != selection_hash
        or replay_row != row
        or replay_query_hash != query_hash
    ):
        raise ValueError("Recovery immutable checkpoint replay mismatch")

    return {
        "candidate_oracle_implementation": "candidate_oracle_exact_fast",
        "previous_checkpoint_reused": False,
        "global_profile_evaluation_seconds": global_seconds,
        "query_oracle_seconds": query_seconds,
        "checkpoint_replay_seconds": replay_seconds,
        "accepted_updates": int(row["accepted_updates"]),
        "changed_candidates": int(row["changed_candidates"]),
        "sweeps_exercised": 2 if row["accepted_updates"] else 1,
        "checkpoint_count": 4,
        "checkpoint_replay_verified_without_search": True,
        "synthetic_metrics_reported_as_retrieval_result": False,
    }


def telemetry_gap_seconds(
    previous_observed_at: str,
    observed_at: str,
    previous_monotonic: float,
    observed_monotonic: float,
) -> tuple[float, float]:
    wall_gap = (
        datetime.fromisoformat(observed_at)
        - datetime.fromisoformat(previous_observed_at)
    ).total_seconds()
    monotonic_gap = observed_monotonic - previous_monotonic
    if wall_gap < 0 or monotonic_gap < 0:
        raise RuntimeError("Recovery telemetry clock moved backwards")
    return wall_gap, monotonic_gap


def enforce_telemetry_cadence(
    wall_gap: float, monotonic_gap: float, maximum_gap_seconds: float
) -> None:
    if max(wall_gap, monotonic_gap) > maximum_gap_seconds:
        raise RuntimeError(
            "Recovery telemetry cadence exceeded "
            f"{maximum_gap_seconds:.3f} seconds: wall={wall_gap:.6f}, "
            f"monotonic={monotonic_gap:.6f}"
        )


def worker(
    root: Path,
    config: dict[str, Any],
    output: Path,
    parent_identity: dict[str, Any],
) -> None:
    stage_log = output / "worker_stages.jsonl"
    stop_watchdog = threading.Event()
    watchdog = threading.Thread(
        target=base.watch_parent, args=(parent_identity, stop_watchdog), daemon=True
    )
    watchdog.start()
    try:
        base.record_stage(
            stage_log, "worker", "STARTED", **base.process_identity(os.getpid())
        )
        thread_state = base.set_worker_thread_limits()
        base.pilot.sharded._write_json_atomic_create_once(
            output / "worker_thread_state.json", thread_state
        )
        base.record_stage(stage_log, "thread_limits", "PASS")

        evidence = preflight(root, config)
        base.pilot.sharded._write_json_atomic_create_once(
            output / "preflight.json", evidence
        )
        base.record_stage(stage_log, "preflight", "PASS")

        queries = base.selected_queries(root)
        parent = read_json(root / base.PARENT_W7_PROPOSAL_PATH)
        score_path = root / parent["input"]["retrieval_scores_path"]
        filters = [
            [("dataset", "=", query["dataset"]), ("query_id", "=", query["query_id"])]
            for query in queries
        ]
        started = time.monotonic()
        table = pq.read_table(
            score_path,
            columns=list(LOAD_COLUMNS),
            filters=filters,
            use_threads=False,
            pre_buffer=False,
        )
        scores = table.to_pandas(use_threads=False)
        input_load_seconds = time.monotonic() - started
        if "relevance" in table.column_names:
            raise ValueError("Recovery decoded actual relevance")
        base.record_stage(
            stage_log,
            "input_load",
            "PASS",
            elapsed_seconds=input_load_seconds,
            rows=len(scores),
        )

        frame = base.validate_loaded_subset(scores, queries)
        del scores, table
        identity = build_identity(config, evidence, git_head(root))
        base.pilot.sharded._write_checkpoint(
            output / "checkpoints" / "run_plan.json",
            kind="w66_synthetic_calibration_recovery_run_plan",
            run_identity_sha256=value_sha256(identity),
            payload=identity,
        )
        search = run_checkpointed_search(frame, identity, output / "checkpoints")
        base.record_stage(
            stage_log,
            "w66_optimized_synthetic_search_and_replay",
            "PASS",
            elapsed_seconds=search["query_oracle_seconds"],
            sweeps_exercised=search["sweeps_exercised"],
        )

        bootstrap = base.run_bootstrap_probe()
        base.record_stage(
            stage_log,
            "bootstrap_probe",
            "PASS",
            elapsed_seconds=bootstrap["mean_seconds"] + bootstrap["ratio_seconds"],
        )
        postflight = preflight(root, config)
        if postflight["base_preflight"] != evidence["base_preflight"]:
            raise ValueError("Recovery input identity changed during worker run")
        result = {
            "status": "COMPLETE",
            "classification": CLASSIFICATION,
            "actual_relevance_loaded": False,
            "synthetic_relevance_only": True,
            "scientific_result_produced": False,
            "full_w66_executed": False,
            "input_load_seconds": input_load_seconds,
            "input_rows": LOAD_PAIR_COUNT,
            "search": search,
            "bootstrap_probe": bootstrap,
            "thread_state_sha256": file_sha256(output / "worker_thread_state.json"),
            "postflight_input_identity_match": True,
            "checkpoint_reuse_into_scientific_run_allowed": False,
        }
        base.pilot.sharded._write_json_atomic_create_once(
            output / "calibration_result.json", result
        )
        base.pilot.sharded._write_json_atomic_create_once(
            output / "_WORKER_COMPLETE.json",
            {
                "status": "COMPLETE",
                "calibration_result_sha256": file_sha256(
                    output / "calibration_result.json"
                ),
                "run_identity_sha256": value_sha256(identity),
            },
        )
        base.record_stage(stage_log, "worker", "COMPLETE")
    finally:
        stop_watchdog.set()
        watchdog.join(timeout=2)


def monitor_worker(
    process: mp.Process,
    root: Path,
    output: Path,
    config: dict[str, Any],
    deadline: float,
) -> dict[str, Any]:
    process.start()
    worker_identity = base.process_identity(process.pid)
    base.pilot.sharded._write_json_atomic_create_once(
        output / "process_identity.json",
        {
            "parent": base.process_identity(os.getpid()),
            "worker": worker_identity,
        },
    )
    telemetry_path = output / "resource_telemetry.jsonl"
    peak_private = 0
    minimum_free = psutil.virtual_memory().available
    maximum_output = base.output_bytes(output)
    maximum_wall_gap = 0.0
    maximum_monotonic_gap = 0.0
    previous_observed_at: str | None = None
    previous_monotonic: float | None = None
    samples = 0

    while True:
        observed_monotonic = time.monotonic()
        sample = base.resource_sample(root, output)
        base.enforce_resource_sample(sample, config)
        base.append_jsonl(telemetry_path, sample)
        if previous_observed_at is not None and previous_monotonic is not None:
            wall_gap, monotonic_gap = telemetry_gap_seconds(
                previous_observed_at,
                sample["observed_at"],
                previous_monotonic,
                observed_monotonic,
            )
            maximum_wall_gap = max(maximum_wall_gap, wall_gap)
            maximum_monotonic_gap = max(maximum_monotonic_gap, monotonic_gap)
            enforce_telemetry_cadence(
                wall_gap,
                monotonic_gap,
                config["maximum_telemetry_gap_seconds"],
            )
        previous_observed_at = sample["observed_at"]
        previous_monotonic = observed_monotonic
        peak_private = max(peak_private, sample["process_tree_private_bytes"])
        minimum_free = min(minimum_free, sample["free_physical_bytes"])
        maximum_output = max(maximum_output, sample["output_bytes"])
        samples += 1

        if not process.is_alive():
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Synthetic W66 calibration recovery deadline expired")
        process.join(min(config["sample_interval_seconds"], remaining))

    process.join()
    if process.exitcode != 0:
        raise RuntimeError(
            f"Synthetic W66 calibration recovery worker exit code {process.exitcode}"
        )
    return {
        "samples": samples,
        "peak_process_tree_private_bytes": peak_private,
        "minimum_free_physical_bytes": minimum_free,
        "maximum_observed_output_bytes": maximum_output,
        "maximum_wall_gap_seconds": maximum_wall_gap,
        "maximum_monotonic_gap_seconds": maximum_monotonic_gap,
        "maximum_allowed_telemetry_gap_seconds": config[
            "maximum_telemetry_gap_seconds"
        ],
        "telemetry_cadence_passed": True,
        "worker_identity": worker_identity,
    }


def run(root: Path, config: dict[str, Any], actor: str) -> Path:
    started = time.monotonic()
    require_approval(config, actor)
    validated = validate_config(root, config)
    output = root / OUTPUT_PATH
    admission = base.host_snapshot(root, output)
    base.enforce_admission(admission, config)
    output.mkdir(parents=True, exist_ok=False)
    config_hash = value_sha256(config)
    base.pilot.sharded._write_json_atomic_create_once(
        output / "_ATTEMPTED.json",
        {
            "started_at": base.utc_now(),
            "protocol_id": PROTOCOL_ID,
            "classification": CLASSIFICATION,
            "config_sha256": config_hash,
            "source_commit": validated["live_commit"],
            "execution_actor": actor,
            "consumed_invocations": 1,
            "remaining_authorized_invocations": 0,
        },
    )
    process = None
    sleep_inhibited = False
    try:
        stage_log = output / "parent_stages.jsonl"
        base.record_stage(stage_log, "attempt", "STARTED")
        base.pilot.sharded._write_json_atomic_create_once(
            output / "admission_snapshot.json", admission
        )
        base.pilot.sharded._write_json_atomic_create_once(
            output / "resolved_config.json", config
        )
        snapshot = output / "source_snapshot"
        for relative, expected_hash in config["source_sha256"].items():
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write((root / relative).read_bytes())
            if file_sha256(destination) != expected_hash:
                raise ValueError("Recovery source changed during snapshot")
        with (output / "tracked_changes.patch").open("xb") as handle:
            subprocess.run(
                ["git", "diff", "--binary", "HEAD"],
                cwd=root,
                stdout=handle,
                check=True,
                timeout=30,
            )
        sleep_inhibited = base.set_sleep_inhibition(True)
        if os.name == "nt" and not sleep_inhibited:
            raise RuntimeError("Unable to inhibit system sleep for recovery")
        base.record_stage(stage_log, "admission_and_snapshot", "PASS")

        parent_identity = base.process_identity(os.getpid())
        process = mp.get_context("spawn").Process(
            target=worker,
            args=(root, config, output, parent_identity),
        )
        deadline = started + config["approved_wall_timeout_seconds"]
        supervision = monitor_worker(process, root, output, config, deadline)
        base.record_stage(stage_log, "worker_supervision", "PASS")
        complete = read_json(output / "_WORKER_COMPLETE.json")
        result = read_json(output / "calibration_result.json")
        if (
            complete["status"] != "COMPLETE"
            or complete["calibration_result_sha256"]
            != file_sha256(output / "calibration_result.json")
            or result["status"] != "COMPLETE"
            or result["actual_relevance_loaded"] is not False
            or result["scientific_result_produced"] is not False
            or result["search"]["checkpoint_replay_verified_without_search"] is not True
            or result["search"]["previous_checkpoint_reused"] is not False
            or supervision["telemetry_cadence_passed"] is not True
        ):
            raise ValueError("Synthetic W66 recovery completion evidence mismatch")
        final_sample = base.resource_sample(root, output)
        base.enforce_resource_sample(final_sample, config)
        elapsed = time.monotonic() - started
        if elapsed >= config["approved_wall_timeout_seconds"]:
            raise TimeoutError(
                "Synthetic W66 recovery deadline expired in finalization"
            )
        base.record_stage(stage_log, "finalization", "READY")
        hashes = {
            path.relative_to(output).as_posix(): file_sha256(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        base.pilot.sharded._write_json_atomic_create_once(
            output / "run_manifest.json",
            {
                "status": "COMPLETE",
                "classification": CLASSIFICATION,
                "completed_at": base.utc_now(),
                "elapsed_seconds": elapsed,
                "protocol_id": PROTOCOL_ID,
                "config_sha256": config_hash,
                "source_commit": validated["live_commit"],
                "execution_actor": actor,
                "environment": config["environment"],
                "platform": platform.platform(),
                "python_executable": sys.executable,
                "admission": admission,
                "supervision": supervision,
                "artifact_sha256": hashes,
                "previous_checkpoint_reused": False,
                "actual_relevance_loaded": False,
                "synthetic_relevance_only": True,
                "engineering_calibration_recovery_completed": True,
                "scientific_result_produced": False,
                "full_w66_executed": False,
                "formal_p1_03_executed": False,
                "training_executed": False,
                "modal_gpu_used": False,
                "remaining_authorized_invocations": 0,
                "independent_resource_review_required": True,
            },
        )
    except BaseException as error:
        base.stop_process(process)
        base.pilot.sharded._write_json_atomic_create_once(
            output / "_INCOMPLETE.json",
            {
                "status": "INCOMPLETE",
                "error_type": type(error).__name__,
                "error": str(error),
                "classification": CLASSIFICATION,
                "remaining_authorized_invocations": 0,
                "completed_result_available": False,
                "partial_metrics_must_not_be_reported_as_complete": True,
                "recovery_requires_separate_approval": True,
            },
        )
        raise
    finally:
        if sleep_inhibited:
            base.set_sleep_inhibition(False)
    return output / "run_manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "run"))
    parser.add_argument("--actor", choices=("human", "codex"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = read_json(root / CONFIG_PATH)
    if args.command == "preflight":
        print(json.dumps(preflight(root, config), indent=2))
    else:
        if args.actor is None:
            parser.error("run requires --actor")
        print(run(root, config, args.actor))


if __name__ == "__main__":
    main()
