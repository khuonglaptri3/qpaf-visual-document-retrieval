"""Predictions and per-query metrics; IDCG/recall denominators use all qrels positives."""
import math

from .config import METRICS
from .dataset import iter_batches


def rank(page_ids, scores):
    """Score descending, page ID ascending (metric_policy.md tie rule)."""
    return sorted(range(len(page_ids)), key=lambda i: (-scores[i], page_ids[i]))


def query_metrics(ranked_labels, relevant_total):
    if relevant_total < 1 or relevant_total < sum(ranked_labels):
        raise ValueError('relevant_total must cover every positive candidate')
    ideal = sum(1/math.log2(i+2) for i in range(min(10, relevant_total)))
    dcg = sum(label/math.log2(i+2) for i, label in enumerate(ranked_labels[:10]))
    first = next((i for i, label in enumerate(ranked_labels[:10]) if label), None)
    return {'ndcg_at_10': dcg/ideal,
            'recall_at_1': sum(ranked_labels[:1])/relevant_total,
            'recall_at_3': sum(ranked_labels[:3])/relevant_total,
            'mrr_at_10': 0. if first is None else 1/(first+1)}


def predict(model, records, batch_size, query_length_cap):
    """Fused scores and gate weights per query, in input order."""
    import torch
    from qpaf.m12.features import build_features
    dtype = next(model.parameters()).dtype
    predictions = []
    was_training = model.training
    model.eval()
    try:
        with torch.no_grad():
            for batch in iter_batches(records, batch_size):
                features = build_features(batch.raw_scores.to(dtype), batch.texts, batch.page_ids,
                                          batch.mask, query_length_cap=query_length_cap)
                output = model(features)
                for row, query_id in enumerate(batch.query_ids):
                    count = int(batch.mask[row].sum())
                    predictions.append({'query_id': query_id, 'page_ids': batch.page_ids[row][:count],
                                        'scores': output.scores[row, :count].tolist(),
                                        'weights': output.weights[row, :count].tolist()})
    finally:
        model.train(was_training)
    return predictions


def evaluate(predictions, records):
    """Equal-weight mean over queries; every record must have exactly one prediction."""
    by_id = {p['query_id']: p for p in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {r.query_id for r in records}:
        raise ValueError('Predictions must cover each evaluated query exactly once')
    per_query = []
    for record in records:
        prediction = by_id[record.query_id]
        if list(prediction['page_ids']) != list(record.page_ids):
            raise ValueError(f'Query {record.query_id}: prediction pages differ from candidates')
        scores = prediction['scores']
        if not all(math.isfinite(value) for value in scores):
            raise ValueError(f'Query {record.query_id}: nonfinite fused score')
        order = rank(record.page_ids, scores)
        values = query_metrics([record.labels[i] for i in order], record.relevant_total)
        per_query.append({'query_id': record.query_id, 'candidates': len(record.page_ids),
                          'relevant_total': record.relevant_total,
                          'relevant_in_candidates': sum(record.labels), **values})
    aggregate = {name: sum(row[name] for row in per_query)/len(per_query) for name in METRICS}
    return {'query_count': len(per_query), **aggregate}, per_query
