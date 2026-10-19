"""Deployable baselines sharing M2.4 candidate rows and evaluator."""
import math

from qpaf.m24.evaluator import evaluate

ROSTER = ('bm25', 'bge_m3', 'colqwen25', 'uniform_combsum', 'rrf_k60',
          'train_fitted_static', 'learned_qarf')
CHANNEL = {'bm25': 0, 'bge_m3': 1, 'colqwen25': 2}


def _normalized(record):
    if not record.page_ids or len(record.page_ids) != len(record.raw_scores):
        raise ValueError('Candidate pages and scores must be nonempty and aligned')
    if len(set(record.page_ids)) != len(record.page_ids):
        raise ValueError('Duplicate candidate page ID')
    rows = record.raw_scores
    if any(len(row) != 3 or any(type(x) not in (int, float) or not math.isfinite(x)
                                for x in row) for row in rows):
        raise ValueError('Every candidate needs three finite raw scores')
    low = [min(row[c] for row in rows) for c in range(3)]
    high = [max(row[c] for row in rows) for c in range(3)]
    values = [tuple((row[c]-low[c])/(high[c]-low[c]) if high[c] > low[c] else 0.
                    for c in range(3)) for row in rows]
    if any(not math.isfinite(x) for row in values for x in row):
        raise ValueError('Score normalization overflow')
    return values


def score_record(record, method, *, weights=None):
    """Score one frozen candidate set without touching labels or qrels."""
    values = _normalized(record)
    if method in CHANNEL:
        return [row[CHANNEL[method]] for row in values]
    if method == 'uniform_combsum':
        return [sum(row)/3 for row in values]
    if method == 'rrf_k60':
        ranks = [[0]*len(values) for _ in range(3)]
        for c in range(3):
            order = sorted(range(len(values)), key=lambda i: (-record.raw_scores[i][c], record.page_ids[i]))
            for rank, index in enumerate(order, 1):
                ranks[c][index] = rank
        return [sum(1/(60+ranks[c][i]) for c in range(3)) for i in range(len(values))]
    if method == 'train_fitted_static':
        if (weights is None or len(weights) != 3 or
                any(type(w) not in (int, float) or not math.isfinite(w) or w < 0 for w in weights) or
                not math.isclose(sum(weights), 1., rel_tol=0, abs_tol=1e-12)):
            raise ValueError('Frozen static weights must be a finite 3-way simplex')
        return [sum(w*x for w, x in zip(weights, row)) for row in values]
    raise ValueError(f'Unsupported or learned baseline: {method}')


def predictions(records, method, *, weights=None):
    return [{'query_id': record.query_id, 'page_ids': list(record.page_ids),
             'scores': score_record(record, method, weights=weights)} for record in records]


def fit_static_on_train(train_records, train_query_ids, denominator=10):
    """Choose from a frozen simplex grid using train labels only."""
    if not train_records or type(denominator) is not int or denominator < 1:
        raise ValueError('Nonempty train records and positive grid denominator required')
    record_ids = [record.query_id for record in train_records]
    if (not train_query_ids or len(set(record_ids)) != len(record_ids) or
            set(record_ids) != set(train_query_ids) or len(record_ids) != len(train_query_ids)):
        raise ValueError('Fit records must match the exact frozen train query IDs')
    best, best_value = None, -math.inf
    for a in range(denominator+1):
        for b in range(denominator-a+1):
            weights = (a/denominator, b/denominator, (denominator-a-b)/denominator)
            value = evaluate(predictions(train_records, 'train_fitted_static', weights=weights),
                             train_records)[0]['ndcg_at_10']
            if value > best_value + 1e-12:
                best, best_value = weights, value
    return {'weights': best, 'train_ndcg_at_10': best_value,
            'grid_denominator': denominator, 'candidates': (denominator+1)*(denominator+2)//2}


def select_co_strongest(validation_metrics, *, tolerance=1e-12):
    """Select every tied deployable method; the caller supplies validation means."""
    if set(validation_metrics) != set(ROSTER):
        raise ValueError('All seven frozen deployable baselines are required')
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
           for value in validation_metrics.values()):
        raise ValueError('Validation nDCG must be finite and in [0,1]')
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Invalid tie tolerance')
    best = max(validation_metrics.values())
    return [method for method in ROSTER if best-validation_metrics[method] <= tolerance]
