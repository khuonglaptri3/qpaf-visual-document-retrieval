from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .constants import (
    QUERY_METRIC_COLUMNS,
    RAW_SCORE_COLUMNS,
    SCORE_COLUMNS,
    SECONDARY_QUERY_METRIC_COLUMNS,
)
from .io import require_columns
from .metrics import evaluate_scores, minmax, stable_order


class CoverageError(RuntimeError):
    def __init__(self, message: str, report: dict, query_audit: pd.DataFrame):
        super().__init__(message)
        self.report = report
        self.query_audit = query_audit


@dataclass(frozen=True)
class CacheBuildResult:
    retrieval_scores: pd.DataFrame
    query_metrics: pd.DataFrame
    query_audit: pd.DataFrame
    coverage_report: dict


def _rank(frame: pd.DataFrame, score_col: str) -> pd.Series:
    result = pd.Series(index=frame.index, dtype="int64")
    for _, group in frame.groupby(["dataset", "query_id"], sort=False):
        order = np.lexsort(
            (
                group["page_id"].astype(str).to_numpy(),
                -group[score_col].astype(float).to_numpy(),
            )
        )
        ranks = np.empty(len(group), dtype=int)
        ranks[order] = np.arange(1, len(group) + 1)
        result.loc[group.index] = ranks
    return result.astype(int)


def _coverage(frame: pd.DataFrame, selected: pd.Series) -> float:
    positives = frame["relevance"].astype(float) > 0
    total = int(positives.sum())
    return 1.0 if total == 0 else float((positives & selected).sum() / total)


def _query_coverage(frame: pd.DataFrame, selected: pd.Series, label: str) -> pd.DataFrame:
    audit_rows = []
    positives = frame["relevance"].astype(float) > 0
    for (dataset, query_id), group in frame.groupby(["dataset", "query_id"], sort=False):
        relevant = positives.loc[group.index]
        total = int(relevant.sum())
        selected_count = int((relevant & selected.loc[group.index]).sum())
        audit_rows.append(
            {
                "dataset": str(dataset),
                "query_id": str(query_id),
                f"relevant_total_{label}": total,
                f"relevant_selected_{label}": selected_count,
                f"coverage_{label}": np.nan if total == 0 else selected_count / total,
            }
        )
    return pd.DataFrame(audit_rows)


def _candidate_mask(
    frame: pd.DataFrame,
    stage1_k: int,
    bm25_k: int,
    dense_k: int,
) -> pd.Series:
    return (
        (frame["stage1_rank"] <= stage1_k)
        | (frame["bm25_rank"] <= bm25_k)
        | (frame["dense_rank"] <= dense_k)
    )


