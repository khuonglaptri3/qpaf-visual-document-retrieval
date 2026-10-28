"""Read-only independent replay of the sealed R7 run on another CPU runtime.

The original verifier requires bit-identical fresh learned scores. This audit
uses its declared reload tolerance and additionally requires identical ranks.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from qpaf.m24.dataset import build_records  # noqa: E402
from qpaf.m44.common import files_manifest, read, sha  # noqa: E402
from qpaf.m44.evaluation import read_wide  # noqa: E402
from qpaf.r7 import runner  # noqa: E402
from qpaf.r7.sealed import COLUMNS, open_sealed_qrels, check_seal  # noqa: E402

METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ranked(prediction):
    return sorted(range(len(prediction['scores'])),
                  key=lambda i: (-prediction['scores'][i], prediction['page_ids'][i]))


def audit(run, pin):
    run = Path(run).resolve()
    require(sha(run / 'manifest.json') == pin, 'R7 manifest hash differs')
    manifest = read(run / 'manifest.json')
    require(manifest['status'].startswith('PASS_TEST172_SEALED_EVALUATION'), 'R7 run status differs')
    require(read(run / '_SUCCESS.json')['manifest_sha256'] == pin, 'success marker differs')
    require((run / '_ATTEMPTED.json').is_file() and (run / '_LABELS_OPENED.json').is_file()
            and not (run / '_FAILED.json').exists(), 'attempt/label/final markers differ')
    require(files_manifest(run) == manifest['files'], 'R7 file receipts differ')
    require(runner.source_hashes(ROOT) == manifest['source_hashes'], 'pinned R7 sources differ')
    require(sha(ROOT / runner.AUTHORIZATION_PATH) == manifest['authorization_sha256'],
            'R7 authorization hash differs')
    seal = check_seal(run)
    require(seal['sha256'] == manifest['prediction_seal_sha256'], 'prediction seal differs')
    auth = read(ROOT / runner.AUTHORIZATION_PATH)
    require(auth['status'] == 'APPROVED' and auth['run_id'] == manifest['run_id'],
            'R7 authorization does not approve this run')
    state = runner.preflight(ROOT, auth)
    fresh = runner.test_predictions(state, ROOT)
    saved = read_wide(run / 'test_predictions.csv.gz', state['test'], COLUMNS)
    parity = {}
    for method in COLUMNS:
        require(len(fresh[method]) == len(saved[method]) == 172, f'{method}: query count differs')
        maximum = 0.0
        nonidentical = 0
        for a, b in zip(fresh[method], saved[method]):
            require(a['query_id'] == b['query_id'] and a['page_ids'] == b['page_ids'],
                    f'{method}: candidates differ')
            for x, y in zip(a['scores'], b['scores']):
                difference = abs(x-y)
                maximum = max(maximum, difference)
                nonidentical += difference != 0
            require(ranked(a) == ranked(b), f'{method}: ranking differs')
        require(maximum <= 1e-7, f'{method}: score reload tolerance exceeded')
        parity[method] = {'max_abs_difference': maximum, 'nonidentical_scores': nonidentical,
                          'ranking_disagreements': 0}
    context, config = state['context'], state['context']['learned_config']
    qrels = open_sealed_qrels(ROOT / auth['held_out']['sealed_qrels'],
                              auth['held_out']['sealed_qrels_sha256'], context['splits']['test'])
    labeled = build_records(state['rows'], state['queries'], qrels, context['splits'], ('test',),
                            positive_threshold=config['data']['positive_threshold'],
                            max_candidates=config['data']['max_candidates'])['test']
    result = runner.score(run, labeled, lambda: None)
    require(read(run / 'metrics_table.json') == result['table'], 'aggregate metrics differ')
    require(read(run / 'paired_per_seed.json') == result['paired'], 'per-seed statistics differ')
    require(read(run / 'oracle_details.json') == result['details'], 'oracle details differ')
    with (run / 'per_query_metrics.csv').open(encoding='utf8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = [(method, row) for method, group in result['per_query'].items() for row in group]
    require(len(rows) == len(expected), 'per-query row count differs')
    max_metric_difference = 0.0
    for stored, (method, calculated) in zip(rows, expected):
        require(stored['method'] == method and stored['query_id'] == calculated['query_id']
                and all(int(stored[k]) == calculated[k] for k in
                        ('candidates', 'relevant_total', 'relevant_in_candidates')),
                'per-query identity or relevance differs')
        for metric in METRICS:
            max_metric_difference = max(max_metric_difference,
                                        abs(float(stored[metric])-calculated[metric]))
    require(max_metric_difference <= 1e-12, 'per-query metric replay differs')
    return {'status': 'PASS_WITH_NUMERICAL_PARITY_NOTE', 'run_id': manifest['run_id'],
            'manifest_sha256': pin, 'authorization_sha256': manifest['authorization_sha256'],
            'prediction_seal_sha256': seal['sha256'], 'query_count': len(labeled),
            'candidate_count': state['report']['test_candidates'],
            'source_verifier': 'FAILS_EXACT_FLOAT_COMPARISON_ON_THIS_CPU',
            'score_tolerance': 1e-7, 'parity': parity,
            'per_query_metric_max_abs_difference': max_metric_difference,
            'aggregate_metrics_replayed': True, 'per_seed_statistics_replayed': True,
            'oracle_details_replayed': True,
            'test_labels_read_by_independent_audit': True,
            'new_training_or_r7_execution': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--expected-manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = audit(args.run, args.expected_manifest_sha256)
    payload = (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode('utf8')
    if args.verify:
        saved = json.loads(args.output.read_text(encoding='utf8'))
        for field in ('status', 'run_id', 'manifest_sha256', 'authorization_sha256',
                      'prediction_seal_sha256', 'query_count', 'candidate_count',
                      'source_verifier', 'score_tolerance', 'aggregate_metrics_replayed',
                      'per_seed_statistics_replayed', 'oracle_details_replayed',
                      'test_labels_read_by_independent_audit', 'new_training_or_r7_execution'):
            require(saved[field] == result[field], f'{field}: audit report differs from replay')
        require(saved['per_query_metric_max_abs_difference'] <= 1e-12 and
                result['per_query_metric_max_abs_difference'] <= 1e-12,
                'per-query metric replay differs')
        require(set(saved['parity']) == set(result['parity']), 'prediction method set differs')
        for method in result['parity']:
            require(saved['parity'][method]['max_abs_difference'] <= 1e-7 and
                    result['parity'][method]['max_abs_difference'] <= 1e-7 and
                    saved['parity'][method]['ranking_disagreements'] == 0 and
                    result['parity'][method]['ranking_disagreements'] == 0,
                    f'{method}: saved or replayed numerical parity differs')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(payload)
    print(json.dumps({'status': result['status'], 'query_count': result['query_count'],
                      'max_score_difference': max(v['max_abs_difference'] for v in result['parity'].values()),
                      'per_query_metric_max_abs_difference': result['per_query_metric_max_abs_difference']}))
