"""Vectorized ViMDoc candidate union and normalization (configs/vimdoc_m3_local_v1.json score_contract).

Per query: top-200 per channel by (score descending, page ID ascending), union
of at most 600 pages in ascending page-ID order, then per-channel min-max over
the union (range <= 1e-15 gives 0). Page arrays must already be in ascending
UTF-8 page-ID order, so a smaller index is a smaller page ID. No label input.
"""
import numpy as np

CHANNELS = ('bm25', 'dense', 'visual')
TOP_K = 200
MAX_UNION = 600
RANGE_EPSILON = 1e-15


def top_k_indices(scores, k=TOP_K):
    """Indices of the k best scores; at the cut-off, equal scores go to the smaller index."""
    scores = np.asarray(scores, dtype=np.float64)
    if scores.ndim != 1 or not np.isfinite(scores).all():
        raise ValueError('scores must be a finite 1-D array')
    if k >= scores.size:
        return np.arange(scores.size)
    threshold = np.partition(scores, scores.size-k)[scores.size-k]
    above = np.flatnonzero(scores > threshold)
    ties = np.flatnonzero(scores == threshold)[:k-above.size]
    return np.sort(np.concatenate([above, ties]))


def query_candidates(channel_scores, top_k=TOP_K, max_union=MAX_UNION):
    """Union indices (ascending), raw scores [n, 3] and normalized scores [n, 3] for one query."""
    if tuple(channel_scores) != CHANNELS:
        raise ValueError(f'channels must be exactly {CHANNELS} in that order')
    arrays = [np.asarray(channel_scores[c], dtype=np.float64) for c in CHANNELS]
    if len({a.size for a in arrays}) != 1:
        raise ValueError('all channels must score the same page universe')
    union = np.unique(np.concatenate([top_k_indices(a, top_k) for a in arrays]))
    if union.size > max_union:
        raise ValueError('candidate union exceeds the contract maximum')
    raw = np.stack([a[union] for a in arrays], axis=1)
    lo, hi = raw.min(axis=0), raw.max(axis=0)
    span = hi-lo
    if not np.isfinite(span).all():
        raise ValueError('score range overflow')
    normalized = np.where(span > RANGE_EPSILON, (raw-lo)/np.where(span > RANGE_EPSILON, span, 1.), 0.)
    return union, raw, normalized


def document_recall(union_page_ids, relevant_documents, document_of):
    """Share of a query's relevant documents with at least one page in the union (coverage audit only)."""
    if not relevant_documents:
        raise ValueError('a coverage query needs at least one relevant document')
    covered = {document_of(page) for page in union_page_ids} & set(relevant_documents)
    return len(covered)/len(set(relevant_documents))
