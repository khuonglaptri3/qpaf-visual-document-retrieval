from __future__ import annotations

import bisect
from dataclasses import asdict

import numpy as np
import pandas as pd

from .bootstrap import bootstrap_mean_ci
from .constants import PREREGISTERED_THRESHOLDS, SCORE_COLUMNS
from .io import require_columns
from .metrics import RankingMetrics, dcg_at_k, evaluate_scores, stable_order
from .profiles import get_profiles


TOLERANCE = 1e-12


def _better_metrics(candidate: RankingMetrics, current: RankingMetrics) -> bool:
    candidate_key = (candidate.ndcg10, candidate.recall3, candidate.mrr10)
    current_key = (current.ndcg10, current.recall3, current.mrr10)
    for left, right in zip(candidate_key, current_key):
        if left > right + TOLERANCE:
            return True
        if left < right - TOLERANCE:
            return False
    return False


def _query_oracle(
    score_matrix: np.ndarray,
    relevance: np.ndarray,
    page_ids: np.ndarray,
    profiles: np.ndarray,
) -> tuple[int, np.ndarray, RankingMetrics]:
    best_index = 0
    best_scores = score_matrix @ profiles[0]
    best_metrics = evaluate_scores(best_scores, relevance, page_ids)
    for index in range(1, len(profiles)):
        scores = score_matrix @ profiles[index]
        metrics = evaluate_scores(scores, relevance, page_ids)
        if _better_metrics(metrics, best_metrics):
            best_index = index
            best_scores = scores
            best_metrics = metrics
    return best_index, best_scores, best_metrics


def _mean_metrics(metrics: list[RankingMetrics]) -> RankingMetrics:
    return RankingMetrics(
        ndcg10=float(np.mean([item.ndcg10 for item in metrics])),
        recall1=float(np.mean([item.recall1 for item in metrics])),
        recall3=float(np.mean([item.recall3 for item in metrics])),
        mrr10=float(np.mean([item.mrr10 for item in metrics])),
    )


def _global_oracle(
    query_data: list[dict],
    profiles: np.ndarray,
) -> tuple[int, list[RankingMetrics]]:
    """Choose one profile for every query, with the same metric tie-break as QARF."""
    best_index = 0
    best_per_query = [
        evaluate_scores(item["score_matrix"] @ profiles[0], item["relevance"], item["page_ids"])
        for item in query_data
    ]
    best_mean = _mean_metrics(best_per_query)
    for index in range(1, len(profiles)):
        per_query = [
            evaluate_scores(item["score_matrix"] @ profiles[index], item["relevance"], item["page_ids"])
            for item in query_data
        ]
        mean = _mean_metrics(per_query)
        if _better_metrics(mean, best_mean):
            best_index = index
            best_per_query = per_query
            best_mean = mean
    return best_index, best_per_query


def _discounts(length: int, k: int = 10) -> np.ndarray:
    discounts = np.zeros(length + 1, dtype=float)
    active = min(length, k)
    discounts[:active] = 1.0 / np.log2(np.arange(2, active + 2, dtype=float))
    return discounts


def _single_item_ndcg(
    current_scores: np.ndarray,
    relevance: np.ndarray,
    page_ids: np.ndarray,
    candidate_index: int,
    new_score: float,
    current_ndcg: float,
    k: int = 10,
) -> float:
    order = stable_order(current_scores, page_ids)
    positions = np.empty(len(order), dtype=int)
    positions[order] = np.arange(len(order))
    old_position = int(positions[candidate_index])
    other_order = order[order != candidate_index]
    other_keys = [(-float(current_scores[i]), str(page_ids[i])) for i in other_order]
    new_position = bisect.bisect_left(other_keys, (-float(new_score), str(page_ids[candidate_index])))
    if new_position == old_position:
        return current_ndcg

    gains = np.power(2.0, relevance.astype(float)) - 1.0
    ranked_gains = gains[order]
    discounts = _discounts(len(order), k)
    ideal_dcg = dcg_at_k(np.sort(relevance)[::-1], k)
    if ideal_dcg <= 0:
        return 0.0
    current_dcg = current_ndcg * ideal_dcg
    item_gain = gains[candidate_index]
    delta = item_gain * (discounts[new_position] - discounts[old_position])

    if new_position < old_position:
        shifts = ranked_gains * (discounts[1:] - discounts[:-1])
        delta += float(shifts[new_position:old_position].sum())
    else:
        shifts = np.zeros(len(order), dtype=float)
        shifts[1:] = ranked_gains[1:] * (discounts[:-2] - discounts[1:-1])
        delta += float(shifts[old_position + 1 : new_position + 1].sum())
    return max(0.0, min(1.0, (current_dcg + delta) / ideal_dcg))


