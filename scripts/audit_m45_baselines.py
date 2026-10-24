"""Independent, read-only M4.5 audit of M4.2/M4.4 validation evidence.

Only development qrels and frozen split IDs are read. No test/confirmation
labels, optimizer step, oracle search or new result-bearing run is involved.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
M42 = Path('results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01')
MTH = Path('results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01')
ORC = Path('results/m4.4/RUN-QPAF-M4_4-ORC-001-20261023T172102Z-A01')
PINS = {
    'm42': '4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86',
    'mth': 'aa2ab51814c883b5552b1b45136c1f25dd7d9921a074891f4ae0397f4b03e4a7',
    'orc': '6d796a27537c191d5b39436cf6fcaffa9e58b4c01628d9558da6ba261739b5a2',
}
ROSTER = ('bm25', 'bge_m3', 'colqwen25', 'uniform_combsum', 'rrf_k60',
          'train_fitted_static', 'learned_qarf')
METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')
CHANNELS = ('bm25_score', 'dense_score', 'visual_score')
TOLERANCE = 1e-12


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def checked_file(root, relative, expected):
    path = (Path(root) / relative).resolve()
    require(path.is_relative_to(Path(root).resolve()) and path.is_file(),
            f'missing or escaped pinned file: {relative}')
    require(sha256(path) == expected, f'hash differs: {relative}')
    return path


def verify_manifest(run, expected_sha256):
    run = Path(run)
    manifest = read_json(checked_file(run, 'manifest.json', expected_sha256))
    require((run / '_ATTEMPTED.json').is_file() and (run / '_SUCCESS.json').is_file() and
            not (run / '_FAILED.json').exists(), f'{run.name}: invalid attempt/final markers')
    require(read_json(run / '_SUCCESS.json')['manifest_sha256'] == expected_sha256,
            f'{run.name}: success marker pin differs')
    paths = [item['path'] for item in manifest['files']]
    require(len(paths) == len(set(paths)), f'{run.name}: duplicate manifest paths')
    for item in manifest['files']:
        path = checked_file(run, item['path'], item['sha256'])
        require(path.stat().st_size == item['size_bytes'], f'{item["path"]}: size differs')
    return manifest


def numeric_difference(actual, expected, label='value'):
    """Compare nested evidence while accepting only protocol-scale float noise."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        require(set(actual) == set(expected), f'{label}: keys differ')
        return max((numeric_difference(actual[k], expected[k], f'{label}.{k}')
                    for k in actual), default=0.0)
    if isinstance(actual, list) and isinstance(expected, list):
        require(len(actual) == len(expected), f'{label}: lengths differ')
        return max((numeric_difference(a, b, f'{label}[{i}]')
                    for i, (a, b) in enumerate(zip(actual, expected))), default=0.0)
    if type(actual) in (float, int) and type(expected) in (float, int):
        require(math.isfinite(actual) and math.isfinite(expected), f'{label}: nonfinite')
        difference = abs(actual - expected)
        require(difference <= TOLERANCE, f'{label}: numeric difference {difference}')
        return difference
    require(actual == expected and type(actual) is type(expected), f'{label}: differs')
    return 0.0


def query_metrics(pages, scores, positives):
    require(pages and len(pages) == len(scores) == len(set(pages)) and positives,
            'missing or duplicate candidates/relevance')
    require(all(math.isfinite(value) for value in scores), 'nonfinite score')
    ranked = sorted(range(len(pages)), key=lambda i: (-scores[i], pages[i]))
    hits = [pages[i] in positives for i in ranked]
    ideal = math.fsum(1 / math.log2(i + 2) for i in range(min(10, len(positives))))
    dcg = math.fsum(hit / math.log2(i + 2) for i, hit in enumerate(hits[:10]))
    first = next((i for i, hit in enumerate(hits[:10], 1) if hit), None)
    return {'candidates': len(pages), 'relevant_total': len(positives),
            'relevant_in_candidates': sum(page in positives for page in pages),
            'ndcg_at_10': dcg / ideal,
            'recall_at_1': sum(hits[:1]) / len(positives),
            'recall_at_3': sum(hits[:3]) / len(positives),
            'mrr_at_10': 1 / first if first else 0.0}


