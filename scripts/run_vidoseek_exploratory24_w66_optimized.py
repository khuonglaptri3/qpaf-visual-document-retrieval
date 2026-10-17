"""Guard an exact-output optimized W66 study on the frozen exploratory-24 sample."""

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
from typing import Any, Iterator

import numpy as np
import pandas as pd
import psutil
import pyarrow.parquet as pq

from oracle_study.metrics import RankingMetrics, evaluate_scores
from oracle_study.profiles import get_profiles
from oracle_study.qpaf import _query_oracle

if __package__:
    from . import calibrate_vidoseek_w66_resources as resources
    from . import run_vidoseek_exploratory24_w66 as frozen
    from .qpaf_candidate_oracle_optimized import candidate_oracle_exact_fast
else:
    import calibrate_vidoseek_w66_resources as resources
    import run_vidoseek_exploratory24_w66 as frozen
    from qpaf_candidate_oracle_optimized import candidate_oracle_exact_fast


PROTOCOL_ID = "vidoseek_p1_02r_w66_exploratory24_optimized_v1"
CLASSIFICATION = (
    "exact_output_optimized_w66_sensitivity_on_frozen_exploratory24_subset_"
    "not_phase_gate"
)
CONFIG_PATH = "configs/vidoseek_w66_exploratory24_optimized_v1.json"
PROPOSAL_PATH = "docs/05_oracle_experiments/w66/vidoseek_w66_exploratory24_optimized_proposal.json"
EXECUTION_REVIEW_PATH = "docs/05_oracle_experiments/w66/QPAF_W66_EXPLORATORY24_OPTIMIZED_EXECUTION_REVIEW.md"
CALIBRATION_REVIEW_PATH = (
    "artifacts/vidoseek_w66_resource_calibration_recovery_review/review.json"
)
CALIBRATION_REVIEW_SHA256 = (
    "70ba5765b708d416db882b6984dbb6ba962e6921b836537aa1b71b09534b4cf0"
)
SCRIPT_PATH = "scripts/run_vidoseek_exploratory24_w66_optimized.py"
TEST_PATH = "tests/test_vidoseek_exploratory24_w66_optimized.py"
OPTIMIZED_PATH = "scripts/qpaf_candidate_oracle_optimized.py"
OPTIMIZED_SHA256 = "3322b024fa689e0b08ba2e9d6cd08347b5e889cbd26980c4cd19a3a002d4c4e5"
FROZEN_W66_SCRIPT_PATH = "scripts/run_vidoseek_exploratory24_w66.py"
OUTPUT_PATH = "runs/vidoseek_w66_exploratory24_optimized_v1"
GRID_NAME = frozen.GRID_NAME
PROFILE_COUNT = frozen.PROFILE_COUNT
PROFILES_SHA256 = frozen.PROFILES_SHA256
QUERY_LIST_SHA256 = frozen.QUERY_LIST_SHA256
PARENT_W7_PROPOSAL_PATH = frozen.PARENT_W7_PROPOSAL_PATH
PARENT_W7_REVIEW_PATH = frozen.PARENT_W7_REVIEW_PATH
PARENT_W7_PROPOSAL_SHA256 = frozen.PARENT_W7_PROPOSAL_SHA256
PARENT_W7_REVIEW_SHA256 = frozen.PARENT_W7_REVIEW_SHA256
PARENT_W7_MANIFEST_SHA256 = frozen.PARENT_W7_MANIFEST_SHA256
BASE_PROTOCOL_PATH = frozen.BASE_PROTOCOL_PATH
BOOTSTRAP_RESAMPLES = frozen.BOOTSTRAP_RESAMPLES
SEED = frozen.SEED
QUERY_COUNT = frozen.QUERY_COUNT
PAGES_PER_QUERY = frozen.PAGES_PER_QUERY
PROPOSED_TIMEOUT_SECONDS = 7_200
PROCESS_TREE_PRIVATE_BYTES_LIMIT = resources.PROCESS_TREE_PRIVATE_BYTES_LIMIT
PRESTART_FREE_PHYSICAL_BYTES_MIN = resources.PRESTART_FREE_PHYSICAL_BYTES_MIN
ABORT_FREE_PHYSICAL_BYTES_BELOW = resources.ABORT_FREE_PHYSICAL_BYTES_BELOW
PRESTART_DISK_FREE_BYTES_MIN = resources.PRESTART_DISK_FREE_BYTES_MIN
OUTPUT_BYTE_LIMIT = resources.OUTPUT_BYTE_LIMIT
SAMPLE_INTERVAL_SECONDS = resources.SAMPLE_INTERVAL_SECONDS
MAX_TELEMETRY_GAP_SECONDS = 5.0
LOAD_COLUMNS = (
    "dataset",
    "query_id",
    "page_id",
    "source",
    "relevance",
    "bm25_score",
    "dense_score",
    "stage1_score",
    "visual_score",
    "branch_ranks",
)
PACKAGES = (
    "numpy",
    "pandas",
    "psutil",
    "pyarrow",
    "PyYAML",
    "threadpoolctl",
)
PREPARATION_STATUS = "PREPARED_RESOURCE_REVIEW_COMPLETE_EXECUTION_CLOSED"
APPROVED_STATUS = "APPROVED_FOR_ONE_OPTIMIZED_W66_INVOCATION"
GIT_RULE = resources.GIT_RULE


