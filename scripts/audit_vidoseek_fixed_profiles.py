"""Separately guarded discovery audit of fixed W7 profiles; no QPAF search."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from oracle_study import vidoseek_p1_02r_oracle as safeguards
from oracle_study import vidoseek_p1_02r_sharded as sharded
from oracle_study.metrics import RankingMetrics, evaluate_scores
from oracle_study.profiles import get_profiles
from oracle_study.qpaf import _better_metrics, _mean_metrics

CONFIG_PATH = "configs/vidoseek_fixed_profile_audit_v1.json"
SCRIPT_PATH = "scripts/audit_vidoseek_fixed_profiles.py"
BASE_PROTOCOL = "configs/vidoseek_p1_02r_oracle_w7_v1.yaml"
OUTPUT_PATH = "runs/vidoseek_fixed_profile_audit_v1"
CLASSIFICATION = "post_hoc_fixed_profile_discovery_headroom_not_qpaf_result"
QUERY_COUNT = 1142
PAGES_PER_QUERY = 5385
TIMEOUT_SECONDS = 1800
CHECKPOINT_KIND = "fixed_w7_profile_metrics"
sha256 = safeguards.file_sha256
value_sha256 = sharded._value_sha256
write_json = sharded._write_json_atomic_create_once


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
        + [SCRIPT_PATH, BASE_PROTOCOL, "configs/vidoseek_p1_02r.yaml"]
    )


def git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=10
    ).strip()


def validate_config(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "protocol_id": "vidoseek_fixed_profile_audit_v1",
        "classification": CLASSIFICATION,
        "base_protocol_path": BASE_PROTOCOL,
        "output_path": OUTPUT_PATH,
        "queries": QUERY_COUNT,
        "pages_per_query": PAGES_PER_QUERY,
        "total_wall_timeout_seconds": TIMEOUT_SECONDS,
        "workers": 1,
        "threads_per_library": 1,
        "invocations": 1,
        "automatic_retries": 0,
        "grid": "w7",
        "profiles": get_profiles("w7").tolist(),
        "channel_order": ["bm25_score", "dense_score", "visual_score"],
        "seed": 20260820,
        "headroom_review_threshold": 0.03,
        "qpaf_search_allowed": False,
        "w66_allowed": False,
        "training_allowed": False,
        "modal_gpu_allowed": False,
    }
    if set(config) != set(expected) | {
        "base_git_commit",
        "source_sha256",
        "environment",
        "authorization",
    }:
        raise ValueError("Audit config fields drift")
    for key, value in expected.items():
        if config.get(key) != value or type(config.get(key)) is not type(value):
            raise ValueError(f"Audit scope drift: {key}")
    if git_head(root) != config["base_git_commit"]:
        raise ValueError("Audit Git HEAD drift")
    if sorted(config["source_sha256"]) != source_paths(root):
        raise ValueError("Audit source inventory drift")
    for relative, expected_hash in config["source_sha256"].items():
        if sha256(root / relative) != expected_hash:
            raise ValueError(f"Audit source hash drift: {relative}")
    environment = {
        "python": platform.python_version(),
        "packages": {
            name: version(name) for name in ("numpy", "pandas", "pyarrow", "PyYAML")
        },
    }
    if environment != config["environment"]:
        raise ValueError("Audit environment drift")
    return safeguards.load_protocol(root / BASE_PROTOCOL)["input_bundle"]


def require_approval(config: dict[str, Any], actor: str) -> None:
    approval = config["authorization"]
    if (
        approval.get("protocol_adopted") is not True
        or approval.get("execution_authorized") is not True
        or approval.get("approved_by") != "user"
        or actor not in {"codex", "human"}
        or approval.get("execution_actor") != actor
        or not approval.get("approval_text")
        or not approval.get("approved_at")
    ):
        raise PermissionError(
            "Separate fixed-profile audit approval pending; no attempt consumed"
        )
    if any(os.environ.get(name) != "1" for name in safeguards.CPU_THREAD_ENV):
        raise RuntimeError("Audit requires one thread per numeric library")
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)


def preflight(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    bundle = validate_config(root, config)
    evidence = safeguards.protocol_bound_preflight(
        root / BASE_PROTOCOL, repo_root=root, allow_recorded_probe_evidence=True
    )
    order = sharded.query_order_from_audit(root / bundle["candidate_audit"]["path"])
    if (
        len(order) != config["queries"]
        or any(d != "Qiuchen-Wang/ViDoSeek" for d, _ in order)
        or bundle["retrieval_scores"]["rows"]
        != config["queries"] * config["pages_per_query"]
    ):
        raise ValueError("Audit population mismatch")
    return {
        "status": "PASS",
        "classification": "read_only_preflight_not_result",
        "base_preflight": evidence,
        "queries": len(order),
        "pages_per_query": config["pages_per_query"],
        "query_order_sha256": value_sha256(order),
        "actual_relevance_loaded": False,
        "scientific_result_produced": False,
        "execution_authorized": config["authorization"]["execution_authorized"],
        "attempt_exists": (root / OUTPUT_PATH).exists(),
    }


def iter_queries(
    path: Path, order: list[tuple[str, str]], pages: int
) -> Iterator[pd.DataFrame]:
    """Stream bounded Arrow batches, yielding one complete query at a time."""
    pending = pd.DataFrame()
    observed = 0
    corpus_ids = None
    for batch in pq.ParquetFile(path).iter_batches(batch_size=pages, use_threads=False):
        frame = pd.concat(
            [pending, batch.to_pandas(use_threads=False)], ignore_index=True
        )
        while len(frame) >= pages:
            if observed >= len(order):
                raise ValueError("Unexpected extra query rows")
            query = sharded._validate_query_frame(
                frame.iloc[:pages], order[observed], pages
            )
            ids = query.page_id.astype(str).to_numpy()
            if corpus_ids is None:
                corpus_ids = ids.copy()
            elif not np.array_equal(corpus_ids, ids):
                raise ValueError("Query candidate corpus differs")
            scores = query[["bm25_score", "dense_score", "visual_score"]].to_numpy(
                float
            )
            if (scores < -1e-12).any() or (scores > 1 + 1e-12).any():
                raise ValueError("Normalized score range mismatch")
            if (query.relevance < 0).any() or not (query.relevance > 0).any():
                raise ValueError("Invalid or uncovered relevance")
            yield query
            observed += 1
            frame = frame.iloc[pages:]
        pending = frame.copy()
    if len(pending) or observed != len(order):
        raise ValueError("Incomplete query coverage")


def select_profile(metrics: list[RankingMetrics]) -> int:
    best = 0
    for index in range(1, len(metrics)):
        if _better_metrics(metrics[index], metrics[best]):
            best = index
    return best


def profile_row(frame: pd.DataFrame, index: int) -> dict[str, Any]:
    """Evaluate seven fixed profiles on a validated [pages, 3] score matrix."""
    matrix = frame[["bm25_score", "dense_score", "visual_score"]].to_numpy(float)
    labels = frame.relevance.to_numpy(float)
    ids = frame.page_id.astype(str).to_numpy()
    metrics = [
        evaluate_scores(matrix @ profile, labels, ids) for profile in get_profiles("w7")
    ]
    return {
        "query_index": index,
        "dataset": str(frame.dataset.iloc[0]),
        "query_id": str(frame.query_id.iloc[0]),
        "source": str(frame.source.iloc[0]),
        "pages": len(frame),
        "relevant_count": int(np.count_nonzero(labels > 0)),
        "input_query_sha256": sharded.dataframe_sha256(
            frame, sort_by=["dataset", "query_id", "page_id"]
        ),
        "profile_metrics": [asdict(m) for m in metrics],
        "qarf_profile_index": select_profile(metrics),
    }


def summarize(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    if len(rows) != config["queries"] or not rows:
        raise ValueError("Summary requires every query")
    metrics = []
    for index, row in enumerate(rows):
        if row["query_index"] != index or len(row["profile_metrics"]) != 7:
            raise ValueError("Profile result coverage mismatch")
        values = [RankingMetrics(**m) for m in row["profile_metrics"]]
        if any(
            not np.isfinite(v) or not -1e-12 <= v <= 1 + 1e-12
            for m in values
            for v in asdict(m).values()
        ):
            raise ValueError("Invalid profile metric")
        if row["qarf_profile_index"] != select_profile(values):
            raise ValueError("QARF profile selection mismatch")
        metrics.append(values)
    means = [_mean_metrics([m[i] for m in metrics]) for i in range(7)]
    global_index = select_profile(means)
    qarf = [m[r["qarf_profile_index"]] for m, r in zip(metrics, rows)]
    bounds = [max(0.0, 1.0 - m.ndcg10) for m in qarf]
    bound = float(np.mean(bounds))
    source_counts = {}
    for row in rows:
        source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
    return {
        "classification": CLASSIFICATION,
        "queries": len(rows),
        "scope": "all_frozen_vidoseek_discovery_queries",
        "seed": config["seed"],
        "random_sampling_or_bootstrap_performed": False,
        "global_profile_index": global_index,
        "global_profile": get_profiles("w7")[global_index].tolist(),
        "global_metrics": asdict(means[global_index]),
        "qarf_metrics": asdict(_mean_metrics(qarf)),
        "profile_mean_metrics": [asdict(m) for m in means],
        "channel_baselines": dict(
            zip(("bm25", "dense", "visual"), [asdict(m) for m in means[:3]])
        ),
        "global_ceiling_queries": sum(
            m[global_index].ndcg10 >= 1 - 1e-12 for m in metrics
        ),
        "qarf_ceiling_queries": sum(m.ndcg10 >= 1 - 1e-12 for m in qarf),
        "global_ceiling_fraction": float(
            np.mean([m[global_index].ndcg10 >= 1 - 1e-12 for m in metrics])
        ),
        "qarf_ceiling_fraction": float(np.mean([m.ndcg10 >= 1 - 1e-12 for m in qarf])),
        "mean_qpaf_gain_upper_bound": bound,
        "source_query_counts": source_counts,
        "headroom_review_threshold": config["headroom_review_threshold"],
        "review_advice": "TARGET_UNATTAINABLE_REVIEW_DIRECTION"
        if bound < config["headroom_review_threshold"]
        else "HEADROOM_POSSIBLE_REVIEW_COMPUTE",
        "qpaf_measured": False,
        "phase1_decision": "NOT_APPLICABLE_FIXED_PROFILE_AUDIT",
        "training_authorized": False,
        "frozen_p1_02_status": "BLOCKED",
    }


def read_checkpoints(
    output: Path, config: dict[str, Any], order: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    expected = {f"{i:06d}.json" for i in range(config["queries"])}
    if {p.name for p in (output / "checkpoints").iterdir()} != expected:
        raise ValueError("Checkpoint inventory mismatch")
    rows = []
    for index, key in enumerate(order):
        row, _ = sharded._read_checkpoint(
            output / "checkpoints" / f"{index:06d}.json",
            kind=CHECKPOINT_KIND,
            run_identity_sha256=value_sha256(config),
        )
        if (row["dataset"], row["query_id"]) != key or row["pages"] != config[
            "pages_per_query"
        ]:
            raise ValueError("Checkpoint query identity mismatch")
        rows.append(row)
    return rows


def worker(root: Path, config: dict[str, Any], output: Path, actor: str) -> None:
    require_approval(config, actor)
    attempt = read_json(output / "_ATTEMPTED.json")
    if (
        attempt["config_sha256"] != value_sha256(config)
        or attempt["remaining_authorized_invocations"] != 0
    ):
        raise ValueError("Audit attempt identity mismatch")
    evidence = preflight(root, config)
    write_json(output / "preflight.json", evidence)
    bundle = safeguards.load_protocol(root / BASE_PROTOCOL)["input_bundle"]
    audit = pd.read_parquet(root / bundle["candidate_audit"]["path"], use_threads=False)
    order = list(audit[["dataset", "query_id"]].itertuples(index=False, name=None))
    for index, frame in enumerate(
        iter_queries(
            root / bundle["retrieval_scores"]["path"], order, config["pages_per_query"]
        )
    ):
        started = time.monotonic()
        row = profile_row(frame, index)
        if (
            row["relevant_count"] != int(audit.relevant_total.iloc[index])
            or row["relevant_count"] != int(audit.relevant_selected.iloc[index])
            or int(audit.candidate_count.iloc[index]) != config["pages_per_query"]
            or float(audit.coverage.iloc[index]) != 1.0
        ):
            raise ValueError("Candidate audit relevance/coverage mismatch")
        row["profile_evaluation_seconds"] = time.monotonic() - started
        sharded._write_checkpoint(
            output / "checkpoints" / f"{index:06d}.json",
            kind=CHECKPOINT_KIND,
            run_identity_sha256=value_sha256(config),
            payload=row,
        )
        print(f"Saved fixed profiles {index + 1}/{len(order)}", flush=True)
    rows = read_checkpoints(output, config, order)
    summary = summarize(rows, config)
    global_index = summary["global_profile_index"]
    enriched = [
        {
            **r,
            "global_metrics": r["profile_metrics"][global_index],
            "qarf_metrics": r["profile_metrics"][r["qarf_profile_index"]],
            "qpaf_gain_upper_bound": max(
                0.0, 1 - r["profile_metrics"][r["qarf_profile_index"]]["ndcg10"]
            ),
        }
        for r in rows
    ]
    write_json(
        output / "per_query.json", {"classification": CLASSIFICATION, "rows": enriched}
    )
    write_json(output / "summary.json", summary)
    # Recheck input/source identity after reading, before declaring completion.
    preflight(root, config)
    write_json(
        output / "_WORKER_COMPLETE.json",
        {"status": "COMPLETE", "query_order_sha256": value_sha256(order)},
    )


def run(root: Path, config: dict[str, Any], actor: str) -> Path:
    started = time.monotonic()
    require_approval(config, actor)  # No source/input access or writes before approval.
    validate_config(root, config)
    output = root / OUTPUT_PATH
    output.mkdir(parents=True, exist_ok=False)
    write_json(
        output / "_ATTEMPTED.json",
        {
            "started_at": utc_now(),
            "config_sha256": value_sha256(config),
            "execution_actor": actor,
            "consumed_invocations": 1,
            "remaining_authorized_invocations": 0,
        },
    )
    process = None
    try:
        write_json(output / "resolved_config.json", config)
        for relative, expected in config["source_sha256"].items():
            destination = output / "source_snapshot" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write((root / relative).read_bytes())
            if sha256(destination) != expected:
                raise ValueError("Source changed during snapshot")
        patch = subprocess.check_output(
            ["git", "diff", "--binary", "HEAD"], cwd=root, timeout=10
        )
        with (output / "tracked_changes.patch").open("xb") as handle:
            handle.write(patch)
        process = mp.get_context("spawn").Process(
            target=worker, args=(root, config, output, actor)
        )
        remaining = config["total_wall_timeout_seconds"] - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Audit deadline expired before worker start")
        safeguards.complete_process_with_timeout(process, remaining)
        complete = read_json(output / "_WORKER_COMPLETE.json")
        bundle = safeguards.load_protocol(root / BASE_PROTOCOL)["input_bundle"]
        order = sharded.query_order_from_audit(root / bundle["candidate_audit"]["path"])
        if complete != {
            "status": "COMPLETE",
            "query_order_sha256": value_sha256(order),
        }:
            raise ValueError("Worker completion identity mismatch")
        rows = read_checkpoints(output, config, order)
        if read_json(output / "summary.json") != summarize(rows, config):
            raise ValueError("Saved summary mismatch")
        hashes = {
            p.relative_to(output).as_posix(): sha256(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        }
        elapsed = time.monotonic() - started
        if elapsed >= config["total_wall_timeout_seconds"]:
            raise TimeoutError("Audit deadline expired during finalization")
        write_json(
            output / "run_manifest.json",
            {
                "status": "COMPLETE",
                "classification": CLASSIFICATION,
                "completed_at": utc_now(),
                "elapsed_seconds": elapsed,
                "config_sha256": value_sha256(config),
                "source_commit": config["base_git_commit"],
                "environment": config["environment"],
                "queries": len(rows),
                "pages_per_query": config["pages_per_query"],
                "artifact_sha256": hashes,
                "input_bundle": bundle,
                "execution_actor": actor,
                "threads": {n: os.environ[n] for n in safeguards.CPU_THREAD_ENV},
                "remaining_authorized_invocations": 0,
                "qpaf_search_executed": False,
                "w66_executed": False,
                "training_executed": False,
                "modal_gpu_used": False,
                "phase1_decision": "NOT_APPLICABLE_FIXED_PROFILE_AUDIT",
                "frozen_p1_02_status": "BLOCKED",
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
                "completed_result_available": False,
                "remaining_authorized_invocations": 0,
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
        print(json.dumps(preflight(root, config), indent=2))
    else:
        if args.actor is None:
            parser.error("run requires --actor")
        print(run(root, config, args.actor))


if __name__ == "__main__":
    main()