def normalized(raw):
    array = np.asarray(raw, dtype=np.float64)
    require(array.ndim == 2 and array.shape[1] == 3 and len(array) > 0 and
            np.isfinite(array).all(), 'raw score shape/finite check failed')
    low = array.min(axis=0)
    span = array.max(axis=0) - low
    return np.divide(array - low, span, out=np.zeros_like(array), where=span > 0)


def fit_static_grid(grouped, qrels, train_ids):
    """Independently evaluate the frozen 66-point simplex using train qrels only."""
    require(train_ids and len(train_ids) == len(set(train_ids)), 'invalid train IDs')
    weights = np.asarray([(a / 10, b / 10, (10 - a - b) / 10)
                          for a in range(11) for b in range(11 - a)], dtype=np.float64)
    totals = np.zeros(66, dtype=np.float64)
    discounts = np.asarray([1 / math.log2(i + 2) for i in range(10)])
    for query_id in train_ids:
        pages_map = grouped.get(query_id)
        judged = qrels.get(query_id)
        require(pages_map and isinstance(judged, dict), 'train row/qrels missing')
        pages = sorted(pages_map)
        positives = {page for page, value in judged.items() if value >= 1}
        require(positives, 'train query lacks positive qrels')
        values = normalized([pages_map[page] for page in pages])
        scores = values @ weights.T
        ranking = np.argsort(-scores, axis=0, kind='stable')[:10]
        labels = np.asarray([page in positives for page in pages], dtype=np.float64)
        gain = (labels[ranking] * discounts[:len(ranking), None]).sum(axis=0)
        ideal = discounts[:min(10, len(positives))].sum()
        totals += gain / ideal
    means = totals / len(train_ids)
    best_index, best_value = None, -math.inf
    for index, value in enumerate(means):
        if value > best_value + TOLERANCE:
            best_index, best_value = index, float(value)
    return {'weights': weights[best_index].tolist(), 'train_ndcg_at_10': best_value,
            'train_queries': len(train_ids), 'grid_ndcg': means.tolist()}


def select_co_strongest(metrics, roster, tolerance=TOLERANCE):
    require(roster and all(method in metrics for method in roster), 'missing deployable row')
    best = max(metrics[method] for method in roster)
    return [method for method in roster if best - metrics[method] <= tolerance]


def paired_summary(deltas, *, seed=20260820, resamples=10000):
    values = np.asarray(deltas, dtype=np.float64)
    require(values.ndim == 1 and len(values) and np.isfinite(values).all(),
            'invalid paired query deltas')
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(values), size=(resamples, len(values)))
    ci = np.percentile(values[draws].mean(axis=1), [2.5, 97.5], method='linear')
    wins = int((values > TOLERANCE).sum())
    ties = int((np.abs(values) <= TOLERANCE).sum())
    losses = int((values < -TOLERANCE).sum())
    require(wins + ties + losses == len(values), 'W/T/L total differs')
    gains = np.maximum(values, 0)
    top_count = max(1, math.ceil(.05 * len(values)))
    total_gain = float(gains.sum())
    mean = float(values.mean())
    std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    return {'mean_delta': mean, 'median_delta': float(np.median(values)),
            'ci95': [float(ci[0]), float(ci[1])],
            'wtl': {'wins': wins, 'ties': ties, 'losses': losses},
            'sample_std_delta': std,
            'paired_standardized_effect': mean / std if std else None,
            'top_5pct_positive_gain_query_count': top_count,
            'top_5pct_positive_gain_share':
                float(np.sort(gains)[-top_count:].sum() / total_gain) if total_gain else 0.0}


def read_ids(path):
    ids = Path(path).read_text(encoding='utf8').splitlines()
    require(ids and len(ids) == len(set(ids)) and all(ids), f'{path}: invalid IDs')
    return ids


