from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .constants import QUERY_METRIC_COLUMNS, SCORE_COLUMNS
from .io import dataframe_sha256, require_columns


def run_preflight(
    scores: pd.DataFrame,
    metrics: pd.DataFrame,
    reference_means: dict[str, float] | None = None,
    reproduction_tolerance: float = 0.01,
) -> dict:
    require_columns(scores, SCORE_COLUMNS, "retrieval score table")
    require_columns(metrics, QUERY_METRIC_COLUMNS, "query metric table")
    duplicate_scores = int(scores.duplicated(["dataset", "query_id", "page_id"]).sum())
    duplicate_metrics = int(metrics.duplicated(["dataset", "query_id"]).sum())
    score_queries = set(zip(scores["dataset"].astype(str), scores["query_id"].astype(str)))
    metric_queries = set(zip(metrics["dataset"].astype(str), metrics["query_id"].astype(str)))
    missing_metrics = sorted(score_queries - metric_queries)
    orphan_metrics = sorted(metric_queries - score_queries)
    invalid_ranks = 0
    for value in scores["branch_ranks"]:
        try:
            parsed = json.loads(value) if isinstance(value, str) else value
            if not all(int(parsed[key]) >= 1 for key in ["bm25", "dense", "stage1", "visual"]):
                invalid_ranks += 1
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            invalid_ranks += 1
    numeric_score_columns = ["relevance", "bm25_score", "dense_score", "stage1_score", "visual_score"]
    finite_scores = bool(np.isfinite(scores[numeric_score_columns].to_numpy(float)).all())
    metric_quality_columns = [
        "ndcg_stage1",
        "ndcg_full",
        "recall_stage1",
        "recall_full",
        "stage1_margin",
    ]
    metric_values = metrics[metric_quality_columns].to_numpy(float)
    finite_metrics = bool(np.isfinite(metric_values).all())
    bounded_quality_metrics = bool(
        np.logical_and(
            metrics[["ndcg_stage1", "ndcg_full", "recall_stage1", "recall_full"]]
            .to_numpy(float)
            >= 0,
            metrics[["ndcg_stage1", "ndcg_full", "recall_stage1", "recall_full"]]
            .to_numpy(float)
            <= 1,
        ).all()
    )
    cost_values = metrics[["stage2_ms", "stage2_flops"]].to_numpy(float)
    valid_stage2_costs = bool(np.isfinite(cost_values).all() and (cost_values > 0).all())
    reproduction_deltas = {}
    reproduction_passed = True
    for column, expected in (reference_means or {}).items():
        if column not in metrics:
            reproduction_deltas[column] = None
            reproduction_passed = False
            continue
        delta = float(metrics[column].mean() - float(expected))
        reproduction_deltas[column] = delta
        reproduction_passed = reproduction_passed and abs(delta) <= reproduction_tolerance
    passed = (
        duplicate_scores == 0
        and duplicate_metrics == 0
        and not missing_metrics
        and not orphan_metrics
        and invalid_ranks == 0
        and finite_scores
        and finite_metrics
        and bounded_quality_metrics
        and valid_stage2_costs
        and reproduction_passed
    )
    return {
        "passed": passed,
        "score_rows": int(len(scores)),
        "query_rows": int(len(metrics)),
        "duplicate_score_rows": duplicate_scores,
        "duplicate_query_rows": duplicate_metrics,
        "missing_query_metrics": missing_metrics[:20],
        "orphan_query_metrics": orphan_metrics[:20],
        "invalid_branch_ranks": invalid_ranks,
        "finite_scores": finite_scores,
        "finite_metrics": finite_metrics,
        "bounded_quality_metrics": bounded_quality_metrics,
        "valid_positive_stage2_costs": valid_stage2_costs,
        "retrieval_score_content_sha256": dataframe_sha256(
            scores, ["dataset", "query_id", "page_id"]
        ),
        "query_metric_content_sha256": dataframe_sha256(
            metrics, ["dataset", "query_id"]
        ),
        "reproduction_tolerance": reproduction_tolerance,
        "reproduction_deltas": reproduction_deltas,
        "reproduction_passed": reproduction_passed,
    }
