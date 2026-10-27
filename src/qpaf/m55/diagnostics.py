"""The fixed M5.1 R5-01–03 scoring contrasts; no labels enter scoring."""
import math
import numbers
import statistics

from qpaf.m24.evaluator import evaluate, rank

METHODS = ('bm25', 'bge_m3', 'colqwen25', 'uniform_combsum',
           'without_bm25', 'without_bge_m3', 'without_colqwen25', 'uniform_zscore')
WEIGHTS = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.), (1/3, 1/3, 1/3),
           (0., .5, .5), (.5, 0., .5), (.5, .5, 0.), (1/3, 1/3, 1/3))
METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')
TOLERANCE = 1e-12


class DiagnosticError(ValueError):
    """A fixed diagnostic or its input violates the preregistered contract."""


def require(ok, message):
    if not ok:
        raise DiagnosticError(message)


def specifications():
    return [{'method': method, 'normalization': 'zscore' if method == 'uniform_zscore' else 'minmax',
             'weights': list(weights)} for method, weights in zip(METHODS, WEIGHTS)]


def _matrix(raw):
    require(isinstance(raw, (list, tuple)) and len(raw) > 0, 'Nonempty score rows required')
    require(all(isinstance(row, (list, tuple)) and len(row) == 3 for row in raw),
            'Exactly three scores per candidate required')
    require(all(isinstance(x, numbers.Real) and not isinstance(x, bool) and math.isfinite(x)
                for row in raw for x in row), 'Scores must be finite real numbers')
    return tuple(tuple(float(x) for x in row) for row in raw)


def normalize_scores(raw_scores, method):
    rows = _matrix(raw_scores)
    require(method in ('minmax', 'zscore'), 'Unregistered normalization')
    columns = list(zip(*rows))
    if method == 'minmax':
        low, high = [min(c) for c in columns], [max(c) for c in columns]
        result = tuple(tuple((row[c]-low[c])/(high[c]-low[c]) if high[c] > low[c] else 0.
                             for c in range(3)) for row in rows)
    else:
        # pstdev is population std (ddof=0); negative standardized scores stay negative.
        means = [statistics.mean(c) for c in columns]
        deviations = [statistics.pstdev(c, mu) for c, mu in zip(columns, means)]
        result = tuple(tuple((row[c]-means[c])/deviations[c] if deviations[c] > 0 else 0.
                             for c in range(3)) for row in rows)
    require(all(math.isfinite(x) for row in result for x in row), 'Normalization overflow')
    return result


def score_record(record, method, saved_minmax=None):
    require(method in METHODS, 'Unregistered diagnostic method')
    require(len(record.page_ids) == len(record.raw_scores) and len(set(record.page_ids)) == len(record.page_ids)
            and all(isinstance(p, str) and p.strip() for p in record.page_ids),
            'Candidate page IDs must be unique and aligned')
    raw = _matrix(record.raw_scores)
    values = (normalize_scores(raw, 'zscore') if method == 'uniform_zscore' else
              normalize_scores(raw, 'minmax') if saved_minmax is None else _matrix(saved_minmax))
    require(len(values) == len(raw), 'Saved score count differs from candidate count')
    if method in ('uniform_combsum', 'uniform_zscore'):
        scores = [sum(row)/3 for row in values]
    else:
        weights = WEIGHTS[METHODS.index(method)]
        scores = [sum(w*x for w, x in zip(weights, row)) for row in values]
    require(all(math.isfinite(s) for s in scores), 'Nonfinite fused score')
    return scores


def compute_diagnostics(records, saved_minmax):
    require(records and len({r.query_id for r in records}) == len(records),
            'Unique nonempty query records required')
    require(set(saved_minmax) == {r.query_id for r in records}, 'Saved normalized query keys differ')
    maximum, constant = 0., [0, 0, 0]
    for rec in records:
        require(len(rec.labels) == len(rec.page_ids) and all(x in (0, 1) for x in rec.labels)
                and type(rec.relevant_total) is int and rec.relevant_total >= max(1, sum(rec.labels)),
                'Binary labels and positive full-qrels denominator required')
        saved = saved_minmax[rec.query_id]
        require(list(saved['page_ids']) == list(rec.page_ids), 'Saved normalized candidate keys/order differ')
        actual, expected = _matrix(saved['scores']), normalize_scores(rec.raw_scores, 'minmax')
        require(len(actual) == len(expected), 'Saved normalized score count differs')
        difference = max(abs(a-b) for row, want in zip(actual, expected) for a, b in zip(row, want))
        require(difference <= TOLERANCE and all(0 <= x <= 1 for row in actual for x in row),
                'Saved min-max differs from frozen raw scores')
        maximum = max(maximum, difference)
        for c, values in enumerate(zip(*rec.raw_scores)):
            constant[c] += int(min(values) == max(values))
    metrics, per_query, top10 = [], [], []
    for method in METHODS:
        predictions = [{'query_id': r.query_id, 'page_ids': list(r.page_ids),
                        'scores': score_record(r, method, saved_minmax[r.query_id]['scores'])} for r in records]
        aggregate, rows = evaluate(predictions, records)
        metrics.append({'method': method, **aggregate})
        per_query.extend({'method': method, **row} for row in rows)
        for prediction in predictions:
            for position, i in enumerate(rank(prediction['page_ids'], prediction['scores'])[:10], 1):
                top10.append({'method': method, 'query_id': prediction['query_id'], 'rank': position,
                              'page_id': prediction['page_ids'][i], 'score': prediction['scores'][i]})
    reference = {row['query_id']: row['ndcg_at_10'] for row in per_query
                 if row['method'] == 'uniform_combsum'}
    contrasts = []
    for method in METHODS:
        differences = [row['ndcg_at_10']-reference[row['query_id']] for row in per_query
                       if row['method'] == method]
        contrasts.append({'method': method, 'reference': 'uniform_combsum',
                          'mean_ndcg_delta': sum(differences)/len(differences),
                          'wins': sum(d > TOLERANCE for d in differences),
                          'ties': sum(abs(d) <= TOLERANCE for d in differences),
                          'losses': sum(d < -TOLERANCE for d in differences)})
    return {'query_count': len(records), 'candidate_count': sum(len(r.page_ids) for r in records),
            'metrics': metrics, 'per_query': per_query, 'top10': top10, 'contrasts': contrasts,
            'normalization_audit': {'max_abs_difference': maximum,
                                    'constant_channel_query_counts': constant,
                                    'zscore_ddof': 0, 'negative_zscores_clipped': False},
            'confirmatory_claim': False}