def _candidate_oracle(
    score_matrix: np.ndarray,
    relevance: np.ndarray,
    page_ids: np.ndarray,
    profiles: np.ndarray,
    query_profile_index: int,
    query_scores: np.ndarray,
    query_metrics: RankingMetrics,
    max_sweeps: int = 2,
) -> tuple[np.ndarray, np.ndarray, RankingMetrics, int]:
    assignments = np.full(len(page_ids), query_profile_index, dtype=int)
    current_scores = query_scores.copy()
    current_metrics = query_metrics
    fixed_order = stable_order(query_scores, page_ids)
    changes = 0

    for _ in range(max_sweeps):
        changed_this_sweep = 0
        for candidate_index in fixed_order:
            best_profile = int(assignments[candidate_index])
            best_ndcg = current_metrics.ndcg10
            best_score = float(current_scores[candidate_index])
            for profile_index, profile in enumerate(profiles):
                if profile_index == assignments[candidate_index]:
                    continue
                new_score = float(score_matrix[candidate_index] @ profile)
                ndcg = _single_item_ndcg(
                    current_scores,
                    relevance,
                    page_ids,
                    int(candidate_index),
                    new_score,
                    current_metrics.ndcg10,
                )
                if ndcg > best_ndcg + TOLERANCE:
                    best_profile = profile_index
                    best_ndcg = ndcg
                    best_score = new_score
            if best_profile != assignments[candidate_index]:
                assignments[candidate_index] = best_profile
                current_scores[candidate_index] = best_score
                current_metrics = evaluate_scores(current_scores, relevance, page_ids)
                changed_this_sweep += 1
                changes += 1
        if changed_this_sweep == 0:
            break
    return assignments, current_scores, current_metrics, changes


def run_qpaf_oracle(
    scores: pd.DataFrame,
    grids: tuple[str, ...] = ("w7", "w66"),
    n_bootstrap: int = 10_000,
) -> tuple[list[dict], dict, pd.DataFrame]:
    require_columns(scores, SCORE_COLUMNS, "retrieval score table")
    if scores.empty:
        raise ValueError("QPAF oracle requires at least one candidate row")
    query_data: list[dict] = []
    for (dataset, query_id), group in scores.groupby(["dataset", "query_id"], sort=False):
        group = group.sort_values("page_id", kind="stable")
        query_data.append(
            {
                "dataset": str(dataset),
                "query_id": str(query_id),
                "source": str(group["source"].iloc[0]) if "source" in group else "unknown",
                "score_matrix": group[["bm25_score", "dense_score", "visual_score"]].to_numpy(float),
                "relevance": group["relevance"].to_numpy(float),
                "page_ids": group["page_id"].astype(str).to_numpy(),
            }
        )

    rows: list[dict] = []
    for grid_name in grids:
        profiles = get_profiles(grid_name)
        global_profile, global_metrics = _global_oracle(query_data, profiles)
        for item, global_query_metrics in zip(query_data, global_metrics):
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
            changed_pages = {
                str(page_ids[index]): [float(x) for x in profiles[assignments[index]]]
                for index in np.flatnonzero(changed_mask)
            }
            counts = np.bincount(assignments, minlength=len(profiles))
            rows.append(
                {
                    "dataset": item["dataset"],
                    "query_id": item["query_id"],
                    "source": item["source"],
                    "relevant_count": int(np.count_nonzero(relevance > 0)),
                    "grid": grid_name,
                    "global_profile": [float(x) for x in profiles[global_profile]],
                    "global_metrics": asdict(global_query_metrics),
                    "qarf_profile": [float(x) for x in profiles[query_profile]],
                    "qarf_metrics": asdict(query_metrics),
                    "qpaf_metrics": asdict(candidate_metrics),
                    "delta_qarf_vs_global": query_metrics.ndcg10 - global_query_metrics.ndcg10,
                    "delta_qpaf_vs_qarf": candidate_metrics.ndcg10 - query_metrics.ndcg10,
                    "delta_qpaf_vs_global": candidate_metrics.ndcg10 - global_query_metrics.ndcg10,
                    # Backward-compatible alias used by the original QPAF reports.
                    "delta_ndcg10": candidate_metrics.ndcg10 - query_metrics.ndcg10,
                    "changed_candidates": int(np.count_nonzero(changed_mask)),
                    "accepted_updates": int(changes),
                    "profile_counts": counts.astype(int).tolist(),
                    "changed_pages": changed_pages,
                }
            )

    result_frame = pd.DataFrame(
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
    summaries = {}
    for grid_name, group in result_frame.groupby("grid", sort=False):
        qarf_delta = group["delta_qarf_vs_global"].to_numpy(float)
        qpaf_delta = group["delta_qpaf_vs_qarf"].to_numpy(float)

        def gain_summary(delta: np.ndarray) -> dict:
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
            "qpaf_vs_global": gain_summary(group["delta_qpaf_vs_global"].to_numpy(float)),
            # Backward-compatible QPAF-vs-QARF summary fields.
            **qpaf_gain,
            "mean_changed_candidates": float(group["changed_candidates"].mean()),
            "profile_counts": profile_totals.astype(int).tolist(),
        }
    primary = summaries.get("w7", next(iter(summaries.values())))
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
        result_frame.groupby(["grid", "source", result_frame["relevant_count"].gt(1).map({True: "multi", False: "single"})])
        .agg(
            queries=("query_id", "size"),
            mean_delta_qarf_vs_global=("delta_qarf_vs_global", "mean"),
            mean_delta_qpaf_vs_qarf=("delta_qpaf_vs_qarf", "mean"),
            mean_delta_qpaf_vs_global=("delta_qpaf_vs_global", "mean"),
        )
        .reset_index(names=["grid", "source", "relevance_group"])
    )
    return rows, summary, subgroup
