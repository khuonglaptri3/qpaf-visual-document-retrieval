from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import os
import platform
import queue
import shutil
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable, Iterator

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .bootstrap import bootstrap_mean_ci
from .constants import PREREGISTERED_THRESHOLDS, SCORE_COLUMNS, SEED
from .io import (
    dataframe_sha256,
    require_columns,
    sha256_file,
    write_json,
    write_jsonl,
    write_parquet,
)
from .metrics import RankingMetrics, evaluate_scores
from .profiles import get_profiles
from .qpaf import _better_metrics, _candidate_oracle, _mean_metrics, _query_oracle
from .report import plot_qpaf


CHECKPOINT_SCHEMA_VERSION = 1
GRID_NAME = "w7"
NUMERIC_INPUT_COLUMNS = [
    "relevance",
    "bm25_score",
    "dense_score",
    "stage1_score",
    "visual_score",
]
QueryKey = tuple[str, str]
QueryFrameFactory = Callable[[], Iterator[tuple[int, QueryKey, pd.DataFrame]]]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _value_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


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


def _checkpoint_envelope(
    kind: str,
    run_identity_sha256: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    unsigned = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "kind": kind,
        "run_identity_sha256": run_identity_sha256,
        "payload": payload,
    }
    return {**unsigned, "content_sha256": _value_sha256(unsigned)}