def read_raw_scores(path, known_ids):
    columns = ['query_id', 'page_id', *CHANNELS]
    table = pq.read_table(path, columns=columns).to_pydict()
    grouped = {}
    for query_id, page_id, *scores in zip(*(table[name] for name in columns)):
        require(query_id in known_ids and isinstance(page_id, str) and page_id,
                'raw score query/page identity differs')
        pages = grouped.setdefault(query_id, {})
        require(page_id not in pages, 'duplicate raw score candidate')
        require(all(type(value) in (float, int) and math.isfinite(value) for value in scores),
                'nonfinite or missing raw channel')
        pages[page_id] = tuple(scores)
    require(set(grouped) == known_ids, 'raw score query coverage differs')
    return grouped, len(table['query_id'])


def read_wide(path, methods, expected_ids, grouped):
    rows = {}
    with gzip.open(path, 'rt', encoding='utf8', newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == ['query_id', 'page_id', *methods], 'wide header differs')
        for row in reader:
            query_id, page_id = row['query_id'], row['page_id']
            require(query_id in expected_ids, 'wide prediction contains another split')
            pages = rows.setdefault(query_id, {})
            require(page_id in grouped[query_id] and page_id not in pages,
                    'wide candidate set or duplicate differs')
            values = {method: float(row[method]) for method in methods}
            require(all(math.isfinite(value) for value in values.values()), 'nonfinite prediction')
            pages[page_id] = values
    require(set(rows) == set(expected_ids), 'wide query coverage differs')
    for query_id in expected_ids:
        require(list(rows[query_id]) == sorted(grouped[query_id]),
                'wide candidate order/coverage differs')
    return rows


def check_baseline_scores(grouped, wide, validation_ids, weights):
    max_diff = {name: 0.0 for name in ROSTER[:-1]}
    for query_id in validation_ids:
        pages = list(wide[query_id])
        raw = np.asarray([grouped[query_id][page] for page in pages], dtype=np.float64)
        norm = normalized(raw)
        ranks = np.empty((len(pages), 3), dtype=np.int64)
        for channel in range(3):
            order = np.argsort(-raw[:, channel], kind='stable')
            ranks[order, channel] = np.arange(1, len(pages) + 1)
        expected = {'bm25': norm[:, 0], 'bge_m3': norm[:, 1], 'colqwen25': norm[:, 2],
                    'uniform_combsum': norm.sum(axis=1) / 3,
                    'rrf_k60': (1 / (60 + ranks)).sum(axis=1),
                    'train_fitted_static': norm @ np.asarray(weights)}
        for index, page_id in enumerate(pages):
            for method, scores in expected.items():
                diff = abs(float(scores[index]) - wide[query_id][page_id][method])
                require(diff <= TOLERANCE, f'{method}: saved score differs')
                max_diff[method] = max(max_diff[method], diff)
    return max_diff


def check_learned_parity(root, config, wide, validation_ids):
    max_diff = {}
    for method, ref in config['saved_predictions'].items():
        saved = read_json(checked_file(root, ref['path'], ref['sha256']))
        require(len(saved) == len(validation_ids), f'{method}: pilot query count differs')
        discrepancy = 0.0
        for query_id, row in zip(validation_ids, saved):
            pages = list(wide[query_id])
            require(row['query_id'] == query_id and row['page_ids'] == pages,
                    f'{method}: pilot candidate order differs')
            for page_id, score in zip(pages, row['scores']):
                discrepancy = max(discrepancy, abs(score - wide[query_id][page_id][method]))
        require(discrepancy <= 1e-7, f'{method}: pilot parity differs')
        max_diff[method] = discrepancy
    return max_diff


def replay_metrics(wide, methods, ids, qrels, saved_csv=None):
    reported = {}
    if saved_csv is not None:
        with Path(saved_csv).open('r', encoding='utf8', newline='') as stream:
            for row in csv.DictReader(stream):
                key = (row['method'], row['query_id'])
                require(key not in reported, 'duplicate saved per-query metric')
                reported[key] = row
        require(set(reported) == {(method, query_id) for method in methods for query_id in ids},
                'saved per-query metric coverage differs')
    values, max_diff = {}, 0.0
    for method in methods:
        method_rows = {}
        for query_id in ids:
            pages = list(wide[query_id])
            positives = {page for page, relevance in qrels[query_id].items() if relevance >= 1}
            metrics = query_metrics(pages, [wide[query_id][page][method] for page in pages], positives)
            if reported:
                saved = reported[method, query_id]
                for key in ('candidates', 'relevant_total', 'relevant_in_candidates'):
                    require(metrics[key] == int(saved[key]), f'{method}: {key} differs')
                for key in METRICS:
                    diff = abs(metrics[key] - float(saved[key]))
                    require(diff <= TOLERANCE, f'{method}: per-query {key} differs')
                    max_diff = max(max_diff, diff)
            method_rows[query_id] = metrics
        values[method] = method_rows
    return values, max_diff


