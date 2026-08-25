from __future__ import annotations


def _assess_direction(gain: dict, coverage: float) -> dict:
    checks = {
        "candidate_coverage_ge_095": coverage >= 0.95,
        "mean_gain_ge_001": gain["mean_delta_ndcg10"] >= 0.01,
        "ci95_lower_gt_zero": gain["delta_ci95"][0] > 0,
        "fraction_gain_ge_003_at_least_010": gain["fraction_gain_ge_003"] >= 0.10,
        "top_5pct_gain_share_below_090": gain["top_5pct_gain_share"] < 0.90,
    }
    feasible = all(checks.values())
    strong = feasible and gain["mean_delta_ndcg10"] >= 0.03
    if not checks["candidate_coverage_ge_095"]:
        status = "invalid_candidate_coverage"
    elif strong:
        status = "strong_signal_for_full_discovery"
    elif feasible:
        status = "feasible_signal"
    else:
        status = "no_clear_signal_on_finance_en_pilot"
    return {"status": status, "checks": checks, **gain}


def assess_short_pilot(oracle_summary: dict, coverage_report: dict, grid: str = "w7") -> dict:
    if grid not in oracle_summary.get("grids", {}):
        raise ValueError(f"Oracle summary does not contain grid {grid!r}")
    coverage = float(coverage_report["final_coverage"])
    grid_summary = oracle_summary["grids"][grid]
    return {
        "study": "vidore_v3_finance_en_short_oracle",
        "scope": "exploratory_feasibility_not_formal_go_no_go",
        "grid": grid,
        "queries": int(grid_summary["queries"]),
        "candidate_coverage": coverage,
        "qarf_vs_global": _assess_direction(grid_summary["qarf_vs_global"], coverage),
        "qpaf_vs_qarf": _assess_direction(grid_summary["qpaf_vs_qarf"], coverage),
    }


def feasibility_markdown(report: dict) -> str:
    lines = [
        "# ViDoRe V3 Finance EN — Short Oracle Feasibility",
        "",
        "> Exploratory pilot only. This report is not a formal Discovery GO/NO-GO decision.",
        "",
        f"- Queries: **{report['queries']}**",
        f"- Candidate coverage: **{report['candidate_coverage']:.4f}**",
        f"- Weight grid: **{report['grid']}**",
        "",
        "| Direction | Mean gain | 95% CI | Fraction gain >= .03 | Top-5% gain share | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for key, label in [("qarf_vs_global", "Global -> QARF"), ("qpaf_vs_qarf", "QARF -> QPAF")]:
        item = report[key]
        lines.append(
            f"| {label} | {item['mean_delta_ndcg10']:.4f} | "
            f"[{item['delta_ci95'][0]:.4f}, {item['delta_ci95'][1]:.4f}] | "
            f"{item['fraction_gain_ge_003']:.3f} | {item['top_5pct_gain_share']:.3f} | "
            f"`{item['status']}` |"
        )
    lines.extend(
        [
            "",
            "A strong signal justifies the full ViDoRe V3 English Discovery study. A negative result here "
            "must not be generalized beyond the finance_en corpus.",
            "",
        ]
    )
    return "\n".join(lines)
