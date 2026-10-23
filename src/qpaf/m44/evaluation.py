"""MTH run: seven deployable baselines plus frozen QPAF on 171 validation queries."""
import csv
import hashlib
import json
from pathlib import Path
import sys

from qpaf.m24.evaluator import evaluate
from qpaf.m25.baselines import ROSTER, predictions as label_free_predictions, select_co_strongest
from qpaf.m44.common import (ROOT, execute_attempt, load_context, read, read_csv_gz, require,
                             verify_run, write_csv_gz, write_json, write_text)

MTH = 'QPAF-M4_4-MTH-001'
METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')
LEARNED = {'learned_qarf', 'qpaf'}


def _scripts():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts import audit_m35_paired, audit_m36_integrity
    return audit_m35_paired, audit_m36_integrity


def check_parity(saved, fresh, *, tolerance):
    """Reloaded checkpoints must reproduce the reviewed validation predictions."""
    return _scripts()[1].compare_predictions(saved, fresh, tolerance)


def learned_predictions(context, method, checkpoint_path, checkpoint_sha256):
    import torch
    from qpaf.m24.checkpoint import load_checkpoint
    from qpaf.m24.evaluator import predict
    from qpaf.m24.trainer import build_model
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    config = context['learned_config']
    checkpoint = load_checkpoint(checkpoint_path, config=config, method=method, expected_sha256=checkpoint_sha256)
    model = build_model(config, method)
    model.load_state_dict(checkpoint['model_state'])
    return predict(model, context['records'], config['training']['batch_size'],
                   config['features']['query_length_cap'])


def method_predictions(context):
    """Return {method: predictions} for the roster plus 'qpaf', and learned parity reports."""
    records, config = context['records'], context['config']
    result = {}
    for method in ROSTER[:-1]:
        weights = context['static_weights'] if method == 'train_fitted_static' else None
        result[method] = label_free_predictions(records, method, weights=weights)
    qarf = context['shared']['inputs']['qarf_checkpoint']
    require(qarf['sha256'] == context['contracts']['learned_qarf']['checkpoint_sha256'],
            'learned QARF checkpoint differs from the M4.2 contract')
    frozen = context['freeze']['frozen_method']['checkpoint']
    sources = {'learned_qarf': ('QARF', context['bundle']/qarf['path'], qarf['sha256']),
               'qpaf': ('QPAF', ROOT/frozen['path'], frozen['sha256'])}
    parity = {}
    for name, (method, path, digest) in sources.items():
        result[name] = learned_predictions(context, method, path, digest)
        saved = read(ROOT/config['saved_predictions'][name]['path'])
        parity[name] = check_parity(saved, result[name], tolerance=config['parity_tolerance'])
    return result, parity


def evaluate_all(predictions, records):
    metrics, per_query = {}, {}
    for method, rows in predictions.items():
        metrics[method], per_query[method] = evaluate(rows, records)
    return metrics, per_query


def contract_sha256(contract):
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(',', ':')).encode('utf8')).hexdigest()


def selection(metrics, contracts, *, tolerance):
    """baseline_policy.md §3: deployable rows only; every row within tolerance is co-strongest."""
    values = {method: metrics[method]['ndcg_at_10'] for method in ROSTER if method in metrics}
    chosen = select_co_strongest(values, tolerance=tolerance)
    return {'candidates': list(ROSTER), 'contract_sha256': {m: contract_sha256(contracts[m]) for m in ROSTER},
            'validation_ndcg_at_10': values, 'best_ndcg_at_10': max(values.values()), 'tolerance': tolerance,
            'co_strongest': chosen, 'proposed_method_eligible': False, 'oracle_rows_eligible': False,
            'rule': 'baseline_policy.md §3: highest validation mean nDCG@10; ties within tolerance are co-strongest',
            'independent_verifier': 'PENDING_M4.5 (Thanh)'}


def build_table(metrics, chosen, *, checkpoint_sha256):
    values = chosen['validation_ndcg_at_10']
    rank = lambda method: 1+sum(other-values[method] > chosen['tolerance'] for other in values.values())
    deployable = [{'method': m, 'rank': rank(m), 'co_strongest': m in chosen['co_strongest'],
                   'optimistic_same_split_selection': m in LEARNED,
                   **{k: metrics[m][k] for k in ('query_count', *METRICS)}} for m in ROSTER]
    proposed = {'method': 'qpaf', 'frozen_checkpoint_sha256': checkpoint_sha256,
                'optimistic_same_split_selection': True,
                **{k: metrics['qpaf'][k] for k in ('query_count', *METRICS)}}
    return {'split': 'validation', 'deployable': deployable, 'proposed_method': proposed,
            'notes': ['Learned QARF and QPAF checkpoints were selected on this validation split; '
                      'their numbers are optimistic.',
                      'Single seed 20260820; not the three-seed confirmatory result.',
                      'Oracle rows are reported separately (QPAF-M4_4-ORC-001) and never enter selection.']}


def table_markdown(table):
    lines = ['| Block | Method | Rank | nDCG@10 | R@1 | R@3 | MRR@10 | Co-strongest |',
             '|---|---|---:|---:|---:|---:|---:|---|']
    for row in table['deployable']:
        lines.append(f"| deployable | {row['method']} | {row['rank']} | {row['ndcg_at_10']:.6f} | "
                     f"{row['recall_at_1']:.6f} | {row['recall_at_3']:.6f} | {row['mrr_at_10']:.6f} | "
                     f"{'yes' if row['co_strongest'] else ''} |")
    row = table['proposed_method']
    lines.append(f"| proposed | {row['method']} (frozen) | | {row['ndcg_at_10']:.6f} | {row['recall_at_1']:.6f} | "
                 f"{row['recall_at_3']:.6f} | {row['mrr_at_10']:.6f} | not eligible |")
    return '\n'.join(lines+['']+[f'- {note}' for note in table['notes']])+'\n'


