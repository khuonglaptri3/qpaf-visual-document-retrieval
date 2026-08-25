from __future__ import annotations

SEED = 20260820

PREREGISTERED_THRESHOLDS = {
    "qpaf": {
        "discovery_mean_delta_ndcg10_min": 0.03,
        "confirmation_mean_delta_ndcg10_min": 0.02,
        "confirmation_ci95_lower_min_exclusive": 0.0,
        "confirmation_fraction_gain_ge_005_min": 0.20,
        "no_go_confirmation_mean_delta_ndcg10_below": 0.01,
        "no_go_top_5pct_gain_share_min": 0.90,
        "must_hold_for_grids": ["w7", "w66"],
    },
    "budget_aware": {
        "quality_absolute_tolerance": 0.01,
        "beneficial_gain_exclusive": 0.01,
        "full_minus_stage1_min": 0.02,
        "beneficial_and_non_beneficial_fraction_min": 0.20,
        "b_star_percent_max": 50,
        "control_gap_at_b_star_min": 0.01,
        "retention_ci95_lower_min": 0.98,
        "no_go_full_minus_stage1_below": 0.01,
        "no_go_b_star_percent_above": 70,
    },
}

SCORE_COLUMNS = [
    "dataset",
    "query_id",
    "page_id",
    "relevance",
    "bm25_score",
    "dense_score",
    "stage1_score",
    "visual_score",
    "branch_ranks",
]

QUERY_METRIC_COLUMNS = [
    "dataset",
    "query_id",
    "source",
    "relevant_count",
    "ndcg_stage1",
    "ndcg_full",
    "recall_stage1",
    "recall_full",
    "stage1_margin",
    "stage2_ms",
    "stage2_flops",
]

SECONDARY_QUERY_METRIC_COLUMNS = [
    "recall1_stage1",
    "recall1_full",
    "recall3_stage1",
    "recall3_full",
    "mrr10_stage1",
    "mrr10_full",
]

RAW_SCORE_COLUMNS = [
    "dataset",
    "query_id",
    "page_id",
    "source",
    "relevance",
    "bm25_score",
    "dense_score",
    "stage1_score",
    "visual_score",
    "full_score",
]

SCORE_NAMES = ["bm25_score", "dense_score", "stage1_score", "visual_score"]