def audit(root=ROOT):
    root = Path(root).resolve()
    bundle, mth, orc = root / M42, root / MTH, root / ORC
    manifests = {key: verify_manifest(path, PINS[key]) for key, path in
                 (('m42', bundle), ('mth', mth), ('orc', orc))}
    config = read_json(root / 'configs/m4.4/evaluation.json')
    authorization = read_json(checked_file(root, 'evidence/revisions/m4.4-001/authorization.json',
                                               manifests['mth']['authorization_sha256']))
    require(authorization['status'] == 'APPROVED' and
            manifests['mth']['authorization_sha256'] == manifests['orc']['authorization_sha256'],
            'M4.4 authorization mismatch')
    require(all(isinstance(authorization['approval'].get(key), str) and
                authorization['approval'][key].strip()
                for key in ('approver', 'approval_text', 'approved_utc')),
            'M4.4 human approval record is incomplete')
    for key, path in (('mth', mth), ('orc', orc)):
        manifest = manifests[key]
        attempt = read_json(path / '_ATTEMPTED.json')
        experiment = authorization['experiments'][manifest['experiment_id']]
        require(authorization['source_commit'] == manifest['source_commit'] ==
                attempt['git_head'] and experiment['run_id'] == manifest['run_id'] ==
                attempt['run_id'] and experiment['invocations'] == 1 and
                experiment['automatic_retries'] == 0 and
                attempt['authorization_sha256'] == manifest['authorization_sha256'],
                f'{key}: authorized attempt lineage differs')
    require(sha256(root / 'configs/m4.4/evaluation.json') ==
            manifests['mth']['config_sha256'] == manifests['orc']['config_sha256'],
            'M4.4 config pin differs')
    require(manifests['mth']['bundle_manifest_sha256'] ==
            manifests['orc']['bundle_manifest_sha256'] == PINS['m42'],
            'M4.4 bundle pin differs')
    freeze = config['freeze']
    checked_file(root, freeze['path'], freeze['sha256'])
    freeze_confirmation = read_json(root / 'evidence/revisions/m4.3-001/owner_confirmation.json')
    require(freeze_confirmation['decision'] == 'CONFIRMED' and
            freeze_confirmation['freeze_sha256'] == freeze['sha256'],
            'M4.3 owner freeze confirmation differs')
    require(manifests['mth']['freeze_sha256'] == manifests['orc']['freeze_sha256'] ==
            freeze['sha256'], 'M4.3 freeze pin differs')
    for key, manifest in manifests.items():
        for name, digest in manifest.get('source_hashes', {}).items():
            checked_file(root, name, digest)
        if key != 'm42':
            require(manifest['test_labels_deserialized'] is False, 'run opened test labels')
    for path in (bundle, mth, orc):
        access = read_json(path / 'access.json')
        require(access['test_labels_deserialized'] is False and
                access['vimdoc_confirmation_accessed'] is False, 'forbidden label access flag')

    shared = read_json(bundle / 'shared_inputs.json')
    contracts = read_json(bundle / 'baseline_contracts.json')
    fitted = read_json(bundle / 'train_fit.json')
    require(set(contracts) == set(ROSTER) and config['roster'] == list(ROSTER),
            'baseline roster differs')
    require(len({contract['shared_inputs_sha256'] for contract in contracts.values()}) == 1 and
            next(iter(contracts.values()))['shared_inputs_sha256'] == sha256(bundle / 'shared_inputs.json'),
            'baseline common-input binding differs')
    require(contracts['rrf_k60']['rank_constant'] == 60 and
            contracts['rrf_k60']['fitting'] is False and
            contracts['train_fitted_static']['fitting'] == 'train_only' and
            contracts['train_fitted_static']['weights'] == fitted['weights'],
            'baseline settings differ')
    splits = {role: read_ids(bundle / shared['inputs'][name]['path']) for role, name in
              (('train', 'split_train'), ('validation', 'split_validation'), ('test', 'split_test'))}
    require(tuple(len(splits[role]) for role in ('train', 'validation', 'test')) == (799, 171, 172),
            'frozen split counts differ')
    ids = set().union(*map(set, splits.values()))
    require(len(ids) == 1142, 'split overlap/union differs')
    qrels = read_json(bundle / shared['inputs']['qrels_development']['path'])
    require(set(qrels) == set(splits['train']) | set(splits['validation']) and
            not set(qrels) & set(splits['test']), 'development qrels include wrong split')
    grouped, raw_rows = read_raw_scores(bundle / shared['inputs']['score_cache']['path'], ids)
    require(raw_rows == 551764, 'shared raw-score row count differs')
    grid = fit_static_grid(grouped, qrels, splits['train'])
    require(grid['weights'] == fitted['weights'] and fitted['candidates'] == 66 and
            abs(grid['train_ndcg_at_10'] - fitted['train_ndcg_at_10']) <= TOLERANCE,
            'independent train-only fit differs')
    grid_csv = root / 'results/m4.2/verification/independent-grid-replay/train_grid.csv'
    with grid_csv.open('r', encoding='utf8', newline='') as stream:
        saved_grid = list(csv.DictReader(stream))
    require(len(saved_grid) == 66, 'saved train grid count differs')
    grid_difference = 0.0
    for index, row in enumerate(saved_grid):
        difference = abs(grid['grid_ndcg'][index] - float(row['mean_train_ndcg_at_10']))
        require(difference <= TOLERANCE, 'saved train grid objective differs')
        grid_difference = max(grid_difference, difference)
    require(sum(row['selected'] == 'True' for row in saved_grid) == 1 and
            next(row for row in saved_grid if row['selected'] == 'True')['bge_m3_weight'] == '0.1',
            'saved train grid selected row differs')

    wide = read_wide(mth / 'predictions.csv.gz', [*ROSTER, 'qpaf'],
                     splits['validation'], grouped)
    candidate_rows = sum(len(wide[query_id]) for query_id in splits['validation'])
    require(candidate_rows == 82255, 'validation candidate count differs')
    score_difference = check_baseline_scores(grouped, wide, splits['validation'], fitted['weights'])
    learned_difference = check_learned_parity(root, config, wide, splits['validation'])
    metrics, per_query_difference = replay_metrics(wide, [*ROSTER, 'qpaf'],
                                                   splits['validation'], qrels,
                                                   mth / 'per_query_metrics.csv')
    aggregate = {method: {name: math.fsum(metrics[method][qid][name]
                                           for qid in splits['validation']) / 171
                          for name in METRICS} for method in [*ROSTER, 'qpaf']}
    table = read_json(mth / 'baseline_table.json')
    selection = read_json(mth / 'selection.json')
    require([row['method'] for row in table['deployable']] == list(ROSTER) and
            selection['candidates'] == list(ROSTER), 'baseline table/selection roster differs')
    aggregate_difference = 0.0
    for row in [*table['deployable'], table['proposed_method']]:
        method = row['method']
        require(row['query_count'] == 171, f'{method}: query count differs')
        for name in METRICS:
            difference = abs(aggregate[method][name] - row[name])
            require(difference <= TOLERANCE, f'{method}: aggregate {name} differs')
            aggregate_difference = max(aggregate_difference, difference)
    for method in ROSTER:
        require(abs(aggregate[method]['ndcg_at_10'] -
                    selection['validation_ndcg_at_10'][method]) <= TOLERANCE,
                f'{method}: selection metric differs')
        contract_hash = hashlib.sha256(json.dumps(contracts[method], sort_keys=True,
                                                 separators=(',', ':')).encode('utf8')).hexdigest()
        require(selection['contract_sha256'][method] == contract_hash,
                f'{method}: contract hash differs')
    strongest = select_co_strongest({m: aggregate[m]['ndcg_at_10'] for m in ROSTER},
                                     ROSTER, selection['tolerance'])
    require(strongest == selection['co_strongest'] == ['train_fitted_static'] and
            selection['oracle_rows_eligible'] is False and
            selection['proposed_method_eligible'] is False,
            'co-strongest selection or eligibility differs')

    saved_paired = read_json(mth / 'paired_exploratory.json')
    require(saved_paired['resamples'] == 10000 and saved_paired['seed'] == 20260820 and
            set(saved_paired['comparisons']) == set(ROSTER), 'paired protocol differs')
    paired = {}
    max_paired_difference = 0.0
    delta_rows = []
    for baseline in ROSTER:
        paired[baseline] = {}
        for name in METRICS:
            deltas = [metrics['qpaf'][query_id][name] - metrics[baseline][query_id][name]
                      for query_id in splits['validation']]
            result = paired_summary(deltas)
            max_paired_difference = max(max_paired_difference,
                                        numeric_difference(result,
                                                           saved_paired['comparisons'][baseline][name],
                                                           f'{baseline}.{name}'))
            if name == 'ndcg_at_10':
                paired[baseline] = result
                for query_id, delta in zip(splits['validation'], deltas):
                    delta_rows.append({'baseline': baseline, 'query_id': query_id,
                                       'qpaf_ndcg_at_10': metrics['qpaf'][query_id][name],
                                       'baseline_ndcg_at_10': metrics[baseline][query_id][name],
                                       'delta_ndcg_at_10': delta})

    oracle_table = read_json(orc / 'oracle_table.json')
    oracle_methods = [row['method'] for row in oracle_table['rows']]
    require(oracle_table['selection_eligible'] is False and
            oracle_table['block'] == 'oracle_context' and
            len(oracle_methods) == len(set(oracle_methods)) == 6 and
            not set(oracle_methods) & set(selection['candidates']),
            'oracle rows entered deployable selection')
    oracle_wide = read_wide(orc / 'oracle_predictions.csv.gz', oracle_methods,
                            splits['validation'], grouped)
    oracle_metrics, _ = replay_metrics(oracle_wide, oracle_methods,
                                       splits['validation'], qrels)
    oracle_difference = 0.0
    for row in oracle_table['rows']:
        for name in METRICS:
            value = math.fsum(oracle_metrics[row['method']][qid][name]
                              for qid in splits['validation']) / 171
            difference = abs(value - row[name])
            require(difference <= TOLERANCE, f'{row["method"]}: oracle metric differs')
            oracle_difference = max(oracle_difference, difference)

    strongest_name = strongest[0]
    report = {
        'schema_version': 1, 'task_id': 'M4.5', 'owner': 'Thanh',
        'technical_reviewer': 'Codex, independent replay at Thanh request',
        'technical_verdict': 'PASS', 'owner_acceptance': 'PENDING_THANH_CONFIRMATION',
        'scope': 'ViDoSeek validation only, 171 queries, one learned seed 20260820',
        'manifest_sha256': PINS,
        'train_only': {'queries': 799, 'grid_candidates': 66,
                       'weights': grid['weights'],
                       'mean_ndcg_at_10': grid['train_ndcg_at_10'],
                       'max_abs_saved_grid_difference': grid_difference},
        'fairness': {'validation_queries': 171, 'shared_candidate_rows': candidate_rows,
                     'all_seven_baselines_share_input_hash': True,
                     'max_abs_baseline_score_difference': score_difference,
                     'max_abs_learned_pilot_difference': learned_difference,
                     'max_abs_per_query_metric_difference': per_query_difference,
                     'max_abs_aggregate_metric_difference': aggregate_difference,
                     'oracle_separate_and_ineligible': True,
                     'max_abs_oracle_metric_difference': oracle_difference},
        'selection': {'co_strongest': strongest,
                      'validation_ndcg_at_10': {m: aggregate[m]['ndcg_at_10']
                                                for m in [*ROSTER, 'qpaf']}},
        'uncertainty': {'unit': 'paired query', 'resamples': 10000,
                        'bootstrap_seed': 20260820, 'wtl_tolerance': TOLERANCE,
                        'max_abs_saved_statistics_difference': max_paired_difference,
                        'qpaf_minus_baseline_ndcg_at_10': paired},
        'interpretation': {'qpaf_minus_strongest_validation_mean':
                           paired[strongest_name]['mean_delta'],
                           'qpaf_exceeds_strongest_on_validation':
                           aggregate['qpaf']['ndcg_at_10'] > aggregate[strongest_name]['ndcg_at_10'],
                           'single_seed_exploratory_only': True,
                           'three_seed_or_confirmation_claim': False,
                           'm46_method_direction_decided': False},
        'limitations': [
            'QARF and QPAF checkpoints were selected on this validation split.',
            'M4.3 owner confirmation was recorded after the M4.4 validation run; no test access occurred.',
            'M4.4 exact-JSON verifier is Python-runtime-sensitive at sub-1e-15 float differences.'
        ],
        'test_labels_deserialized': False, 'vimdoc_confirmation_accessed': False,
        'new_result_bearing_run': False,
    }
    return report, delta_rows


