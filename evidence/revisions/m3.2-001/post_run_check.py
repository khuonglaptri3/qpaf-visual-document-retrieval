"""Read-only integrity check of the finished M3.2 run against its committed authorization.

Run from anywhere with any Python 3.11+ (standard library only):
    python evidence/revisions/m3.2-001/post_run_check.py [--write]
--write stores the results next to this file as post_run_verification.json (create-once).
This is the first-pass check by the executor; independent validation is M3.3.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
results = []


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def check(name, passed, detail=''):
    results.append({'check': name, 'status': 'PASS' if passed else 'FAIL', 'detail': str(detail)})


def skipped(name, detail):
    results.append({'check': name, 'status': 'SKIPPED', 'detail': detail})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    auth_path = HERE/'authorization.json'
    auth = read(auth_path)
    pin = sha(auth_path)
    namespace = REPO/'results/m3.2'/auth['run_id']
    stage = namespace/auth['method']['name']
    attempts = [p for p in stage.iterdir() if p.is_dir()]
    check('exactly one attempt directory', len(attempts) == 1, [p.name for p in attempts])
    attempt = attempts[0]
    attempted, success = read(namespace/'_ATTEMPTED.json'), read(namespace/'_SUCCESS.json')
    check('_ATTEMPTED and _SUCCESS bind the authorization file hash', attempted['authorization_sha256'] == pin == success['authorization_sha256'])
    check('exactly one final marker and it is _SUCCESS', (namespace/'_SUCCESS.json').exists() and not (namespace/'_FAILED.json').exists())
    check('namespace holds only the expected entries', sorted(p.name for p in namespace.iterdir()) == ['QARF', '_ATTEMPTED.json', '_SUCCESS.json', 'supervisor.log'])
    check('finished within the authorized wall limit', success['wall_seconds'] < auth['limits']['wall_time_seconds'], f"{success['wall_seconds']} s")
    check('_SUCCESS receipt/summary hashes match the files', success['receipt_sha256'] == sha(attempt/'receipt.json') and success['summary_sha256'] == sha(attempt/'summary.json'))
    check('complete.json points at the attempt and its receipt', read(stage/'complete.json') == {'attempt': attempt.name, 'receipt_sha256': sha(attempt/'receipt.json')})

    receipt = read(attempt/'receipt.json')
    listed = {o['path'] for o in receipt['outputs']}
    local = {p.relative_to(attempt).as_posix() for p in attempt.rglob('*') if p.is_file()}
    absent = sorted(listed - local)
    changed = sorted(o['path'] for o in receipt['outputs'] if (attempt/o['path']).is_file() and sha(attempt/o['path']) != o['sha256'])
    check('every receipt output that is present re-hashes identically', not changed, changed)
    only_local = sorted(local - listed - {'receipt.json'})
    check('no file in the attempt is missing from the receipt (receipt.json cannot list itself)', not only_local, only_local)
    for path in absent:
        skipped(f'receipt output not present locally: {path}', 'kept outside git; compare its SHA-256 with the receipt entry before use')

    summary = read(attempt/'summary.json')
    for kind, rel in (('best', 'checkpoints/best.pt'), ('last', 'checkpoints/last.pt')):
        check(f'{kind} checkpoint hash in summary matches the file', summary['checkpoint_sha256'][kind] == sha(attempt/rel))
    config = auth['config']
    check('resolved_config.json equals the authorized expectation', sha(attempt/'resolved_config.json') == config['expected_resolved_config_json_sha256'])
    provenance = read(attempt/'provenance.json')
    check('provenance config hash equals the authorized expectation', provenance['config_sha256'] == config['expected_provenance_config_object_hash'])
    check('provenance git commit equals the supervised HEAD', provenance['source']['git_commit'] == attempted['git_head'])
    inputs = json.dumps(provenance['inputs'])
    files = auth['sealed_inputs']['files_relative_to_run_path']
    for label, rel in (('scores', 'inputs/score_cache.parquet'), ('queries', 'inputs/query_texts.json'), ('development qrels', 'inputs/qrels_development.json'),
                       ('train ids', 'inputs/splits/train_ids.txt'), ('validation ids', 'inputs/splits/val_ids.txt'), ('test ids', 'inputs/splits/test_ids.txt')):
        check(f'the run consumed the sealed {label}', files[rel] in inputs)
    check('the sealed test qrels were not a run input', auth['sealed_inputs']['sealed_not_to_be_opened']['inputs/qrels_test_sealed.json'] not in inputs)
    check('method, granularity and torch match the authorization', (summary['method'], summary['granularity'], summary['torch']) == (auth['method']['name'], auth['method']['gate_granularity'], auth['runtime']['torch']))

    manifest = read(attempt/'data_manifest.json')
    check('test split was not opened', manifest['test'] == {'queries': 172, 'state': 'not_opened'} and summary['test_split'] == 'not_opened')
    check('train/validation sizes and candidate recall as sealed', (manifest['train']['queries'], manifest['validation']['queries'], manifest['train']['candidate_recall'], manifest['validation']['candidate_recall']) == (799, 171, 1.0, 1.0))
    check('checkpoint reload parity passed within tolerance', summary['reload_parity']['passed'] is True and summary['reload_parity']['max_abs_difference'] <= 1e-7)
    rows = list(csv.DictReader(open(attempt/'epochs.csv', encoding='utf-8')))
    check('20 epochs, 50 steps each, no skipped queries', len(rows) == 20 and all(r['train_steps'] == '50' and r['train_skipped_queries'] == '0' for r in rows))
    check('all epoch losses and metrics are finite', all(math.isfinite(float(v)) for r in rows for k, v in r.items() if k != 'selected'))
    metric = [float(r['validation_ndcg_at_10']) for r in rows]
    check('selected epoch is the earliest maximum of validation nDCG@10', summary['selected_epoch'] == metric.index(max(metric))+1, f"epoch {summary['selected_epoch']}")
    check('per-query file has one row per validation query', len(list(csv.DictReader(open(attempt/'validation_per_query.csv', encoding='utf-8')))) == 171)
    predictions = attempt/'validation_predictions.json'
    if predictions.is_file():
        scores = [x for q in read(predictions) for x in q['scores']]
        check('predictions cover 171 queries with finite scores', len(read(predictions)) == 171 and all(math.isfinite(x) for x in scores), f'{len(scores)} scores')
    else:
        skipped('predictions are finite', 'validation_predictions.json is kept outside git and is not present here')

    observations = {
        'validation_ndcg_at_10_by_epoch': metric,
        'selected_epoch': summary['selected_epoch'],
        'first_epoch_value': metric[0], 'last_epoch_value': metric[-1],
        'train_loss_first_to_last': [float(rows[0]['train_loss']), float(rows[-1]['train_loss'])],
        'note': 'Facts read from epochs.csv; no interpretation is recorded here.'}
    failed = [r['check'] for r in results if r['status'] == 'FAIL']
    report = {'run_id': auth['run_id'], 'authorization_sha256': pin, 'checked_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
              'checker': 'executor first-pass check (AI-assisted); not independent validation, which is M3.3',
              'verdict': 'ALL CHECKS PASS' if not failed else 'FAILED', 'failed': failed,
              'counts': {s: sum(r['status'] == s for r in results) for s in ('PASS', 'FAIL', 'SKIPPED')},
              'checks': results, 'observations': observations}
    for r in results:
        print(f"{r['status']:7} {r['check']}" + (f"  [{r['detail']}]" if r['detail'] and r['status'] != 'PASS' else ''))
    print('\nverdict:', report['verdict'], report['counts'])
    if args.write:
        with (HERE/'post_run_verification.json').open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print('written:', HERE/'post_run_verification.json')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
