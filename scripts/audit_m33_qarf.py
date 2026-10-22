"""Independent, read-only M3.3 audit of the one authorized QARF pilot.

Run with the M3.2-pinned Python environment after restoring the M3.1 sealed
inputs. Test qrels are hashed by the seal verifier but never deserialized here.
Use --output only for a new, create-once review record.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = ROOT / 'evidence/revisions/m3.2-001/authorization.json'
AUTH_SHA256 = 'ae51a3a5601d43b0a758d5feb69b74b4ba24b0413965e5fee96ed7015ede9b4b'
PREDICTIONS_SHA256 = '658c8162b690bff751609298aa8e77bf80cdf035cdbb45711ca5f1050407ab1e'
METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')


class AuditError(ValueError):
    """The reviewed run or its independent replay does not meet M3.3."""


def sha(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise AuditError(message)


def check_supervisor_markers(namespace, authorization_sha256):
    namespace = Path(namespace)
    for name in ('_ATTEMPTED.json', '_SUCCESS.json', 'supervisor.log'):
        require((namespace / name).is_file(), f'missing supervisor marker: {name}')
    require(not (namespace / '_FAILED.json').exists(), 'both final markers or failed run')
    attempted, success = read(namespace / '_ATTEMPTED.json'), read(namespace / '_SUCCESS.json')
    require(attempted.get('authorization_sha256') == authorization_sha256, 'attempt authorization mismatch')
    require(success.get('authorization_sha256') == authorization_sha256, 'success authorization mismatch')
    require(success.get('exit_code') == 0, 'supervised process did not exit successfully')
    require(attempted.get('run_id') == success.get('run_id'), 'supervisor run IDs disagree')
    return attempted, success


def calculate_validation(predictions, qrels, validation_ids, candidate_pages, *, threshold=1):
    """Compute binary page metrics without importing the training evaluator."""
    require(len(validation_ids) == len(set(validation_ids)), 'duplicate validation ID')
    require(len(predictions) == len(validation_ids), 'predictions do not cover validation')
    require([p.get('query_id') for p in predictions] == list(validation_ids), 'prediction query order differs')
    per_query = []
    for prediction in predictions:
        query_id = prediction['query_id']
        pages, scores = prediction.get('page_ids'), prediction.get('scores')
        expected_pages = candidate_pages.get(query_id)
        require(isinstance(pages, list) and pages == expected_pages, f'{query_id}: candidate pages/order differ')
        require(len(pages) > 0 and len(pages) == len(set(pages)), f'{query_id}: empty/duplicate pages')
        require(isinstance(scores, list) and len(scores) == len(pages), f'{query_id}: scores missing')
        require(all(type(value) in (int, float) and math.isfinite(value) for value in scores),
                f'{query_id}: nonfinite or nonnumeric score')
        judged = qrels.get(query_id)
        require(isinstance(judged, dict), f'{query_id}: missing development qrels')
        positives = {page for page, relevance in judged.items() if relevance >= threshold}
        require(positives, f'{query_id}: no positive qrel')
        captured = len(positives.intersection(pages))
        require(captured > 0, f'{query_id}: uncovered positive')
        ranked = sorted(range(len(pages)), key=lambda index: (-scores[index], pages[index]))
        labels = [int(pages[index] in positives) for index in ranked[:10]]
        ideal = sum(1 / math.log2(index + 2) for index in range(min(10, len(positives))))
        dcg = sum(label / math.log2(index + 2) for index, label in enumerate(labels))
        first = next((index for index, label in enumerate(labels) if label), None)
        per_query.append({
            'query_id': query_id,
            'candidates': len(pages),
            'relevant_total': len(positives),
            'relevant_in_candidates': captured,
            'ndcg_at_10': dcg / ideal,
            'recall_at_1': sum(labels[:1]) / len(positives),
            'recall_at_3': sum(labels[:3]) / len(positives),
            'mrr_at_10': 0.0 if first is None else 1 / (first + 1),
        })
    aggregate = {'query_count': len(per_query)}
    aggregate.update({name: sum(row[name] for row in per_query) / len(per_query) for name in METRICS})
    return aggregate, per_query


def compare_reported_metrics(aggregate, per_query, attempt):
    reported = read(attempt / 'validation_metrics.json')
    rows = list(csv.DictReader((attempt / 'validation_per_query.csv').open(encoding='utf-8', newline='')))
    require(reported['query_count'] == len(per_query) == len(rows), 'metric query counts differ')
    largest = 0.0
    for calculated, row in zip(per_query, rows):
        require(calculated['query_id'] == row['query_id'], 'per-query metric order differs')
        for key in ('candidates', 'relevant_total', 'relevant_in_candidates'):
            require(calculated[key] == int(row[key]), f'{calculated["query_id"]}: {key} differs')
        for key in METRICS:
            difference = abs(calculated[key] - float(row[key]))
            largest = max(largest, difference)
            require(difference <= 1e-12, f'{calculated["query_id"]}: {key} differs')
    for key in METRICS:
        difference = abs(aggregate[key] - reported[key])
        largest = max(largest, difference)
        require(difference <= 1e-12, f'aggregate {key} differs')
    return largest


def check_receipt(attempt, success):
    require(sha(attempt / 'receipt.json') == success['receipt_sha256'], 'receipt hash differs from success marker')
    receipt = read(attempt / 'receipt.json')
    listed = set()
    for output in receipt['outputs']:
        rel = Path(output['path'])
        require(not rel.is_absolute() and '..' not in rel.parts, 'unsafe receipt path')
        path = attempt / rel
        require(output['path'] not in listed and path.is_file(), f'missing/duplicate receipt output: {rel}')
        listed.add(output['path'])
        require(path.stat().st_size == output['size_bytes'], f'{rel}: byte size differs')
        require(sha(path) == output['sha256'], f'{rel}: SHA-256 differs')
    local = {path.relative_to(attempt).as_posix() for path in attempt.rglob('*') if path.is_file()}
    require(local == listed | {'receipt.json'}, 'unlisted attempt output')
    return len(listed)


def run_read_only(command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    require(result.returncode == 0, f'read-only check failed: {result.stderr.strip() or result.stdout[-300:]}')
    return result.stdout


def candidate_pages_from_seal(path, validation_ids):
    import pyarrow.parquet as parquet
    table = parquet.read_table(path, columns=['query_id', 'page_id'])
    columns = table.to_pydict()
    wanted = set(validation_ids)
    pages = {query_id: [] for query_id in validation_ids}
    for query_id, page_id in zip(columns['query_id'], columns['page_id']):
        if query_id in wanted:
            pages[query_id].append(page_id)
    for query_id, items in pages.items():
        require(items and len(items) == len(set(items)), f'{query_id}: sealed candidates missing/duplicated')
        require(items == sorted(items), f'{query_id}: sealed candidate order differs')
    return pages


def fresh_checkpoint_replay(seal, attempt, config, expected_predictions, summary):
    import torch
    from qpaf.m24.checkpoint import load_checkpoint
    from qpaf.m24.dataset import build_records, read_score_rows, read_split_ids
    from qpaf.m24.evaluator import predict
    from qpaf.m24.trainer import build_model

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    best = load_checkpoint(attempt / 'checkpoints/best.pt', config=config, method='QARF',
                           expected_sha256=summary['checkpoint_sha256']['best'])
    last = load_checkpoint(attempt / 'checkpoints/last.pt', config=config, method='QARF',
                           expected_sha256=summary['checkpoint_sha256']['last'])
    require(best['epoch'] == summary['selected_epoch'], 'best checkpoint epoch differs')
    require(last['epoch'] == config['training']['epochs'], 'last checkpoint epoch differs')
    rows = read_score_rows(seal / 'inputs/score_cache.parquet')
    queries = read(seal / 'inputs/query_texts.json')
    qrels = read(seal / 'inputs/qrels_development.json')
    splits = read_split_ids(seal / 'inputs/splits')
    records = build_records(rows, queries, qrels, splits, ('validation',),
                            positive_threshold=config['data']['positive_threshold'],
                            max_candidates=config['data']['max_candidates'])['validation']
    model = build_model(config, 'QARF')
    model.load_state_dict(best['model_state'])
    replay = predict(model, records, config['training']['batch_size'], config['features']['query_length_cap'])
    require(len(replay) == len(expected_predictions), 'fresh reload query count differs')
    score_max, weight_max = 0.0, 0.0
    for original, fresh in zip(expected_predictions, replay):
        require(original['query_id'] == fresh['query_id'] and original['page_ids'] == fresh['page_ids'],
                'fresh reload query/candidate order differs')
        require(len(original['scores']) == len(fresh['scores']), 'fresh reload score count differs')
        score_max = max(score_max, *(abs(x - y) for x, y in zip(original['scores'], fresh['scores'])))
        original_weights, fresh_weights = original['weights'], fresh['weights']
        require(len(original_weights) == len(fresh_weights), 'fresh reload weight count differs')
        require(all(len(a) == len(b) for a, b in zip(original_weights, fresh_weights)),
                'fresh reload weight dimensions differ')
        weight_max = max(weight_max, *(abs(x - y) for a, b in zip(original_weights, fresh_weights)
                                       for x, y in zip(a, b)))
    tolerance = config['evaluation']['reload_tolerance']
    require(score_max <= tolerance, f'fresh checkpoint reload differs by {score_max} > {tolerance}')
    require(weight_max <= tolerance, f'fresh checkpoint weights differ by {weight_max} > {tolerance}')
    return {'best_epoch': best['epoch'], 'last_epoch': last['epoch'],
            'score_max_abs_difference': score_max, 'weight_max_abs_difference': weight_max,
            'tolerance': tolerance, 'status': 'PASS_FRESH_PROCESS'}


def audit():
    import numpy
    import pandas
    import pyarrow
    import torch
    from qpaf.m24.config import load_config

    require(sha(AUTH_PATH) == AUTH_SHA256, 'authorization pin differs')
    auth = read(AUTH_PATH)
    require(auth['status'] == 'APPROVED' and auth['method']['name'] == 'QARF', 'authorization is not QARF approved')
    versions = {'python': platform.python_version(), 'torch': torch.__version__,
                'numpy': numpy.__version__, 'pandas': pandas.__version__, 'pyarrow': pyarrow.__version__}
    require(all(versions[key] == auth['runtime'][key] for key in versions), 'numerical runtime differs from M3.2 pin')
    seal_pin = ROOT / auth['sealed_inputs']['seal_pin']['path']
    require(sha(seal_pin) == auth['sealed_inputs']['seal_pin']['sha256'], 'seal pin file differs')
    pin = read(seal_pin)
    require(pin['manifest_sha256'] == auth['sealed_inputs']['manifest_sha256'], 'seal manifest pin differs')
    seal = ROOT / auth['sealed_inputs']['run_path']
    seal_output = run_read_only([sys.executable, str(ROOT / 'scripts/seal_m31_inputs.py'),
                                 '--verify', str(seal), '--expected-manifest-sha256', pin['manifest_sha256']])
    require(read(ROOT / 'evidence/revisions/m3.1-001/verification.json')['status'] == 'PASS',
            'M3.1 recorded verification is not PASS')
    seal_replay = json.loads(seal_output)
    require(seal_replay['status'] == 'PASS' and seal_replay['parity_identical'], 'M3.1 replay failed')

    namespace = ROOT / 'results/m3.2' / auth['run_id']
    attempted, success = check_supervisor_markers(namespace, AUTH_SHA256)
    require(success['run_id'] == auth['run_id'], 'success run ID differs from authorization')
    require(success['wall_seconds'] <= auth['limits']['wall_time_seconds'], 'run exceeded wall limit')
    require(sorted(path.name for path in namespace.iterdir()) ==
            ['QARF', '_ATTEMPTED.json', '_SUCCESS.json', 'supervisor.log'], 'unexpected run namespace entry')
    stage = namespace / 'QARF'
    attempts = [path for path in stage.iterdir() if path.is_dir()]
    require(len(attempts) == 1, 'run has multiple/no attempts')
    attempt = attempts[0]
    require(read(stage / 'complete.json') == {'attempt': attempt.name, 'receipt_sha256': success['receipt_sha256']},
            'complete marker differs')
    receipt_count = check_receipt(attempt, success)
    require(sha(attempt / 'summary.json') == success['summary_sha256'], 'summary hash differs')
    predictions_path = attempt / 'validation_predictions.json'
    require(sha(predictions_path) == PREDICTIONS_SHA256, 'prediction handoff hash differs')
    require(read(attempt / 'status.json')['status'] == 'completed', 'runner status is not completed')
    first_pass = run_read_only([sys.executable, str(ROOT / 'evidence/revisions/m3.2-001/post_run_check.py')])
    require(re.search(r"verdict: ALL CHECKS PASS \{'PASS': 30, 'FAIL': 0, 'SKIPPED': 0\}", first_pass),
            'M3.2 first-pass checker no longer reproduces 30/30')
    prior = read(ROOT / 'evidence/revisions/m3.2-001/post_run_verification.json')
    require(prior['counts'] == {'PASS': 30, 'FAIL': 0, 'SKIPPED': 0}, 'committed first-pass report differs')

    config = load_config(seal / 'inputs/shared_base.toml')
    require(sha(seal / 'inputs/shared_base.toml') == auth['config']['file_sha256'], 'config hash differs')
    summary = read(attempt / 'summary.json')
    require(summary['method'] == 'QARF' and summary['granularity'] == 'query' and
            summary['seed'] == auth['method']['seed'] and summary['test_split'] == 'not_opened',
            'summary method/seed/test boundary differs')
    require(summary['validation']['query_count'] == auth['sealed_inputs']['split']['counts']['validation'],
            'validation count differs')
    provenance = read(attempt / 'provenance.json')
    require(provenance['source']['git_commit'] == attempted['git_head'], 'source commit differs')
    require(provenance['config_sha256'] == auth['config']['expected_provenance_config_object_hash'],
            'provenance config digest differs')
    for key, rel in [('config', 'inputs/shared_base.toml'), ('scores', 'inputs/score_cache.parquet'),
                     ('queries', 'inputs/query_texts.json'), ('qrels', 'inputs/qrels_development.json')]:
        require(provenance['inputs'][key] == auth['sealed_inputs']['files_relative_to_run_path'][rel],
                f'provenance {key} input differs from seal')
    for key, filename in [('train_ids.txt', 'train_ids.txt'), ('val_ids.txt', 'val_ids.txt'),
                          ('test_ids.txt', 'test_ids.txt')]:
        require(provenance['inputs']['splits'][key] ==
                auth['sealed_inputs']['files_relative_to_run_path']['inputs/splits/' + filename],
                f'provenance {filename} differs from seal')
    require(summary['experiment_id'] == config['experiment_id'], 'summary differs from frozen config identity')
    identity_note = ('The frozen M2.7 config and summary retain QPAF-M2_7-MTH-001; '
                     'authorization, supervised markers and registry bind the actual M3.2 run as '
                     'QPAF-M3_2-MTH-001. Historical bytes are unchanged.')
    require(auth['experiment_id'] == 'QPAF-M3_2-MTH-001' and
            summary['experiment_id'] == 'QPAF-M2_7-MTH-001', 'unexpected experiment ID mapping')

    validation_ids = (seal / 'inputs/splits/val_ids.txt').read_text(encoding='utf-8').splitlines()
    require(len(validation_ids) == 171, 'validation split count differs')
    candidate_pages = candidate_pages_from_seal(seal / 'inputs/score_cache.parquet', validation_ids)
    predictions = read(predictions_path)
    development_qrels = read(seal / 'inputs/qrels_development.json')
    metrics, per_query = calculate_validation(predictions, development_qrels,
                                               validation_ids, candidate_pages,
                                               threshold=config['data']['positive_threshold'])
    metric_max = compare_reported_metrics(metrics, per_query, attempt)
    reload_result = fresh_checkpoint_replay(seal, attempt, config, predictions, summary)
    return {
        'schema_version': 1,
        'task_id': 'M3.3',
        'owner': 'Thanh',
        'executed_by': 'Codex at Thanh\'s request',
        'checked_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'run_id': auth['run_id'],
        'technical_verdict': 'PASS',
        'owner_acceptance': 'PENDING_THANH_CONFIRMATION',
        'authorization_sha256': AUTH_SHA256,
        'seal_manifest_sha256': pin['manifest_sha256'],
        'prediction_sha256': PREDICTIONS_SHA256,
        'runtime': versions,
        'm3_1_seal_replay': seal_replay,
        'm3_2_first_pass': {'pass': 30, 'fail': 0, 'skipped': 0},
        'receipt_outputs_rehashed': receipt_count,
        'validation_metrics_recomputed': metrics,
        'validation_queries': len(per_query),
        'validation_candidates': sum(row['candidates'] for row in per_query),
        'metric_max_abs_difference': metric_max,
        'fresh_checkpoint_reload': reload_result,
        'provenance_note': identity_note,
        'development_interpretation': ('Selected validation nDCG@10 peaks at epoch 1 and then falls; '
                                       'the selected maximum is optimistic for that same validation split. '
                                       'No cause is inferred and no baseline comparison is claimed.'),
        'test_labels_opened': False,
        'training_executed_by_audit': False,
        'm3_4_execution_authorized': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new create-once JSON report path')
    args = parser.parse_args(argv)
    if args.output is not None and args.output.exists():
        raise AuditError(f'output already exists: {args.output}')
    report = audit()
    if args.output is None:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print(f'M3.3 technical verdict: {report["technical_verdict"]}; written {args.output}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(f'M3.3 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