def build_cache(
    raw: pd.DataFrame,
    min_coverage: float = 0.95,
    official_query_metrics: pd.DataFrame | None = None,
) -> CacheBuildResult:
    require_columns(raw, RAW_SCORE_COLUMNS, "raw score table")
    raw = raw.copy()
    if raw.duplicated(["dataset", "query_id", "page_id"]).any():
        raise ValueError("Raw score table contains duplicate dataset/query/page rows")
    numeric = [
        "relevance",
        "bm25_score",
        "dense_score",
        "stage1_score",
        "visual_score",
        "full_score",
    ]
    if raw[numeric].isna().any().any() or not np.isfinite(raw[numeric].to_numpy(float)).all():
        raise ValueError("Raw score table contains missing or non-finite scores")
    if raw["relevance"].lt(0).any():
        raise ValueError("Raw score table relevance must be non-negative")

    for branch in ["bm25", "dense", "stage1", "visual"]:
        raw[f"{branch}_rank"] = _rank(raw, f"{branch}_score")

    initial = _candidate_mask(raw, 200, 100, 100)
    initial_coverage = _coverage(raw, initial)
    initial_audit = _query_coverage(raw, initial, "initial")
    expanded = False
    selected = initial
    if initial_coverage < min_coverage:
        expanded = True
        selected = _candidate_mask(raw, 300, 200, 200)
    final_coverage = _coverage(raw, selected)
    final_audit = _query_coverage(raw, selected, "final")
    query_audit = initial_audit.merge(final_audit, on=["dataset", "query_id"], how="outer")
    query_audit["status"] = np.where(
        query_audit["relevant_total_final"].eq(0),
        "missing_or_empty_qrels",
        np.where(
            query_audit["coverage_final"].ge(min_coverage),
            "ok",
            "candidate_coverage_below_gate",
        ),
    )
    base_report = {
        "minimum_required": min_coverage,
        "initial_coverage": initial_coverage,
        "final_coverage": final_coverage,
        "expanded_once": expanded,
        "queries_without_relevant_pages": int(
            query_audit["status"].eq("missing_or_empty_qrels").sum()
        ),
        "queries_below_candidate_gate": int(
            query_audit["status"].eq("candidate_coverage_below_gate").sum()
        ),
    }
    if final_coverage < min_coverage:
        raise CoverageError(
            f"Candidate coverage {final_coverage:.4f} is below required {min_coverage:.4f} "
            "after the single allowed expansion",
            base_report,
            query_audit,
        )

    candidate = raw.loc[selected].copy()
    # Pandas 3 rejects assigning normalized floats back into integer columns.
    # Scores are continuous by contract, so make that type explicit first.
    for column in ["bm25_score", "dense_score", "stage1_score", "visual_score"]:
        candidate[column] = candidate[column].astype(float)
    for _, group in candidate.groupby(["dataset", "query_id"], sort=False):
        for column in ["bm25_score", "dense_score", "stage1_score", "visual_score"]:
            candidate.loc[group.index, column] = minmax(group[column].to_numpy(float))

    candidate["branch_ranks"] = candidate.apply(
        lambda row: json.dumps(
            {
                "bm25": int(row["bm25_rank"]),
                "dense": int(row["dense_rank"]),
                "stage1": int(row["stage1_rank"]),
                "visual": int(row["visual_rank"]),
            },
            separators=(",", ":"),
        ),
        axis=1,
    )
    retrieval_columns = SCORE_COLUMNS + ["source"]
    retrieval_scores = candidate[retrieval_columns].sort_values(
        ["dataset", "query_id", "page_id"], kind="stable"
    )

    metric_rows = []
    for (dataset, query_id), group in raw.groupby(["dataset", "query_id"], sort=False):
        page_ids = group["page_id"].astype(str).to_numpy()
        relevance = group["relevance"].to_numpy(float)
        stage1 = evaluate_scores(group["stage1_score"].to_numpy(float), relevance, page_ids)
        full = evaluate_scores(group["full_score"].to_numpy(float), relevance, page_ids)
        order = stable_order(group["stage1_score"].to_numpy(float), page_ids)
        sorted_scores = group["stage1_score"].to_numpy(float)[order]
        margin = float(sorted_scores[0] - sorted_scores[1]) if len(sorted_scores) > 1 else 0.0
        first = group.iloc[0]
        metric_rows.append(
            {
                "dataset": str(dataset),
                "query_id": str(query_id),
                "source": str(first["source"]),
                "relevant_count": int(np.count_nonzero(relevance > 0)),
                "ndcg_stage1": stage1.ndcg10,
                "ndcg_full": full.ndcg10,
                "recall_stage1": stage1.recall3,
                "recall_full": full.recall3,
                "recall1_stage1": stage1.recall1,
                "recall1_full": full.recall1,
                "recall3_stage1": stage1.recall3,
                "recall3_full": full.recall3,
                "mrr10_stage1": stage1.mrr10,
                "mrr10_full": full.mrr10,
                "stage1_margin": margin,
                "stage2_ms": float(first.get("stage2_ms", np.nan)),
                "stage2_flops": float(first.get("stage2_flops", np.nan)),
            }
        )
    computed_query_metrics = pd.DataFrame(
        metric_rows,
        columns=QUERY_METRIC_COLUMNS + SECONDARY_QUERY_METRIC_COLUMNS,
    )
    if official_query_metrics is None:
        query_metrics = computed_query_metrics
        metrics_source = "raw_score_table"
    else:
        require_columns(official_query_metrics, QUERY_METRIC_COLUMNS, "official query metric table")
        retained_columns = QUERY_METRIC_COLUMNS + [
            column
            for column in SECONDARY_QUERY_METRIC_COLUMNS
            if column in official_query_metrics.columns
        ]
        query_metrics = official_query_metrics[retained_columns].copy()
        if query_metrics.duplicated(["dataset", "query_id"]).any():
            raise ValueError("Official query metric table contains duplicate dataset/query rows")
        raw_queries = set(map(tuple, raw[["dataset", "query_id"]].astype(str).to_numpy()))
        metric_queries = set(
            map(tuple, query_metrics[["dataset", "query_id"]].astype(str).to_numpy())
        )
        if raw_queries != metric_queries:
            missing = sorted(raw_queries - metric_queries)[:20]
            extra = sorted(metric_queries - raw_queries)[:20]
            raise ValueError(
                f"Official query metrics do not match raw queries; missing={missing}, extra={extra}"
            )
        metrics_source = "official_full_corpus_export"
    report = {
        **base_report,
        "candidate_rows": int(len(candidate)),
        "queries": int(candidate[["dataset", "query_id"]].drop_duplicates().shape[0]),
        "query_metrics_source": metrics_source,
    }
    return CacheBuildResult(retrieval_scores, query_metrics, query_audit, report)
