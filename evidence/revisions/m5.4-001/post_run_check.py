"""Read-only first-pass check of the finished M5.4 QARF seed-3 run against its authorization and the seed-1 run.

Run from anywhere with any Python 3.11+ (standard library only):
    python evidence/revisions/m5.4-001/post_run_check.py [--write]
--write stores the results next to this file as post_run_verification.json (create-once).
This is the executor's check; the independent seed-3 QARF review is separate and gates the matched QPAF run.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
results = []


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with open(path, encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def check(name, passed, detail=''):
    results.append({'check': name, 'status': 'PASS' if passed else 'FAIL', 'detail': str(detail)})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    auth_path = HERE/'authorization.json'
    auth, pin = read(auth_path), sha(auth_path)
    namespace = REPO/'results/m5.4'/auth['run_id']
    stage = namespace/auth['method']['name']
    attempts = [p for p in stage.iterdir() if p.is_dir()]
    check('exactly one attempt directory', len(attempts) == 1, [p.name for p in attempts])
    attempt = attempts[0]
    attempted, success = read(namespace/'_ATTEMPTED.json'), read(namespace/'_SUCCESS.json')
    check('_ATTEMPTED and _SUCCESS bind the authorization file hash', attempted['authorization_sha256'] == pin == success['authorization_sha256'])
    check('exactly one final marker and it is _SUCCESS', not (namespace/'_FAILED.json').exists())
    check('namespace holds only the expected entries', sorted(p.name for p in namespace.iterdir()) == ['QARF', '_ATTEMPTED.json', '_SUCCESS.json', 'supervisor.log'])
    check('finished within the authorized wall limit', success['wall_seconds'] < auth['limits']['wall_time_seconds'], f"{success['wall_seconds']} s")
    check('_SUCCESS receipt/summary hashes match the files', success['receipt_sha256'] == sha(attempt/'receipt.json') and success['summary_sha256'] == sha(attempt/'summary.json'))
    check('complete.json points at the attempt and its receipt', read(stage/'complete.json') == {'attempt': attempt.name, 'receipt_sha256': sha(attempt/'receipt.json')})

    receipt = read(attempt/'receipt.json')
    listed = {o['path'] for o in receipt['outputs']}
    local = {p.relative_to(attempt).as_posix() for p in attempt.rglob('*') if p.is_file()}
    changed = sorted(o['path'] for o in receipt['outputs'] if not (attempt/o['path']).is_file() or sha(attempt/o['path']) != o['sha256'])
    check('every receipt output is present and re-hashes identically', not changed, changed)
    check('no file in the attempt is missing from the receipt (receipt.json cannot list itself)', local - listed == {'receipt.json'}, sorted(local - listed))

    summary = read(attempt/'summary.json')
    for kind in ('best', 'last'):
        check(f'{kind} checkpoint hash in summary matches the file', summary['checkpoint_sha256'][kind] == sha(attempt/f'checkpoints/{kind}.pt'))
    config = auth['config']
    check('the seed config file still matches its pin', sha(REPO/config['path']) == config['file_sha256'])
    check('resolved_config.json equals the authorized expectation', sha(attempt/'resolved_config.json') == config['expected_resolved_config_json_sha256'])
    provenance = read(attempt/'provenance.json')
    check('provenance config hash equals the authorized expectation', provenance['config_sha256'] == config['expected_provenance_config_object_hash'])
    check('provenance git commit equals the supervised HEAD', provenance['source']['git_commit'] == attempted['git_head'])
    check('summary names QARF, query granularity, seed 20260822 and the pinned torch',
          (summary['method'], summary['granularity'], summary['seed'], summary['torch']) == ('QARF', 'query', 20260822, auth['runtime']['torch']))
    sealed = auth['sealed_inputs']['files_relative_to_run_path']
    check('the run consumed the sealed scores, queries, development qrels and splits',
          (provenance['inputs']['scores'], provenance['inputs']['queries'], provenance['inputs']['qrels'], provenance['inputs']['splits']) ==
          (sealed['inputs/score_cache.parquet'], sealed['inputs/query_texts.json'], sealed['inputs/qrels_development.json'],
           {name: sealed['inputs/splits/'+name] for name in ('train_ids.txt', 'val_ids.txt', 'test_ids.txt')}))
    check('the sealed test qrels were not a run input', auth['sealed_inputs']['sealed_not_to_be_opened']['inputs/qrels_test_sealed.json'] not in json.dumps(provenance['inputs']))

    manifest = read(attempt/'data_manifest.json')
    check('test split was not opened', manifest['test'] == {'queries': 172, 'state': 'not_opened'} and summary['test_split'] == 'not_opened')
    check('train/validation sizes and candidate recall as sealed', (manifest['train']['queries'], manifest['validation']['queries'], manifest['train']['candidate_recall'], manifest['validation']['candidate_recall']) == (799, 171, 1.0, 1.0))
    check('in-process reload parity passed within tolerance', summary['reload_parity']['passed'] is True and summary['reload_parity']['max_abs_difference'] <= 1e-7)
    fresh = success['fresh_process_reload']
    check('fresh-process reload passed in a separate interpreter within 1e-7', fresh['status'] == 'PASS' and fresh['tolerance'] == 1e-7 and
          max(fresh['score_max_abs_difference'], fresh['weight_max_abs_difference'], fresh['metric_max_abs_difference']) <= 1e-7 and
          fresh['queries'] == 171, {k: fresh[k] for k in ('score_max_abs_difference', 'weight_max_abs_difference', 'metric_max_abs_difference')})
    check('fresh-process reload loaded the checkpoints named in the summary', fresh['checkpoint_sha256'] == summary['checkpoint_sha256'])
    epochs = rows(attempt/'epochs.csv')
    check('20 epochs, 50 steps each, no skipped queries', len(epochs) == 20 and all(r['train_steps'] == '50' and r['train_skipped_queries'] == '0' for r in epochs))
    check('all epoch losses and metrics are finite', all(math.isfinite(float(v)) for r in epochs for k, v in r.items() if k != 'selected'))
    check('all step losses and gradient norms are finite', all(math.isfinite(float(r[k])) for r in rows(attempt/'steps.csv') for k in ('loss', 'grad_norm')))
    metric = [float(r['validation_ndcg_at_10']) for r in epochs]
    check('selected epoch is the earliest maximum of validation nDCG@10', summary['selected_epoch'] == metric.index(max(metric))+1, f"epoch {summary['selected_epoch']}")
    predictions = read(attempt/'validation_predictions.json')
    check('predictions cover 171 queries with finite scores and weights', len(predictions) == 171 and all(
        math.isfinite(x) for q in predictions for x in [*q['scores'], *(w for row in q['weights'] for w in row)]))
    check('QARF fusion weights are constant within every query (query-level gate)', all(len({tuple(w) for w in q['weights']}) == 1 for q in predictions))

    reference = auth['seed_contract']['seed_reference']
    seed1 = REPO/reference['attempt_path']
    check('data_manifest.json is byte-identical to the seed-1 QARF run (rows, order, counts)', sha(attempt/'data_manifest.json') == reference['data_manifest_sha256'] == sha(seed1/'data_manifest.json'))
    check('provenance inputs equal the seed-1 inputs except the config hash', provenance['inputs'] == {**read(seed1/'provenance.json')['inputs'], 'config': config['file_sha256']})
    first_config, second_config = read(seed1/'resolved_config.json'), read(attempt/'resolved_config.json')
    check('resolved config differs from seed 1 only in training.seed', first_config['training'].pop('seed') == 20260820 and
          second_config['training'].pop('seed') == 20260822 and first_config == second_config)
    first = read(seed1/'summary.json')
    check('same epochs and parameter count as seed 1', (summary['epochs'], summary['parameter_count']) == (first['epochs'], first['parameter_count']))
    check('per-query rows list the same validation queries in the same order as seed 1', [r['query_id'] for r in rows(attempt/'validation_per_query.csv')] == [r['query_id'] for r in rows(seed1/'validation_per_query.csv')])
    check('predictions rank exactly the seed-1 candidate pages per query', [(q['query_id'], q['page_ids']) for q in predictions] == [(q['query_id'], q['page_ids']) for q in read(seed1/'validation_predictions.json')])

    observations = {
        'validation_ndcg_at_10_by_epoch': metric, 'selected_epoch': summary['selected_epoch'],
        'seed1_selected_epoch': first['selected_epoch'], 'seed1_validation_ndcg_at_10': first['validation']['ndcg_at_10'],
        'validation': summary['validation'], 'train_loss_first_to_last': [float(epochs[0]['train_loss']), float(epochs[-1]['train_loss'])],
        'wall_seconds': success['wall_seconds'], 'peak_rss_mb': read(attempt/'telemetry.json')['peak_rss_mb'],
        'seed2_validation_ndcg_at_10_by_epoch': (seed2 := [float(r['validation_ndcg_at_10']) for r in rows(
            REPO/'results/m5.3/RUN-QPAF-M5_3-MTH-001-20261025T135954Z-A01/QARF/20261025T140512-0de4dd1d/epochs.csv')]),
        'epochs_equal_to_seed2': [i+1 for i, (a, b) in enumerate(zip(metric, seed2)) if a == b],
        'note': 'Facts read from the run files; no interpretation and no seed comparison claim is recorded here.'}
    failed = [r['check'] for r in results if r['status'] == 'FAIL']
    report = {'run_id': auth['run_id'], 'authorization_sha256': pin, 'checked_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
              'checker': 'executor first-pass check (AI-assisted); not the independent seed-3 QARF review',
              'verdict': 'ALL CHECKS PASS' if not failed else 'FAILED', 'failed': failed,
              'counts': {s: sum(r['status'] == s for r in results) for s in ('PASS', 'FAIL')},
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
