"""A005 Stages 2-4 on the ViMDoc score cache: records, static grid, deployable baselines.

Only train and validation queries are loaded. Document qrels stay a separate
table (never written onto pages): page labels in the records are all zero and
the trainer, probe and metrics receive relevant documents explicitly.
"""
import numpy as np

from qpaf.m24.dataset import QueryRecord
from qpaf.m46.probe import grid_points

from .model import document_metrics

CHANNELS = ('bm25', 'dense', 'visual')
RRF_K = 60


def load_records(frame, queries, qrels, role_ids):
    """QueryRecords for the given query IDs from candidate_scores rows (raw scores; features renormalize)."""
    wanted = set(role_ids)
    frame = frame[frame['query_id'].isin(wanted)]
    records = []
    for query_id, group in frame.groupby('query_id', sort=False):
        group = group.sort_values('page_id', key=lambda s: s.map(lambda v: v.encode('utf-8')))
        raw = tuple(map(tuple, group[list(CHANNELS)].to_numpy(dtype=np.float64)))
        records.append(QueryRecord(query_id, queries[query_id], tuple(group['page_id']), raw,
                                   (0,)*len(raw), len(qrels[query_id])))
    if {r.query_id for r in records} != wanted:
        raise ValueError('candidate rows do not cover every requested query')
    return sorted(records, key=lambda r: r.query_id.encode('utf-8'))


def normalized(record):
    """Per-query min-max of the union, as in the frozen contract (range <= 1e-15 gives 0)."""
    raw = np.asarray(record.raw_scores, dtype=np.float64)
    lo, hi = raw.min(axis=0), raw.max(axis=0)
    span = hi-lo
    return np.where(span > 1e-15, (raw-lo)/np.where(span > 1e-15, span, 1.), 0.)


def rrf(record, k=RRF_K):
    """Reciprocal rank fusion over the union; ranks per channel by (raw score desc, page ID asc)."""
    raw = np.asarray(record.raw_scores, dtype=np.float64)
    scores = np.zeros(len(record.page_ids))
    for channel in range(3):
        order = sorted(range(len(record.page_ids)), key=lambda i: (-raw[i, channel], record.page_ids[i]))
        for rank, index in enumerate(order, start=1):
            scores[index] += 1/(k+rank)
    return scores


def mean_ndcg(records, qrels, score_fn):
    values = [document_metrics(list(r.page_ids), score_fn(r).tolist(), qrels[r.query_id])['ndcg_at_10']
              for r in records]
    return sum(values)/len(values), values


def static_grid(records, qrels):
    """Train-only 66-point grid on normalized scores; ties keep the earlier grid point."""
    cache = [normalized(r) for r in records]
    rows = []
    for weights in grid_points():
        w = np.asarray(weights)
        scores = iter([c@w for c in cache])
        value, _ = mean_ndcg(records, qrels, lambda r: next(scores))
        rows.append({'weights': weights, 'ndcg_at_10': value})
    best = max(range(len(rows)), key=lambda i: (rows[i]['ndcg_at_10'], -i))
    return rows, rows[best]['weights']


def document_groups(record, relevant):
    """Page-to-document index groups and the relevant-document mask for one query."""
    from .model import document_of
    documents = sorted({document_of(p) for p in record.page_ids})
    index = {d: i for i, d in enumerate(documents)}
    groups = np.array([index[document_of(p)] for p in record.page_ids])
    positive = np.array([d in set(relevant) for d in documents])
    return groups, positive, len(documents)


def doc_profile_loss(records, qrels, weights, golden):
    """A005 §4.3 on documents: min over log τ of the query-mean listwise loss for static weights."""
    w = np.asarray(weights, dtype=np.float64)
    prepared = []
    for record in records:
        groups, positive, count = document_groups(record, qrels[record.query_id])
        if positive.all() or not positive.any():
            continue
        doc_scores = np.full(count, -np.inf)
        np.maximum.at(doc_scores, groups, normalized(record)@w)
        prepared.append((doc_scores, positive))

    def loss(log_tau):
        tau, total = np.exp(log_tau), 0.
        for scores, positive in prepared:
            logits = scores/tau
            peak = logits.max()
            log_z = peak+np.log(np.exp(logits-peak).sum())
            log_pos = peak+np.log(np.exp(logits[positive]-peak).sum())
            total += log_z-log_pos
        return total/len(prepared)
    return golden(loss), len(prepared)


def baselines(records, qrels, static_weights):
    """Validation nDCG@10 and per-query values for the deployable roster available on ViMDoc."""
    fns = {'bm25': lambda r: normalized(r)[:, 0], 'bge_m3': lambda r: normalized(r)[:, 1],
           'colqwen25': lambda r: normalized(r)[:, 2], 'uniform_combsum': lambda r: normalized(r).mean(axis=1),
           'rrf_k60': rrf, 'train_fitted_static': lambda r: normalized(r)@np.asarray(static_weights)}
    return {name: dict(zip(('ndcg_at_10', 'per_query'), mean_ndcg(records, qrels, fn))) for name, fn in fns.items()}
