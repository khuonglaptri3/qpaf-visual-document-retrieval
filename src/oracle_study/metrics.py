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


def _relevance_vector(relevance: np.ndarray) -> np.ndarray:
    relevance = np.asarray(relevance, dtype=float)
    if relevance.ndim != 1:
        raise ValueError("Relevance must be a one-dimensional vector")
    if not np.isfinite(relevance).all():
        raise ValueError("Relevance must be finite")
    if (relevance < 0).any():
        raise ValueError("Relevance must be non-negative")
    return relevance


def stable_order(scores: np.ndarray, page_ids: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    page_ids = np.asarray(page_ids, dtype=str)
    if scores.ndim != 1 or page_ids.ndim != 1:
        raise ValueError("Scores and page IDs must be one-dimensional vectors")
    if len(scores) != len(page_ids):
        raise ValueError("Scores and page IDs must have the same length")
    if not np.isfinite(scores).all():
        raise ValueError("Scores must be finite")
    if len(np.unique(page_ids)) != len(page_ids):
        raise ValueError("Page IDs must be unique within a query")
    return np.lexsort((page_ids, -scores))


def dcg_at_k(relevance: np.ndarray, k: int) -> float:
    rel = _relevance_vector(relevance)[:k]
    if rel.size == 0:
        return 0.0
    discounts = 1.0 / np.log2(np.arange(2, rel.size + 2, dtype=float))
    return float(np.sum((np.power(2.0, rel) - 1.0) * discounts))


def ndcg_at_k(relevance: np.ndarray, k: int = 10) -> float:
    rel = _relevance_vector(relevance)
    ideal = dcg_at_k(np.sort(rel)[::-1], k)
    if ideal <= 0:
        return 0.0
    return dcg_at_k(rel, k) / ideal


def recall_at_k(relevance: np.ndarray, k: int) -> float:
    rel = _relevance_vector(relevance)
    positives = int(np.count_nonzero(rel > 0))
    if positives == 0:
        return 0.0
    return float(np.count_nonzero(rel[:k] > 0) / positives)


def mrr_at_k(relevance: np.ndarray, k: int = 10) -> float:
    hits = np.flatnonzero(_relevance_vector(relevance)[:k] > 0)
    return 0.0 if hits.size == 0 else 1.0 / float(hits[0] + 1)


def evaluate_scores(
    scores: np.ndarray,
    relevance: np.ndarray,
    page_ids: np.ndarray,
) -> RankingMetrics:
    order = stable_order(scores, page_ids)
    relevance = _relevance_vector(relevance)
    if len(relevance) != len(order):
        raise ValueError("Scores, relevance, and page IDs must have the same length")
    ranked_rel = relevance[order]
    return RankingMetrics(
        ndcg10=ndcg_at_k(ranked_rel, 10),
        recall1=recall_at_k(ranked_rel, 1),
        recall3=recall_at_k(ranked_rel, 3),
        mrr10=mrr_at_k(ranked_rel, 10),
    )


def minmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1:
        raise ValueError("Min-max normalization requires a one-dimensional vector")
    if values.size == 0:
        return values.copy()
    if not np.isfinite(values).all():
        raise ValueError("Scores must be finite before normalization")
    low = float(values.min())
    high = float(values.max())
    if math.isclose(low, high, rel_tol=0.0, abs_tol=1e-15):
        return np.zeros_like(values, dtype=float)
    return (values - low) / (high - low)


def normalize_three_channel_scores(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 2 or scores.shape[1] != 3:
        raise ValueError("Three-channel scores must have shape [C,3]")
    if not np.isfinite(scores).all():
        raise ValueError("Three-channel scores must be finite")
    if scores.shape[0] == 0:
        return scores.copy()
    return np.column_stack([minmax(scores[:, index]) for index in range(3)])
