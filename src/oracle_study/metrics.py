from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RankingMetrics:
    ndcg10: float
    recall1: float
    recall3: float
    mrr10: float


def stable_order(scores: np.ndarray, page_ids: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    page_ids = np.asarray(page_ids, dtype=str)
    safe_scores = np.nan_to_num(scores, nan=-np.inf)
    return np.lexsort((page_ids, -safe_scores))


def dcg_at_k(relevance: np.ndarray, k: int) -> float:
    rel = np.asarray(relevance, dtype=float)[:k]
    if rel.size == 0:
        return 0.0
    discounts = 1.0 / np.log2(np.arange(2, rel.size + 2, dtype=float))
    return float(np.sum((np.power(2.0, rel) - 1.0) * discounts))


def ndcg_at_k(relevance: np.ndarray, k: int = 10) -> float:
    rel = np.asarray(relevance, dtype=float)
    ideal = dcg_at_k(np.sort(rel)[::-1], k)
    if ideal <= 0:
        return 0.0
    return dcg_at_k(rel, k) / ideal


def recall_at_k(relevance: np.ndarray, k: int) -> float:
    rel = np.asarray(relevance, dtype=float)
    positives = int(np.count_nonzero(rel > 0))
    if positives == 0:
        return 0.0
    return float(np.count_nonzero(rel[:k] > 0) / positives)


def mrr_at_k(relevance: np.ndarray, k: int = 10) -> float:
    hits = np.flatnonzero(np.asarray(relevance, dtype=float)[:k] > 0)
    return 0.0 if hits.size == 0 else 1.0 / float(hits[0] + 1)


def evaluate_scores(
    scores: np.ndarray,
    relevance: np.ndarray,
    page_ids: np.ndarray,
) -> RankingMetrics:
    order = stable_order(scores, page_ids)
    ranked_rel = np.asarray(relevance, dtype=float)[order]
    return RankingMetrics(
        ndcg10=ndcg_at_k(ranked_rel, 10),
        recall1=recall_at_k(ranked_rel, 1),
        recall3=recall_at_k(ranked_rel, 3),
        mrr10=mrr_at_k(ranked_rel, 10),
    )


def minmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return values.copy()
    low = float(np.nanmin(values))
    high = float(np.nanmax(values))
    if not math.isfinite(low) or not math.isfinite(high):
        raise ValueError("Scores must be finite before normalization")
    if math.isclose(low, high, rel_tol=0.0, abs_tol=1e-15):
        return np.zeros_like(values, dtype=float)
    return (values - low) / (high - low)

