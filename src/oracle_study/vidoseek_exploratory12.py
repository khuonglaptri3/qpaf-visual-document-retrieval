"""Separately guarded exploratory pilot; never a full-discovery phase decision."""

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
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd

from . import vidoseek_p1_02r_oracle as safeguards
from . import vidoseek_p1_02r_sharded as sharded


PROTOCOL_ID = "vidoseek_p1_02r_w7_exploratory12_v1"
CLASSIFICATION = "exploratory_subset_oracle_not_full_w7_or_phase_gate"
PROPOSAL_PATH = "docs/05_oracle_experiments/exploratory12/vidoseek_w7_exploratory12_proposal.json"
BASE_PROTOCOL_PATH = "configs/vidoseek_p1_02r_oracle_w7_v1.yaml"
CONFIG_PATH = "configs/vidoseek_w7_exploratory12_v1.json"
OUTPUT_PATH = "runs/vidoseek_w7_exploratory12_v1"
QUERY_LIST_SHA256 = "03b6480ae76d8de483106ae48e3c3a10da99cdad0812ffe1aa2c54687a2d7a64"
TIMEOUT_SECONDS = 21600
BOOTSTRAP_RESAMPLES = 10000
SEED = 20260820
QUERY_COUNT = 12
PAGES_PER_QUERY = 5385
PACKAGES = ("numpy", "pandas", "pyarrow", "PyYAML")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_paths(root: Path) -> list[str]:
    return sorted(
        [
            p.relative_to(root).as_posix()
            for p in (root / "src/oracle_study").glob("*.py")
        ]
        + [PROPOSAL_PATH, BASE_PROTOCOL_PATH, "configs/vidoseek_p1_02r.yaml"]
    )


