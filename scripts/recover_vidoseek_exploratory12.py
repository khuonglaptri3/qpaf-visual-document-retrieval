"""Separately authorized, create-once recovery of the interrupted exploratory pilot."""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import time
from typing import Any

from oracle_study import vidoseek_exploratory12 as pilot

CONFIG_PATH = "configs/vidoseek_exploratory12_recovery_v1.json"
SCRIPT_PATH = "scripts/recover_vidoseek_exploratory12.py"
OUTPUT_PATH = "runs/vidoseek_exploratory12_recovery_v1"
REVIEW_PATH = "artifacts/vidoseek_exploratory12_interruption_review_20260907/checkpoint_integrity_review.json"
RECOVERY_ID = "vidoseek_exploratory12_recovery_v1"
TIMEOUT_SECONDS = 21600
INHERITED_QUERIES = 4
sha256 = pilot.safeguards.file_sha256
read_json = pilot.read_json
write_json = pilot.sharded._write_json_atomic_create_once


def inventory(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def require_approval(config: dict[str, Any], actor: str) -> None:
    approval = config["authorization"]
    if (
        approval.get("recovery_adopted") is not True
        or approval.get("execution_authorized") is not True
        or approval.get("approved_by") != "user"
        or actor not in {"codex", "human"}
        or approval.get("execution_actor") != actor
        or not approval.get("approval_text")
        or not approval.get("approved_at")
    ):
        raise PermissionError(
            "Separate recovery approval is pending; no attempt consumed"
        )
    if any(os.environ.get(name) != "1" for name in pilot.safeguards.CPU_THREAD_ENV):
        raise RuntimeError("Recovery CPU thread limits must all be one")


def validate_config(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "recovery_id": RECOVERY_ID,
        "parent_output_path": pilot.OUTPUT_PATH,
        "output_path": OUTPUT_PATH,
        "review_path": REVIEW_PATH,
        "total_wall_timeout_seconds": TIMEOUT_SECONDS,
        "workers": 1,
        "threads_per_library": 1,
        "invocations": 1,
        "automatic_retries": 0,
        "inherited_queries": INHERITED_QUERIES,
        "new_queries": pilot.QUERY_COUNT - INHERITED_QUERIES,
    }
    for key, value in expected.items():
        if config.get(key) != value or type(config.get(key)) is not type(value):
            raise ValueError(f"Recovery scope drift: {key}")
    if sha256(root / SCRIPT_PATH) != config["runner_sha256"]:
        raise ValueError("Recovery runner source drift")
    if sha256(root / REVIEW_PATH) != config["review_sha256"]:
        raise ValueError("Interruption review drift")
    review = read_json(root / REVIEW_PATH)
    if (
        review["audit_status"] != "PASS_SAVED_CHECKPOINTS_ONLY"
        or review["verified_query_checkpoints"] != INHERITED_QUERIES
        or review["verified_global_checkpoints"] != pilot.QUERY_COUNT
        or not all(value is True for value in review["checks"].values())
    ):
        raise ValueError("Parent checkpoint review is not valid")
    parent = root / pilot.OUTPUT_PATH
    if inventory(parent) != review["artifact_sha256"]:
        raise ValueError("Parent artifact inventory/hash drift")
    original = read_json(parent / "resolved_config.json")
    proposal = pilot.validate_config(root, original)
    original_hash = pilot.sharded._value_sha256(original)
    if original_hash != review["config_canonical_sha256"]:
        raise ValueError("Parent config identity drift")
    if original != read_json(root / pilot.CONFIG_PATH):
        raise ValueError("Current parent config differs from executed snapshot")
    attempt = read_json(parent / "_ATTEMPTED.json")
    if (
        attempt["remaining_authorized_invocations"] != 0
        or attempt["consumed_invocations"] != 1
    ):
        raise ValueError("Parent invocation must be consumed")
    if attempt["config_sha256"] != original_hash:
        raise ValueError("Parent attempt config identity drift")
    plan = read_json(parent / "checkpoints/run_plan.json")["payload"]
    identity = pilot.sharded._value_sha256(plan)
    order = [(q["dataset"], q["query_id"]) for q in proposal["selection"]["queries"]]
    expected_plan = pilot.sharded.build_run_identity(
        protocol_id=pilot.PROTOCOL_ID,
        protocol_sha256=original_hash,
        source_commit=original["base_git_commit"],
        retrieval_score_sha256=proposal["input"]["retrieval_scores_byte_sha256"],
        retrieval_score_content_sha256=plan["retrieval_score_content_sha256"],
        query_order=order,
        pages_per_query=pilot.PAGES_PER_QUERY,
        bootstrap_resamples=pilot.BOOTSTRAP_RESAMPLES,
    )
    if plan != expected_plan or identity != review["run_identity_sha256"]:
        raise ValueError("Parent checkpoint science identity drift")
    kinds = {
        "run_plan.json": "run_plan",
        "global_selection.json": "global_profile_selection",
    }
    kinds.update(
        {
            f"global/{i:06d}.json": "global_profile_metrics"
            for i in range(pilot.QUERY_COUNT)
        }
    )
    kinds.update(
        {
            f"queries/{i:06d}.json": "query_oracle_result"
            for i in range(INHERITED_QUERIES)
        }
    )
    if set(inventory(parent / "checkpoints")) != set(kinds):
        raise ValueError("Parent checkpoint inventory is not the reviewed subset")
    for name, kind in kinds.items():
        pilot.sharded._validate_checkpoint_envelope(
            read_json(parent / "checkpoints" / name),
            kind=kind,
            run_identity_sha256=identity,
        )
    return review


def preflight(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    review = validate_config(root, config)
    original = read_json(root / pilot.OUTPUT_PATH / "resolved_config.json")
    base = pilot.preflight(root, original)
    return {
        "status": "PASS",
        "classification": "read_only_recovery_preflight_not_result",
        "inherited_queries": INHERITED_QUERIES,
        "missing_queries": pilot.QUERY_COUNT - INHERITED_QUERIES,
        "parent_run_identity_sha256": review["run_identity_sha256"],
        "original_preflight": base,
        "actual_relevance_loaded": False,
        "scientific_result_produced": False,
    }


def copy_parent(root: Path, output: Path, review: dict[str, Any]) -> None:
    """Copy verified bytes to new evidence and checkpoint directories; never move/link."""
    parent = root / pilot.OUTPUT_PATH
    for relative, expected in review["artifact_sha256"].items():
        source = parent / relative
        if (
            not source.resolve().is_relative_to(parent.resolve())
            or sha256(source) != expected
        ):
            raise ValueError(f"Parent changed before copy: {relative}")
        destination = output / "parent_snapshot" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(source.read_bytes())
        if sha256(destination) != expected:
            raise ValueError(f"Parent changed during copy: {relative}")
    shutil.copytree(output / "parent_snapshot/checkpoints", output / "checkpoints")


def check_inherited(output: Path) -> dict[str, str]:
    inherited = inventory(output / "parent_snapshot/checkpoints")
    for relative, expected in inherited.items():
        if sha256(output / "checkpoints" / relative) != expected:
            raise ValueError(f"Inherited checkpoint changed: {relative}")
    return inherited


def worker(root: Path, config: dict[str, Any], output: Path) -> None:
    preflight(root, config)
    original = read_json(output / "parent_snapshot/resolved_config.json")
    check_inherited(output)
    # The new authorization wraps the existing worker, not the consumed run launcher.
    pilot.worker(root, original, output, pilot.sharded._value_sha256(original))
    inherited = check_inherited(output)
    timings = read_json(output / "timings.json")["timings"]
    # Raw timings.json measures this invocation, including validation of reused work.
    labeled = []
    for entry in timings:
        row = dict(entry)
        pass_index = len(labeled) % pilot.QUERY_COUNT
        directory = "global" if entry["pass"] == "global" else "queries"
        row["checkpoint_reused"] = f"{directory}/{pass_index:06d}.json" in inherited
        row["measurement_scope"] = (
            "recovery_checkpoint_validation"
            if row["checkpoint_reused"]
            else "recovery_new_query_search_and_checkpoint"
        )
        row["original_search_seconds"] = None
        labeled.append(row)
    write_json(
        output / "recovery_timings.json",
        {
            "timings": labeled,
            "original_search_timings": "not_reconstructed; original progress log retained separately",
        },
    )


def validate_outputs(output: Path) -> None:
    for name in (
        "per_query.json",
        "summary.json",
        "timings.json",
        "preflight.json",
        "recovery_timings.json",
    ):
        if not (output / name).is_file():
            raise RuntimeError(f"Recovery worker did not finish: {name}")
    original_proposal = read_json(
        output / "parent_snapshot/source_snapshot" / pilot.PROPOSAL_PATH
    )
    order = [
        (q["dataset"], q["query_id"]) for q in original_proposal["selection"]["queries"]
    ]
    rows = read_json(output / "per_query.json")["rows"]
    if (
        len(rows) != pilot.QUERY_COUNT
        or [(r["dataset"], r["query_id"]) for r in rows] != order
    ):
        raise ValueError("Recovery result query coverage mismatch")
    check_inherited(output)
    expected = {f"{i:06d}.json" for i in range(pilot.QUERY_COUNT)}
    if {p.name for p in (output / "checkpoints/queries").iterdir()} != expected:
        raise ValueError("Recovery checkpoint coverage mismatch")
    summary = read_json(output / "summary.json")
    if (
        summary.get("phase1_decision") != "NOT_APPLICABLE_EXPLORATORY_SUBSET"
        or summary.get("training_authorized") is not False
        or "discovery_gate" in summary
    ):
        raise ValueError("Recovery must not produce a formal phase decision")
    timings = read_json(output / "recovery_timings.json")["timings"]
    if (
        len(timings) != pilot.QUERY_COUNT * 2
        or sum(t["checkpoint_reused"] for t in timings)
        != pilot.QUERY_COUNT + INHERITED_QUERIES
    ):
        raise ValueError("Recovery timing/reuse coverage mismatch")


def run(root: Path, config: dict[str, Any], actor: str) -> Path:
    started = time.monotonic()
    require_approval(config, actor)  # Refuse before input access or writes.
    review = validate_config(root, config)
    output = root / OUTPUT_PATH
    output.mkdir(parents=True, exist_ok=False)  # Any old attempt blocks a second one.
    config_hash = pilot.sharded._value_sha256(config)
    write_json(
        output / "_ATTEMPTED.json",
        {
            "recovery_id": RECOVERY_ID,
            "started_at": pilot.utc_now(),
            "config_sha256": config_hash,
            "execution_actor": actor,
            "consumed_invocations": 1,
            "remaining_authorized_invocations": 0,
            "parent_run_identity_sha256": review["run_identity_sha256"],
        },
    )
    process = None
    try:
        write_json(output / "resolved_config.json", config)
        copy_parent(root, output, review)
        for relative in (SCRIPT_PATH, REVIEW_PATH):
            destination = output / "recovery_source_snapshot" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write((root / relative).read_bytes())
        process = mp.get_context("spawn").Process(
            target=worker, args=(root, config, output)
        )
        remaining = TIMEOUT_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Recovery deadline expired before worker start")
        pilot.safeguards.complete_process_with_timeout(process, remaining)
        validate_outputs(output)
        if inventory(root / pilot.OUTPUT_PATH) != review["artifact_sha256"]:
            raise ValueError("Original run changed during recovery")
        hashes = inventory(output)
        elapsed = time.monotonic() - started
        if elapsed >= TIMEOUT_SECONDS:
            raise TimeoutError("Recovery deadline expired during finalization")
        original = read_json(output / "parent_snapshot/resolved_config.json")
        write_json(
            output / "run_manifest.json",
            {
                "status": "COMPLETE",
                "classification": pilot.CLASSIFICATION,
                "recovery_id": RECOVERY_ID,
                "completed_at": pilot.utc_now(),
                "elapsed_seconds": elapsed,
                "elapsed_scope": "this_recovery_invocation_only",
                "config_sha256": config_hash,
                "source_commit": original["base_git_commit"],
                "source_snapshot_required": True,
                "environment": original["environment"],
                "parent_config_sha256": review["config_canonical_sha256"],
                "parent_run_identity_sha256": review["run_identity_sha256"],
                "parent_output_path": pilot.OUTPUT_PATH,
                "parent_review_sha256": config["review_sha256"],
                "execution_actor": actor,
                "threads": {
                    name: os.environ[name] for name in pilot.safeguards.CPU_THREAD_ENV
                },
                "queries": pilot.QUERY_COUNT,
                "pages_per_query": pilot.PAGES_PER_QUERY,
                "inherited_queries": INHERITED_QUERIES,
                "new_queries": pilot.QUERY_COUNT - INHERITED_QUERIES,
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
        write_json(
            output / "_INCOMPLETE.json",
            {
                "status": "INCOMPLETE",
                "error_type": type(error).__name__,
                "error": str(error),
                "remaining_authorized_invocations": 0,
                "completed_result_available": False,
            },
        )
        raise
    return output / "run_manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "run"))
    parser.add_argument("--actor", choices=("codex", "human"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = read_json(root / CONFIG_PATH)
    if args.command == "preflight":
        import json

        print(json.dumps(preflight(root, config), indent=2))
    else:
        if args.actor is None:
            parser.error("run requires --actor")
        print(run(root, config, args.actor))


if __name__ == "__main__":
    main()
