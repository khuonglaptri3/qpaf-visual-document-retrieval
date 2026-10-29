"""A005 Stage 1 BM25 re-run in a second Modal workspace, exchanging only candidate-sized arrays.

The 6.6 GB BM25 matrix could not be downloaded intact, so it is recomputed remotely
with the same code and pinned image, its full SHA-256 is compared with the original
marker, and only what the candidate union needs comes back: the BM25 top-200 per
query and the BM25 scores on the union with the locally computed dense and visual
top-200. Locally, a full BM25 row is rebuilt with every non-union page set below
all known scores; `top_k_indices` then returns the same top-200 as the original row
(ties included), so the union, raw scores and normalization are unchanged.
"""
import numpy as np

from .candidates import MAX_UNION, TOP_K, top_k_indices


def channel_tops(matrix):
    """Top-200 indices per row of a [queries, pages] score matrix, as int32 [queries, 200]."""
    return np.stack([top_k_indices(row) for row in matrix]).astype(np.int32)


def union_scores(bm25_rows, bm25_top, dense_top, visual_top):
    """Per query: union indices (ascending, padded with -1 to 600) and BM25 scores on them (padded with 0)."""
    queries = len(bm25_rows)
    union = np.full((queries, MAX_UNION), -1, dtype=np.int32)
    values = np.zeros((queries, MAX_UNION), dtype=np.float64)
    for q in range(queries):
        members = np.unique(np.concatenate([bm25_top[q], dense_top[q], visual_top[q]]))
        if members.size > MAX_UNION:
            raise ValueError('candidate union exceeds the contract maximum')
        union[q, :members.size] = members
        values[q, :members.size] = np.asarray(bm25_rows[q], dtype=np.float64)[members]
    return union, values


def rebuild_rows(total, bm25_top, union, values, dense_top, visual_top):
    """Full-width BM25 rows that give the original top-200; refuses inputs that disagree with the local tops."""
    rows = np.empty((len(union), total), dtype=np.float64)
    for q in range(len(union)):
        members = union[q][union[q] >= 0]
        expected = np.unique(np.concatenate([bm25_top[q], dense_top[q], visual_top[q]]))
        if not np.array_equal(members, expected):
            raise ValueError(f'query row {q}: remote union differs from the local dense/visual tops')
        known = values[q, :members.size]
        rows[q] = known.min()-1.
        rows[q, members] = known
        if not np.array_equal(top_k_indices(rows[q]), np.sort(bm25_top[q])):
            raise ValueError(f'query row {q}: rebuilt BM25 row does not reproduce the remote top-{TOP_K}')
    return rows
