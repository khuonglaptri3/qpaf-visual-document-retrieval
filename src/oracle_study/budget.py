from __future__ import annotations

import numpy as np
import pandas as pd

from .bootstrap import bootstrap_ratio_ci
from .constants import PREREGISTERED_THRESHOLDS, QUERY_METRIC_COLUMNS, SEED
from .io import require_columns


def _select_quality(stage1: np.ndarray, full: np.ndarray, selected: np.ndarray) -> np.ndarray:
    return np.where(selected, full, stage1)


def run_budget_oracle(
    metrics: pd.DataFrame,
    random_repeats: int = 100,
    n_bootstrap: int = 10_000,
    seed: int = SEED,
) -> tuple[list[dict], pd.DataFrame, dict]:
    require_columns(metrics, QUERY_METRIC_COLUMNS, "query metric table")
    if metrics.duplicated(["dataset", "query_id"]).any():
        raise ValueError("Query metric table contains duplicate dataset/query rows")
    if metrics.empty:
        raise ValueError("Budget oracle requires at least one query")
    stage1 = metrics["ndcg_stage1"].to_numpy(float)
    full = metrics["ndcg_full"].to_numpy(float)
    margin = metrics["stage1_margin"].to_numpy(float)
    if not np.isfinite(np.column_stack([stage1, full, margin])).all():
        raise ValueError("Budget oracle requires finite stage1/full metrics and margins")
    query_ids = metrics["query_id"].astype(str).to_numpy()
    gain = full - stage1
    stage2_ms = metrics["stage2_ms"].to_numpy(float)
    stage2_flops = metrics["stage2_flops"].to_numpy(float)
    if (
        not np.isfinite(np.column_stack([stage2_ms, stage2_flops])).all()
        or (stage2_ms <= 0).any()
        or (stage2_flops <= 0).any()
    ):
        raise ValueError("Budget oracle requires finite, positive per-query Stage-2 latency and FLOPs")
    n = len(metrics)
    oracle_order = np.lexsort((query_ids, -gain))
    margin_order = np.lexsort((query_ids, margin))
    latency_efficiency = np.divide(
        gain,
        stage2_ms,
        out=np.full(n, -np.inf, dtype=float),
        where=np.isfinite(stage2_ms) & (stage2_ms > 0),
    )
    flops_efficiency = np.divide(
        gain,
        stage2_flops,
        out=np.full(n, -np.inf, dtype=float),
        where=np.isfinite(stage2_flops) & (stage2_flops > 0),
    )
    latency_order = np.lexsort((query_ids, -latency_efficiency))
    flops_order = np.lexsort((query_ids, -flops_efficiency))
    rng = np.random.default_rng(seed)
    curve_rows = []
    selections = {}
    full_mean = float(full.mean())
    secondary_pairs = {
        metric: (
            metrics[f"{metric}_stage1"].to_numpy(float),
            metrics[f"{metric}_full"].to_numpy(float),
        )
        for metric in ["recall1", "recall3", "mrr10"]
        if f"{metric}_stage1" in metrics and f"{metric}_full" in metrics
    }

    for budget in range(0, 101, 5):
        count = int(round(n * budget / 100.0))
        oracle_selected = np.zeros(n, dtype=bool)
        oracle_selected[oracle_order[:count]] = True
        margin_selected = np.zeros(n, dtype=bool)
        margin_selected[margin_order[:count]] = True
        latency_selected = np.zeros(n, dtype=bool)
        latency_selected[latency_order[:count]] = True
        flops_selected = np.zeros(n, dtype=bool)
        flops_selected[flops_order[:count]] = True
        oracle_values = _select_quality(stage1, full, oracle_selected)
        margin_values = _select_quality(stage1, full, margin_selected)
        latency_values = _select_quality(stage1, full, latency_selected)
        flops_values = _select_quality(stage1, full, flops_selected)
        random_means = []
        for _ in range(random_repeats):
            random_selected = np.zeros(n, dtype=bool)
            if count:
                random_selected[rng.choice(n, size=count, replace=False)] = True
            random_means.append(float(_select_quality(stage1, full, random_selected).mean()))
        curve_row = {
                "budget_percent": budget,
                "invocations": count,
                "oracle_ndcg10": float(oracle_values.mean()),
                "margin_ndcg10": float(margin_values.mean()),
                "random_ndcg10": float(np.mean(random_means)),
                "cheap_ndcg10": float(stage1.mean()),
                "full_ndcg10": full_mean,
                "oracle_stage2_ms": float(np.nansum(stage2_ms[oracle_selected])),
                "oracle_stage2_flops": float(np.nansum(stage2_flops[oracle_selected])),
                "latency_efficient_ndcg10": float(latency_values.mean()),
                "latency_efficient_stage2_ms": float(np.nansum(stage2_ms[latency_selected])),
                "flops_efficient_ndcg10": float(flops_values.mean()),
                "flops_efficient_stage2_flops": float(np.nansum(stage2_flops[flops_selected])),
            }
        for metric, (cheap_metric, full_metric) in secondary_pairs.items():
            curve_row[f"oracle_{metric}"] = float(
                _select_quality(cheap_metric, full_metric, oracle_selected).mean()
            )
            curve_row[f"cheap_{metric}"] = float(cheap_metric.mean())
            curve_row[f"full_{metric}"] = float(full_metric.mean())
        curve_rows.append(curve_row)
        selections[budget] = oracle_selected

    curve = pd.DataFrame(curve_rows)
    threshold = PREREGISTERED_THRESHOLDS["budget_aware"]
    retention = (
        curve["oracle_ndcg10"].to_numpy(float) / full_mean
        if abs(full_mean) > 1e-15
        else np.ones(len(curve), dtype=float)
    )
    eligible = curve[
        (
            curve["oracle_ndcg10"]
            >= full_mean - threshold["quality_absolute_tolerance"]
        )
        & (retention >= threshold["retention_ci95_lower_min"])
    ]
    b_star = int(eligible.iloc[0]["budget_percent"]) if not eligible.empty else 100
    selected_at_b = selections[b_star]
    selected_values = _select_quality(stage1, full, selected_at_b)
    retention_ci = bootstrap_ratio_ci(selected_values, full, n_bootstrap, seed)
    b_row = curve.loc[curve["budget_percent"] == b_star].iloc[0]
    beneficial = gain > threshold["beneficial_gain_exclusive"]
    full_gain = float(full.mean() - stage1.mean())
    control_gap = float(
        b_row["oracle_ndcg10"] - max(b_row["margin_ndcg10"], b_row["random_ndcg10"])
    )

    strong = (
        full_gain >= threshold["full_minus_stage1_min"]
        and float(beneficial.mean()) >= threshold["beneficial_and_non_beneficial_fraction_min"]
        and float((~beneficial).mean()) >= threshold["beneficial_and_non_beneficial_fraction_min"]
        and b_star <= threshold["b_star_percent_max"]
        and control_gap >= threshold["control_gap_at_b_star_min"]
        and retention_ci[0] >= threshold["retention_ci95_lower_min"]
    )
    no_go = (
        full_gain < threshold["no_go_full_minus_stage1_below"]
        or b_star > threshold["no_go_b_star_percent_above"]
    )
    gate = "pass" if strong else "fail" if no_go else "inconclusive"

    per_query = []
    for index, row in metrics.reset_index(drop=True).iterrows():
        per_query.append(
            {
                "dataset": str(row["dataset"]),
                "query_id": str(row["query_id"]),
                "source": str(row["source"]),
                "ndcg_stage1": float(stage1[index]),
                "ndcg_full": float(full[index]),
                "delta_ndcg10": float(gain[index]),
                "beneficial": bool(beneficial[index]),
                "selected_at_b_star": bool(selected_at_b[index]),
                "stage2_ms": None if pd.isna(row["stage2_ms"]) else float(row["stage2_ms"]),
                "stage2_flops": None if pd.isna(row["stage2_flops"]) else float(row["stage2_flops"]),
            }
        )
    summary = {
        "queries": n,
        "mean_stage1_ndcg10": float(stage1.mean()),
        "mean_full_ndcg10": full_mean,
        "full_minus_stage1": full_gain,
        "beneficial_fraction": float(beneficial.mean()),
        "non_beneficial_fraction": float((~beneficial).mean()),
        "b_star_percent": b_star,
        "quality_at_b_star": float(b_row["oracle_ndcg10"]),
        "control_gap_at_b_star": control_gap,
        "retention_ci95": [float(retention_ci[0]), float(retention_ci[1])],
        "discovery_gate": gate,
    }
    for metric in secondary_pairs:
        summary[f"{metric}_at_b_star"] = float(b_row[f"oracle_{metric}"])
        summary[f"{metric}_stage1"] = float(b_row[f"cheap_{metric}"])
        summary[f"{metric}_full"] = float(b_row[f"full_{metric}"])
    return per_query, curve, summary