def delta_csv(rows):
    stream = io.StringIO(newline='')
    fields = ['baseline', 'query_id', 'qpaf_ndcg_at_10',
              'baseline_ndcg_at_10', 'delta_ndcg_at_10']
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf8')


def verify_owner_acceptance(output_dir):
    output_dir = Path(output_dir)
    confirmation_path = output_dir / 'owner_confirmation.json'
    event_path = output_dir / 'governance_events.jsonl'
    confirmation = read_json(confirmation_path)
    require(confirmation['task_id'] == 'M4.5' and
            confirmation['reviewer'] == 'Thanh' and
            confirmation['decision'] == 'ACCEPTED' and
            confirmation['confirmation_text'] == 'Có, ghi Thanh chấp nhận M4.5' and
            confirmation['technical_report_sha256'] == sha256(output_dir / 'verification.json') and
            confirmation['per_query_sha256'] == sha256(output_dir / 'per_query_deltas.csv') and
            confirmation['m46_direction_decided'] is False and
            confirmation['qpaf_superiority_claimed'] is False,
            'owner confirmation does not bind the accepted M4.5 audit')
    events = event_path.read_text(encoding='utf8').splitlines()
    require(len(events) == 1, 'M4.5 governance event count differs')
    event = json.loads(events[0])
    require(event['task_id'] == 'M4.5' and
            event['event_type'] == 'ACCEPTANCE_RECORDED' and
            event['registry_status'] == 'PASS' and
            event['human_review'] == 'ACCEPTED_BY_THANH' and
            event['verification_sha256'] == confirmation['technical_report_sha256'] and
            event['per_query_sha256'] == confirmation['per_query_sha256'] and
            event['review_signoff_sha256'] == sha256(confirmation_path) and
            event['m46_direction_decided'] is False and
            event['qpaf_superiority_claimed'] is False,
            'M4.5 governance event does not bind the owner confirmation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    report, rows = audit()
    csv_bytes = delta_csv(rows)
    report['per_query_deltas_sha256'] = hashlib.sha256(csv_bytes).hexdigest()
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')
    if args.verify:
        require(read_json(args.output_dir / 'verification.json') == report and
                (args.output_dir / 'per_query_deltas.csv').read_bytes() == csv_bytes,
                'M4.5 evidence differs from independent replay')
        require(sorted(p.name for p in args.output_dir.iterdir()) ==
                ['README.md', 'governance_events.jsonl', 'owner_confirmation.json',
                 'per_query_deltas.csv', 'verification.json'],
                'M4.5 evidence file set differs')
        verify_owner_acceptance(args.output_dir)
        print('M4.5 independent audit: PASS')
    else:
        require(not args.output_dir.exists(), 'M4.5 output directory already exists')
        args.output_dir.mkdir(parents=True)
        (args.output_dir / 'per_query_deltas.csv').write_bytes(csv_bytes)
        (args.output_dir / 'verification.json').write_bytes(encoded)
        print('M4.5 technical audit created; owner acceptance pending')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as exc:
        raise SystemExit(f'M4.5 refused: {exc}')
