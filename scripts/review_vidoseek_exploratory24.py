"""Independently verify the completed exploratory-24 result bundle."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/vidoseek_w7_exploratory24_v1"
OUTPUT = ROOT / "artifacts/vidoseek_exploratory24_review/result_integrity_review.json"
TOLERANCE = 1e-12


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def value_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def assert_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=TOLERANCE):
        raise ValueError(f"{label} mismatch: {actual!r} != {expected!r}")


def bootstrap_mean_ci(values: np.ndarray, count: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    estimates = np.empty(count, dtype=float)
    for start in range(0, count, 256):
        size = min(256, count - start)
        indices = rng.integers(0, values.size, size=(size, values.size))
        estimates[start : start + size] = values[indices].mean(axis=1)
    return [float(value) for value in np.quantile(estimates, [0.025, 0.975])]


def ranking_metrics(
    scores: np.ndarray, relevance: np.ndarray, page_ids: np.ndarray
) -> dict[str, float]:
    order = np.lexsort((page_ids.astype(str), -np.asarray(scores, dtype=float)))
    ranked = np.asarray(relevance, dtype=float)[order]
    top = ranked[:10]
    discounts = 1.0 / np.log2(np.arange(2, len(top) + 2, dtype=float))
    dcg = float(np.sum((np.power(2.0, top) - 1.0) * discounts))
    ideal = np.sort(ranked)[::-1][:10]
    ideal_dcg = float(np.sum((np.power(2.0, ideal) - 1.0) * discounts))
    positives = int(np.count_nonzero(ranked > 0))
    hits = np.flatnonzero(top > 0)
    return {
        "ndcg10": dcg / ideal_dcg if ideal_dcg > 0 else 0.0,
        "recall1": float(np.count_nonzero(ranked[:1] > 0) / positives),
        "recall3": float(np.count_nonzero(ranked[:3] > 0) / positives),
        "mrr10": 0.0 if hits.size == 0 else 1.0 / float(hits[0] + 1),
    }


def gain_summary(delta: np.ndarray, count: int, seed: int) -> dict[str, Any]:
    positive = np.clip(delta, 0.0, None)
    top_count = max(1, int(np.ceil(len(positive) * 0.05)))
    positive_total = float(positive.sum())
    return {
        "mean_delta_ndcg10": float(delta.mean()),
        "delta_ci95": bootstrap_mean_ci(delta, count, seed),
        "fraction_gain_ge_001": float(np.mean(delta >= 0.01)),
        "fraction_gain_ge_003": float(np.mean(delta >= 0.03)),
        "fraction_gain_ge_005": float(np.mean(delta >= 0.05)),
        "top_5pct_gain_share": (
            float(np.sort(positive)[-top_count:].sum() / positive_total)
            if positive_total > 0
            else 0.0
        ),
    }


def validate_envelope(path: Path, kind: str, run_identity: str) -> dict[str, Any]:
    envelope = read_json(path)
    expected_fields = {
        "schema_version",
        "kind",
        "run_identity_sha256",
        "payload",
        "content_sha256",
    }
    if set(envelope) != expected_fields or envelope["schema_version"] != 1:
        raise ValueError(f"Invalid checkpoint envelope: {path}")
    if envelope["kind"] != kind or envelope["run_identity_sha256"] != run_identity:
        raise ValueError(f"Checkpoint identity mismatch: {path}")
    unsigned = {key: envelope[key] for key in expected_fields - {"content_sha256"}}
    if envelope["content_sha256"] != value_sha256(unsigned):
        raise ValueError(f"Checkpoint content hash mismatch: {path}")
    return envelope


def compare_gain(observed: dict[str, Any], expected: dict[str, Any], label: str) -> int:
    comparisons = 0
    for key, value in expected.items():
        if isinstance(value, list):
            for index, expected_item in enumerate(value):
                assert_close(
                    observed[key][index], expected_item, f"{label}.{key}[{index}]"
                )
                comparisons += 1
        else:
            assert_close(observed[key], value, f"{label}.{key}")
            comparisons += 1
    return comparisons


def main() -> None:
    manifest = read_json(RUN / "run_manifest.json")
    config = read_json(RUN / "resolved_config.json")
    summary = read_json(RUN / "summary.json")
    per_query = read_json(RUN / "per_query.json")
    timings = read_json(RUN / "timings.json")["timings"]
    proposal = read_json(
        RUN / "source_snapshot/docs/vidoseek_w7_exploratory24_proposal.json"
    )

    if manifest["status"] != "COMPLETE" or (RUN / "_INCOMPLETE.json").exists():
        raise ValueError("Run is not exclusively complete")
    if manifest["config_sha256"] != value_sha256(config):
        raise ValueError("Resolved config hash mismatch")
    if manifest["elapsed_seconds"] >= config["total_wall_timeout_seconds"]:
        raise ValueError("Run exceeded the approved wall-time cap")
    if manifest["remaining_authorized_invocations"] != 0:
        raise ValueError("Authorized invocation was not consumed")
    if manifest["queries"] != 24 or manifest["pages_per_query"] != 5385:
        raise ValueError("Manifest scope mismatch")
    if any(
        manifest[field]
        for field in ("full_w7_executed", "learned_qpaf_executed", "modal_gpu_used")
    ):
        raise ValueError("Run crossed an excluded scope boundary")
    if manifest["phase1_decision"] != "NOT_APPLICABLE_EXPLORATORY_SUBSET":
        raise ValueError("Exploratory run claimed a formal phase decision")

    hash_failures = []
    for relative, expected in manifest["artifact_sha256"].items():
        path = RUN / relative
        if not path.is_file() or file_sha256(path) != expected:
            hash_failures.append(relative)
    if hash_failures:
        raise ValueError(f"Artifact hash failures: {hash_failures}")
    expected_manifest_files = {
        path.relative_to(RUN).as_posix()
        for path in RUN.rglob("*")
        if path.is_file() and path.name != "run_manifest.json"
    }
    if set(manifest["artifact_sha256"]) != expected_manifest_files:
        raise ValueError("Manifest file inventory mismatch")

    for relative, expected in config["source_sha256"].items():
        snapshot = RUN / "source_snapshot" / relative
        if file_sha256(snapshot) != expected:
            raise ValueError(f"Source snapshot hash mismatch: {relative}")

    plan = read_json(RUN / "checkpoints/run_plan.json")
    run_identity = plan["run_identity_sha256"]
    plan = validate_envelope(
        RUN / "checkpoints/run_plan.json", "run_plan", run_identity
    )
    if value_sha256(plan["payload"]) != run_identity:
        raise ValueError("Run identity payload hash mismatch")
    if plan["payload"]["protocol_sha256"] != manifest["config_sha256"]:
        raise ValueError("Run plan protocol hash mismatch")
    if plan["payload"]["bootstrap_resamples"] != 10_000:
        raise ValueError("Bootstrap count mismatch")

    expected_keys = [
        [item["dataset"], item["query_id"]] for item in proposal["selection"]["queries"]
    ]
    if value_sha256(expected_keys) != plan["payload"]["query_order_sha256"]:
        raise ValueError("Frozen query order hash mismatch")

    global_envelopes = []
    for index, (dataset, query_id) in enumerate(expected_keys):
        envelope = validate_envelope(
            RUN / f"checkpoints/global/{index:06d}.json",
            "global_profile_metrics",
            run_identity,
        )
        payload = envelope["payload"]
        if [payload["dataset"], payload["query_id"]] != [dataset, query_id]:
            raise ValueError(f"Global query identity mismatch at index {index}")
        if payload["query_index"] != index or len(payload["profile_metrics"]) != 7:
            raise ValueError(f"Global checkpoint coverage mismatch at index {index}")
        global_envelopes.append(envelope)

    selection = validate_envelope(
        RUN / "checkpoints/global_selection.json",
        "global_profile_selection",
        run_identity,
    )
    global_chain = value_sha256([item["content_sha256"] for item in global_envelopes])
    if selection["payload"]["global_checkpoint_chain_sha256"] != global_chain:
        raise ValueError("Global checkpoint chain mismatch")
    profiles = plan["payload"]["profiles"]
    profile_index = selection["payload"]["profile_index"]
    if selection["payload"]["profile"] != profiles[profile_index]:
        raise ValueError("Global profile selection mismatch")

    rows = per_query["rows"]
    if len(rows) != 24:
        raise ValueError("Per-query row count mismatch")
    selected_query_ids = [key[1] for key in expected_keys]
    raw = pq.read_table(
        ROOT / proposal["input"]["retrieval_scores_path"],
        columns=[
            "query_id",
            "page_id",
            "relevance",
            "bm25_score",
            "dense_score",
            "visual_score",
        ],
        filters=[("query_id", "in", selected_query_ids)],
        use_threads=False,
    ).to_pandas(use_threads=False)
    if len(raw) != 24 * 5385:
        raise ValueError("Selected raw input coverage mismatch")
    raw_groups = {query_id: frame for query_id, frame in raw.groupby("query_id")}
    metric_comparisons = 0
    ranking_metric_comparisons = 0
    for index, ((dataset, query_id), row) in enumerate(zip(expected_keys, rows)):
        envelope = validate_envelope(
            RUN / f"checkpoints/queries/{index:06d}.json",
            "query_oracle_result",
            run_identity,
        )
        payload = envelope["payload"]
        if payload["row"] != row or payload["query_index"] != index:
            raise ValueError(f"Query checkpoint row mismatch at index {index}")
        if [row["dataset"], row["query_id"]] != [dataset, query_id]:
            raise ValueError(f"Frozen query mismatch at index {index}")
        if payload["global_selection_sha256"] != selection["content_sha256"]:
            raise ValueError(f"Global selection link mismatch at index {index}")
        if row["global_profile"] != selection["payload"]["profile"]:
            raise ValueError(f"Global profile mismatch at index {index}")
        if len(row["profile_counts"]) != 7 or sum(row["profile_counts"]) != 5385:
            raise ValueError(f"Profile assignment coverage mismatch at index {index}")
        qarf_index = profiles.index(row["qarf_profile"])
        if row["changed_candidates"] != 5385 - row["profile_counts"][qarf_index]:
            raise ValueError(f"Changed candidate count mismatch at index {index}")
        if len(row["changed_pages"]) != row["changed_candidates"]:
            raise ValueError(f"Changed page mapping mismatch at index {index}")
        frame = raw_groups[query_id]
        if len(frame) != 5385 or frame["page_id"].nunique() != 5385:
            raise ValueError(f"Raw query coverage mismatch at index {index}")
        matrix = frame[["bm25_score", "dense_score", "visual_score"]].to_numpy(float)
        relevance = frame["relevance"].to_numpy(float)
        page_ids = frame["page_id"].astype(str).to_numpy()
        if int(np.count_nonzero(relevance > 0)) != row["relevant_count"]:
            raise ValueError(f"Relevant count mismatch at index {index}")
        raw_metric_sets = {
            "global_metrics": ranking_metrics(
                matrix @ np.asarray(row["global_profile"]), relevance, page_ids
            ),
            "qarf_metrics": ranking_metrics(
                matrix @ np.asarray(row["qarf_profile"]), relevance, page_ids
            ),
        }
        page_weights = np.tile(np.asarray(row["qarf_profile"]), (len(frame), 1))
        page_position = {page_id: position for position, page_id in enumerate(page_ids)}
        for page_id, weights in row["changed_pages"].items():
            if page_id not in page_position:
                raise ValueError(f"Changed page is absent at index {index}: {page_id}")
            page_weights[page_position[page_id]] = weights
        raw_metric_sets["qpaf_metrics"] = ranking_metrics(
            np.sum(matrix * page_weights, axis=1), relevance, page_ids
        )
        for group_name, metrics in raw_metric_sets.items():
            for metric_name, expected in metrics.items():
                assert_close(
                    row[group_name][metric_name],
                    expected,
                    f"raw[{index}].{group_name}.{metric_name}",
                )
                ranking_metric_comparisons += 1
        for profile_number, profile in enumerate(profiles):
            metrics = ranking_metrics(matrix @ np.asarray(profile), relevance, page_ids)
            checkpoint_metrics = global_envelopes[index]["payload"]["profile_metrics"][
                profile_number
            ]
            for metric_name, expected in metrics.items():
                assert_close(
                    checkpoint_metrics[metric_name],
                    expected,
                    f"raw_global[{index}][{profile_number}].{metric_name}",
                )
                ranking_metric_comparisons += 1
        for metric_name in ("ndcg10", "recall1", "recall3", "mrr10"):
            values = [
                float(row[group][metric_name])
                for group in ("global_metrics", "qarf_metrics", "qpaf_metrics")
            ]
            if not all(
                math.isfinite(value) and -TOLERANCE <= value <= 1 + TOLERANCE
                for value in values
            ):
                raise ValueError(f"Invalid metric at index {index}: {metric_name}")
            metric_comparisons += len(values)
        expected_deltas = {
            "delta_qarf_vs_global": row["qarf_metrics"]["ndcg10"]
            - row["global_metrics"]["ndcg10"],
            "delta_qpaf_vs_qarf": row["qpaf_metrics"]["ndcg10"]
            - row["qarf_metrics"]["ndcg10"],
            "delta_qpaf_vs_global": row["qpaf_metrics"]["ndcg10"]
            - row["global_metrics"]["ndcg10"],
            "delta_ndcg10": row["qpaf_metrics"]["ndcg10"]
            - row["qarf_metrics"]["ndcg10"],
        }
        for name, expected in expected_deltas.items():
            assert_close(row[name], expected, f"row[{index}].{name}")
            metric_comparisons += 1

    grid = summary["grids"]["w7"]
    global_values = np.asarray([row["global_metrics"]["ndcg10"] for row in rows])
    qarf_values = np.asarray([row["qarf_metrics"]["ndcg10"] for row in rows])
    qpaf_values = np.asarray([row["qpaf_metrics"]["ndcg10"] for row in rows])
    deltas = {
        "qarf_vs_global": qarf_values - global_values,
        "qpaf_vs_qarf": qpaf_values - qarf_values,
        "qpaf_vs_global": qpaf_values - global_values,
    }
    for name, values in (
        ("mean_global_ndcg10", global_values),
        ("mean_qarf_ndcg10", qarf_values),
        ("mean_qpaf_ndcg10", qpaf_values),
    ):
        assert_close(grid[name], values.mean(), name)
        metric_comparisons += 1
    for name, values in deltas.items():
        metric_comparisons += compare_gain(
            grid[name], gain_summary(values, 10_000, 20260820), name
        )
    metric_comparisons += compare_gain(
        grid, gain_summary(deltas["qpaf_vs_qarf"], 10_000, 20260820), "w7"
    )
    expected_counts = np.sum([row["profile_counts"] for row in rows], axis=0).tolist()
    if grid["profile_counts"] != expected_counts or sum(expected_counts) != 24 * 5385:
        raise ValueError("Aggregate profile counts mismatch")
    assert_close(
        grid["mean_changed_candidates"],
        np.mean([row["changed_candidates"] for row in rows]),
        "mean_changed_candidates",
    )

    tolerance = plan["payload"]["strict_improvement_tolerance"]
    expected_wtl = {}
    for field in ("delta_qarf_vs_global", "delta_qpaf_vs_qarf"):
        values = np.asarray([row[field] for row in rows])
        expected_wtl[field] = {
            "win": int(np.sum(values > tolerance)),
            "tie": int(np.sum(np.abs(values) <= tolerance)),
            "loss": int(np.sum(values < -tolerance)),
        }
    if summary["win_tie_loss"] != expected_wtl:
        raise ValueError("Win/tie/loss mismatch")
    if len(timings) != 48:
        raise ValueError("Timing coverage mismatch")
    if [item["query_id"] for item in timings[:24]] != [key[1] for key in expected_keys]:
        raise ValueError("Global timing order mismatch")
    if [item["query_id"] for item in timings[24:]] != [key[1] for key in expected_keys]:
        raise ValueError("Query timing order mismatch")

    review = {
        "status": "PASS",
        "classification": "independent_review_of_exploratory24_subset_oracle",
        "run_manifest_sha256": file_sha256(RUN / "run_manifest.json"),
        "verified_manifest_artifacts": len(manifest["artifact_sha256"]),
        "verified_checkpoint_envelopes": 50,
        "verified_source_snapshots": len(config["source_sha256"]),
        "verified_metric_values_and_deltas": metric_comparisons,
        "verified_raw_ranking_metrics": ranking_metric_comparisons,
        "queries": 24,
        "pages_per_query": 5385,
        "candidate_pairs": 24 * 5385,
        "elapsed_seconds": manifest["elapsed_seconds"],
        "recomputed": {
            "mean_global_ndcg10": float(global_values.mean()),
            "mean_qarf_ndcg10": float(qarf_values.mean()),
            "mean_qpaf_ndcg10": float(qpaf_values.mean()),
            "mean_qpaf_vs_qarf_delta_ndcg10": float(deltas["qpaf_vs_qarf"].mean()),
            "qpaf_vs_qarf_ci95": bootstrap_mean_ci(
                deltas["qpaf_vs_qarf"], 10_000, 20260820
            ),
            "qpaf_vs_qarf_win_tie_loss": expected_wtl["delta_qpaf_vs_qarf"],
            "qpaf_vs_qarf_top_5pct_gain_share": gain_summary(
                deltas["qpaf_vs_qarf"], 10_000, 20260820
            )["top_5pct_gain_share"],
            "changed_queries": int(np.sum(deltas["qpaf_vs_qarf"] > tolerance)),
            "changed_candidates": int(sum(row["changed_candidates"] for row in rows)),
        },
        "boundaries": {
            "formal_phase1_decision": False,
            "full_w7_executed": False,
            "w66_executed": False,
            "training_executed": False,
            "modal_gpu_used": False,
            "frozen_p1_02_status": manifest["frozen_p1_02_status"],
            "remaining_authorized_invocations": 0,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT.parent / "query_comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "audit_index",
                "query_id",
                "global_ndcg10",
                "qarf_ndcg10",
                "qpaf_ndcg10",
                "qpaf_minus_qarf",
                "changed_candidates",
            ]
        )
        for selected, row in zip(proposal["selection"]["queries"], rows):
            writer.writerow(
                [
                    selected["audit_index"],
                    row["query_id"],
                    row["global_metrics"]["ndcg10"],
                    row["qarf_metrics"]["ndcg10"],
                    row["qpaf_metrics"]["ndcg10"],
                    row["delta_qpaf_vs_qarf"],
                    row["changed_candidates"],
                ]
            )

    labels = [str(item["audit_index"]) for item in proposal["selection"]["queries"]]
    positions = np.arange(len(rows))
    figure, axes = plt.subplots(2, 1, figsize=(14, 8), constrained_layout=True)
    width = 0.25
    axes[0].bar(positions - width, global_values, width, label="Global")
    axes[0].bar(positions, qarf_values, width, label="QARF")
    axes[0].bar(positions + width, qpaf_values, width, label="QPAF")
    axes[0].set_ylabel("nDCG@10")
    axes[0].set_ylim(0, 1.05)
    axes[0].set_title("Exploratory-24 retrieval quality by frozen audit index")
    axes[0].legend(loc="lower right")
    axes[1].bar(positions, deltas["qpaf_vs_qarf"], color="#2a9d8f")
    axes[1].axhline(0.03, color="#e76f51", linestyle="--", linewidth=1, label="0.03")
    axes[1].set_ylabel("QPAF - QARF nDCG@10")
    axes[1].set_xlabel("Frozen audit index")
    axes[1].legend(loc="upper right")
    for axis in axes:
        axis.set_xticks(positions)
        axis.set_xticklabels(labels, rotation=60, ha="right")
        axis.grid(axis="y", alpha=0.2)
    figure.savefig(OUTPUT.parent / "comparison.png", dpi=180)
    plt.close(figure)

    OUTPUT.write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(review, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
