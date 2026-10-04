"""Guarded exploratory-24 W7/QARF/QPAF feasibility runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import random
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pandas as pd

from oracle_study import vidoseek_exploratory12 as pilot


PROTOCOL_ID = "vidoseek_p1_02r_w7_exploratory24_v1"
CLASSIFICATION = "exploratory24_subset_oracle_not_full_w7_or_phase_gate"
PROPOSAL_PATH = "docs/05_oracle_experiments/exploratory24/vidoseek_w7_exploratory24_proposal.json"
ORIGINAL_PROPOSAL_PATH = "docs/05_oracle_experiments/exploratory12/vidoseek_w7_exploratory12_proposal.json"
FIXED_AUDIT_REVIEW_PATH = (
    "artifacts/vidoseek_fixed_profile_audit_review/result_integrity_review.json"
)
BASE_PROTOCOL_PATH = "configs/vidoseek_p1_02r_oracle_w7_v1.yaml"
CONFIG_PATH = "configs/vidoseek_w7_exploratory24_v1.json"
SCRIPT_PATH = "scripts/run_vidoseek_exploratory24.py"
OUTPUT_PATH = "runs/vidoseek_w7_exploratory24_v1"
QUERY_LIST_SHA256 = "95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b"
ORIGINAL_PROPOSAL_SHA256 = (
    "ccc0c9469c0ee42e540ece1b5aefc8acf82c3117b8db77affb748799495c08f6"
)
FIXED_AUDIT_REVIEW_SHA256 = (
    "9358ba32f0dd5015685efb34f007abb6bd59ec1ec66668bc6d39b08955eac176"
)
TIMEOUT_SECONDS = 43200
BOOTSTRAP_RESAMPLES = 10000
SEED = 20260820
QUERY_COUNT = 24
PAGES_PER_QUERY = 5385
PACKAGES = ("numpy", "pandas", "pyarrow", "PyYAML")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_paths(root: Path) -> list[str]:
    return sorted(
        [
            p.relative_to(root).as_posix()
            for p in (root / "src/oracle_study").glob("*.py")
        ]
        + [
            SCRIPT_PATH,
            PROPOSAL_PATH,
            ORIGINAL_PROPOSAL_PATH,
            FIXED_AUDIT_REVIEW_PATH,
            BASE_PROTOCOL_PATH,
            "configs/vidoseek_p1_02r.yaml",
        ]
    )


def git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=10
    ).strip()


def canonical_query_hash(queries: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        queries, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def selected_queries(root: Path, proposal: dict[str, Any]) -> list[dict[str, Any]]:
    base = pilot.safeguards.load_protocol(root / BASE_PROTOCOL_PATH)
    audit_path = root / base["input_bundle"]["candidate_audit"]["path"]
    audit = pilot.sharded.query_order_from_audit(audit_path)
    original = read_json(root / ORIGINAL_PROPOSAL_PATH)["selection"]["queries"]
    excluded = {int(query["audit_index"]) for query in original}
    if len(audit) != 1142 or len(excluded) != 12:
        raise ValueError("Exploratory-24 source population mismatch")
    remainder = [index for index in range(len(audit)) if index not in excluded]
    positions = sorted(random.Random(SEED).sample(range(len(remainder)), QUERY_COUNT))
    indices = [remainder[position] for position in positions]
    expected = [
        {"audit_index": index, "dataset": audit[index][0], "query_id": audit[index][1]}
        for index in indices
    ]
    selection = proposal["selection"]
    if positions != selection["sampled_remainder_positions"]:
        raise ValueError("Exploratory-24 remainder positions drift")
    if expected != selection["queries"] or len(set(indices) & excluded) != 0:
        raise ValueError("Exploratory-24 frozen query selection drift")
    return expected


def validate_config(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "protocol_id": PROTOCOL_ID,
        "classification": CLASSIFICATION,
        "proposal_path": PROPOSAL_PATH,
        "base_protocol_path": BASE_PROTOCOL_PATH,
        "output_path": OUTPUT_PATH,
        "total_wall_timeout_seconds": TIMEOUT_SECONDS,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "seed": SEED,
        "queries": QUERY_COUNT,
        "pages_per_query": PAGES_PER_QUERY,
        "workers": 1,
        "threads_per_library": 1,
        "invocations": 1,
        "automatic_retries": 0,
    }
    if set(config) != set(expected) | {
        "base_git_commit",
        "source_sha256",
        "environment",
        "authorization",
    }:
        raise ValueError("Exploratory-24 config fields drift")
    for key, value in expected.items():
        if config.get(key) != value or type(config.get(key)) is not type(value):
            raise ValueError(f"Exploratory-24 scope drift: {key}")
    if git_head(root) != config["base_git_commit"]:
        raise ValueError("Exploratory-24 Git HEAD drift")
    if sorted(config["source_sha256"]) != source_paths(root):
        raise ValueError("Exploratory-24 source inventory drift")
    for relative, expected_hash in config["source_sha256"].items():
        if pilot.safeguards.file_sha256(root / relative) != expected_hash:
            raise ValueError(f"Exploratory-24 source hash drift: {relative}")
    environment = {
        "python": platform.python_version(),
        "packages": {name: version(name) for name in PACKAGES},
    }
    if environment != config["environment"]:
        raise ValueError("Exploratory-24 environment drift")
    proposal = read_json(root / PROPOSAL_PATH)
    queries = selected_queries(root, proposal)
    if (
        canonical_query_hash(queries) != QUERY_LIST_SHA256
        or proposal["selection"]["canonical_query_list_sha256"] != QUERY_LIST_SHA256
    ):
        raise ValueError("Exploratory-24 query-list hash drift")
    return proposal


def require_approval(config: dict[str, Any], actor: str) -> None:
    approval = config["authorization"]
    if (
        approval.get("protocol_adopted") is not True
        or approval.get("execution_authorized") is not True
        or approval.get("approved_by") != "user"
        or approval.get("execution_actor") != actor
        or actor not in {"human", "codex"}
        or not approval.get("approval_text")
        or not approval.get("approved_at")
    ):
        raise PermissionError(
            "Separate exploratory-24 execution approval pending; no attempt consumed"
        )
    if any(os.environ.get(name) != "1" for name in pilot.safeguards.CPU_THREAD_ENV):
        raise RuntimeError("Exploratory-24 requires one thread per numeric library")


def preflight(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    proposal = validate_config(root, config)
    evidence = pilot.safeguards.protocol_bound_preflight(
        root / BASE_PROTOCOL_PATH,
        repo_root=root,
        allow_recorded_probe_evidence=True,
    )
    base = pilot.safeguards.load_protocol(root / BASE_PROTOCOL_PATH)
    audit_path = root / base["input_bundle"]["candidate_audit"]["path"]
    if (
        pilot.safeguards.file_sha256(audit_path)
        != proposal["selection"]["candidate_audit_sha256"]
    ):
        raise ValueError("Exploratory-24 candidate audit hash drift")
    if (
        pilot.safeguards.file_sha256(root / ORIGINAL_PROPOSAL_PATH)
        != ORIGINAL_PROPOSAL_SHA256
        or proposal["selection"]["original12_proposal_sha256"]
        != ORIGINAL_PROPOSAL_SHA256
    ):
        raise ValueError("Original exploratory-12 selection evidence drift")
    if (
        evidence["retrieval_score_sha256"]
        != proposal["input"]["retrieval_scores_byte_sha256"]
    ):
        raise ValueError("Exploratory-24 retrieval score hash drift")
    review = read_json(root / FIXED_AUDIT_REVIEW_PATH)
    if (
        pilot.safeguards.file_sha256(root / FIXED_AUDIT_REVIEW_PATH)
        != FIXED_AUDIT_REVIEW_SHA256
        or proposal["trigger"]["fixed_profile_review_sha256"]
        != FIXED_AUDIT_REVIEW_SHA256
        or review["status"] != "PASS"
        or review["review_advice"] != "HEADROOM_POSSIBLE_REVIEW_COMPUTE"
        or review["qpaf_measured"] is not False
        or review["mean_qpaf_gain_upper_bound"] < review["headroom_threshold"]
    ):
        raise ValueError("Fixed-profile headroom trigger is invalid")
    return {
        "status": "PASS",
        "classification": "read_only_exploratory24_preflight_not_result",
        "base_preflight": evidence,
        "query_list_sha256": QUERY_LIST_SHA256,
        "queries": QUERY_COUNT,
        "pages_per_query": PAGES_PER_QUERY,
        "candidate_pairs": QUERY_COUNT * PAGES_PER_QUERY,
        "excluded_original_queries": 12,
        "trigger_review_sha256": FIXED_AUDIT_REVIEW_SHA256,
        "trigger_headroom_upper_bound": review["mean_qpaf_gain_upper_bound"],
        "actual_relevance_loaded": False,
        "page_level_oracle_executed": False,
        "scientific_result_produced": False,
        "execution_authorized": config["authorization"]["execution_authorized"],
        "attempt_exists": (root / OUTPUT_PATH).exists(),
    }


def worker(
    root: Path, config: dict[str, Any], output: Path, identity_hash: str
) -> None:
    evidence = preflight(root, config)
    proposal = read_json(root / PROPOSAL_PATH)
    selected = proposal["selection"]["queries"]
    order = [(query["dataset"], query["query_id"]) for query in selected]
    scores = pd.read_parquet(
        root / proposal["input"]["retrieval_scores_path"],
        filters=[
            [("dataset", "=", dataset), ("query_id", "=", query_id)]
            for dataset, query_id in order
        ],
    )
    if len(scores) != QUERY_COUNT * PAGES_PER_QUERY:
        raise ValueError("Exploratory-24 subset pair count mismatch")
    identity = pilot.sharded.build_run_identity(
        protocol_id=PROTOCOL_ID,
        protocol_sha256=identity_hash,
        source_commit=config["base_git_commit"],
        retrieval_score_sha256=evidence["base_preflight"]["retrieval_score_sha256"],
        retrieval_score_content_sha256=evidence["base_preflight"][
            "retrieval_score_content_sha256"
        ],
        query_order=order,
        pages_per_query=PAGES_PER_QUERY,
        bootstrap_resamples=BOOTSTRAP_RESAMPLES,
    )
    rows, summary, timings = pilot.evaluate_subset(
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
        raise ValueError("Exploratory-24 result query coverage mismatch")
    summary.update(
        {
            "classification": CLASSIFICATION,
            "global_scope": "selected_exploratory24_queries_only",
        }
    )
    for name, value in {
        "preflight.json": evidence,
        "per_query.json": {"classification": CLASSIFICATION, "rows": rows},
        "summary.json": summary,
        "timings.json": {"timings": timings},
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
                ["git", "diff", "--binary", "HEAD"], cwd=root, stdout=handle, check=True
            )
        process = mp.get_context("spawn").Process(
            target=worker, args=(root, config, output, config_hash)
        )
        remaining = TIMEOUT_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Exploratory-24 deadline expired before worker start")
        pilot.safeguards.complete_process_with_timeout(process, remaining)
        for name in (
            "per_query.json",
            "summary.json",
            "timings.json",
            "preflight.json",
        ):
            if not (output / name).is_file():
                raise RuntimeError(f"Exploratory-24 worker did not finish: {name}")
        if len(read_json(output / "per_query.json")["rows"]) != QUERY_COUNT:
            raise ValueError("Refusing an exploratory-24 result with missing queries")
        hashes = {
            path.relative_to(output).as_posix(): pilot.safeguards.file_sha256(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        elapsed = time.monotonic() - started
        if elapsed >= TIMEOUT_SECONDS:
            raise TimeoutError("Exploratory-24 deadline expired during finalization")
        pilot.sharded._write_json_atomic_create_once(
            output / "run_manifest.json",
            {
                "status": "COMPLETE",
                "classification": CLASSIFICATION,
                "completed_at": pilot.utc_now(),
                "elapsed_seconds": elapsed,
                "protocol_id": PROTOCOL_ID,
                "config_sha256": config_hash,
                "source_commit": config["base_git_commit"],
                "source_snapshot_required": True,
                "execution_actor": actor,
                "environment": config["environment"],
                "platform": platform.platform(),
                "python_executable": sys.executable,
                "threads": {
                    name: os.environ[name] for name in pilot.safeguards.CPU_THREAD_ENV
                },
                "queries": QUERY_COUNT,
                "pages_per_query": PAGES_PER_QUERY,
                "artifact_sha256": hashes,
                "frozen_p1_02_status": "BLOCKED",
                "phase1_decision": "NOT_APPLICABLE_EXPLORATORY_SUBSET",
                "full_w7_executed": False,
                "modal_gpu_used": False,
                "learned_qpaf_executed": False,
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
