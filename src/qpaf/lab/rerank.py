"""F5: a zero-shot reranker on the top-K pages of the static fusion, interpolated with it (docs/feature_lab/F5).

The reranker sees only (query text, page OCR), never labels, so its scores are a fourth label-free signal.
Within each held-out fold the static anchor is the lab's train-fold anchor; only the top-K pages under it are
reranked and they always stay above the rest, so λ = 0 reproduces the static ranking exactly.
"""
import numpy as np

from qpaf.m46.probe import grid_points

from .data import fold_of
from .model import unit_max, unit_ndcg

TOP_K = 20
LAMBDAS = tuple(i/10 for i in range(11))
GRID = np.asarray(grid_points())


def minmax(values):
    """Per-column min-max over the given rows; a constant column maps to 0 (as qpaf.m12.features)."""
    values = np.asarray(values, dtype=np.float64)
    low, high = values.min(axis=0), values.max(axis=0)
    span = high-low
    return (values-low)/np.where(span > 0, span, 1.)


def grid_table(queries):
    """[queries, 66] unit nDCG@10 of every grid weight on the per-query min-max scores."""
    return np.stack([unit_ndcg(unit_max(minmax(q.raw)@GRID.T, q.units, len(q.unit_ids)), q.positive, q.relevant_total)
                     for q in queries])


def fold_anchors(queries, folds=5):
    """Train-fold static anchors, same grid and tie rule as qpaf.lab.train.fit_anchor."""
    table, fold = grid_table(queries), np.array([fold_of(q.query_id, folds) for q in queries])
    anchors = []
    for k in range(folds):
        total = table[fold != k].sum(axis=0)
        anchors.append(GRID[max(range(len(GRID)), key=lambda i: (total[i], -i))].tolist())
    return anchors


def top_pages(q, anchor, k=TOP_K):
    """Indices of the top-k pages under the static anchor; ties go to the smaller page index."""
    fused = minmax(q.raw)@np.asarray(anchor)
    return np.argsort(-fused, kind='stable')[:k]


def fuse(q, anchor, rerank, lam, k=TOP_K):
    """Page scores: top-k pages get 2 + (1−λ)·minmax(fused) + λ·minmax(rerank) over the top-k, others keep fused.

    `rerank` maps a page index to the reranker score; it must cover top_pages(q, anchor, k).
    """
    fused = minmax(q.raw)@np.asarray(anchor)
    top = top_pages(q, anchor, k)
    mixed = (1-lam)*minmax(fused[top]) + lam*minmax(np.array([rerank[i] for i in top]))
    scores = fused.copy()
    scores[top] = 2+mixed
    return scores


def unit_score(q, page_scores):
    return unit_ndcg(unit_max(page_scores, q.units, len(q.unit_ids)), q.positive, q.relevant_total)
