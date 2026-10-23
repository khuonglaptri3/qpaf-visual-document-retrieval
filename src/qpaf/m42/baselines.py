"""M4.1 document semantics with M1.5 roster and M2.5 train-only static grid.

Pure functions over supplied data: no dataset loading, retriever, training or
confirmation access. Qrels must already contain canonical DOCUMENT IDs.
"""
import math

ROSTER = ('bm25', 'bge_m3', 'colqwen25', 'uniform_combsum', 'rrf_k60',
          'train_fitted_static', 'learned_qarf')
CHANNELS = ('bm25_score', 'dense_score', 'visual_score')
SCORE_COLUMNS = frozenset(('query_id', 'page_id', *CHANNELS))


def _ids(values, name):
    if (not isinstance(values, (list, tuple)) or not values or
            any(not isinstance(v, str) or not v or
                          any(c in v for c in '\r\n\t') for v in values) or
            len(set(values)) != len(values)):
        raise ValueError(f'{name} must be unique nonempty string IDs')


def _finite(value):
    if type(value) not in (float, int):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _query_rows(rows):
    if not rows or len(rows) > 600:
        raise ValueError('Require 1..600 common candidate rows per query')
    if any(not isinstance(r, dict) or set(r) != SCORE_COLUMNS for r in rows):
        raise ValueError('Only five score columns allowed; labels stay separate')
    pages = [r['page_id'] for r in rows]
    _ids(pages, 'Candidate pages')
    _ids([rows[0]['query_id']], 'Query')
    if pages != sorted(pages) or any(r['query_id'] != rows[0]['query_id'] for r in rows):
        raise ValueError('Require one query and ascending frozen candidate page IDs')
    if any(not _finite(r[c]) for r in rows for c in CHANNELS):
        raise ValueError('Require three finite numeric raw scores for every page')
    return pages


def _normalized(rows):
    values = [[0.] * 3 for _ in rows]
    for c, channel in enumerate(CHANNELS):
        low, high = min(r[channel] for r in rows), max(r[channel] for r in rows)
        span = high - low
        if not _finite(span):
            raise ValueError('Score normalization overflow')
        if span > 1e-15:
            for i, r in enumerate(rows):
                values[i][c] = (r[channel] - low) / span
    return values


def score_pages(rows, method, *, weights=None):
    """Label-free page scores on the EXACT common, fully rescored union."""
    pages = _query_rows(rows)
    values = _normalized(rows)
    if method in ROSTER[:3]:
        c = ROSTER.index(method)
        return [v[c] for v in values]
    if method == 'uniform_combsum':
        return [sum(v) / 3 for v in values]
    if method == 'rrf_k60':
        scores = [0.] * len(rows)
        for channel in CHANNELS:
            order = sorted(range(len(rows)), key=lambda i: (-rows[i][channel], pages[i]))
            for rank, index in enumerate(order, 1):
                scores[index] += 1 / (60 + rank)
        return scores
    if method == 'train_fitted_static':
        if (weights is None or len(weights) != 3 or
                any(not _finite(w) or w < 0 for w in weights) or
                not math.isclose(sum(weights), 1., rel_tol=0., abs_tol=1e-12)):
            raise ValueError('Static weights must be a finite nonnegative 3-way simplex')
        return [sum(w*x for w, x in zip(weights, v)) for v in values]
    raise ValueError(f'Unsupported baseline or checkpoint required: {method}')


def document_ranking(page_ids, scores):
    """Fuse before max aggregation; final underscore suffix identifies the page."""
    _ids(page_ids, 'Candidate pages')
    if len(page_ids) != len(scores) or any(not _finite(s) for s in scores):
        raise ValueError('Page scores must be finite and aligned')
    docs = {}
    for page, score in zip(page_ids, scores):
        document, separator, suffix = page.rpartition('_')
        if not separator or not document or not suffix:
            raise ValueError('Page ID must have a document and final underscore segment')
        docs[document] = max(docs.get(document, -math.inf), score)
    return sorted(docs.items(), key=lambda item: (-item[1], item[0]))


def document_ndcg_at_10(page_ids, scores, relevant_document_ids):
    """Binary document nDCG; missing relevant documents still count toward IDCG."""
    _ids(relevant_document_ids, 'Document qrels')
    relevant = set(relevant_document_ids)
    ranked = document_ranking(page_ids, scores)
    dcg = sum(1/math.log2(i+2) for i, (doc, _) in enumerate(ranked[:10]) if doc in relevant)
    ideal = sum(1/math.log2(i+2) for i in range(min(10, len(relevant))))
    return dcg / ideal


def audit_train_inputs(score_rows, document_qrels, train_query_ids):
    """Reject any query outside the caller's exact frozen TRAIN ID manifest.

    Byte-level provenance and train-manifest authenticity are checked by the
    freeze verifier; this function validates already supplied in-memory rows.
    """
    _ids(train_query_ids, 'Frozen train queries')
    if not isinstance(document_qrels, dict) or set(document_qrels) != set(train_query_ids):
        raise ValueError('Document qrels must match exact train query IDs only')
    grouped = {q: [] for q in train_query_ids}
    for r in score_rows:
        if not isinstance(r, dict) or set(r) != SCORE_COLUMNS:
            raise ValueError('Only five score columns allowed; labels stay separate')
        if r['query_id'] not in grouped:
            raise ValueError('Score query is outside frozen train IDs')
        grouped[r['query_id']].append(r)
    for q, rows in grouped.items():
        _query_rows(rows)
        _ids(document_qrels[q], 'Document qrels')
    return grouped


def fit_static_on_train(score_rows, document_qrels, train_query_ids, denominator=10):
    """Reference static fitting; does not load labels or authorize a real run.

    Grid/tie policy inherited from configs/m2.5/freeze.json, evaluated with the
    M4.1 DOCUMENT objective instead of the historical M2.5 page objective.
    """
    if type(denominator) is not int or denominator != 10:
        raise ValueError('The inherited grid denominator is frozen at 10')
    grouped = audit_train_inputs(score_rows, document_qrels, train_query_ids)
    prepared = [(q, [r['page_id'] for r in rows], _normalized(rows))
                for q, rows in grouped.items()]
    results = []
    for a in range(denominator+1):
        for b in range(denominator-a+1):
            weights = (a/denominator, b/denominator, (denominator-a-b)/denominator)
            value = sum(document_ndcg_at_10(
                pages, [sum(w*x for w, x in zip(weights, v)) for v in values],
                document_qrels[q]) for q, pages, values in prepared) / len(prepared)
            results.append((weights, value))
    best_value = max(v for _, v in results)
    # Compare with the global maximum, avoiding order-dependent tolerance drift.
    weights, value = next((w, v) for w, v in results if best_value-v <= 1e-12)
    return {'weights': weights, 'train_document_ndcg_at_10': value,
            'grid_denominator': denominator, 'grid_candidates': len(results)}