def read_json(path: Path) -> dict[str, Any]:
    return resources.read_json(path)


def value_sha256(value: Any) -> str:
    return resources.value_sha256(value)


def file_sha256(path: Path) -> str:
    return resources.file_sha256(path)


def git_head(root: Path) -> str:
    return resources.git_head(root)


def source_paths(root: Path) -> list[str]:
    return sorted(
        [
            path.relative_to(root).as_posix()
            for path in (root / "src/oracle_study").glob("*.py")
        ]
        + [
            SCRIPT_PATH,
            OPTIMIZED_PATH,
            FROZEN_W66_SCRIPT_PATH,
            resources.SCRIPT_PATH,
            PROPOSAL_PATH,
            EXECUTION_REVIEW_PATH,
            CALIBRATION_REVIEW_PATH,
            PARENT_W7_PROPOSAL_PATH,
            frozen.PARENT_W7_CONFIG_PATH,
            frozen.PARENT_W7_SCRIPT_PATH,
            PARENT_W7_REVIEW_PATH,
            BASE_PROTOCOL_PATH,
            "configs/vidoseek_p1_02r.yaml",
        ]
    )


def selected_queries(root: Path) -> list[dict[str, Any]]:
    return frozen.selected_queries(root)


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
        raise ValueError("Optimized W66 authorization/resource state drift")
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
            raise ValueError("Optimized W66 preparation Git fields drift")
        return frozen.pilot.safeguards.require_exact_git_execution_checkout(
            root,
            approved_parent_commit=record["prepared_parent_commit"],
            approval_commit_changed_paths=record["preparation_commit_changed_paths"],
            execution_label="Optimized exploratory-24 W66 preparation",
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
        raise ValueError("Optimized W66 approval Git fields drift")
    return frozen.pilot.safeguards.require_exact_git_execution_checkout(
        root,
        approved_parent_commit=record["approved_parent_commit"],
        approval_commit_changed_paths=record["approval_commit_changed_paths"],
        execution_label="Optimized exploratory-24 W66 approval",
    )


def validate_config(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "protocol_id": PROTOCOL_ID,
        "classification": CLASSIFICATION,
        "proposal_path": PROPOSAL_PATH,
        "execution_review_path": EXECUTION_REVIEW_PATH,
        "calibration_review_path": CALIBRATION_REVIEW_PATH,
        "calibration_review_sha256": CALIBRATION_REVIEW_SHA256,
        "parent_w7_proposal_path": PARENT_W7_PROPOSAL_PATH,
        "parent_w7_result_review_path": PARENT_W7_REVIEW_PATH,
        "base_protocol_path": BASE_PROTOCOL_PATH,
        "frozen_w66_runner_path": FROZEN_W66_SCRIPT_PATH,
        "optimized_candidate_oracle_path": OPTIMIZED_PATH,
        "optimized_candidate_oracle_sha256": OPTIMIZED_SHA256,
        "output_path": OUTPUT_PATH,
        "grid": GRID_NAME,
        "profile_count": PROFILE_COUNT,
        "profiles_canonical_sha256": PROFILES_SHA256,
        "query_list_sha256": QUERY_LIST_SHA256,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "seed": SEED,
        "queries": QUERY_COUNT,
        "pages_per_query": PAGES_PER_QUERY,
        "load_columns": list(LOAD_COLUMNS),
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
        "actual_relevance_allowed_after_attempt": True,
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
        raise ValueError("Optimized exploratory-24 W66 config fields drift")
    for key, expected_value in expected.items():
        if config.get(key) != expected_value or type(config.get(key)) is not type(
            expected_value
        ):
            raise ValueError(f"Optimized exploratory-24 W66 scope drift: {key}")
    if set(config["authorization"]) != {
        "protocol_adopted",
        "resource_budget_approved",
        "execution_authorized",
        "approved_by",
        "execution_actor",
        "approval_text",
        "approved_at",
    }:
        raise ValueError("Optimized W66 authorization fields drift")
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
        raise ValueError("Closed optimized W66 approval Git state drift")
    if sorted(config["source_sha256"]) != source_paths(root):
        raise ValueError("Optimized W66 source inventory drift")
    for relative, expected_hash in config["source_sha256"].items():
        if file_sha256(root / relative) != expected_hash:
            raise ValueError(f"Optimized W66 source hash drift: {relative}")
    environment = {
        "python": platform.python_version(),
        "packages": {name: version(name) for name in PACKAGES},
    }
    if config["environment"] != environment:
        raise ValueError("Optimized W66 Python/package environment drift")

    proposal = read_json(root / PROPOSAL_PATH)
    if (
        proposal.get("proposal_id") != PROTOCOL_ID
        or proposal.get("status")
        != "PREPARED_RESOURCE_REVIEW_COMPLETE_EXECUTION_CLOSED"
        or proposal.get("execution_authorized") is not False
        or proposal["selection"]["canonical_query_list_sha256"] != QUERY_LIST_SHA256
        or proposal["oracle"]["profiles_canonical_sha256"] != PROFILES_SHA256
        or proposal["oracle"]["candidate_oracle_implementation"]
        != "candidate_oracle_exact_fast"
        or proposal["oracle"]["candidate_oracle_sha256"] != OPTIMIZED_SHA256
        or proposal["resources"]["proposed_wall_timeout_seconds"]
        != PROPOSED_TIMEOUT_SECONDS
        or proposal["resources"]["approved_wall_timeout_seconds"] != 0
        or proposal["resources"]["approved_invocations"] != 0
    ):
        raise ValueError("Optimized exploratory-24 W66 proposal drift")
    calibration = read_json(root / CALIBRATION_REVIEW_PATH)
    if (
        file_sha256(root / CALIBRATION_REVIEW_PATH) != CALIBRATION_REVIEW_SHA256
        or calibration.get("status")
        != "PASS_COMPLETE_ENGINEERING_RECOVERY_NOT_SCIENTIFIC_RESULT"
        or calibration.get("decision")
        != "GO_PREPARE_EXACT_OPTIMIZED_FULL_W66_PROTOCOL_ONLY"
        or calibration.get("full_w66_execution_authorized") is not False
        or calibration["timing"]["query_oracle_seconds"]
        != proposal["resources"]["measured_one_query_search_seconds"]
        or calibration["conditional_full24_timing"][
            "conservative_two_times_total_illustration_seconds"
        ]
        != proposal["resources"]["conservative_full24_illustration_seconds"]
    ):
        raise ValueError("Optimized W66 calibration-review evidence drift")
    if file_sha256(root / OPTIMIZED_PATH) != OPTIMIZED_SHA256:
        raise ValueError("Optimized W66 candidate-oracle implementation drift")
    selected_queries(root)
    profiles = get_profiles(GRID_NAME)
    if (
        profiles.shape != (PROFILE_COUNT, 3)
        or value_sha256(profiles.tolist()) != PROFILES_SHA256
    ):
        raise ValueError("Optimized W66 profile grid drift")
    return {
        "state": state,
        "live_commit": live_commit,
        "proposal": proposal,
        "calibration": calibration,
    }


def require_approval(config: dict[str, Any], actor: str) -> None:
    try:
        state = _approval_state(config)
    except (KeyError, TypeError, ValueError):
        state = "closed"
    approval = config.get("authorization", {})
    if state != "approved" or approval.get("execution_actor") != actor:
        raise PermissionError(
            "Separate optimized exploratory-24 W66 execution approval pending; "
            "no attempt consumed"
        )
    if actor not in {"human", "codex"}:
        raise PermissionError("Invalid optimized exploratory-24 W66 actor")
    if any(
        os.environ.get(name) != "1" for name in frozen.pilot.safeguards.CPU_THREAD_ENV
    ):
        raise RuntimeError(
            "Optimized exploratory-24 W66 requires one numeric-library thread"
        )


def host_snapshot(root: Path, output: Path) -> dict[str, Any]:
    return resources.host_snapshot(root, output)


def enforce_admission(snapshot: dict[str, Any], config: dict[str, Any]) -> None:
    if snapshot["output_exists"]:
        raise FileExistsError("Optimized exploratory-24 W66 output already exists")
    if snapshot["free_physical_bytes"] < config["prestart_free_physical_bytes_min"]:
        raise RuntimeError("Insufficient free physical memory for optimized W66")
    if snapshot["disk_free_bytes"] < config["prestart_disk_free_bytes_min"]:
        raise RuntimeError("Insufficient free disk space for optimized W66")


def enforce_resource_sample(sample: dict[str, Any], config: dict[str, Any]) -> None:
    if (
        sample["process_tree_private_bytes"]
        > config["process_tree_private_bytes_limit"]
    ):
        raise MemoryError("Optimized W66 process-tree private-byte limit exceeded")
    if sample["free_physical_bytes"] < config["abort_free_physical_bytes_below"]:
        raise MemoryError("Optimized W66 host free-memory abort threshold crossed")
    if sample["output_bytes"] > config["output_byte_limit"]:
        raise RuntimeError("Optimized W66 output-byte limit exceeded")


def preflight(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    validated = validate_config(root, config)
    evidence = frozen.pilot.safeguards.protocol_bound_preflight(
        root / BASE_PROTOCOL_PATH,
        repo_root=root,
        allow_recorded_probe_evidence=True,
    )
    proposal = validated["proposal"]
    review = read_json(root / PARENT_W7_REVIEW_PATH)
    gain = review["recomputed"]
    if (
        file_sha256(root / PARENT_W7_PROPOSAL_PATH) != PARENT_W7_PROPOSAL_SHA256
        or proposal["parent_w7_evidence"]["proposal_sha256"]
        != PARENT_W7_PROPOSAL_SHA256
        or file_sha256(root / PARENT_W7_REVIEW_PATH) != PARENT_W7_REVIEW_SHA256
        or proposal["parent_w7_evidence"]["result_review_sha256"]
        != PARENT_W7_REVIEW_SHA256
        or review["status"] != "PASS"
        or review["run_manifest_sha256"] != PARENT_W7_MANIFEST_SHA256
        or gain["mean_qpaf_vs_qarf_delta_ndcg10"] < 0.03
        or gain["qpaf_vs_qarf_ci95"][0] <= 0
        or gain["qpaf_vs_qarf_top_5pct_gain_share"] >= 0.90
    ):
        raise ValueError("Parent exploratory-24 W7 continuation evidence is invalid")
    score_path = root / proposal["input"]["retrieval_scores_path"]
    schema_names = pq.ParquetFile(score_path).schema_arrow.names
    if evidence["retrieval_score_sha256"] != proposal["input"][
        "retrieval_scores_byte_sha256"
    ] or any(column not in schema_names for column in LOAD_COLUMNS):
        raise ValueError("Optimized W66 score input/schema drift")
    snapshot = host_snapshot(root, root / OUTPUT_PATH)
    return {
        "status": "PASS",
        "classification": "read_only_optimized_w66_preflight_not_result",
        "base_preflight": evidence,
        "parent_w7_review_sha256": PARENT_W7_REVIEW_SHA256,
        "parent_w7_manifest_sha256": PARENT_W7_MANIFEST_SHA256,
        "calibration_review_sha256": CALIBRATION_REVIEW_SHA256,
        "candidate_oracle_implementation": "candidate_oracle_exact_fast",
        "candidate_oracle_sha256": OPTIMIZED_SHA256,
        "query_list_sha256": QUERY_LIST_SHA256,
        "grid": GRID_NAME,
        "profile_count": PROFILE_COUNT,
        "profiles_canonical_sha256": PROFILES_SHA256,
        "queries": QUERY_COUNT,
        "pages_per_query": PAGES_PER_QUERY,
        "candidate_pairs": QUERY_COUNT * PAGES_PER_QUERY,
        "load_columns": list(LOAD_COLUMNS),
        "actual_relevance_loaded": False,
        "w66_oracle_executed": False,
        "scientific_result_produced": False,
        "proposed_wall_timeout_seconds": PROPOSED_TIMEOUT_SECONDS,
        "approved_wall_timeout_seconds": config["approved_wall_timeout_seconds"],
        "resource_budget_status": config["resource_budget_status"],
        "authorized_invocations": config["invocations"],
        "execution_authorized": config["authorization"]["execution_authorized"],
        "host_snapshot": snapshot,
        "admission_thresholds_currently_met": (
            not snapshot["output_exists"]
            and snapshot["free_physical_bytes"]
            >= config["prestart_free_physical_bytes_min"]
            and snapshot["disk_free_bytes"] >= config["prestart_disk_free_bytes_min"]
        ),
        "attempt_exists": snapshot["output_exists"],
    }


def build_run_identity(
    *,
    protocol_sha256: str,
    source_commit: str,
    retrieval_score_sha256: str,
    retrieval_score_content_sha256: str,
    query_order: list[tuple[str, str]],
    pages_per_query: int,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    profiles = get_profiles(GRID_NAME)
    return {
        "schema_version": frozen.pilot.sharded.CHECKPOINT_SCHEMA_VERSION,
        "classification": "query_sharded_exact_optimized_w66_checkpoint_identity",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha256,
        "source_commit": source_commit,
        "retrieval_score_sha256": retrieval_score_sha256,
        "retrieval_score_content_sha256": retrieval_score_content_sha256,
        "query_order_sha256": value_sha256([list(key) for key in query_order]),
        "queries": len(query_order),
        "pages_per_query": pages_per_query,
        "grid": GRID_NAME,
        "profiles": profiles.tolist(),
        "channel_order": ["bm25_score", "dense_score", "visual_score"],
        "reported_metrics": ["ndcg10", "recall1", "recall3", "mrr10"],
        "profile_selection_tie_break": ["ndcg10", "recall3", "mrr10"],
        "ranking_tie_break": "ascending_page_id",
        "qpaf_max_sweeps": 2,
        "strict_improvement_tolerance": 1e-12,
        "candidate_oracle_implementation": "candidate_oracle_exact_fast",
        "candidate_oracle_sha256": OPTIMIZED_SHA256,
        "previous_checkpoint_reuse_allowed": False,
        "bootstrap_unit": "query",
        "bootstrap_seed": SEED,
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_confidence": 0.95,
        "bootstrap_interval": "percentile",
    }


def query_result_row(
    frame: pd.DataFrame,
    profiles: np.ndarray,
    global_profile_index: int,
    global_query_metrics: Any,
) -> dict[str, Any]:
    item = frozen.pilot.sharded._query_item(frame)
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


def global_checkpoint(
    path: Path,
    *,
    run_identity_sha256: str,
    query_index: int,
    query_key: tuple[str, str],
    frame: pd.DataFrame,
    profiles: np.ndarray,
) -> tuple[dict[str, Any], str, bool]:
    input_sha256 = frozen.pilot.sharded.dataframe_sha256(
        frame, sort_by=["dataset", "query_id", "page_id"]
    )
    if path.exists():
        payload, content_sha256 = frozen.pilot.sharded._read_checkpoint(
            path,
            kind="w66_optimized_global_profile_metrics",
            run_identity_sha256=run_identity_sha256,
        )
        reused = True
    else:
        item = frozen.pilot.sharded._query_item(frame)
        payload = {
            "query_index": query_index,
            "dataset": query_key[0],
            "query_id": query_key[1],
            "input_query_sha256": input_sha256,
            "profile_metrics": [
                asdict(
                    evaluate_scores(
                        item["score_matrix"] @ profile,
                        item["relevance"],
                        item["page_ids"],
                    )
                )
                for profile in profiles
            ],
        }
        content_sha256 = frozen.pilot.sharded._write_checkpoint(
            path,
            kind="w66_optimized_global_profile_metrics",
            run_identity_sha256=run_identity_sha256,
            payload=payload,
        )
        reused = False
    expected = {
        "query_index": query_index,
        "dataset": query_key[0],
        "query_id": query_key[1],
        "input_query_sha256": input_sha256,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(
                f"Optimized W66 Global checkpoint {field} mismatch for {query_key}"
            )
    metrics = payload.get("profile_metrics")
    if not isinstance(metrics, list) or len(metrics) != len(profiles):
        raise ValueError(
            f"Optimized W66 Global checkpoint profile count mismatch for {query_key}"
        )
    for profile_index, metric in enumerate(metrics):
        frozen.pilot.sharded._validate_metric_dict(
            metric, f"optimized W66 global profile {profile_index}"
        )
    return payload, content_sha256, reused


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
    input_sha256 = frozen.pilot.sharded.dataframe_sha256(
        frame, sort_by=["dataset", "query_id", "page_id"]
    )
    if path.exists():
        payload, content_sha256 = frozen.pilot.sharded._read_checkpoint(
            path,
            kind="w66_optimized_query_oracle_result",
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
            "row": query_result_row(
                frame,
                profiles,
                global_profile_index,
                global_query_metrics,
            ),
        }
        content_sha256 = frozen.pilot.sharded._write_checkpoint(
            path,
            kind="w66_optimized_query_oracle_result",
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
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(
                f"Optimized W66 query checkpoint {field} mismatch for {query_key}"
            )
    row = payload.get("row")
    if not isinstance(row, dict):
        raise ValueError(f"Optimized W66 query checkpoint row invalid for {query_key}")
    if (
        row.get("dataset") != query_key[0]
        or row.get("query_id") != query_key[1]
        or row.get("grid") != GRID_NAME
    ):
        raise ValueError(
            f"Optimized W66 query checkpoint identity mismatch for {query_key}"
        )
    for name in ("global_metrics", "qarf_metrics", "qpaf_metrics"):
        frozen.pilot.sharded._validate_metric_dict(row.get(name), name)
    return row, content_sha256, reused


def checkpoint_inventory(directory: Path, expected_count: int, label: str) -> None:
    frozen.checkpoint_inventory(directory, expected_count, label)


def run_query_sharded_w66(
    *,
    query_order: list[tuple[str, str]],
    query_frames: Any,
    expected_pages_per_query: int,
    checkpoint_root: Path,
    run_identity: dict[str, Any],
    n_bootstrap: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, int]]:
    if not query_order:
        raise ValueError("Query-sharded optimized W66 requires at least one query")
    expected_identity = build_run_identity(
        protocol_sha256=run_identity["protocol_sha256"],
        source_commit=run_identity["source_commit"],
        retrieval_score_sha256=run_identity["retrieval_score_sha256"],
        retrieval_score_content_sha256=run_identity["retrieval_score_content_sha256"],
        query_order=query_order,
        pages_per_query=expected_pages_per_query,
        bootstrap_resamples=n_bootstrap,
    )
    if run_identity != expected_identity:
        raise ValueError(
            "Query-sharded optimized W66 identity does not match frozen semantics"
        )
    identity_sha256 = value_sha256(run_identity)
    plan_path = checkpoint_root / "run_plan.json"
    if plan_path.exists():
        plan, _ = frozen.pilot.sharded._read_checkpoint(
            plan_path,
            kind="w66_optimized_run_plan",
            run_identity_sha256=identity_sha256,
        )
        if plan != run_identity:
            raise ValueError("Optimized W66 checkpoint run plan mismatch")
        plan_reused = 1
    else:
        frozen.pilot.sharded._write_checkpoint(
            plan_path,
            kind="w66_optimized_run_plan",
            run_identity_sha256=identity_sha256,
            payload=run_identity,
        )
        plan_reused = 0

    profiles = get_profiles(GRID_NAME)
    global_directory = checkpoint_root / "global"
    global_payloads = []
    global_hashes = []
    global_reused = 0
    expected_index = 0
    for index, key, frame in query_frames():
        if index != expected_index or key != query_order[index]:
            raise ValueError("Optimized W66 Global pass sequence is not canonical")
        payload, content_sha256, reused = global_checkpoint(
            global_directory / f"{index:06d}.json",
            run_identity_sha256=identity_sha256,
            query_index=index,
            query_key=key,
            frame=frame,
            profiles=profiles,
        )
        global_payloads.append(payload)
        global_hashes.append(content_sha256)
        global_reused += int(reused)
        expected_index += 1
    if expected_index != len(query_order):
        raise ValueError("Optimized W66 Global pass did not cover every query")
    checkpoint_inventory(global_directory, len(query_order), "Optimized W66 Global")

    global_profile_index, global_query_metrics = frozen.select_global_profile(
        global_payloads, profiles
    )
    selection_payload = {
        "profile_index": global_profile_index,
        "profile": profiles[global_profile_index].astype(float).tolist(),
        "global_checkpoint_chain_sha256": value_sha256(global_hashes),
    }
    selection_path = checkpoint_root / "global_selection.json"
    if selection_path.exists():
        observed, global_selection_sha256 = frozen.pilot.sharded._read_checkpoint(
            selection_path,
            kind="w66_optimized_global_profile_selection",
            run_identity_sha256=identity_sha256,
        )
        if observed != selection_payload:
            raise ValueError("Optimized W66 Global profile selection mismatch")
        selection_reused = 1
    else:
        global_selection_sha256 = frozen.pilot.sharded._write_checkpoint(
            selection_path,
            kind="w66_optimized_global_profile_selection",
            run_identity_sha256=identity_sha256,
            payload=selection_payload,
        )
        selection_reused = 0

    query_directory = checkpoint_root / "queries"
    rows = []
    query_reused = 0
    expected_index = 0
    for index, key, frame in query_frames():
        if index != expected_index or key != query_order[index]:
            raise ValueError("Optimized W66 query pass sequence is not canonical")
        row, _, reused = query_checkpoint(
            query_directory / f"{index:06d}.json",
            run_identity_sha256=identity_sha256,
            query_index=index,
            query_key=key,
            frame=frame,
            profiles=profiles,
            global_profile_index=global_profile_index,
            global_query_metrics=global_query_metrics[index],
            global_selection_sha256=global_selection_sha256,
        )
        rows.append(row)
        query_reused += int(reused)
        expected_index += 1
    if expected_index != len(query_order):
        raise ValueError("Optimized W66 query pass did not cover every query")
    checkpoint_inventory(query_directory, len(query_order), "Optimized W66 query")

    summary = frozen.pilot.exploratory_summary(rows, n_bootstrap)
    summary.update(
        {
            "classification": CLASSIFICATION,
            "candidate_oracle_implementation": "candidate_oracle_exact_fast",
            "candidate_oracle_sha256": OPTIMIZED_SHA256,
            "global_scope": "same_frozen_exploratory24_queries_only",
            "phase1_decision": "NOT_APPLICABLE_EXPLORATORY_W66_SUBSET",
            "training_authorized": False,
            "parent_w7_review_sha256": PARENT_W7_REVIEW_SHA256,
            "w7_w66_comparison_requires_independent_review": True,
        }
    )
    stats = {
        "plan_reused": plan_reused,
        "global_created": len(query_order) - global_reused,
        "global_reused": global_reused,
        "selection_reused": selection_reused,
        "query_created": len(query_order) - query_reused,
        "query_reused": query_reused,
    }
    return rows, summary, stats


def evaluate_subset(
    scores: pd.DataFrame,
    query_order: list[tuple[str, str]],
    identity: dict[str, Any],
    checkpoint_root: Path,
    pages: int,
    n_bootstrap: int,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, int],
]:
    timings: list[dict[str, Any]] = []
    pass_number = 0

    def frames() -> Iterator[tuple[int, tuple[str, str], pd.DataFrame]]:
        nonlocal pass_number
        pass_number += 1
        for index, key in enumerate(query_order):
            selected = scores.loc[
                (scores.dataset == key[0]) & (scores.query_id == key[1])
            ]
            frame = frozen.pilot.sharded._validate_query_frame(selected, key, pages)
            started = time.perf_counter()
            yield index, key, frame
            elapsed = time.perf_counter() - started
            timings.append(
                {
                    "pass": "global" if pass_number == 1 else "query_oracle",
                    "query_id": key[1],
                    "elapsed_seconds_including_checkpoint": elapsed,
                }
            )
            print(
                f"Optimized W66 {timings[-1]['pass']} "
                f"{index + 1}/{len(query_order)}: {elapsed:.3f}s",
                flush=True,
            )

    rows, summary, stats = run_query_sharded_w66(
        query_order=query_order,
        query_frames=frames,
        expected_pages_per_query=pages,
        checkpoint_root=checkpoint_root,
        run_identity=identity,
        n_bootstrap=n_bootstrap,
    )
    return rows, summary, timings, stats


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
        raise RuntimeError("Optimized W66 telemetry clock moved backwards")
    return wall_gap, monotonic_gap


def enforce_telemetry_cadence(
    wall_gap: float, monotonic_gap: float, maximum_gap_seconds: float
) -> None:
    if max(wall_gap, monotonic_gap) > maximum_gap_seconds:
        raise RuntimeError(
            "Optimized W66 telemetry cadence exceeded "
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
        target=resources.watch_parent,
        args=(parent_identity, stop_watchdog),
        daemon=True,
    )
    watchdog.start()
    try:
        resources.record_stage(
            stage_log, "worker", "STARTED", **resources.process_identity(os.getpid())
        )
        thread_state = resources.set_worker_thread_limits()
        frozen.pilot.sharded._write_json_atomic_create_once(
            output / "worker_thread_state.json", thread_state
        )
        resources.record_stage(stage_log, "thread_limits", "PASS")

        evidence = preflight(root, config)
        frozen.pilot.sharded._write_json_atomic_create_once(
            output / "preflight.json", evidence
        )
        resources.record_stage(stage_log, "preflight", "PASS")

        selected = selected_queries(root)
        order = [(query["dataset"], query["query_id"]) for query in selected]
        proposal = read_json(root / PROPOSAL_PATH)
        filters = [
            [("dataset", "=", dataset), ("query_id", "=", query_id)]
            for dataset, query_id in order
        ]
        load_started = time.monotonic()
        table = pq.read_table(
            root / proposal["input"]["retrieval_scores_path"],
            columns=list(LOAD_COLUMNS),
            filters=filters,
            use_threads=False,
            pre_buffer=False,
        )
        scores = table.to_pandas(use_threads=False)
        input_load_seconds = time.monotonic() - load_started
        if list(scores.columns) != list(LOAD_COLUMNS):
            raise ValueError("Optimized W66 loaded column order drift")
        if len(scores) != QUERY_COUNT * PAGES_PER_QUERY:
            raise ValueError("Optimized W66 subset pair count mismatch")
        resources.record_stage(
            stage_log,
            "input_load",
            "PASS",
            elapsed_seconds=input_load_seconds,
            rows=len(scores),
        )

        identity = build_run_identity(
            protocol_sha256=value_sha256(config),
            source_commit=git_head(root),
            retrieval_score_sha256=evidence["base_preflight"]["retrieval_score_sha256"],
            retrieval_score_content_sha256=evidence["base_preflight"][
                "retrieval_score_content_sha256"
            ],
            query_order=order,
            pages_per_query=PAGES_PER_QUERY,
            bootstrap_resamples=BOOTSTRAP_RESAMPLES,
        )
        rows, summary, timings, stats = evaluate_subset(
            scores,
            order,
            identity,
            output / "checkpoints",
            PAGES_PER_QUERY,
            BOOTSTRAP_RESAMPLES,
        )
        del scores, table
        if (
            len(rows) != QUERY_COUNT
            or [(row["dataset"], row["query_id"]) for row in rows] != order
        ):
            raise ValueError("Optimized W66 result query coverage mismatch")
        for name, value in {
            "per_query.json": {"classification": CLASSIFICATION, "rows": rows},
            "summary.json": summary,
            "timings.json": {
                "input_load_seconds": input_load_seconds,
                "timings": timings,
            },
            "checkpoint_stats.json": stats,
        }.items():
            frozen.pilot.sharded._write_json_atomic_create_once(output / name, value)

        postflight = preflight(root, config)
        if postflight["base_preflight"] != evidence["base_preflight"]:
            raise ValueError("Optimized W66 input identity changed during worker run")
        frozen.pilot.sharded._write_json_atomic_create_once(
            output / "_WORKER_COMPLETE.json",
            {
                "status": "COMPLETE",
                "run_identity_sha256": value_sha256(identity),
                "per_query_sha256": file_sha256(output / "per_query.json"),
                "summary_sha256": file_sha256(output / "summary.json"),
                "queries": len(rows),
                "candidate_oracle_implementation": "candidate_oracle_exact_fast",
                "candidate_oracle_sha256": OPTIMIZED_SHA256,
            },
        )
        resources.record_stage(stage_log, "worker", "COMPLETE")
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
    worker_identity = resources.process_identity(process.pid)
    frozen.pilot.sharded._write_json_atomic_create_once(
        output / "process_identity.json",
        {
            "parent": resources.process_identity(os.getpid()),
            "worker": worker_identity,
        },
    )
    telemetry_path = output / "resource_telemetry.jsonl"
    peak_private = 0
    minimum_free = psutil.virtual_memory().available
    maximum_output = resources.output_bytes(output)
    maximum_wall_gap = 0.0
    maximum_monotonic_gap = 0.0
    previous_observed_at: str | None = None
    previous_monotonic: float | None = None
    samples = 0

    while True:
        observed_monotonic = time.monotonic()
        sample = resources.resource_sample(root, output)
        enforce_resource_sample(sample, config)
        resources.append_jsonl(telemetry_path, sample)
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
            raise TimeoutError("Optimized exploratory-24 W66 deadline expired")
        process.join(min(config["sample_interval_seconds"], remaining))

    process.join()
    if process.exitcode != 0:
        raise RuntimeError(f"Optimized W66 worker exit code {process.exitcode}")
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
    admission = host_snapshot(root, output)
    enforce_admission(admission, config)
    output.mkdir(parents=True, exist_ok=False)
    config_hash = value_sha256(config)
    frozen.pilot.sharded._write_json_atomic_create_once(
        output / "_ATTEMPTED.json",
        {
            "started_at": resources.utc_now(),
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
        resources.record_stage(stage_log, "attempt", "STARTED")
        frozen.pilot.sharded._write_json_atomic_create_once(
            output / "admission_snapshot.json", admission
        )
        frozen.pilot.sharded._write_json_atomic_create_once(
            output / "resolved_config.json", config
        )
        snapshot = output / "source_snapshot"
        for relative, expected_hash in config["source_sha256"].items():
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write((root / relative).read_bytes())
            if file_sha256(destination) != expected_hash:
                raise ValueError("Optimized W66 source changed during snapshot")
        with (output / "tracked_changes.patch").open("xb") as handle:
            subprocess.run(
                ["git", "diff", "--binary", "HEAD"],
                cwd=root,
                stdout=handle,
                check=True,
                timeout=30,
            )
        sleep_inhibited = resources.set_sleep_inhibition(True)
        if os.name == "nt" and not sleep_inhibited:
            raise RuntimeError("Unable to inhibit system sleep for optimized W66")
        resources.record_stage(stage_log, "admission_and_snapshot", "PASS")

        parent_identity = resources.process_identity(os.getpid())
        process = mp.get_context("spawn").Process(
            target=worker,
            args=(root, config, output, parent_identity),
        )
        deadline = started + config["approved_wall_timeout_seconds"]
        supervision = monitor_worker(process, root, output, config, deadline)
        resources.record_stage(stage_log, "worker_supervision", "PASS")

        complete = read_json(output / "_WORKER_COMPLETE.json")
        rows = read_json(output / "per_query.json")["rows"]
        summary = read_json(output / "summary.json")
        if (
            complete["status"] != "COMPLETE"
            or complete["per_query_sha256"] != file_sha256(output / "per_query.json")
            or complete["summary_sha256"] != file_sha256(output / "summary.json")
            or complete["queries"] != QUERY_COUNT
            or len(rows) != QUERY_COUNT
            or summary["classification"] != CLASSIFICATION
            or supervision["telemetry_cadence_passed"] is not True
        ):
            raise ValueError("Optimized W66 completion evidence mismatch")
        final_sample = resources.resource_sample(root, output)
        enforce_resource_sample(final_sample, config)
        elapsed = time.monotonic() - started
        if elapsed >= config["approved_wall_timeout_seconds"]:
            raise TimeoutError("Optimized W66 deadline expired in finalization")
        resources.record_stage(stage_log, "finalization", "READY")
        hashes = {
            path.relative_to(output).as_posix(): file_sha256(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        frozen.pilot.sharded._write_json_atomic_create_once(
            output / "run_manifest.json",
            {
                "status": "COMPLETE",
                "classification": CLASSIFICATION,
                "completed_at": resources.utc_now(),
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
                "grid": GRID_NAME,
                "profile_count": PROFILE_COUNT,
                "profiles_canonical_sha256": PROFILES_SHA256,
                "query_list_sha256": QUERY_LIST_SHA256,
                "queries": QUERY_COUNT,
                "pages_per_query": PAGES_PER_QUERY,
                "candidate_oracle_implementation": "candidate_oracle_exact_fast",
                "candidate_oracle_sha256": OPTIMIZED_SHA256,
                "previous_checkpoint_reused": False,
                "actual_relevance_loaded_after_attempt": True,
                "exploratory_w66_executed": True,
                "scientific_result_requires_independent_review": True,
                "frozen_p1_02_status": "BLOCKED",
                "phase1_decision": "NOT_APPLICABLE_EXPLORATORY_W66_SUBSET",
                "formal_p1_03_executed": False,
                "training_executed": False,
                "modal_gpu_used": False,
                "remaining_authorized_invocations": 0,
            },
        )
    except BaseException as error:
        resources.stop_process(process)
        frozen.pilot.sharded._write_json_atomic_create_once(
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
            resources.set_sleep_inhibition(False)
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
