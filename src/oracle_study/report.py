from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_qpaf(result_frame: pd.DataFrame, output: str | Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for grid, group in result_frame.groupby("grid", sort=False):
        axes[0].hist(group["delta_qarf_vs_global"], bins=20, alpha=0.55, label=f"QARF {grid}")
        axes[0].hist(group["delta_qpaf_vs_qarf"], bins=20, alpha=0.45, label=f"QPAF {grid}")
        axes[1].scatter(group["global_ndcg10"], group["qarf_ndcg10"], s=9, alpha=0.45, label=grid)
        axes[2].scatter(group["qarf_ndcg10"], group["qpaf_ndcg10"], s=9, alpha=0.45, label=grid)
    axes[0].set_title("Adaptive fusion oracle gain")
    axes[0].set_xlabel("Δ nDCG@10")
    axes[0].set_ylabel("Queries")
    axes[1].plot([0, 1], [0, 1], color="black", linewidth=1)
    axes[1].set_title("Global vs QARF")
    axes[1].set_xlabel("Global nDCG@10")
    axes[1].set_ylabel("QARF nDCG@10")
    axes[2].plot([0, 1], [0, 1], color="black", linewidth=1)
    axes[2].set_title("QARF vs QPAF")
    axes[2].set_xlabel("QARF nDCG@10")
    axes[2].set_ylabel("QPAF nDCG@10")
    for axis in axes:
        axis.legend()
        axis.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_budget(curve: pd.DataFrame, output: str | Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(7, 4.5))
    axis.plot(curve["budget_percent"], curve["oracle_ndcg10"], marker="o", label="Oracle")
    axis.plot(curve["budget_percent"], curve["margin_ndcg10"], label="Stage-1 margin")
    axis.plot(curve["budget_percent"], curve["random_ndcg10"], label="Random")
    axis.axhline(curve["full_ndcg10"].iloc[0], color="black", linestyle="--", label="Full HEAVEN")
    axis.axhline(curve["cheap_ndcg10"].iloc[0], color="gray", linestyle=":", label="Stage 1")
    axis.set_xlabel("Stage-2 invocation budget (%)")
    axis.set_ylabel("Mean nDCG@10")
    axis.set_title("Budget-aware oracle curve")
    axis.grid(alpha=0.2)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_budget_cost(curve: pd.DataFrame, output: str | Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(
        curve["latency_efficient_stage2_ms"],
        curve["latency_efficient_ndcg10"],
        marker="o",
    )
    axes[0].set_xlabel("Cumulative Stage-2 latency (ms)")
    axes[0].set_ylabel("Mean nDCG@10")
    axes[0].set_title("Gain / latency oracle")
    axes[1].plot(
        curve["flops_efficient_stage2_flops"],
        curve["flops_efficient_ndcg10"],
        marker="o",
    )
    axes[1].set_xlabel("Cumulative Stage-2 FLOPs")
    axes[1].set_ylabel("Mean nDCG@10")
    axes[1].set_title("Gain / FLOPs oracle")
    for axis in axes:
        axis.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def decision_markdown(decision: dict) -> str:
    return (
        "# Oracle Study Decision\n\n"
        f"- QPAF gate: **{decision['qpaf_gate']}**\n"
        f"- Budget-Aware gate: **{decision['budget_gate']}**\n"
        f"- Recommended direction: **{decision['recommended_direction']}**\n\n"
        "The decision uses the preregistered thresholds. Do not reinterpret a failed or "
        "inconclusive gate as a positive result.\n\n"
        "## Preregistered thresholds\n\n"
        "```json\n"
        f"{json.dumps(decision['preregistered_thresholds'], indent=2)}\n"
        "```\n\n"
        "## Observed summaries\n\n"
        "```json\n"
        f"{json.dumps(decision['observed'], indent=2)}\n"
        "```\n"
    )