def _validate_checkpoint_envelope(
    envelope: dict[str, Any],
    *,
    kind: str,
    run_identity_sha256: str,
) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "kind",
        "run_identity_sha256",
        "payload",
        "content_sha256",
    }
    if set(envelope) != expected_fields:
        raise ValueError(f"{kind} checkpoint fields are invalid")
    if envelope["schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError(f"{kind} checkpoint schema version is invalid")
    if envelope["kind"] != kind:
        raise ValueError(f"Expected {kind} checkpoint, got {envelope['kind']}")
    if envelope["run_identity_sha256"] != run_identity_sha256:
        raise ValueError(f"{kind} checkpoint run identity mismatch")
    unsigned = {
        field: envelope[field] for field in expected_fields - {"content_sha256"}
    }
    if envelope["content_sha256"] != _value_sha256(unsigned):
        raise ValueError(f"{kind} checkpoint content hash mismatch")
    payload = envelope["payload"]
    if not isinstance(payload, dict):
        raise ValueError(f"{kind} checkpoint payload must be a mapping")
    return payload


def _read_checkpoint(
    path: Path,
    *,
    kind: str,
    run_identity_sha256: str,
) -> tuple[dict[str, Any], str]:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read {kind} checkpoint: {path}") from error
    if not isinstance(envelope, dict):
        raise ValueError(f"{kind} checkpoint must be a mapping")
    payload = _validate_checkpoint_envelope(
        envelope,
        kind=kind,
        run_identity_sha256=run_identity_sha256,
    )
    return payload, envelope["content_sha256"]


def _write_checkpoint(
    path: Path,
    *,
    kind: str,
    run_identity_sha256: str,
    payload: dict[str, Any],
) -> str:
    envelope = _checkpoint_envelope(kind, run_identity_sha256, payload)
    _write_json_atomic_create_once(path, envelope)
    return envelope["content_sha256"]


def query_order_from_audit(audit_path: Path) -> list[QueryKey]:
    audit = pd.read_parquet(audit_path, columns=["dataset", "query_id"])
    if audit.empty:
        raise ValueError("Candidate audit contains no queries")
    keys = [
        (str(dataset), str(query_id))
        for dataset, query_id in audit[["dataset", "query_id"]].itertuples(
            index=False, name=None
        )
    ]
    if len(set(keys)) != len(keys):
        raise ValueError("Candidate audit query order contains duplicates")
    return keys


def _validate_query_frame(
    frame: pd.DataFrame,
    expected_key: QueryKey,
    expected_pages_per_query: int,
) -> pd.DataFrame:
    require_columns(frame, SCORE_COLUMNS, "query shard")
    if len(frame) != expected_pages_per_query:
        raise ValueError(
            f"Query {expected_key} has {len(frame)} rows; "
            f"expected {expected_pages_per_query}"
        )
    ordered = frame.sort_values("page_id", kind="stable").reset_index(drop=True)
    observed_keys = set(
        zip(
            ordered["dataset"].astype(str),
            ordered["query_id"].astype(str),
        )
    )
    if observed_keys != {expected_key}:
        raise ValueError(f"Query shard identity mismatch for {expected_key}")
    if ordered["page_id"].astype(str).duplicated().any():
        raise ValueError(f"Query {expected_key} contains duplicate page IDs")
    numeric = ordered[NUMERIC_INPUT_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError(f"Query {expected_key} contains non-finite values")
    return ordered


def iter_dataframe_queries(
    scores: pd.DataFrame,
    query_order: list[QueryKey],
    expected_pages_per_query: int,
) -> Iterator[tuple[int, QueryKey, pd.DataFrame]]:
    require_columns(scores, SCORE_COLUMNS, "retrieval score table")
    groups = scores.groupby(["dataset", "query_id"], sort=False)
    observed = 0
    for index, ((dataset, query_id), group) in enumerate(groups):
        if index >= len(query_order):
            raise ValueError("Retrieval scores contain unexpected extra queries")
        key = (str(dataset), str(query_id))
        if key != query_order[index]:
            raise ValueError("Retrieval-score query order differs from candidate audit")
        yield (
            index,
            key,
            _validate_query_frame(
                group,
                key,
                expected_pages_per_query,
            ),
        )
        observed += 1
    if observed != len(query_order):
        raise ValueError("Retrieval scores are missing candidate-audit queries")


def iter_parquet_queries(
    scores_path: Path,
    query_order: list[QueryKey],
    expected_pages_per_query: int,
) -> Iterator[tuple[int, QueryKey, pd.DataFrame]]:
    parquet = pq.ParquetFile(scores_path)
    expected_index = 0
    for row_group_index in range(parquet.metadata.num_row_groups):
        frame = parquet.read_row_group(row_group_index).to_pandas()
        require_columns(frame, SCORE_COLUMNS, "retrieval score row group")
        for (dataset, query_id), group in frame.groupby(
            ["dataset", "query_id"], sort=False
        ):
            if expected_index >= len(query_order):
                raise ValueError("Retrieval scores contain unexpected extra queries")
            key = (str(dataset), str(query_id))
            if key != query_order[expected_index]:
                raise ValueError(
                    "Retrieval-score row-group query order differs from candidate audit"
                )
            yield (
                expected_index,
                key,
                _validate_query_frame(
                    group,
                    key,
                    expected_pages_per_query,
                ),
            )
            expected_index += 1
    if expected_index != len(query_order):
        raise ValueError("Retrieval scores are missing candidate-audit queries")


def build_run_identity(
    *,
    protocol_id: str,
    protocol_sha256: str,
    source_commit: str,
    retrieval_score_sha256: str,
    retrieval_score_content_sha256: str,
    query_order: list[QueryKey],
    pages_per_query: int,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    profiles = get_profiles(GRID_NAME)
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "classification": "query_sharded_w7_oracle_checkpoint_identity",
        "protocol_id": protocol_id,
        "protocol_sha256": protocol_sha256,
        "source_commit": source_commit,
        "retrieval_score_sha256": retrieval_score_sha256,
        "retrieval_score_content_sha256": retrieval_score_content_sha256,
        "query_order_sha256": _value_sha256([list(key) for key in query_order]),
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


def _query_item(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "dataset": str(frame["dataset"].iloc[0]),
        "query_id": str(frame["query_id"].iloc[0]),
        "source": str(frame["source"].iloc[0]) if "source" in frame else "unknown",
        "score_matrix": frame[["bm25_score", "dense_score", "visual_score"]].to_numpy(
            float
        ),
        "relevance": frame["relevance"].to_numpy(float),
        "page_ids": frame["page_id"].astype(str).to_numpy(),
    }


def _global_metrics(frame: pd.DataFrame, profiles: np.ndarray) -> list[RankingMetrics]:
    item = _query_item(frame)
    return [
        evaluate_scores(
            item["score_matrix"] @ profile,
            item["relevance"],
            item["page_ids"],
        )
        for profile in profiles
    ]


def _validate_metric_dict(value: Any, label: str) -> RankingMetrics:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    try:
        metrics = RankingMetrics(**value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} fields are invalid") from error
    if not all(np.isfinite(float(value)) for value in asdict(metrics).values()):
        raise ValueError(f"{label} contains non-finite metrics")
    return metrics


def _global_checkpoint(
    path: Path,
    *,
    run_identity_sha256: str,
    query_index: int,
    query_key: QueryKey,
    frame: pd.DataFrame,
    profiles: np.ndarray,
) -> tuple[dict[str, Any], str, bool]:
    input_sha256 = dataframe_sha256(
        frame,
        sort_by=["dataset", "query_id", "page_id"],
    )
    if path.exists():
        payload, content_sha256 = _read_checkpoint(
            path,
            kind="global_profile_metrics",
            run_identity_sha256=run_identity_sha256,
        )
        reused = True
    else:
        payload = {
            "query_index": query_index,
            "dataset": query_key[0],
            "query_id": query_key[1],
            "input_query_sha256": input_sha256,
            "profile_metrics": [
                asdict(metrics) for metrics in _global_metrics(frame, profiles)
            ],
        }
        content_sha256 = _write_checkpoint(
            path,
            kind="global_profile_metrics",
            run_identity_sha256=run_identity_sha256,
            payload=payload,
        )
        reused = False
    expected_identity = {
        "query_index": query_index,
        "dataset": query_key[0],
        "query_id": query_key[1],
        "input_query_sha256": input_sha256,
    }
    for field, expected in expected_identity.items():
        if payload.get(field) != expected:
            raise ValueError(f"Global checkpoint {field} mismatch for {query_key}")
    metrics = payload.get("profile_metrics")
    if not isinstance(metrics, list) or len(metrics) != len(profiles):
        raise ValueError(f"Global checkpoint profile count mismatch for {query_key}")
    for profile_index, value in enumerate(metrics):
        _validate_metric_dict(value, f"global profile {profile_index}")
    return payload, content_sha256, reused


def _select_global_profile(
    global_payloads: list[dict[str, Any]],
) -> tuple[int, list[RankingMetrics]]:
    per_profile = [
        [
            _validate_metric_dict(
                payload["profile_metrics"][profile_index],
                f"global profile {profile_index}",
            )
            for payload in global_payloads
        ]
        for profile_index in range(len(get_profiles(GRID_NAME)))
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


def _query_result_row(
    frame: pd.DataFrame,
    profiles: np.ndarray,
    global_profile_index: int,
    global_query_metrics: RankingMetrics,
) -> dict[str, Any]:
    item = _query_item(frame)
    score_matrix = item["score_matrix"]
    relevance = item["relevance"]
    page_ids = item["page_ids"]
    query_profile, query_scores, query_metrics = _query_oracle(
        score_matrix,
        relevance,
        page_ids,
        profiles,
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
    changed_pages = {
        str(page_ids[index]): [float(x) for x in profiles[assignments[index]]]
        for index in np.flatnonzero(changed_mask)
    }
    counts = np.bincount(assignments, minlength=len(profiles))
    return {
        "dataset": item["dataset"],
        "query_id": item["query_id"],
        "source": item["source"],
        "relevant_count": int(np.count_nonzero(relevance > 0)),
        "grid": GRID_NAME,
        "global_profile": [float(x) for x in profiles[global_profile_index]],
        "global_metrics": asdict(global_query_metrics),
        "qarf_profile": [float(x) for x in profiles[query_profile]],
        "qarf_metrics": asdict(query_metrics),
        "qpaf_metrics": asdict(candidate_metrics),
        "delta_qarf_vs_global": query_metrics.ndcg10 - global_query_metrics.ndcg10,
        "delta_qpaf_vs_qarf": candidate_metrics.ndcg10 - query_metrics.ndcg10,
        "delta_qpaf_vs_global": candidate_metrics.ndcg10 - global_query_metrics.ndcg10,
        "delta_ndcg10": candidate_metrics.ndcg10 - query_metrics.ndcg10,
        "changed_candidates": int(np.count_nonzero(changed_mask)),
        "accepted_updates": int(changes),
        "profile_counts": counts.astype(int).tolist(),
        "changed_pages": changed_pages,
    }


def _validate_query_payload(
    payload: dict[str, Any],
    *,
    query_index: int,
    query_key: QueryKey,
    input_sha256: str,
    global_selection_sha256: str,
) -> dict[str, Any]:
    expected = {
        "query_index": query_index,
        "dataset": query_key[0],
        "query_id": query_key[1],
        "input_query_sha256": input_sha256,
        "global_selection_sha256": global_selection_sha256,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"Query checkpoint {field} mismatch for {query_key}")
    row = payload.get("row")
    if not isinstance(row, dict):
        raise ValueError(f"Query checkpoint row is invalid for {query_key}")
    if (
        row.get("dataset") != query_key[0]
        or row.get("query_id") != query_key[1]
        or row.get("grid") != GRID_NAME
    ):
        raise ValueError(f"Query checkpoint result identity mismatch for {query_key}")
    for name in ["global_metrics", "qarf_metrics", "qpaf_metrics"]:
        _validate_metric_dict(row.get(name), name)
    return row


def _query_checkpoint(
    path: Path,
    *,
    run_identity_sha256: str,
    query_index: int,
    query_key: QueryKey,
    frame: pd.DataFrame,
    profiles: np.ndarray,
    global_profile_index: int,
    global_query_metrics: RankingMetrics,
    global_selection_sha256: str,
) -> tuple[dict[str, Any], str, bool]:
    input_sha256 = dataframe_sha256(
        frame,
        sort_by=["dataset", "query_id", "page_id"],
    )
    if path.exists():
        payload, content_sha256 = _read_checkpoint(
            path,
            kind="query_oracle_result",
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
            "row": _query_result_row(
                frame,
                profiles,
                global_profile_index,
                global_query_metrics,
            ),
        }
        content_sha256 = _write_checkpoint(
            path,
            kind="query_oracle_result",
            run_identity_sha256=run_identity_sha256,
            payload=payload,
        )
        reused = False
    row = _validate_query_payload(
        payload,
        query_index=query_index,
        query_key=query_key,
        input_sha256=input_sha256,
        global_selection_sha256=global_selection_sha256,
    )
    return row, content_sha256, reused


def _result_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dataset": row["dataset"],
                "query_id": row["query_id"],
                "source": row["source"],
                "relevant_count": row["relevant_count"],
                "grid": row["grid"],
                "global_ndcg10": row["global_metrics"]["ndcg10"],
                "qarf_ndcg10": row["qarf_metrics"]["ndcg10"],
                "qpaf_ndcg10": row["qpaf_metrics"]["ndcg10"],
                "delta_qarf_vs_global": row["delta_qarf_vs_global"],
                "delta_qpaf_vs_qarf": row["delta_qpaf_vs_qarf"],
                "delta_qpaf_vs_global": row["delta_qpaf_vs_global"],
                "delta_ndcg10": row["delta_ndcg10"],
                "changed_candidates": row["changed_candidates"],
            }
            for row in rows
        ]
    )


def summarize_oracle_rows(
    rows: list[dict[str, Any]],
    n_bootstrap: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    result_frame = _result_frame(rows)
    summaries = {}
    for grid_name, group in result_frame.groupby("grid", sort=False):
        qarf_delta = group["delta_qarf_vs_global"].to_numpy(float)
        qpaf_delta = group["delta_qpaf_vs_qarf"].to_numpy(float)

        def gain_summary(delta: np.ndarray) -> dict[str, Any]:
            ci_low, ci_high = bootstrap_mean_ci(delta, n_bootstrap)
            positive = np.clip(delta, 0.0, None)
            top_count = max(1, int(np.ceil(len(positive) * 0.05)))
            positive_total = float(positive.sum())
            concentration = (
                float(np.sort(positive)[-top_count:].sum() / positive_total)
                if positive_total > 0
                else 0.0
            )
            return {
                "mean_delta_ndcg10": float(delta.mean()),
                "delta_ci95": [ci_low, ci_high],
                "fraction_gain_ge_001": float(np.mean(delta >= 0.01)),
                "fraction_gain_ge_003": float(np.mean(delta >= 0.03)),
                "fraction_gain_ge_005": float(np.mean(delta >= 0.05)),
                "top_5pct_gain_share": concentration,
            }

        qarf_gain = gain_summary(qarf_delta)
        qpaf_gain = gain_summary(qpaf_delta)
        grid_rows = [row for row in rows if row["grid"] == grid_name]
        profile_totals = np.sum(
            np.asarray([row["profile_counts"] for row in grid_rows], dtype=int),
            axis=0,
        )
        summaries[grid_name] = {
            "queries": int(len(group)),
            "global_profile": grid_rows[0]["global_profile"],
            "mean_global_ndcg10": float(group["global_ndcg10"].mean()),
            "mean_qarf_ndcg10": float(group["qarf_ndcg10"].mean()),
            "mean_qpaf_ndcg10": float(group["qpaf_ndcg10"].mean()),
            "qarf_vs_global": qarf_gain,
            "qpaf_vs_qarf": qpaf_gain,
            "qpaf_vs_global": gain_summary(
                group["delta_qpaf_vs_global"].to_numpy(float)
            ),
            **qpaf_gain,
            "mean_changed_candidates": float(group["changed_candidates"].mean()),
            "profile_counts": profile_totals.astype(int).tolist(),
        }
    primary = summaries.get(GRID_NAME, next(iter(summaries.values())))
    discovery_min = PREREGISTERED_THRESHOLDS["qpaf"]["discovery_mean_delta_ndcg10_min"]
    required_sensitivity = [grid for grid in ["w7", "w66"] if grid in summaries]
    discovery_holds_across_grids = len(required_sensitivity) == 2 and all(
        summaries[grid]["mean_delta_ndcg10"] >= discovery_min
        and summaries[grid]["delta_ci95"][0] > 0
        for grid in required_sensitivity
    )
    if discovery_holds_across_grids:
        discovery_gate = "pass"
    elif (
        primary["mean_delta_ndcg10"]
        < PREREGISTERED_THRESHOLDS["qpaf"]["no_go_confirmation_mean_delta_ndcg10_below"]
    ):
        discovery_gate = "fail"
    else:
        discovery_gate = "inconclusive"
    summary = {"grids": summaries, "discovery_gate": discovery_gate}

    subgroup = (
        result_frame.groupby(
            [
                "grid",
                "source",
                result_frame["relevant_count"]
                .gt(1)
                .map({True: "multi", False: "single"}),
            ]
        )
        .agg(
            queries=("query_id", "size"),
            mean_delta_qarf_vs_global=("delta_qarf_vs_global", "mean"),
            mean_delta_qpaf_vs_qarf=("delta_qpaf_vs_qarf", "mean"),
            mean_delta_qpaf_vs_global=("delta_qpaf_vs_global", "mean"),
        )
        .reset_index(names=["grid", "source", "relevance_group"])
    )
    return summary, subgroup


def _checkpoint_inventory(directory: Path, expected_count: int, label: str) -> None:
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


def run_query_sharded_w7(
    *,
    query_order: list[QueryKey],
    query_frames: QueryFrameFactory,
    expected_pages_per_query: int,
    checkpoint_root: Path,
    run_identity: dict[str, Any],
    n_bootstrap: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], pd.DataFrame, dict[str, int]]:
    if not query_order:
        raise ValueError("Query-sharded W7 requires at least one query")
    expected_identity = build_run_identity(
        protocol_id=run_identity["protocol_id"],
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
            "Query-sharded W7 run identity does not match frozen semantics"
        )
    run_identity_sha256 = _value_sha256(run_identity)
    plan_path = checkpoint_root / "run_plan.json"
    if plan_path.exists():
        plan, _ = _read_checkpoint(
            plan_path,
            kind="run_plan",
            run_identity_sha256=run_identity_sha256,
        )
        if plan != run_identity:
            raise ValueError("Checkpoint run plan does not match the requested run")
        plan_reused = 1
    else:
        _write_checkpoint(
            plan_path,
            kind="run_plan",
            run_identity_sha256=run_identity_sha256,
            payload=run_identity,
        )
        plan_reused = 0

    profiles = get_profiles(GRID_NAME)
    global_directory = checkpoint_root / "global"
    global_payloads: list[dict[str, Any]] = []
    global_hashes: list[str] = []
    global_reused = 0
    expected_index = 0
    for index, key, frame in query_frames():
        if index != expected_index or key != query_order[index]:
            raise ValueError("Global pass query sequence is not canonical")
        payload, content_sha256, reused = _global_checkpoint(
            global_directory / f"{index:06d}.json",
            run_identity_sha256=run_identity_sha256,
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
        raise ValueError("Global pass did not cover every query")
    _checkpoint_inventory(global_directory, len(query_order), "Global")

    global_profile_index, global_query_metrics = _select_global_profile(global_payloads)
    selection_payload = {
        "profile_index": global_profile_index,
        "profile": profiles[global_profile_index].astype(float).tolist(),
        "global_checkpoint_chain_sha256": _value_sha256(global_hashes),
    }
    selection_path = checkpoint_root / "global_selection.json"
    if selection_path.exists():
        observed_selection, global_selection_sha256 = _read_checkpoint(
            selection_path,
            kind="global_profile_selection",
            run_identity_sha256=run_identity_sha256,
        )
        if observed_selection != selection_payload:
            raise ValueError("Global profile selection checkpoint mismatch")
        selection_reused = 1
    else:
        global_selection_sha256 = _write_checkpoint(
            selection_path,
            kind="global_profile_selection",
            run_identity_sha256=run_identity_sha256,
            payload=selection_payload,
        )
        selection_reused = 0

    query_directory = checkpoint_root / "queries"
    rows: list[dict[str, Any]] = []
    query_reused = 0
    expected_index = 0
    for index, key, frame in query_frames():
        if index != expected_index or key != query_order[index]:
            raise ValueError("Query-oracle pass sequence is not canonical")
        row, _, reused = _query_checkpoint(
            query_directory / f"{index:06d}.json",
            run_identity_sha256=run_identity_sha256,
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
        raise ValueError("Query-oracle pass did not cover every query")
    _checkpoint_inventory(query_directory, len(query_order), "Query")

    summary, subgroup = summarize_oracle_rows(rows, n_bootstrap)
    stats = {
        "plan_reused": plan_reused,
        "global_created": len(query_order) - global_reused,
        "global_reused": global_reused,
        "selection_reused": selection_reused,
        "query_created": len(query_order) - query_reused,
        "query_reused": query_reused,
    }
    return rows, summary, subgroup, stats


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _write_immutable_oracle_outputs(
    output_dir: Path,
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    subgroup: pd.DataFrame,
    run_identity: dict[str, Any],
    checkpoint_root: Path,
    checkpoint_stats: dict[str, int],
) -> None:
    if output_dir.exists():
        raise FileExistsError(f"Oracle output directory already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent)
    )
    try:
        result_frame = _result_frame(rows)
        output_frame = result_frame.drop(
            columns=["relevant_count", "changed_candidates"]
        )
        write_jsonl(rows, staging / "qpaf_oracle_results.jsonl")
        write_json(summary, staging / "qpaf_summary.json")
        write_parquet(output_frame, staging / "qpaf_query_summary.parquet")
        subgroup.to_csv(staging / "qpaf_subgroups.csv", index=False)
        plot_qpaf(output_frame, staging / "qpaf_oracle_gain.png")
        result_files = [
            "qpaf_oracle_results.jsonl",
            "qpaf_summary.json",
            "qpaf_query_summary.parquet",
            "qpaf_subgroups.csv",
            "qpaf_oracle_gain.png",
        ]
        manifest = {
            "schema_version": 1,
            "status": "PASS",
            "classification": "oracle_upper_bound_post_hoc",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "run_identity": run_identity,
            "checkpoint_plan_sha256": sha256_file(checkpoint_root / "run_plan.json"),
            "checkpoint_stats": checkpoint_stats,
            "outputs": {
                name: {
                    "bytes": (staging / name).stat().st_size,
                    "sha256": sha256_file(staging / name),
                }
                for name in result_files
            },
            "boundaries": {
                "oracle_upper_bound_not_deployable_result": True,
                "frozen_p1_02_status": "BLOCKED",
                "p1_03_authorized": False,
                "learned_qpaf_executed": False,
                "modal_or_gpu_used": False,
                "full_score_produced": False,
            },
        }
        write_json(manifest, staging / "run_manifest.json")
        staging.rename(output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def require_full_w7_execution_approval(
    protocol: dict[str, Any],
    repo_root: Path,
) -> str:
    from .vidoseek_p1_02r_oracle import CPU_THREAD_ENV, validate_protocol

    validate_protocol(protocol, repo_root)
    readiness = protocol["execution_readiness"]
    execution = protocol["execution"]
    if readiness.get("ready_for_execution_approval") is not True:
        raise RuntimeError("P1-02R-O1 full W7 is prepared but not authorized")
    for field in [
        "local_cpu_oracle_allowed",
        "oracle_analysis_allowed",
        "full_w7_sharded_allowed",
        "checkpoint_writes_allowed",
        "output_writes_allowed",
    ]:
        if execution.get(field) is not True:
            raise RuntimeError(f"P1-02R-O1 full-W7 execution guard is closed: {field}")
    for field in [
        "performance_probe_allowed",
        "performance_probe_output_write_allowed",
        "full_page_calibration_allowed",
        "full_page_calibration_output_write_allowed",
        "modal_allowed",
        "gpu_allowed",
        "p1_03_allowed",
        "learned_qpaf_allowed",
    ]:
        if execution.get(field) is not False:
            raise RuntimeError(f"P1-02R-O1 forbidden execution flag opened: {field}")
    approval = protocol.get("authorization", {}).get("full_w7_execution", {})
    if (
        approval.get("approved_by") != "user"
        or approval.get("execution_actor") != "human"
        or approval.get("authorized_invocations") != 1
        or approval.get("consumed_invocations") != 0
        or approval.get("remaining_authorized_invocations") != 1
        or approval.get("automatic_retry_allowed") is not False
        or not isinstance(approval.get("approval_commit"), str)
        or len(approval["approval_commit"]) != 40
    ):
        raise RuntimeError("P1-02R-O1 full-W7 approval provenance is incomplete")
    if any(os.environ.get(name) != "1" for name in CPU_THREAD_ENV):
        raise RuntimeError("P1-02R-O1 CPU thread limits are not pinned to one")
    return approval["approval_commit"]


def run_protocol_sharded_w7(protocol_path: Path) -> Path:
    from .vidoseek_p1_02r_oracle import (
        _repo_path,
        load_protocol,
        protocol_bound_preflight,
        text_sha256,
    )

    protocol_path = protocol_path.resolve()
    repo_root = protocol_path.parents[1]
    protocol = load_protocol(protocol_path)
    source_commit = require_full_w7_execution_approval(protocol, repo_root)
    preflight = protocol_bound_preflight(
        protocol_path,
        repo_root,
        allow_recorded_probe_evidence=True,
    )
    scores = protocol["input_bundle"]["retrieval_scores"]
    audit = protocol["input_bundle"]["candidate_audit"]
    scores_path = _repo_path(repo_root, scores["path"])
    audit_path = _repo_path(repo_root, audit["path"])
    query_order = query_order_from_audit(audit_path)
    run_identity = build_run_identity(
        protocol_id=protocol["protocol_id"],
        protocol_sha256=text_sha256(protocol_path),
        source_commit=source_commit,
        retrieval_score_sha256=preflight["retrieval_score_sha256"],
        retrieval_score_content_sha256=preflight["retrieval_score_content_sha256"],
        query_order=query_order,
        pages_per_query=scores["pages_per_query"],
        bootstrap_resamples=protocol["bootstrap"]["resamples"],
    )
    wrapper = protocol["sharded_wrapper"]
    checkpoint_root = _repo_path(repo_root, wrapper["checkpoint_root"])
    rows, summary, subgroup, stats = run_query_sharded_w7(
        query_order=query_order,
        query_frames=lambda: iter_parquet_queries(
            scores_path,
            query_order,
            scores["pages_per_query"],
        ),
        expected_pages_per_query=scores["pages_per_query"],
        checkpoint_root=checkpoint_root,
        run_identity=run_identity,
        n_bootstrap=protocol["bootstrap"]["resamples"],
    )
    output_dir = _repo_path(
        repo_root,
        protocol["planned_outputs"]["immutable_output_dir"],
    )
    _write_immutable_oracle_outputs(
        output_dir,
        rows=rows,
        summary=summary,
        subgroup=subgroup,
        run_identity=run_identity,
        checkpoint_root=checkpoint_root,
        checkpoint_stats=stats,
    )
    return output_dir


def require_full_page_calibration_execution_approval(
    protocol: dict[str, Any],
    repo_root: Path,
) -> str:
    from .vidoseek_p1_02r_oracle import CPU_THREAD_ENV, validate_protocol

    validate_protocol(protocol, repo_root)
    readiness = protocol["execution_readiness"]
    execution = protocol["execution"]
    calibration = protocol["full_page_calibration"]
    if readiness.get("full_page_calibration_authorized") is not True:
        raise RuntimeError(
            "P1-02R-O1 full-page calibration is prepared but not authorized"
        )
    if calibration.get("command_currently_authorized") is not True:
        raise RuntimeError("P1-02R-O1 full-page calibration command is closed")
    for field in [
        "full_page_calibration_allowed",
        "full_page_calibration_output_write_allowed",
        "checkpoint_writes_allowed",
    ]:
        if execution.get(field) is not True:
            raise RuntimeError(
                f"P1-02R-O1 full-page calibration guard is closed: {field}"
            )
    for field in [
        "performance_probe_allowed",
        "performance_probe_output_write_allowed",
        "local_cpu_oracle_allowed",
        "modal_allowed",
        "gpu_allowed",
        "oracle_analysis_allowed",
        "full_w7_sharded_allowed",
        "p1_03_allowed",
        "learned_qpaf_allowed",
        "output_writes_allowed",
    ]:
        if execution.get(field) is not False:
            raise RuntimeError(f"P1-02R-O1 forbidden execution flag opened: {field}")
    approval = protocol.get("authorization", {}).get(
        "full_page_calibration_execution", {}
    )
    if (
        approval.get("approved_by") != "user"
        or approval.get("execution_actor") != "human"
        or approval.get("authorized_invocations") != 1
        or approval.get("consumed_invocations") != 0
        or approval.get("remaining_authorized_invocations") != 1
        or approval.get("automatic_retry_allowed") is not False
        or not isinstance(approval.get("approval_commit"), str)
        or len(approval["approval_commit"]) != 40
    ):
        raise RuntimeError(
            "P1-02R-O1 full-page calibration approval provenance is incomplete"
        )
    if any(os.environ.get(name) != "1" for name in CPU_THREAD_ENV):
        raise RuntimeError("P1-02R-O1 CPU thread limits are not pinned to one")
    return approval["approval_commit"]


def _calibration_attempt_marker(
    protocol: dict[str, Any],
    protocol_sha256: str,
    source_commit: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "STARTED",
        "classification": "engineering_full_page_calibration_attempt_not_result",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol_sha256,
        "approval_commit": source_commit,
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


def _full_page_calibration_worker(
    frame: pd.DataFrame,
    query_key: QueryKey,
    run_identity: dict[str, Any],
    bootstrap_resamples: int,
    result_queue: Any,
) -> None:
    try:
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(
            prefix="p1_02r_o1_full_page_calibration_"
        ) as directory:
            run_query_sharded_w7(
                query_order=[query_key],
                query_frames=lambda: iter_dataframe_queries(
                    frame,
                    [query_key],
                    len(frame),
                ),
                expected_pages_per_query=len(frame),
                checkpoint_root=Path(directory),
                run_identity=run_identity,
                n_bootstrap=bootstrap_resamples,
            )
        result_queue.put({"elapsed_seconds": time.perf_counter() - started})
    except BaseException as error:  # pragma: no cover - parent reports worker failure
        result_queue.put({"error": f"{type(error).__name__}: {error}"})


def run_protocol_full_page_calibration(protocol_path: Path) -> Path:
    from .vidoseek_p1_02r_oracle import (
        CPU_THREAD_ENV,
        PROBE_SCORE_COLUMNS,
        _repo_path,
        build_probe_case,
        complete_process_with_timeout,
        file_sha256,
        load_protocol,
        protocol_bound_preflight,
        text_sha256,
    )

    protocol_path = protocol_path.resolve()
    repo_root = protocol_path.parents[1]
    protocol = load_protocol(protocol_path)
    source_commit = require_full_page_calibration_execution_approval(
        protocol,
        repo_root,
    )
    calibration = protocol["full_page_calibration"]
    protocol_sha256 = text_sha256(protocol_path)
    attempt_path = _repo_path(repo_root, calibration["attempt_marker_path"])
    _write_json_atomic_create_once(
        attempt_path,
        _calibration_attempt_marker(protocol, protocol_sha256, source_commit),
    )
    preflight = protocol_bound_preflight(
        protocol_path,
        repo_root,
        allow_recorded_probe_evidence=True,
    )
    scores = protocol["input_bundle"]["retrieval_scores"]
    audit = protocol["input_bundle"]["candidate_audit"]
    audit_path = _repo_path(repo_root, audit["path"])
    query_order = query_order_from_audit(audit_path)
    query_index = calibration["query_index"]
    query_key = query_order[query_index]
    score_path = _repo_path(repo_root, scores["path"])
    candidates = pd.read_parquet(
        score_path,
        columns=PROBE_SCORE_COLUMNS,
        filters=[
            ("dataset", "==", query_key[0]),
            ("query_id", "==", query_key[1]),
        ],
    )
    frame = build_probe_case(
        candidates,
        [query_key[1]],
        calibration["pages_per_query"],
    )
    calibration_identity = build_run_identity(
        protocol_id=protocol["protocol_id"],
        protocol_sha256=protocol_sha256,
        source_commit=source_commit,
        retrieval_score_sha256=preflight["retrieval_score_sha256"],
        retrieval_score_content_sha256=preflight["retrieval_score_content_sha256"],
        query_order=[query_key],
        pages_per_query=calibration["pages_per_query"],
        bootstrap_resamples=calibration["bootstrap_resamples"],
    )
    context = mp.get_context("spawn")
    result_queue = context.Queue()
    process = context.Process(
        target=_full_page_calibration_worker,
        args=(
            frame,
            query_key,
            calibration_identity,
            calibration["bootstrap_resamples"],
            result_queue,
        ),
    )
    complete_process_with_timeout(
        process,
        float(calibration["hard_timeout_seconds"]),
    )
    try:
        result = result_queue.get(timeout=5)
    except queue.Empty as error:
        raise RuntimeError("Full-page calibration worker returned no timing") from error
    finally:
        result_queue.close()
    if "error" in result:
        raise RuntimeError(f"Full-page calibration worker failed: {result['error']}")
    manifest = {
        "schema_version": 1,
        "status": "PASS",
        "classification": "engineering_full_page_calibration_not_result",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol_sha256,
        "source_commit": source_commit,
        "attempt_marker_sha256": file_sha256(attempt_path),
        "completed_at": datetime.now(timezone.utc).isoformat(),
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
        "calibration_contract": {
            "query_index": query_index,
            "query_id": query_key[1],
            "pages_per_query": len(frame),
            "bootstrap_resamples": calibration["bootstrap_resamples"],
            "cpu_thread_limit": calibration["cpu_thread_limit"],
            "max_workers": calibration["max_workers"],
            "hard_timeout_seconds": calibration["hard_timeout_seconds"],
            "actual_relevance_loaded": False,
            "synthetic_relevance_rule": calibration["synthetic_relevance_rule"],
        },
        "elapsed_seconds": result["elapsed_seconds"],
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
    output_path = _repo_path(repo_root, calibration["output_manifest_path"])
    _write_json_atomic_create_once(output_path, manifest)
    return output_path
