"""ORC run: label-using W7/W66 oracle context rows on the same validation pool; never selectable."""
import csv
from pathlib import Path
import sys

import numpy as np

from qpaf.m24.evaluator import evaluate
from qpaf.m25.baselines import _normalized
from qpaf.m44.common import (ROOT, execute_attempt, load_context, read, read_csv_gz, require, verify_run,
                             write_csv_gz, write_json)

ORC = 'QPAF-M4_4-ORC-001'
GRIDS = ('w7', 'w66')
KINDS = ('global', 'qarf', 'qpaf')
METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')
NAMES = tuple(f'oracle_{kind}_{grid}' for grid in GRIDS for kind in KINDS)


def oracle_scores(records, grid, *, deadline=lambda: None):
    """Global, per-query and per-page oracle scores with the frozen profiles and tie rules."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from oracle_study.profiles import get_profiles
    from oracle_study.qpaf import _global_oracle, _query_oracle
    from scripts.qpaf_candidate_oracle_optimized import candidate_oracle_exact_fast
    profiles = get_profiles(grid)
    data = [{'score_matrix': np.asarray(_normalized(r), dtype=float),
             'relevance': np.asarray(r.labels, dtype=float), 'page_ids': np.asarray(r.page_ids)} for r in records]
    global_index, _ = _global_oracle(data, profiles)
    rows = {f'oracle_{kind}_{grid}': [] for kind in KINDS}
    details = []
    for record, item in zip(records, data):
        deadline()
        matrix, relevance, pages = item['score_matrix'], item['relevance'], item['page_ids']
        query_index, query_scores, query_metrics = _query_oracle(matrix, relevance, pages, profiles)
        assignments, page_scores, _, updates = candidate_oracle_exact_fast(
            matrix, relevance, pages, profiles, query_index, query_scores, query_metrics, max_sweeps=2)
        for kind, scores in (('global', matrix @ profiles[global_index]), ('qarf', query_scores),
                             ('qpaf', page_scores)):
            rows[f'oracle_{kind}_{grid}'].append({'query_id': record.query_id, 'page_ids': list(record.page_ids),
                                                  'scores': [float(x) for x in scores]})
        details.append({'query_id': record.query_id, 'qarf_profile': profiles[query_index].tolist(),
                        'changed_candidates': int(np.count_nonzero(assignments != query_index)),
                        'accepted_updates': int(updates)})
    return rows, {'grid': grid, 'profiles': len(profiles), 'global_profile': profiles[global_index].tolist(),
                  'per_query': details}


def oracle_table(metrics, frozen_qpaf_ndcg, details):
    rows = [{'method': name, 'grid': name.rsplit('_', 1)[1], 'kind': name.split('_')[1],
             **{k: metrics[name][k] for k in ('query_count', *METRICS)},
             'gap_vs_frozen_qpaf_ndcg_at_10': metrics[name]['ndcg_at_10']-frozen_qpaf_ndcg} for name in NAMES]
    return {'split': 'validation', 'block': 'oracle_context', 'selection_eligible': False, 'rows': rows,
            'frozen_qpaf_validation_ndcg_at_10': frozen_qpaf_ndcg,
            'global_profiles': {grid: details[grid]['global_profile'] for grid in GRIDS},
            'notes': ['Oracle rows use validation labels to choose profiles; they are non-deployable upper '
                      'bounds (baseline_policy.md §2) and never enter strongest-baseline selection.',
                      'Profiles are the frozen W7/W66 sets; no other profile or sweep was searched.']}


def _compute(context, deadline):
    rows, details = {}, {}
    for grid in GRIDS:
        grid_rows, details[grid] = oracle_scores(context['records'], grid, deadline=deadline)
        rows.update(grid_rows)
    metrics, per_query = {}, {}
    for name in NAMES:
        metrics[name], per_query[name] = evaluate(rows[name], context['records'])
    frozen = context['freeze']['frozen_method']['validation']['ndcg_at_10']
    return rows, details, metrics, per_query, oracle_table(metrics, frozen, details)


def produce_orc(context, output, deadline):
    rows, details, metrics, per_query, table = _compute(context, deadline)
    records = context['records']
    write_csv_gz(output/'oracle_predictions.csv.gz', ['query_id', 'page_id', *NAMES],
                 ([r.query_id, page, *(rows[n][i]['scores'][j] for n in NAMES)]
                  for i, r in enumerate(records) for j, page in enumerate(r.page_ids)))
    with (output/'oracle_per_query.csv').open('x', encoding='utf8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['method', 'query_id', *METRICS])
        for name in NAMES:
            for row in per_query[name]:
                writer.writerow([name, row['query_id'], *(repr(float(row[k])) for k in METRICS)])
    write_json(output/'oracle_table.json', table)
    write_json(output/'oracle_details.json', details)
    return {'oracle_ndcg_at_10': {name: metrics[name]['ndcg_at_10'] for name in NAMES}}


def execute_orc(root, authorization, expected_sha256, run_id):
    return execute_attempt(root, authorization, expected_sha256, ORC, run_id, produce_orc)


def verify_orc(root, output, expected_manifest_sha256, *, recompute=True):
    """Re-hash; re-score saved oracle predictions; optionally replay the whole oracle."""
    root, output = Path(root).resolve(), Path(output)
    manifest = verify_run(output, expected_manifest_sha256)
    context = load_context(root)
    saved = read_csv_gz(output/'oracle_predictions.csv.gz')
    require(saved and list(saved[0]) == ['query_id', 'page_id', *NAMES], 'oracle prediction columns differ')
    metrics, cursor = {}, 0
    rebuilt = {name: [] for name in NAMES}
    for record in context['records']:
        chunk = saved[cursor:cursor+len(record.page_ids)]
        cursor += len(record.page_ids)
        require([r['page_id'] for r in chunk] == list(record.page_ids), 'saved oracle rows differ')
        for name in NAMES:
            rebuilt[name].append({'query_id': record.query_id, 'page_ids': list(record.page_ids),
                                  'scores': [float(r[name]) for r in chunk]})
    require(cursor == len(saved), 'saved oracle predictions contain extra rows')
    for name in NAMES:
        metrics[name] = evaluate(rebuilt[name], context['records'])[0]
    frozen = context['freeze']['frozen_method']['validation']['ndcg_at_10']
    stored = read(output/'oracle_table.json')
    require(oracle_table(metrics, frozen, read(output/'oracle_details.json'))['rows'] == stored['rows'],
            'oracle table does not replay from saved predictions')
    if recompute:
        replay = _compute(context, lambda: None)
        require(replay[4]['rows'] == stored['rows'], 'oracle recomputation differs')
    return {'status': 'PASS', 'run_id': manifest['run_id'], 'recomputed': recompute,
            'oracle_ndcg_at_10': {name: metrics[name]['ndcg_at_10'] for name in NAMES},
            'test_labels_deserialized': False}
