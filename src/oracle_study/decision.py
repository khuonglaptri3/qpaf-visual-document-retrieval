from __future__ import annotations

from .constants import PREREGISTERED_THRESHOLDS


def qpaf_confirmation_gate(discovery: dict, confirmation: dict) -> str:
    threshold = PREREGISTERED_THRESHOLDS["qpaf"]
    d = discovery["grids"]
    c = confirmation["grids"]
    required = {"w7", "w66"}
    if not required.issubset(d) or not required.issubset(c):
        return "inconclusive"
    def strong_for_grid(grid: str) -> bool:
        return (
            d[grid]["mean_delta_ndcg10"] >= threshold["discovery_mean_delta_ndcg10_min"]
            and c[grid]["mean_delta_ndcg10"] >= threshold["confirmation_mean_delta_ndcg10_min"]
            and c[grid]["delta_ci95"][0] > threshold["confirmation_ci95_lower_min_exclusive"]
            and c[grid]["fraction_gain_ge_005"]
            >= threshold["confirmation_fraction_gain_ge_005_min"]
        )

    strong = all(strong_for_grid(grid) for grid in required)
    if strong:
        return "pass"
    primary = c["w7"]
    concentrated = (
        primary.get("top_5pct_gain_share", 0.0)
        >= threshold["no_go_top_5pct_gain_share_min"]
    )
    if (
        primary["mean_delta_ndcg10"]
        < threshold["no_go_confirmation_mean_delta_ndcg10_below"]
        or concentrated
    ):
        return "fail"
    return "inconclusive"


def budget_confirmation_gate(discovery: dict, confirmation: dict) -> str:
    threshold = PREREGISTERED_THRESHOLDS["budget_aware"]
    keys = [
        "full_minus_stage1",
        "beneficial_fraction",
        "non_beneficial_fraction",
        "b_star_percent",
        "control_gap_at_b_star",
        "retention_ci95",
    ]
    if any(key not in discovery or key not in confirmation for key in keys):
        return "inconclusive"
    def strong(summary: dict) -> bool:
        return (
            summary["full_minus_stage1"] >= threshold["full_minus_stage1_min"]
            and summary["beneficial_fraction"]
            >= threshold["beneficial_and_non_beneficial_fraction_min"]
            and summary["non_beneficial_fraction"]
            >= threshold["beneficial_and_non_beneficial_fraction_min"]
            and summary["b_star_percent"] <= threshold["b_star_percent_max"]
            and summary["control_gap_at_b_star"] >= threshold["control_gap_at_b_star_min"]
            and summary["retention_ci95"][0] >= threshold["retention_ci95_lower_min"]
        )
    if strong(discovery) and strong(confirmation):
        return "pass"
    if (
        confirmation["full_minus_stage1"] < threshold["no_go_full_minus_stage1_below"]
        or confirmation["b_star_percent"] > threshold["no_go_b_star_percent_above"]
    ):
        return "fail"
    return "inconclusive"


def final_decision(
    qpaf_discovery: dict | None,
    qpaf_confirmation: dict | None,
    budget_discovery: dict | None,
    budget_confirmation: dict | None,
) -> dict:
    qpaf = (
        qpaf_confirmation_gate(qpaf_discovery, qpaf_confirmation)
        if qpaf_discovery and qpaf_confirmation
        else "not_run"
    )
    budget = (
        budget_confirmation_gate(budget_discovery, budget_confirmation)
        if budget_discovery and budget_confirmation
        else "not_run"
    )
    if budget == "pass":
        choice = "budget_aware_adaptive_heaven"
    elif qpaf == "pass":
        choice = "qpaf"
    elif budget == "fail" and qpaf == "fail":
        choice = "reject_both"
    else:
        choice = "inconclusive_do_not_rewrite_proposal"
    return {
        "qpaf_gate": qpaf,
        "budget_gate": budget,
        "recommended_direction": choice,
        "preregistered_thresholds": PREREGISTERED_THRESHOLDS,
        "observed": {
            "qpaf_discovery": qpaf_discovery,
            "qpaf_confirmation": qpaf_confirmation,
            "budget_discovery": budget_discovery,
            "budget_confirmation": budget_confirmation,
        },
    }