def git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


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
    for key, value in expected.items():
        if config.get(key) != value or type(config.get(key)) is not type(value):
            raise ValueError(f"Exploratory protocol drift: {key}")
    if git_head(root) != config["base_git_commit"]:
        raise ValueError("Exploratory base Git commit drift")
    hashes = config["source_sha256"]
    if sorted(hashes) != source_paths(root):
        raise ValueError("Exploratory source inventory drift")
    for relative, expected_hash in hashes.items():
        if safeguards.file_sha256(root / relative) != expected_hash:
            raise ValueError(f"Exploratory source hash drift: {relative}")
    actual_environment = {
        "python": platform.python_version(),
        "packages": {name: version(name) for name in PACKAGES},
    }
    if config["environment"] != actual_environment:
        raise ValueError("Exploratory Python/package environment drift")
    proposal = read_json(root / PROPOSAL_PATH)
    queries = proposal["selection"]["queries"]
    encoded = json.dumps(
        queries, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != QUERY_LIST_SHA256:
        raise ValueError("Frozen exploratory query list drift")
    if proposal["selection"]["canonical_query_list_sha256"] != QUERY_LIST_SHA256:
        raise ValueError("Exploratory query-list hash declaration drift")
    return proposal


def preflight(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    proposal = validate_config(root, config)
    evidence = safeguards.run_cli_preflight(root / BASE_PROTOCOL_PATH)
    base = safeguards.load_protocol(root / BASE_PROTOCOL_PATH)
    audit_path = root / base["input_bundle"]["candidate_audit"]["path"]
    audit = sharded.query_order_from_audit(audit_path)  # ID columns only.
    indices = sorted(random.Random(SEED).sample(range(len(audit)), QUERY_COUNT))
    expected = [
        {"audit_index": i, "dataset": audit[i][0], "query_id": audit[i][1]}
        for i in indices
    ]
    if expected != proposal["selection"]["queries"] or len(audit) != 1142:
        raise ValueError("Exploratory selection differs from frozen candidate audit")
    if (
        safeguards.file_sha256(audit_path)
        != proposal["selection"]["candidate_audit_sha256"]
    ):
        raise ValueError("Exploratory candidate audit hash drift")
    if (
        evidence["retrieval_score_sha256"]
        != proposal["input"]["retrieval_scores_byte_sha256"]
    ):
        raise ValueError("Exploratory retrieval score hash drift")
    return {
        "status": "PASS",
        "classification": "read_only_preflight_not_result",
        "base_preflight": evidence,
        "query_list_sha256": QUERY_LIST_SHA256,
        "queries": QUERY_COUNT,
        "pages_per_query": PAGES_PER_QUERY,
        "actual_relevance_loaded": False,
        "scientific_result_produced": False,
    }


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
            "Exploratory protocol/execution approval is pending; no attempt consumed"
        )
    if any(os.environ.get(name) != "1" for name in safeguards.CPU_THREAD_ENV):
        raise RuntimeError("Exploratory CPU thread limits must all be one")


def exploratory_summary(rows: list[dict[str, Any]], n_bootstrap: int) -> dict[str, Any]:
    summary, _ = sharded.summarize_oracle_rows(rows, n_bootstrap)
    # The shared summary computes formal gates. They are inapplicable to a subset.
    summary.pop("discovery_gate")
    summary.update(
        {
            "classification": CLASSIFICATION,
            "phase1_decision": "NOT_APPLICABLE_EXPLORATORY_SUBSET",
            "training_authorized": False,
            "global_scope": "selected_exploratory_queries_only",
            "confidence_interval_interpretation": "exploratory_query_bootstrap_not_population_proof",
        }
    )
    summary["win_tie_loss"] = {}
    for name in ("delta_qarf_vs_global", "delta_qpaf_vs_qarf"):
        delta = np.asarray([row[name] for row in rows], dtype=float)
        summary["win_tie_loss"][name] = {
            "win": int((delta > 1e-12).sum()),
            "tie": int((np.abs(delta) <= 1e-12).sum()),
            "loss": int((delta < -1e-12).sum()),
        }
    return summary


def evaluate_subset(
    scores: pd.DataFrame,
    query_order: list[tuple[str, str]],
    identity: dict[str, Any],
    checkpoint_root: Path,
    pages: int,
    n_bootstrap: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    timings: list[dict[str, Any]] = []
    pass_number = 0

    def frames() -> Iterator[tuple[int, tuple[str, str], pd.DataFrame]]:
        nonlocal pass_number
        pass_number += 1
        for index, key in enumerate(query_order):
            selected = scores.loc[
                (scores.dataset == key[0]) & (scores.query_id == key[1])
            ]
            frame = sharded._validate_query_frame(selected, key, pages)
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
                f"{timings[-1]['pass']} {index + 1}/{len(query_order)}: {elapsed:.3f}s",
                flush=True,
            )

    rows, _, _, _ = sharded.run_query_sharded_w7(
        query_order=query_order,
        query_frames=frames,
        expected_pages_per_query=pages,
        checkpoint_root=checkpoint_root,
        run_identity=identity,
        n_bootstrap=n_bootstrap,
    )
    return rows, exploratory_summary(rows, n_bootstrap), timings


def worker(
    root: Path, config: dict[str, Any], output: Path, identity_hash: str
) -> None:
    evidence = preflight(root, config)
    proposal = read_json(root / PROPOSAL_PATH)
    selected = proposal["selection"]["queries"]
    order = [(q["dataset"], q["query_id"]) for q in selected]
    # Only after approval, attempt consumption, hash checks, and ID-only selection validation.
    scores = pd.read_parquet(
        root / proposal["input"]["retrieval_scores_path"],
        filters=[
            [("dataset", "=", dataset), ("query_id", "=", query)]
            for dataset, query in order
        ],
    )
    if len(scores) != QUERY_COUNT * PAGES_PER_QUERY:
        raise ValueError("Exploratory subset pair count mismatch")
    identity = sharded.build_run_identity(
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
    rows, summary, timings = evaluate_subset(
        scores,
        order,
        identity,
        output / "checkpoints",
        PAGES_PER_QUERY,
        BOOTSTRAP_RESAMPLES,
    )
    if (
        len(rows) != QUERY_COUNT
        or [(r["dataset"], r["query_id"]) for r in rows] != order
    ):
        raise ValueError("Exploratory result query coverage mismatch")
    for name, value in {
        "preflight.json": evidence,
        "per_query.json": {"classification": CLASSIFICATION, "rows": rows},
        "summary.json": summary,
        "timings.json": {"timings": timings},
    }.items():
        sharded._write_json_atomic_create_once(output / name, value)


def run(root: Path, config: dict[str, Any], actor: str) -> Path:
    started = time.monotonic()
    require_approval(config, actor)  # Closed drafts cause no writes or label reads.
    validate_config(root, config)
    output = root / OUTPUT_PATH
    output.mkdir(
        parents=True, exist_ok=False
    )  # Any prior attempt forbids retry/resume.
    config_hash = sharded._value_sha256(config)
    sharded._write_json_atomic_create_once(
        output / "_ATTEMPTED.json",
        {
            "started_at": utc_now(),
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
        sharded._write_json_atomic_create_once(output / "resolved_config.json", config)
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
        context = mp.get_context("spawn")
        process = context.Process(
            target=worker, args=(root, config, output, config_hash)
        )
        remaining = TIMEOUT_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Exploratory total deadline expired before worker start")
        safeguards.complete_process_with_timeout(process, remaining)
        required = ["per_query.json", "summary.json", "timings.json", "preflight.json"]
        for name in required:
            if not (output / name).is_file():
                raise RuntimeError(f"Exploratory worker did not finish: {name}")
        if len(read_json(output / "per_query.json")["rows"]) != QUERY_COUNT:
            raise ValueError("Refusing a completed result with missing queries")
        hashes = {
            path.relative_to(output).as_posix(): safeguards.file_sha256(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        elapsed = time.monotonic() - started
        if elapsed >= TIMEOUT_SECONDS:
            raise TimeoutError("Exploratory total deadline expired during finalization")
        sharded._write_json_atomic_create_once(
            output / "run_manifest.json",
            {
                "status": "COMPLETE",
                "classification": CLASSIFICATION,
                "completed_at": utc_now(),
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
                    name: os.environ[name] for name in safeguards.CPU_THREAD_ENV
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
            },
        )
    except BaseException as error:
        if process is not None and process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
        sharded._write_json_atomic_create_once(
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
    root = Path(__file__).resolve().parents[2]
    config = read_json(root / CONFIG_PATH)
    if args.command == "preflight":
        print(json.dumps(preflight(root, config), indent=2))
    else:
        if args.actor is None:
            parser.error("run requires --actor")
        print(run(root, config, args.actor))


if __name__ == "__main__":
    main()
