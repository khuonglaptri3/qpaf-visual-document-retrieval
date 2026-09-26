"""Exact binary-label Oracle over explicit convex fusion weight sets."""
import math
from .metrics import paired_summary, validate_qrels


def weight_sets(config):
    result = {}
    for name, spec in config['weights'].items():
        if set(spec) == {'values'}:
            values = spec['values']
        elif set(spec) == {'simplex_divisions'}:
            n = spec['simplex_divisions']
            if type(n) is not int or n < 1:
                raise ValueError('Simplex divisions must be a positive integer')
            values = [[a/n, b/n, (n-a-b)/n] for a in range(n+1) for b in range(n-a+1)]
        else:
            raise ValueError(f'Invalid weight specification: {name}')
        if not values:
            raise ValueError('Empty weight set')
        for row in values:
            if len(row) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in row) or not math.isclose(sum(row), 1, abs_tol=1e-12):
                raise ValueError(f'Invalid simplex weight in {name}')
        if len({tuple(row) for row in values}) != len(values):
            raise ValueError(f'Duplicate profiles in {name}')
        result[name] = values
    if not result:
        raise ValueError('At least one weight set is required')
    return result


def evaluate(scores, query_ids, page_ids, qrels, config):
    import numpy as np
    scores = np.asarray(scores, dtype=np.float64)
    if not query_ids or not page_ids or len(set(query_ids)) != len(query_ids) or len(set(page_ids)) != len(page_ids):
        raise ValueError('Empty or duplicate cache IDs')
    if scores.shape != (len(query_ids), len(page_ids), 3) or not np.isfinite(scores).all():
        raise ValueError('Score cache shape/nonfinite values do not match IDs')
    if set(qrels) != set(query_ids):
        raise ValueError('Query IDs and qrels do not match')
    pages = set(page_ids)
    for labels in qrels.values():
        validate_qrels(labels)
        if not set(labels) <= pages:
            raise ValueError('Qrels reference pages missing from the full corpus')
    cutoff = config['oracle']['metric_k']
    depth = config['retrieval']['candidate_k']
    if cutoff < 1 or depth < 1:
        raise ValueError('Cutoff and candidate depth must be positive')
    if config['retrieval']['normalization'] != 'minmax':
        raise ValueError('Unsupported normalization')
    # Canonical ID order gives a label-independent tie break for every sorter.
    canonical = sorted(range(len(page_ids)), key=lambda i: page_ids[i])
    ids = np.asarray([page_ids[i] for i in canonical])
    weights = weight_sets(config)
    profile_metrics = {name: [] for name in weights}
    rows, decisions = [], []
    for qi, query in enumerate(query_ids):
        raw = scores[qi, canonical, :]
        top = np.argsort(-raw, axis=0, kind='stable')[:depth]
        pool = np.unique(top.reshape(-1)) # remains canonical ID order
        pool_ids = ids[pool]
        pool_scores = raw[pool]
        ranges = np.ptp(pool_scores, axis=0)
        normalized = np.divide(pool_scores-pool_scores.min(axis=0), ranges,
                               out=np.zeros_like(pool_scores), where=ranges != 0)
        labels = np.array([qrels[query].get(str(page), 0) for page in pool_ids])
        total_relevant = sum(v == 1 for v in qrels[query].values())
        discounts = 1/np.log2(np.arange(min(cutoff, len(pool)))+2)
        ideal = sum(1/math.log2(i+2) for i in range(min(cutoff, total_relevant)))
        for name, profiles in weights.items():
            fused = normalized @ np.asarray(profiles).T
            rankings = np.argsort(-fused, axis=0, kind='stable')[:cutoff]
            ndcgs = (labels[rankings]*discounts[:, None]).sum(axis=0)/ideal
            profile_metrics[name].append(ndcgs)
            best = int(np.argmax(ndcgs))
            chosen = np.where(labels == 1, np.argmax(fused, axis=1), np.argmin(fused, axis=1))
            adaptive = fused[np.arange(len(pool)), chosen]
            ranking = np.argsort(-adaptive, kind='stable')[:cutoff]
            qpaf = float((labels[ranking]*discounts).sum()/ideal)
            qarf = float(ndcgs[best])
            rows.append({'query_id': query, 'weight_set': name,
                         f'global_ndcg{cutoff}': None, f'qarf_ndcg{cutoff}': qarf,
                         f'qpaf_ndcg{cutoff}': qpaf, 'delta_qpaf_qarf': qpaf-qarf,
                         'candidate_count': len(pool), 'candidate_recall': float(labels.sum()/total_relevant)})
            decisions.append({'query_id': query, 'weight_set': name,
                              'candidate_page_ids': pool_ids.tolist(), 'qarf_profile': best,
                              'qpaf_profiles': chosen.tolist()})
    summary = {'n_queries': len(query_ids), 'n_pages': len(page_ids), 'metric': f'nDCG@{cutoff}',
               'oracle_definition': 'binary_independent_page_extrema',
               'tie_break': 'page_id_ascending', 'label_policy': 'qrels_only_after_candidates_and_normalization',
               'weight_sets': {}, 'independent_review': 'pending'}
    for name, profiles in weights.items():
        matrix = np.asarray(profile_metrics[name])
        global_index = int(np.argmax(matrix.mean(axis=0)))
        selected_rows = [row for row in rows if row['weight_set'] == name]
        for i, row in enumerate(selected_rows):
            row[f'global_ndcg{cutoff}'] = float(matrix[i, global_index])
        stats = paired_summary([row['delta_qpaf_qarf'] for row in selected_rows],
                               config['oracle']['bootstrap_samples'], config['oracle']['seed'],
                               config['oracle']['tie_tolerance'])
        stats.update({f'{method}_mean': sum(row[f'{method}_ndcg{cutoff}'] for row in selected_rows)/len(query_ids)
                      for method in ('global', 'qarf', 'qpaf')})
        stats.update({'profiles': profiles, 'global_profile_index': global_index,
                      'candidate_recall_mean': sum(row['candidate_recall'] for row in selected_rows)/len(query_ids)})
        summary['weight_sets'][name] = stats
    return rows, summary, decisions