def paired(per_query, *, resamples, seed):
    """Single-seed exploratory QPAF minus each deployable row, reusing the M3.5 statistics."""
    paired_statistics = _scripts()[0].paired_statistics
    qpaf = {row['query_id']: row for row in per_query['qpaf']}
    result = {}
    for method in ROSTER:
        rows = per_query[method]
        require([r['query_id'] for r in rows] == list(qpaf), f'{method}: query rows are not paired')
        deltas = [{'query_id': r['query_id'], **{'delta_'+k: qpaf[r['query_id']][k]-r[k] for k in METRICS}}
                  for r in rows]
        result[method] = paired_statistics(deltas, resamples=resamples, seed=seed)
    return result


def _wide_rows(predictions, records, methods):
    for index, record in enumerate(records):
        for position, page in enumerate(record.page_ids):
            row = [record.query_id, page]
            for method in methods:
                prediction = predictions[method][index]
                require(prediction['query_id'] == record.query_id and prediction['page_ids'][position] == page,
                        f'{method}: prediction order differs from candidates')
                row.append(float(prediction['scores'][position]))
            yield row


def read_wide(path, records, methods):
    """Rebuild per-method predictions from the saved wide CSV.gz, in candidate order."""
    rows = read_csv_gz(path)
    require(rows and list(rows[0]) == ['query_id', 'page_id', *methods], 'prediction columns differ')
    result, cursor = {m: [] for m in methods}, 0
    for record in records:
        chunk = rows[cursor:cursor+len(record.page_ids)]
        cursor += len(record.page_ids)
        require([r['query_id'] for r in chunk] == [record.query_id]*len(record.page_ids) and
                [r['page_id'] for r in chunk] == list(record.page_ids), 'saved prediction rows differ')
        for method in methods:
            result[method].append({'query_id': record.query_id, 'page_ids': list(record.page_ids),
                                   'scores': [float(r[method]) for r in chunk]})
    require(cursor == len(rows), 'saved predictions contain extra rows')
    return result


def write_per_query(path, per_query):
    with Path(path).open('x', encoding='utf8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['method', 'query_id', 'candidates', 'relevant_total', 'relevant_in_candidates', *METRICS])
        for method, rows in per_query.items():
            for r in rows:
                writer.writerow([method, r['query_id'], r['candidates'], r['relevant_total'],
                                 r['relevant_in_candidates'], *(repr(float(r[k])) for k in METRICS)])


def derived(context, metrics, per_query):
    config = context['config']
    chosen = selection(metrics, context['contracts'], tolerance=config['co_strongest_tolerance'])
    table = build_table(metrics, chosen, checkpoint_sha256=context['freeze']['frozen_method']['checkpoint']['sha256'])
    stats = {'scope': config['paired']['scope'], 'resamples': config['paired']['resamples'],
             'seed': config['paired']['seed'],
             'comparisons': paired(per_query, resamples=config['paired']['resamples'], seed=config['paired']['seed'])}
    return chosen, table, stats


def produce_mth(context, output, deadline):
    predictions, parity = method_predictions(context)
    deadline()
    metrics, per_query = evaluate_all(predictions, context['records'])
    chosen, table, stats = derived(context, metrics, per_query)
    methods = [*ROSTER, 'qpaf']
    write_csv_gz(output/'predictions.csv.gz', ['query_id', 'page_id', *methods],
                 _wide_rows(predictions, context['records'], methods))
    write_per_query(output/'per_query_metrics.csv', per_query)
    write_json(output/'baseline_table.json', table)
    write_text(output/'baseline_table.md', table_markdown(table))
    write_json(output/'selection.json', chosen)
    write_json(output/'paired_exploratory.json', stats)
    write_json(output/'learned_parity.json', parity)
    return {'co_strongest': chosen['co_strongest'], 'validation_ndcg_at_10': chosen['validation_ndcg_at_10'],
            'qpaf_ndcg_at_10': metrics['qpaf']['ndcg_at_10']}


def execute_mth(root, authorization, expected_sha256, run_id):
    return execute_attempt(root, authorization, expected_sha256, MTH, run_id, produce_mth)


def verify_mth(root, output, expected_manifest_sha256):
    """Re-hash, then recompute metrics, selection, table and paired statistics from saved predictions."""
    root, output = Path(root).resolve(), Path(output)
    manifest = verify_run(output, expected_manifest_sha256)
    context = load_context(root)
    methods = [*ROSTER, 'qpaf']
    metrics, per_query = evaluate_all(read_wide(output/'predictions.csv.gz', context['records'], methods),
                                      context['records'])
    chosen, table, stats = derived(context, metrics, per_query)
    for name, value in [('selection.json', chosen), ('baseline_table.json', table),
                        ('paired_exploratory.json', stats)]:
        require(read(output/name) == json.loads(json.dumps(value)), f'{name} does not replay')
    return {'status': 'PASS', 'run_id': manifest['run_id'], 'co_strongest': chosen['co_strongest'],
            'validation_ndcg_at_10': chosen['validation_ndcg_at_10'],
            'qpaf_ndcg_at_10': metrics['qpaf']['ndcg_at_10'], 'test_labels_deserialized': False}
