"""Guard and run one synthetic W66 resource calibration."""

from __future__ import annotations

import argparse
import ctypes
import json
import multiprocessing as mp
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psutil
import pyarrow as pa
import pyarrow.parquet as pq
from threadpoolctl import threadpool_info, threadpool_limits

from oracle_study import vidoseek_exploratory12 as pilot
from oracle_study.bootstrap import bootstrap_mean_ci, bootstrap_ratio_ci
from oracle_study.profiles import get_profiles

if __package__:
    from . import run_vidoseek_exploratory24_w66 as w66
else:
    import run_vidoseek_exploratory24_w66 as w66


PROTOCOL_ID = "vidoseek_w66_resource_calibration_v1"
CLASSIFICATION = "synthetic_w66_engineering_calibration_not_retrieval_result"
CONFIG_PATH = "configs/vidoseek_w66_resource_calibration_v1.json"
PROPOSAL_PATH = "docs/vidoseek_w66_resource_calibration_proposal.json"
RESOURCE_REVIEW_JSON = "docs/QPAF_W66_RESOURCE_BUDGET_REVIEW.json"
RESOURCE_REVIEW_MD = "docs/QPAF_W66_RESOURCE_BUDGET_REVIEW.md"
EXECUTION_REVIEW_PATH = "docs/QPAF_W66_RESOURCE_CALIBRATION_EXECUTION_REVIEW.md"
PARENT_W7_PROPOSAL_PATH = "docs/vidoseek_w7_exploratory24_proposal.json"
PARENT_W7_REVIEW_PATH = (
    "artifacts/vidoseek_exploratory24_review/result_integrity_review.json"
)
BASE_PROTOCOL_PATH = "configs/vidoseek_p1_02r_oracle_w7_v1.yaml"
SCRIPT_PATH = "scripts/calibrate_vidoseek_w66_resources.py"
W66_SCRIPT_PATH = "scripts/run_vidoseek_exploratory24_w66.py"
OUTPUT_PATH = "runs/vidoseek_w66_resource_calibration_v1"
GRID_NAME = "w66"
PROFILE_COUNT = 66
PROFILES_SHA256 = "c04139858954fd0a7f7baa5dad548f3675a41b8682e9798039508e4077da5973"
QUERY_LIST_SHA256 = "95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b"
CALIBRATION_AUDIT_INDEX = 1129
CALIBRATION_QUERY_ID = "05e2dbaf2d299e33a0e7bf92a434214c84381bf1_5"
PAGES_PER_QUERY = 5385
SYNTHETIC_RELEVANT_INDEX = 2692
LOAD_QUERY_COUNT = 24
LOAD_PAIR_COUNT = 129_240
BOOTSTRAP_SAMPLE_SIZE = 24
BOOTSTRAP_RESAMPLES = 10_000
SEED = 20260820
PROPOSED_TIMEOUT_SECONDS = 21_600
PROCESS_TREE_PRIVATE_BYTES_LIMIT = 2_147_483_648
PRESTART_FREE_PHYSICAL_BYTES_MIN = 4_294_967_296
ABORT_FREE_PHYSICAL_BYTES_BELOW = 2_147_483_648
PRESTART_DISK_FREE_BYTES_MIN = 5_368_709_120
OUTPUT_BYTE_LIMIT = 104_857_600
SAMPLE_INTERVAL_SECONDS = 1
PARENT_DEATH_EXIT_CODE = 70
LOAD_COLUMNS = (
    "dataset",
    "query_id",
    "page_id",
    "source",
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
PREPARATION_STATUS = "PREPARED_CALIBRATION_EXECUTION_CLOSED"
APPROVED_STATUS = "APPROVED_FOR_ONE_CALIBRATION_INVOCATION"
GIT_RULE = "single_non_merge_direct_child_with_exact_changed_paths"
_NUMERIC_THREAD_LIMITER: Any = None


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def value_sha256(value: Any) -> str:
    return pilot.sharded._value_sha256(value)


def file_sha256(path: Path) -> str:
    return pilot.safeguards.file_sha256(path)


def git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=10
    ).strip()


