"""Guard and run a W66 sensitivity study on the frozen exploratory-24 sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd

from oracle_study import vidoseek_exploratory12 as pilot
from oracle_study.metrics import RankingMetrics, evaluate_scores
from oracle_study.profiles import get_profiles
from oracle_study.qpaf import (
    _better_metrics,
    _candidate_oracle,
    _mean_metrics,
    _query_oracle,
)


PROTOCOL_ID = "vidoseek_p1_02r_w66_exploratory24_v1"
CLASSIFICATION = "w66_sensitivity_on_frozen_exploratory24_subset_not_phase_gate"
PROPOSAL_PATH = "docs/vidoseek_w66_exploratory24_proposal.json"
PARENT_W7_PROPOSAL_PATH = "docs/vidoseek_w7_exploratory24_proposal.json"
PARENT_W7_CONFIG_PATH = "configs/vidoseek_w7_exploratory24_v1.json"
PARENT_W7_SCRIPT_PATH = "scripts/run_vidoseek_exploratory24.py"
PARENT_W7_REVIEW_PATH = (
    "artifacts/vidoseek_exploratory24_review/result_integrity_review.json"
)
BASE_PROTOCOL_PATH = "configs/vidoseek_p1_02r_oracle_w7_v1.yaml"
CONFIG_PATH = "configs/vidoseek_w66_exploratory24_v1.json"
SCRIPT_PATH = "scripts/run_vidoseek_exploratory24_w66.py"
OUTPUT_PATH = "runs/vidoseek_w66_exploratory24_v1"
GRID_NAME = "w66"
PROFILE_COUNT = 66
PROFILES_SHA256 = "c04139858954fd0a7f7baa5dad548f3675a41b8682e9798039508e4077da5973"
QUERY_LIST_SHA256 = "95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b"
PARENT_W7_PROPOSAL_SHA256 = (
    "1f3d76ce5976a8568fac1119e7de5791af0550ddea8331641613ff7a91a086b2"
)
PARENT_W7_REVIEW_SHA256 = (
    "716a184eedcbe73c34dc166bcaa60d594546625dcb288049fd71807f63b61319"
)
PARENT_W7_MANIFEST_SHA256 = (
    "0fcfbceee0e581240f241447abae1cb85cbb4f11cfee4f4d5343c2f81e06d9ee"
)
BOOTSTRAP_RESAMPLES = 10_000
SEED = 20260820
QUERY_COUNT = 24
PAGES_PER_QUERY = 5385
PACKAGES = ("numpy", "pandas", "pyarrow", "PyYAML")
RESOURCE_BUDGET_STATUS = "PENDING_SEPARATE_RESOURCE_REVIEW"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=10
    ).strip()


def canonical_query_hash(queries: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        queries, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_paths(root: Path) -> list[str]:
    return sorted(
        [
            path.relative_to(root).as_posix()
            for path in (root / "src/oracle_study").glob("*.py")
        ]
        + [
            SCRIPT_PATH,
            PROPOSAL_PATH,
            PARENT_W7_PROPOSAL_PATH,
            PARENT_W7_CONFIG_PATH,
            PARENT_W7_SCRIPT_PATH,
            PARENT_W7_REVIEW_PATH,
            BASE_PROTOCOL_PATH,
            "configs/vidoseek_p1_02r.yaml",
        ]
    )


def selected_queries(root: Path) -> list[dict[str, Any]]:
    parent = read_json(root / PARENT_W7_PROPOSAL_PATH)
    queries = parent["selection"]["queries"]
    if (
        len(queries) != QUERY_COUNT
        or canonical_query_hash(queries) != QUERY_LIST_SHA256
        or parent["selection"]["canonical_query_list_sha256"] != QUERY_LIST_SHA256
    ):
        raise ValueError("Parent exploratory-24 query selection drift")
    return queries


def validate_config(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "protocol_id": PROTOCOL_ID,
        "classification": CLASSIFICATION,
        "proposal_path": PROPOSAL_PATH,
        "parent_w7_proposal_path": PARENT_W7_PROPOSAL_PATH,
        "parent_w7_result_review_path": PARENT_W7_REVIEW_PATH,
        "base_protocol_path": BASE_PROTOCOL_PATH,
        "output_path": OUTPUT_PATH,
        "grid": GRID_NAME,
        "profile_count": PROFILE_COUNT,
        "profiles_canonical_sha256": PROFILES_SHA256,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "seed": SEED,
        "queries": QUERY_COUNT,
        "pages_per_query": PAGES_PER_QUERY,
        "workers": 1,
        "threads_per_library": 1,
        "automatic_retries": 0,
    }
    if set(config) != set(expected) | {
        "preparation_git",
        "source_sha256",
        "environment",
        "authorization",
        "resource_budget_status",
        "total_wall_timeout_seconds",
        "invocations",
    }:
        raise ValueError("Exploratory-24 W66 config fields drift")
    for key, value in expected.items():
        if config.get(key) != value or type(config.get(key)) is not type(value):
            raise ValueError(f"Exploratory-24 W66 scope drift: {key}")

    approval = config["authorization"]
    expected_approval_fields = {
        "protocol_adopted",
        "resource_budget_approved",
        "execution_authorized",
        "approved_by",
        "execution_actor",
        "approval_text",
        "approved_at",
    }
    if not isinstance(approval, dict) or set(approval) != expected_approval_fields:
        raise ValueError("Exploratory-24 W66 authorization fields drift")
    closed_state = (
        config.get("resource_budget_status") == RESOURCE_BUDGET_STATUS
        and config.get("total_wall_timeout_seconds") == 0
        and config.get("invocations") == 0
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
    approved_state = (
        config.get("resource_budget_status") == "APPROVED_FOR_ONE_INVOCATION"
        and type(config.get("total_wall_timeout_seconds")) is int
        and config["total_wall_timeout_seconds"] > 0
        and config.get("invocations") == 1
        and approval.get("protocol_adopted") is True
        and approval.get("resource_budget_approved") is True
        and approval.get("execution_authorized") is True
        and approval.get("approved_by") == "user"
        and approval.get("execution_actor") in {"human", "codex"}
        and bool(approval.get("approval_text"))
        and bool(approval.get("approved_at"))
    )
    if not (closed_state or approved_state):
        raise ValueError("Exploratory-24 W66 authorization/resource state drift")

    preparation = config["preparation_git"]
    if set(preparation) != {
        "prepared_parent_commit",
        "preparation_commit_rule",
        "preparation_commit_changed_paths",
    }:
        raise ValueError("Exploratory-24 W66 preparation provenance drift")
    if preparation["preparation_commit_rule"] != pilot.safeguards.EXECUTION_COMMIT_RULE:
        raise ValueError("Exploratory-24 W66 preparation commit rule drift")
    pilot.safeguards.require_exact_git_execution_checkout(
        root,
        approved_parent_commit=preparation["prepared_parent_commit"],
        approval_commit_changed_paths=preparation["preparation_commit_changed_paths"],
        execution_label="Exploratory-24 W66 preparation",
    )

    if sorted(config["source_sha256"]) != source_paths(root):
        raise ValueError("Exploratory-24 W66 source inventory drift")
    for relative, expected_hash in config["source_sha256"].items():
        if pilot.safeguards.file_sha256(root / relative) != expected_hash:
            raise ValueError(f"Exploratory-24 W66 source hash drift: {relative}")
    environment = {
        "python": platform.python_version(),
        "packages": {name: version(name) for name in PACKAGES},
    }
    if config["environment"] != environment:
        raise ValueError("Exploratory-24 W66 environment drift")

    proposal = read_json(root / PROPOSAL_PATH)
    if (
        proposal["proposal_id"] != PROTOCOL_ID
        or proposal["status"] != "PREPARED_RESOURCE_REVIEW_REQUIRED_EXECUTION_CLOSED"
        or proposal["execution_authorized"] is not False
        or proposal["selection"]["canonical_query_list_sha256"] != QUERY_LIST_SHA256
        or proposal["oracle"]["grid"] != GRID_NAME
        or proposal["oracle"]["profile_count"] != PROFILE_COUNT
        or proposal["oracle"]["profiles_canonical_sha256"] != PROFILES_SHA256
        or proposal["resource_review"]["approved_wall_timeout_seconds"] != 0
        or proposal["resource_review"]["approved_invocations"] != 0
    ):
        raise ValueError("Exploratory-24 W66 proposal drift")
    selected_queries(root)

    profiles = get_profiles(GRID_NAME)
    if (
        profiles.shape != (PROFILE_COUNT, 3)
        or not np.all(profiles >= 0)
        or not np.allclose(profiles.sum(axis=1), 1.0, rtol=0.0, atol=1e-12)
        or len(np.unique(profiles, axis=0)) != PROFILE_COUNT
        or pilot.sharded._value_sha256(profiles.tolist()) != PROFILES_SHA256
    ):
        raise ValueError("Exploratory-24 W66 profile grid drift")
    return proposal


def require_approval(config: dict[str, Any], actor: str) -> None:
    approval = config["authorization"]
    if (
        approval.get("protocol_adopted") is not True
        or approval.get("resource_budget_approved") is not True
        or approval.get("execution_authorized") is not True
        or approval.get("approved_by") != "user"
        or approval.get("execution_actor") != actor
        or actor not in {"human", "codex"}
        or not approval.get("approval_text")
        or not approval.get("approved_at")
        or config.get("resource_budget_status") != "APPROVED_FOR_ONE_INVOCATION"
        or type(config.get("total_wall_timeout_seconds")) is not int
        or config["total_wall_timeout_seconds"] <= 0
        or config.get("invocations") != 1
        or config.get("automatic_retries") != 0
    ):
        raise PermissionError(
            "Separate exploratory-24 W66 resource and execution approval pending; "
            "no attempt consumed"
        )
    if any(os.environ.get(name) != "1" for name in pilot.safeguards.CPU_THREAD_ENV):
        raise RuntimeError("Exploratory-24 W66 requires one thread per numeric library")


def preflight(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    proposal = validate_config(root, config)
    evidence = pilot.safeguards.protocol_bound_preflight(
        root / BASE_PROTOCOL_PATH,
        repo_root=root,
        allow_recorded_probe_evidence=True,
    )
    if (
        pilot.safeguards.file_sha256(root / PARENT_W7_PROPOSAL_PATH)
        != PARENT_W7_PROPOSAL_SHA256
        or proposal["parent_w7_evidence"]["proposal_sha256"]
        != PARENT_W7_PROPOSAL_SHA256
    ):
        raise ValueError("Parent exploratory-24 W7 proposal drift")
    if (
        pilot.safeguards.file_sha256(root / PARENT_W7_REVIEW_PATH)
        != PARENT_W7_REVIEW_SHA256
        or proposal["parent_w7_evidence"]["result_review_sha256"]
        != PARENT_W7_REVIEW_SHA256
    ):
        raise ValueError("Parent exploratory-24 W7 review drift")
    review = read_json(root / PARENT_W7_REVIEW_PATH)
    gain = review["recomputed"]
    if (
        review["status"] != "PASS"
        or review["run_manifest_sha256"] != PARENT_W7_MANIFEST_SHA256
        or review["boundaries"]["w66_executed"] is not False
        or review["boundaries"]["training_executed"] is not False
        or gain["mean_qpaf_vs_qarf_delta_ndcg10"] < 0.03
        or gain["qpaf_vs_qarf_ci95"][0] <= 0
        or gain["qpaf_vs_qarf_top_5pct_gain_share"] >= 0.90
    ):
        raise ValueError("Parent exploratory-24 W7 continuation evidence is invalid")
    if (
        evidence["retrieval_score_sha256"]
        != proposal["input"]["retrieval_scores_byte_sha256"]
    ):
        raise ValueError("Exploratory-24 W66 retrieval score hash drift")
    return {
        "status": "PASS",
        "classification": "read_only_w66_preflight_not_result",
        "base_preflight": evidence,
        "parent_w7_review_sha256": PARENT_W7_REVIEW_SHA256,
        "parent_w7_manifest_sha256": PARENT_W7_MANIFEST_SHA256,
        "query_list_sha256": QUERY_LIST_SHA256,
        "grid": GRID_NAME,
        "profile_count": PROFILE_COUNT,
        "profiles_canonical_sha256": PROFILES_SHA256,
        "queries": QUERY_COUNT,
        "pages_per_query": PAGES_PER_QUERY,
        "candidate_pairs": QUERY_COUNT * PAGES_PER_QUERY,
        "resource_budget_status": config["resource_budget_status"],
        "approved_wall_timeout_seconds": config["total_wall_timeout_seconds"],
        "authorized_invocations": config["invocations"],
        "actual_relevance_loaded": False,
        "w66_oracle_executed": False,
        "scientific_result_produced": False,
        "execution_authorized": config["authorization"]["execution_authorized"],
        "attempt_exists": (root / OUTPUT_PATH).exists(),
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
        "schema_version": pilot.sharded.CHECKPOINT_SCHEMA_VERSION,
        "classification": "query_sharded_w66_oracle_checkpoint_identity",
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": protocol_sha256,
        "source_commit": source_commit,
        "retrieval_score_sha256": retrieval_score_sha256,
        "retrieval_score_content_sha256": retrieval_score_content_sha256,
        "query_order_sha256": pilot.sharded._value_sha256(
            [list(key) for key in query_order]
        ),
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
        "bootstrap_unit": "query",
        "bootstrap_seed": SEED,
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_confidence": 0.95,
        "bootstrap_interval": "percentile",
    }


def select_global_profile(
    global_payloads: list[dict[str, Any]], profiles: np.ndarray
) -> tuple[int, list[RankingMetrics]]:
    per_profile = [
        [
            pilot.sharded._validate_metric_dict(
                payload["profile_metrics"][profile_index],
                f"global profile {profile_index}",
            )
            for payload in global_payloads
        ]
        for profile_index in range(len(profiles))
    ]
    best_index = 0
    best_per_query = per_profile[0]
    best_mean = _mean_metrics(best_per_query)
    for profile_index in range(1, len(per_profile)):
        candidate_mean = _mean_metrics(per_profile[profile_index])
        if _better_metrics(candidate_mean, best_mean):
            best_index = profile_index
            best_per_query = per_profile[profile_index]
            best_mean = candidate_mean
    return best_index, best_per_query


def query_result_row(
    frame: pd.DataFrame,
    profiles: np.ndarray,
    global_profile_index: int,
    global_query_metrics: Any,
) -> dict[str, Any]:
    item = pilot.sharded._query_item(frame)
    score_matrix = item["score_matrix"]
    relevance = item["relevance"]
    page_ids = item["page_ids"]
    query_profile, query_scores, query_metrics = _query_oracle(
        score_matrix, relevance, page_ids, profiles
    )
    assignments, _, candidate_metrics, changes = _candidate_oracle(
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
    input_sha256 = pilot.sharded.dataframe_sha256(
        frame, sort_by=["dataset", "query_id", "page_id"]
    )
    if path.exists():
        payload, content_sha256 = pilot.sharded._read_checkpoint(
            path,
            kind="w66_global_profile_metrics",
            run_identity_sha256=run_identity_sha256,
        )
        reused = True
    else:
        item = pilot.sharded._query_item(frame)
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
        content_sha256 = pilot.sharded._write_checkpoint(
            path,
            kind="w66_global_profile_metrics",
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
            raise ValueError(f"W66 Global checkpoint {field} mismatch for {query_key}")
    metrics = payload.get("profile_metrics")
    if not isinstance(metrics, list) or len(metrics) != len(profiles):
        raise ValueError(
            f"W66 Global checkpoint profile count mismatch for {query_key}"
        )
    for profile_index, value in enumerate(metrics):
        pilot.sharded._validate_metric_dict(
            value, f"W66 global profile {profile_index}"
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
    input_sha256 = pilot.sharded.dataframe_sha256(
        frame, sort_by=["dataset", "query_id", "page_id"]
    )
    if path.exists():
        payload, content_sha256 = pilot.sharded._read_checkpoint(
            path,
            kind="w66_query_oracle_result",
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
        content_sha256 = pilot.sharded._write_checkpoint(
            path,
            kind="w66_query_oracle_result",
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
            raise ValueError(f"W66 query checkpoint {field} mismatch for {query_key}")
    row = payload.get("row")
    if not isinstance(row, dict):
        raise ValueError(f"W66 query checkpoint row is invalid for {query_key}")
    if (
        row.get("dataset") != query_key[0]
        or row.get("query_id") != query_key[1]
        or row.get("grid") != GRID_NAME
    ):
        raise ValueError(
            f"W66 query checkpoint result identity mismatch for {query_key}"
        )
    for name in ("global_metrics", "qarf_metrics", "qpaf_metrics"):
        pilot.sharded._validate_metric_dict(row.get(name), name)
    return row, content_sha256, reused


def checkpoint_inventory(directory: Path, expected_count: int, label: str) -> None:
    expected = {f"{index:06d}.json" for index in range(expected_count)}
    actual = (
        {path.name for path in directory.iterdir()} if directory.exists() else set()
    )
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(
            f"{label} checkpoint inventory mismatch; "
            f"missing={missing[:3]}, unexpected={unexpected[:3]}"
        )


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
        raise ValueError("Query-sharded W66 requires at least one query")
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
            "Query-sharded W66 run identity does not match frozen semantics"
        )
    identity_sha256 = pilot.sharded._value_sha256(run_identity)
    plan_path = checkpoint_root / "run_plan.json"
    if plan_path.exists():
        plan, _ = pilot.sharded._read_checkpoint(
            plan_path,
            kind="w66_run_plan",
            run_identity_sha256=identity_sha256,
        )
        if plan != run_identity:
            raise ValueError("W66 checkpoint run plan does not match the requested run")
        plan_reused = 1
    else:
        pilot.sharded._write_checkpoint(
            plan_path,
            kind="w66_run_plan",
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
            raise ValueError("W66 Global pass query sequence is not canonical")
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
        raise ValueError("W66 Global pass did not cover every query")
    checkpoint_inventory(global_directory, len(query_order), "W66 Global")

    global_profile_index, global_query_metrics = select_global_profile(
        global_payloads, profiles
    )
    selection_payload = {
        "profile_index": global_profile_index,
        "profile": profiles[global_profile_index].astype(float).tolist(),
        "global_checkpoint_chain_sha256": pilot.sharded._value_sha256(global_hashes),
    }
    selection_path = checkpoint_root / "global_selection.json"
    if selection_path.exists():
        observed, global_selection_sha256 = pilot.sharded._read_checkpoint(
            selection_path,
            kind="w66_global_profile_selection",
            run_identity_sha256=identity_sha256,
        )
        if observed != selection_payload:
            raise ValueError("W66 Global profile selection checkpoint mismatch")
        selection_reused = 1
    else:
        global_selection_sha256 = pilot.sharded._write_checkpoint(
            selection_path,
            kind="w66_global_profile_selection",
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
            raise ValueError("W66 query-oracle pass sequence is not canonical")
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
        raise ValueError("W66 query-oracle pass did not cover every query")
    checkpoint_inventory(query_directory, len(query_order), "W66 query")

    summary = pilot.exploratory_summary(rows, n_bootstrap)
    summary.update(
        {
            "classification": CLASSIFICATION,
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
            frame = pilot.sharded._validate_query_frame(selected, key, pages)
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
                f"W66 {timings[-1]['pass']} {index + 1}/{len(query_order)}: "
                f"{elapsed:.3f}s",
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


def worker(
    root: Path, config: dict[str, Any], output: Path, identity_hash: str
) -> None:
    evidence = preflight(root, config)
    proposal = read_json(root / PROPOSAL_PATH)
    selected = selected_queries(root)
    order = [(query["dataset"], query["query_id"]) for query in selected]
    scores = pd.read_parquet(
        root / proposal["input"]["retrieval_scores_path"],
        filters=[
            [("dataset", "=", dataset), ("query_id", "=", query_id)]
            for dataset, query_id in order
        ],
    )
    if len(scores) != QUERY_COUNT * PAGES_PER_QUERY:
        raise ValueError("Exploratory-24 W66 subset pair count mismatch")
    identity = build_run_identity(
        protocol_sha256=identity_hash,
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
    if (
        len(rows) != QUERY_COUNT
        or [(row["dataset"], row["query_id"]) for row in rows] != order
    ):
        raise ValueError("Exploratory-24 W66 result query coverage mismatch")
    for name, value in {
        "preflight.json": evidence,
        "per_query.json": {"classification": CLASSIFICATION, "rows": rows},
        "summary.json": summary,
        "timings.json": {"timings": timings},
        "checkpoint_stats.json": stats,
    }.items():
        pilot.sharded._write_json_atomic_create_once(output / name, value)


def run(root: Path, config: dict[str, Any], actor: str) -> Path:
    started = time.monotonic()
    require_approval(config, actor)
    validate_config(root, config)
    output = root / OUTPUT_PATH
    output.mkdir(parents=True, exist_ok=False)
    config_hash = pilot.sharded._value_sha256(config)
    pilot.sharded._write_json_atomic_create_once(
        output / "_ATTEMPTED.json",
        {
            "started_at": pilot.utc_now(),
            "protocol_id": PROTOCOL_ID,
            "classification": CLASSIFICATION,
            "config_sha256": config_hash,
            "execution_actor": actor,
            "consumed_invocations": 1,
            "remaining_authorized_invocations": 0,
        },
    )
    process = None
    timeout = config["total_wall_timeout_seconds"]
    try:
        pilot.sharded._write_json_atomic_create_once(
            output / "resolved_config.json", config
        )
        snapshot = output / "source_snapshot"
        for relative in config["source_sha256"]:
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write((root / relative).read_bytes())
        with (output / "tracked_changes.patch").open("xb") as handle:
            subprocess.run(
                ["git", "diff", "--binary", "HEAD"],
                cwd=root,
                stdout=handle,
                check=True,
            )
        process = mp.get_context("spawn").Process(
            target=worker, args=(root, config, output, config_hash)
        )
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError(
                "Exploratory-24 W66 deadline expired before worker start"
            )
        pilot.safeguards.complete_process_with_timeout(process, remaining)
        required = (
            "preflight.json",
            "per_query.json",
            "summary.json",
            "timings.json",
            "checkpoint_stats.json",
        )
        for name in required:
            if not (output / name).is_file():
                raise RuntimeError(f"Exploratory-24 W66 worker did not finish: {name}")
        if len(read_json(output / "per_query.json")["rows"]) != QUERY_COUNT:
            raise ValueError(
                "Refusing an exploratory-24 W66 result with missing queries"
            )
        hashes = {
            path.relative_to(output).as_posix(): pilot.safeguards.file_sha256(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        elapsed = time.monotonic() - started
        if elapsed >= timeout:
            raise TimeoutError(
                "Exploratory-24 W66 deadline expired during finalization"
            )
        pilot.sharded._write_json_atomic_create_once(
            output / "run_manifest.json",
            {
                "status": "COMPLETE",
                "classification": CLASSIFICATION,
                "completed_at": pilot.utc_now(),
                "elapsed_seconds": elapsed,
                "protocol_id": PROTOCOL_ID,
                "config_sha256": config_hash,
                "source_commit": git_head(root),
                "source_snapshot_required": True,
                "execution_actor": actor,
                "environment": config["environment"],
                "platform": platform.platform(),
                "python_executable": sys.executable,
                "threads": {
                    name: os.environ[name] for name in pilot.safeguards.CPU_THREAD_ENV
                },
                "grid": GRID_NAME,
                "profile_count": PROFILE_COUNT,
                "profiles_canonical_sha256": PROFILES_SHA256,
                "query_list_sha256": QUERY_LIST_SHA256,
                "queries": QUERY_COUNT,
                "pages_per_query": PAGES_PER_QUERY,
                "parent_w7_review_sha256": PARENT_W7_REVIEW_SHA256,
                "parent_w7_manifest_sha256": PARENT_W7_MANIFEST_SHA256,
                "artifact_sha256": hashes,
                "frozen_p1_02_status": "BLOCKED",
                "phase1_decision": "NOT_APPLICABLE_EXPLORATORY_W66_SUBSET",
                "exploratory_w66_executed": True,
                "formal_p1_03_executed": False,
                "modal_gpu_used": False,
                "training_executed": False,
                "remaining_authorized_invocations": 0,
                "independent_result_review_required": True,
            },
        )
    except BaseException as error:
        if process is not None and process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
        pilot.sharded._write_json_atomic_create_once(
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