def source_paths(root: Path) -> list[str]:
    return sorted(
        [
            path.relative_to(root).as_posix()
            for path in (root / "src/oracle_study").glob("*.py")
        ]
        + [
            SCRIPT_PATH,
            W66_SCRIPT_PATH,
            PROPOSAL_PATH,
            RESOURCE_REVIEW_JSON,
            RESOURCE_REVIEW_MD,
            EXECUTION_REVIEW_PATH,
            PARENT_W7_PROPOSAL_PATH,
            PARENT_W7_REVIEW_PATH,
            BASE_PROTOCOL_PATH,
            "configs/vidoseek_p1_02r.yaml",
        ]
    )


def selected_queries(root: Path) -> list[dict[str, Any]]:
    parent = read_json(root / PARENT_W7_PROPOSAL_PATH)
    queries = parent["selection"]["queries"]
    if (
        len(queries) != LOAD_QUERY_COUNT
        or w66.canonical_query_hash(queries) != QUERY_LIST_SHA256
        or parent["selection"]["canonical_query_list_sha256"] != QUERY_LIST_SHA256
    ):
        raise ValueError("Frozen exploratory-24 query selection drift")
    selected = [
        query for query in queries if query["audit_index"] == CALIBRATION_AUDIT_INDEX
    ]
    if selected != [
        {
            "audit_index": CALIBRATION_AUDIT_INDEX,
            "dataset": "Qiuchen-Wang/ViDoSeek",
            "query_id": CALIBRATION_QUERY_ID,
        }
    ]:
        raise ValueError("Synthetic calibration query selection drift")
    return queries


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
        raise ValueError("Calibration authorization/resource state drift")
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
            raise ValueError("Calibration preparation Git fields drift")
        return pilot.safeguards.require_exact_git_execution_checkout(
            root,
            approved_parent_commit=record["prepared_parent_commit"],
            approval_commit_changed_paths=record["preparation_commit_changed_paths"],
            execution_label="W66 resource-calibration preparation",
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
        raise ValueError("Calibration approval Git fields drift")
    return pilot.safeguards.require_exact_git_execution_checkout(
        root,
        approved_parent_commit=record["approved_parent_commit"],
        approval_commit_changed_paths=record["approval_commit_changed_paths"],
        execution_label="W66 resource-calibration approval",
    )


def validate_config(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "protocol_id": PROTOCOL_ID,
        "classification": CLASSIFICATION,
        "proposal_path": PROPOSAL_PATH,
        "resource_review_json_path": RESOURCE_REVIEW_JSON,
        "resource_review_markdown_path": RESOURCE_REVIEW_MD,
        "execution_review_path": EXECUTION_REVIEW_PATH,
        "parent_w7_proposal_path": PARENT_W7_PROPOSAL_PATH,
        "parent_w7_result_review_path": PARENT_W7_REVIEW_PATH,
        "base_protocol_path": BASE_PROTOCOL_PATH,
        "w66_runner_path": W66_SCRIPT_PATH,
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
        raise ValueError("Calibration config fields drift")
    for key, value in expected.items():
        if config.get(key) != value or type(config.get(key)) is not type(value):
            raise ValueError(f"Calibration scope drift: {key}")
    if set(config["authorization"]) != {
        "protocol_adopted",
        "resource_budget_approved",
        "execution_authorized",
        "approved_by",
        "execution_actor",
        "approval_text",
        "approved_at",
    }:
        raise ValueError("Calibration authorization fields drift")
    state = _approval_state(config)
    live_commit = require_git_provenance(root, config, state)

    approval_git = config["approval_git"]
    if state == "closed" and approval_git != {
        "approved_parent_commit": None,
        "approval_commit_rule": GIT_RULE,
        "approval_commit_changed_paths": [
            CONFIG_PATH,
            EXECUTION_REVIEW_PATH,
        ],
    }:
        raise ValueError("Closed calibration approval Git state drift")

    if sorted(config["source_sha256"]) != source_paths(root):
        raise ValueError("Calibration source inventory drift")
    for relative, expected_hash in config["source_sha256"].items():
        if file_sha256(root / relative) != expected_hash:
            raise ValueError(f"Calibration source hash drift: {relative}")
    environment = {
        "python": platform.python_version(),
        "packages": {name: version(name) for name in PACKAGES},
    }
    if config["environment"] != environment:
        raise ValueError("Calibration Python/package environment drift")

    proposal = read_json(root / PROPOSAL_PATH)
    if (
        proposal.get("protocol_id") != PROTOCOL_ID
        or proposal.get("status") != "PREPARED_EXECUTION_CLOSED"
        or proposal.get("execution_authorized") is not False
        or proposal["selection"]["audit_index"] != CALIBRATION_AUDIT_INDEX
        or proposal["selection"]["query_id"] != CALIBRATION_QUERY_ID
        or proposal["synthetic_relevance"]["sorted_page_index"]
        != SYNTHETIC_RELEVANT_INDEX
        or proposal["resources"]["proposed_wall_timeout_seconds"]
        != PROPOSED_TIMEOUT_SECONDS
    ):
        raise ValueError("Calibration proposal drift")
    review = read_json(root / RESOURCE_REVIEW_JSON)
    calibration = review["minimal_calibration_proposal"]
    if (
        review["decision"] != "NO_GO_FULL_W66_PENDING_CALIBRATION_AND_RESOURCE_GUARDS"
        or calibration["protocol_id"] != PROTOCOL_ID
        or calibration["audit_index"] != CALIBRATION_AUDIT_INDEX
        or calibration["query_id"] != CALIBRATION_QUERY_ID
        or calibration["proposed_wall_timeout_seconds"] != PROPOSED_TIMEOUT_SECONDS
        or calibration["currently_authorized_invocations"] != 0
    ):
        raise ValueError("W66 resource-review evidence drift")
    selected_queries(root)
    profiles = get_profiles(GRID_NAME)
    if (
        profiles.shape != (PROFILE_COUNT, 3)
        or value_sha256(profiles.tolist()) != PROFILES_SHA256
    ):
        raise ValueError("W66 profile grid drift")
    return {"state": state, "live_commit": live_commit, "proposal": proposal}


def require_approval(config: dict[str, Any], actor: str) -> None:
    try:
        state = _approval_state(config)
    except (KeyError, TypeError, ValueError):
        state = "closed"
    approval = config.get("authorization", {})
    if state != "approved" or approval.get("execution_actor") != actor:
        raise PermissionError(
            "Separate synthetic W66 calibration approval pending; no attempt consumed"
        )
    if actor not in {"human", "codex"}:
        raise PermissionError("Invalid synthetic W66 calibration actor")
    if any(os.environ.get(name) != "1" for name in pilot.safeguards.CPU_THREAD_ENV):
        raise RuntimeError(
            "Synthetic W66 calibration requires one numeric-library thread"
        )


def host_snapshot(root: Path, output: Path) -> dict[str, Any]:
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(root)
    return {
        "observed_at": utc_now(),
        "free_physical_bytes": int(memory.available),
        "total_physical_bytes": int(memory.total),
        "disk_free_bytes": int(disk.free),
        "output_exists": output.exists(),
    }


def enforce_admission(snapshot: dict[str, Any], config: dict[str, Any]) -> None:
    if snapshot["output_exists"]:
        raise FileExistsError("Synthetic W66 calibration output already exists")
    if snapshot["free_physical_bytes"] < config["prestart_free_physical_bytes_min"]:
        raise RuntimeError(
            "Insufficient free physical memory for calibration admission"
        )
    if snapshot["disk_free_bytes"] < config["prestart_disk_free_bytes_min"]:
        raise RuntimeError("Insufficient free disk space for calibration admission")


def preflight(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    validate_config(root, config)
    evidence = pilot.safeguards.protocol_bound_preflight(
        root / BASE_PROTOCOL_PATH,
        repo_root=root,
        allow_recorded_probe_evidence=True,
    )
    parent = read_json(root / PARENT_W7_PROPOSAL_PATH)
    score_path = root / parent["input"]["retrieval_scores_path"]
    schema_names = pq.ParquetFile(score_path).schema_arrow.names
    if (
        evidence["retrieval_score_sha256"]
        != parent["input"]["retrieval_scores_byte_sha256"]
        or any(column not in schema_names for column in LOAD_COLUMNS)
        or "relevance" in LOAD_COLUMNS
    ):
        raise ValueError("Calibration score input/schema drift")
    snapshot = host_snapshot(root, root / OUTPUT_PATH)
    return {
        "status": "PASS",
        "classification": "read_only_synthetic_calibration_preflight_not_result",
        "base_preflight": evidence,
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
        "host_snapshot": snapshot,
        "admission_thresholds_currently_met": (
            not snapshot["output_exists"]
            and snapshot["free_physical_bytes"]
            >= config["prestart_free_physical_bytes_min"]
            and snapshot["disk_free_bytes"] >= config["prestart_disk_free_bytes_min"]
        ),
        "attempt_exists": (root / OUTPUT_PATH).exists(),
    }


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def record_stage(path: Path, stage: str, status: str, **details: Any) -> None:
    append_jsonl(
        path,
        {"observed_at": utc_now(), "stage": stage, "status": status, **details},
    )


def output_bytes(output: Path) -> int:
    return sum(path.stat().st_size for path in output.rglob("*") if path.is_file())


def process_identity(pid: int) -> dict[str, Any]:
    process = psutil.Process(pid)
    return {"pid": pid, "create_time": float(process.create_time())}


def parent_identity_alive(identity: dict[str, Any]) -> bool:
    try:
        process = psutil.Process(int(identity["pid"]))
        return (
            process.is_running()
            and abs(float(process.create_time()) - float(identity["create_time"]))
            < 1e-6
        )
    except (psutil.Error, KeyError, TypeError, ValueError):
        return False


def watch_parent(identity: dict[str, Any], stop: threading.Event) -> None:
    while not stop.wait(SAMPLE_INTERVAL_SECONDS):
        if not parent_identity_alive(identity):
            os._exit(PARENT_DEATH_EXIT_CODE)


def private_bytes(process: psutil.Process) -> int:
    info = process.memory_full_info()
    if not hasattr(info, "private"):
        raise RuntimeError("Private-byte telemetry is unavailable")
    return int(info.private)


def resource_sample(root: Path, output: Path) -> dict[str, Any]:
    parent = psutil.Process(os.getpid())
    processes = [parent, *parent.children(recursive=True)]
    seen: set[tuple[int, float]] = set()
    rows = []
    total_private = 0
    for process in processes:
        try:
            identity = (process.pid, float(process.create_time()))
            if identity in seen:
                continue
            seen.add(identity)
            private = private_bytes(process)
            cpu = process.cpu_times()
            rows.append(
                {
                    "pid": process.pid,
                    "create_time": identity[1],
                    "private_bytes": private,
                    "working_set_bytes": int(process.memory_info().rss),
                    "cpu_user_seconds": float(cpu.user),
                    "cpu_system_seconds": float(cpu.system),
                }
            )
            total_private += private
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    memory = psutil.virtual_memory()
    return {
        "observed_at": utc_now(),
        "processes": rows,
        "process_tree_private_bytes": total_private,
        "free_physical_bytes": int(memory.available),
        "output_bytes": output_bytes(output),
        "disk_free_bytes": int(shutil.disk_usage(root).free),
    }


def enforce_resource_sample(sample: dict[str, Any], config: dict[str, Any]) -> None:
    if (
        sample["process_tree_private_bytes"]
        > config["process_tree_private_bytes_limit"]
    ):
        raise MemoryError("Calibration process-tree private-byte limit exceeded")
    if sample["free_physical_bytes"] < config["abort_free_physical_bytes_below"]:
        raise MemoryError("Calibration host free-memory abort threshold crossed")
    if sample["output_bytes"] > config["output_byte_limit"]:
        raise RuntimeError("Calibration output-byte limit exceeded")


def set_worker_thread_limits() -> dict[str, Any]:
    global _NUMERIC_THREAD_LIMITER
    if any(os.environ.get(name) != "1" for name in pilot.safeguards.CPU_THREAD_ENV):
        raise RuntimeError("Worker numeric-library thread environment drift")
    _NUMERIC_THREAD_LIMITER = threadpool_limits(limits=1)
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    np.ones((2, 2), dtype=float) @ np.ones((2, 2), dtype=float)
    pools = threadpool_info()
    if any(int(pool["num_threads"]) != 1 for pool in pools):
        raise RuntimeError("Worker numeric-library runtime pool is not single-threaded")
    if pa.cpu_count() != 1 or pa.io_thread_count() != 1:
        raise RuntimeError("Worker Arrow CPU/I/O pools are not single-threaded")
    return {
        "environment": {
            name: os.environ[name] for name in pilot.safeguards.CPU_THREAD_ENV
        },
        "arrow_cpu_threads": pa.cpu_count(),
        "arrow_io_threads": pa.io_thread_count(),
        "numeric_pools": pools,
    }


def validate_loaded_subset(
    scores: pd.DataFrame, queries: list[dict[str, Any]]
) -> pd.DataFrame:
    if list(scores.columns) != list(LOAD_COLUMNS) or "relevance" in scores:
        raise ValueError("Calibration decoded an unexpected score column")
    if len(scores) != LOAD_PAIR_COUNT:
        raise ValueError("Calibration subset pair count mismatch")
    expected_keys = [(query["dataset"], query["query_id"]) for query in queries]
    observed_keys = list(
        scores[["dataset", "query_id"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    if observed_keys != expected_keys:
        raise ValueError("Calibration subset query order mismatch")
    counts = scores.groupby(["dataset", "query_id"], sort=False).size().tolist()
    if counts != [PAGES_PER_QUERY] * LOAD_QUERY_COUNT:
        raise ValueError("Calibration subset page coverage mismatch")
    numeric = scores[["bm25_score", "dense_score", "visual_score"]].to_numpy(float)
    if (
        not np.isfinite(numeric).all()
        or (numeric < -1e-12).any()
        or (numeric > 1 + 1e-12).any()
    ):
        raise ValueError("Calibration normalized score values drift")
    query = scores.loc[
        (scores["dataset"] == "Qiuchen-Wang/ViDoSeek")
        & (scores["query_id"] == CALIBRATION_QUERY_ID)
    ].sort_values("page_id", kind="stable")
    if len(query) != PAGES_PER_QUERY or query["page_id"].astype(str).duplicated().any():
        raise ValueError("Calibration query page identity drift")
    query = query.reset_index(drop=True).copy()
    query["relevance"] = 0.0
    query.loc[SYNTHETIC_RELEVANT_INDEX, "relevance"] = 1.0
    return pilot.sharded._validate_query_frame(
        query,
        ("Qiuchen-Wang/ViDoSeek", CALIBRATION_QUERY_ID),
        PAGES_PER_QUERY,
    )


def build_identity(
    config: dict[str, Any], evidence: dict[str, Any], source_commit: str
) -> dict[str, Any]:
    return {
        "schema_version": pilot.sharded.CHECKPOINT_SCHEMA_VERSION,
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
        "channel_order": ["bm25_score", "dense_score", "visual_score"],
        "profile_selection_tie_break": ["ndcg10", "recall3", "mrr10"],
        "ranking_tie_break": "ascending_page_id",
        "qpaf_max_sweeps": 2,
        "strict_improvement_tolerance": 1e-12,
        "bootstrap_seed": SEED,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "checkpoint_reuse_into_scientific_run_allowed": False,
    }


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
        raise ValueError("Calibration Global checkpoint unexpectedly pre-existed")
    global_index, global_metrics = w66.select_global_profile([global_payload], profiles)
    selection = {
        "profile_index": global_index,
        "profile": profiles[global_index].astype(float).tolist(),
        "global_checkpoint_content_sha256": global_hash,
        "scope": "one_synthetic_calibration_query_only",
    }
    selection_hash = pilot.sharded._write_checkpoint(
        checkpoint_root / "global_selection.json",
        kind="w66_synthetic_calibration_global_selection",
        run_identity_sha256=identity_sha256,
        payload=selection,
    )

    query_started = time.monotonic()
    row, query_hash, query_reused = w66.query_checkpoint(
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
        raise ValueError("Calibration query checkpoint unexpectedly pre-existed")

    replay_started = time.monotonic()
    _, replay_global_hash, replay_global_reused = w66.global_checkpoint(
        checkpoint_root / "global" / "000000.json",
        run_identity_sha256=identity_sha256,
        query_index=0,
        query_key=key,
        frame=frame,
        profiles=profiles,
    )
    replay_selection, replay_selection_hash = pilot.sharded._read_checkpoint(
        checkpoint_root / "global_selection.json",
        kind="w66_synthetic_calibration_global_selection",
        run_identity_sha256=identity_sha256,
    )
    replay_row, replay_query_hash, replay_query_reused = w66.query_checkpoint(
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
        raise ValueError("Calibration immutable checkpoint replay mismatch")

    return {
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


def run_bootstrap_probe() -> dict[str, Any]:
    values = np.arange(BOOTSTRAP_SAMPLE_SIZE, dtype=float) / (BOOTSTRAP_SAMPLE_SIZE - 1)
    denominator = np.ones(BOOTSTRAP_SAMPLE_SIZE, dtype=float)
    started = time.monotonic()
    mean_ci = bootstrap_mean_ci(values, BOOTSTRAP_RESAMPLES, SEED)
    mean_seconds = time.monotonic() - started
    started = time.monotonic()
    ratio_ci = bootstrap_ratio_ci(values, denominator, BOOTSTRAP_RESAMPLES, SEED)
    ratio_seconds = time.monotonic() - started
    if mean_ci != ratio_ci:
        raise ValueError("Synthetic bootstrap probe functions disagree")
    return {
        "sample_size": BOOTSTRAP_SAMPLE_SIZE,
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": SEED,
        "mean_ci": list(mean_ci),
        "ratio_ci": list(ratio_ci),
        "mean_seconds": mean_seconds,
        "ratio_seconds": ratio_seconds,
    }


def worker(
    root: Path,
    config: dict[str, Any],
    output: Path,
    parent_identity: dict[str, Any],
) -> None:
    stage_log = output / "worker_stages.jsonl"
    stop_watchdog = threading.Event()
    watchdog = threading.Thread(
        target=watch_parent, args=(parent_identity, stop_watchdog), daemon=True
    )
    watchdog.start()
    try:
        record_stage(stage_log, "worker", "STARTED", **process_identity(os.getpid()))
        thread_state = set_worker_thread_limits()
        pilot.sharded._write_json_atomic_create_once(
            output / "worker_thread_state.json", thread_state
        )
        record_stage(stage_log, "thread_limits", "PASS")

        evidence = preflight(root, config)
        pilot.sharded._write_json_atomic_create_once(
            output / "preflight.json", evidence
        )
        record_stage(stage_log, "preflight", "PASS")

        queries = selected_queries(root)
        parent = read_json(root / PARENT_W7_PROPOSAL_PATH)
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
            raise ValueError("Calibration decoded actual relevance")
        record_stage(
            stage_log,
            "input_load",
            "PASS",
            elapsed_seconds=input_load_seconds,
            rows=len(scores),
        )

        frame = validate_loaded_subset(scores, queries)
        del scores, table
        identity = build_identity(config, evidence, git_head(root))
        pilot.sharded._write_checkpoint(
            output / "checkpoints" / "run_plan.json",
            kind="w66_synthetic_calibration_run_plan",
            run_identity_sha256=value_sha256(identity),
            payload=identity,
        )
        search = run_checkpointed_search(frame, identity, output / "checkpoints")
        record_stage(
            stage_log,
            "w66_synthetic_search_and_replay",
            "PASS",
            elapsed_seconds=search["query_oracle_seconds"],
            sweeps_exercised=search["sweeps_exercised"],
        )

        bootstrap = run_bootstrap_probe()
        record_stage(
            stage_log,
            "bootstrap_probe",
            "PASS",
            elapsed_seconds=bootstrap["mean_seconds"] + bootstrap["ratio_seconds"],
        )
        postflight = preflight(root, config)
        if postflight["base_preflight"] != evidence["base_preflight"]:
            raise ValueError("Calibration input identity changed during worker run")
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
        pilot.sharded._write_json_atomic_create_once(
            output / "calibration_result.json", result
        )
        pilot.sharded._write_json_atomic_create_once(
            output / "_WORKER_COMPLETE.json",
            {
                "status": "COMPLETE",
                "calibration_result_sha256": file_sha256(
                    output / "calibration_result.json"
                ),
                "run_identity_sha256": value_sha256(identity),
            },
        )
        record_stage(stage_log, "worker", "COMPLETE")
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
    worker_identity = process_identity(process.pid)
    pilot.sharded._write_json_atomic_create_once(
        output / "process_identity.json",
        {
            "parent": process_identity(os.getpid()),
            "worker": worker_identity,
        },
    )
    telemetry_path = output / "resource_telemetry.jsonl"
    peak_private = 0
    minimum_free = psutil.virtual_memory().available
    maximum_output = output_bytes(output)
    samples = 0
    while process.is_alive():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Synthetic W66 calibration deadline expired")
        sample = resource_sample(root, output)
        enforce_resource_sample(sample, config)
        append_jsonl(telemetry_path, sample)
        peak_private = max(peak_private, sample["process_tree_private_bytes"])
        minimum_free = min(minimum_free, sample["free_physical_bytes"])
        maximum_output = max(maximum_output, sample["output_bytes"])
        samples += 1
        process.join(min(config["sample_interval_seconds"], remaining))
    process.join()
    if process.exitcode != 0:
        raise RuntimeError(
            f"Synthetic W66 calibration worker exit code {process.exitcode}"
        )
    final_sample = resource_sample(root, output)
    enforce_resource_sample(final_sample, config)
    append_jsonl(telemetry_path, final_sample)
    peak_private = max(peak_private, final_sample["process_tree_private_bytes"])
    minimum_free = min(minimum_free, final_sample["free_physical_bytes"])
    maximum_output = max(maximum_output, final_sample["output_bytes"])
    return {
        "samples": samples + 1,
        "peak_process_tree_private_bytes": peak_private,
        "minimum_free_physical_bytes": minimum_free,
        "maximum_observed_output_bytes": maximum_output,
        "worker_identity": worker_identity,
    }


def stop_process(process: mp.Process | None) -> None:
    if process is None or not process.is_alive():
        return
    process.terminate()
    process.join(5)
    if process.is_alive():
        process.kill()
        process.join(5)


def set_sleep_inhibition(enabled: bool) -> bool:
    if os.name != "nt":
        return False
    continuous = 0x80000000
    system_required = 0x00000001
    flags = continuous | system_required if enabled else continuous
    return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))


def run(root: Path, config: dict[str, Any], actor: str) -> Path:
    started = time.monotonic()
    require_approval(config, actor)
    validated = validate_config(root, config)
    output = root / OUTPUT_PATH
    admission = host_snapshot(root, output)
    enforce_admission(admission, config)
    output.mkdir(parents=True, exist_ok=False)
    config_hash = value_sha256(config)
    pilot.sharded._write_json_atomic_create_once(
        output / "_ATTEMPTED.json",
        {
            "started_at": utc_now(),
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
        record_stage(stage_log, "attempt", "STARTED")
        pilot.sharded._write_json_atomic_create_once(
            output / "admission_snapshot.json", admission
        )
        pilot.sharded._write_json_atomic_create_once(
            output / "resolved_config.json", config
        )
        snapshot = output / "source_snapshot"
        for relative, expected_hash in config["source_sha256"].items():
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write((root / relative).read_bytes())
            if file_sha256(destination) != expected_hash:
                raise ValueError("Calibration source changed during snapshot")
        with (output / "tracked_changes.patch").open("xb") as handle:
            subprocess.run(
                ["git", "diff", "--binary", "HEAD"],
                cwd=root,
                stdout=handle,
                check=True,
                timeout=30,
            )
        sleep_inhibited = set_sleep_inhibition(True)
        if os.name == "nt" and not sleep_inhibited:
            raise RuntimeError("Unable to inhibit system sleep for calibration")
        record_stage(stage_log, "admission_and_snapshot", "PASS")

        parent_identity = process_identity(os.getpid())
        process = mp.get_context("spawn").Process(
            target=worker,
            args=(root, config, output, parent_identity),
        )
        deadline = started + config["approved_wall_timeout_seconds"]
        supervision = monitor_worker(process, root, output, config, deadline)
        record_stage(stage_log, "worker_supervision", "PASS")
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
        ):
            raise ValueError("Synthetic W66 calibration completion evidence mismatch")
        final_sample = resource_sample(root, output)
        enforce_resource_sample(final_sample, config)
        elapsed = time.monotonic() - started
        if elapsed >= config["approved_wall_timeout_seconds"]:
            raise TimeoutError(
                "Synthetic W66 calibration deadline expired in finalization"
            )
        record_stage(stage_log, "finalization", "READY")
        hashes = {
            path.relative_to(output).as_posix(): file_sha256(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        pilot.sharded._write_json_atomic_create_once(
            output / "run_manifest.json",
            {
                "status": "COMPLETE",
                "classification": CLASSIFICATION,
                "completed_at": utc_now(),
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
                "actual_relevance_loaded": False,
                "synthetic_relevance_only": True,
                "engineering_calibration_completed": True,
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
        stop_process(process)
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
    finally:
        if sleep_inhibited:
            set_sleep_inhibition(False)
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
