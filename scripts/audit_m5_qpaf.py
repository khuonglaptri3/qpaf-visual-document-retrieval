"""Read-only technical audit of an authorized M5.3/M5.4 QPAF seed run.

Requires the M3.1 inputs restored at their sealed paths and the authorized
Python/Torch/NumPy/pandas/PyArrow runtime. Never opens test qrels or trains.
The metric recomputation, receipt and marker checks reuse the independent M3.3
helpers; the checkpoint replay below builds the QPAF model itself.

    python scripts/audit_m5_qpaf.py --task M5.3 --output <new file>
    python scripts/audit_m5_qpaf.py --task M5.3 --verify evidence/revisions/m5.3-r02/validation.json

--verify replays the audit and requires every field to equal the saved report,
except the fresh-reload differences, which must stay within the tolerance (they
differ by ~1e-16 between machines).
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from scripts import audit_m33_qarf as independent  # noqa: E402


TASKS = {
    'M5.3': {'folder': 'm5.3-002', 'seed': 20260821, 'review_id': 'M5.3-QPAF-technical-review',
             'auth_sha': '132a1287c2cd3aeb688399b3fde39a0582bc3d8b53a2b057242df5c9257eaecd',
             'run_id': 'RUN-QPAF-M5_3-MTH-002-20261026T025155Z-A01', 'attempt': '20261026T025443-a29ae705'},
    'M5.4': {'folder': 'm5.4-002', 'seed': 20260822, 'review_id': 'M5.4-QPAF-technical-review',
             'auth_sha': '1d7e64d367a1aa25ae1e7ca8140f61e19d193660a3dfadd294fddec2cf17f845',
             'run_id': 'RUN-QPAF-M5_4-MTH-002-20261026T025155Z-A01', 'attempt': '20261026T025834-242457dc'},
}
SEAL_SHA = '0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893'
SEED1_QARF_ATTEMPT = 'results/m3.2/RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01/QARF/20261022T040759-ff3934df'
QARF_ATTEMPTS = {
    20260821: 'results/m5.3/RUN-QPAF-M5_3-MTH-001-20261025T135954Z-A01/QARF/20261025T140512-0de4dd1d',
    20260822: 'results/m5.4/RUN-QPAF-M5_4-MTH-001-20261025T154818Z-A01/QARF/20261025T155859-f0aefa1c',
}
QPAF_ATTEMPTS = {
    20260821: 'results/m5.3/RUN-QPAF-M5_3-MTH-002-20261026T025155Z-A01/QPAF/20261026T025443-a29ae705',
    20260822: 'results/m5.4/RUN-QPAF-M5_4-MTH-002-20261026T025155Z-A01/QPAF/20261026T025834-242457dc',
}
RELOAD_FIELDS = ('score_max_abs_difference', 'weight_max_abs_difference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def events(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf8').splitlines() if line.strip()]


def run_check(command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf8')
    require(result.returncode == 0,
            f'read-only check failed: {result.stderr.strip() or result.stdout[-500:]}')
    return result.stdout


def epoch_ndcg(attempt):
    with (ROOT / attempt / 'epochs.csv').open(encoding='utf8', newline='') as stream:
        return [float(row['validation_ndcg_at_10']) for row in csv.DictReader(stream)]


def qpaf_replay(seal, attempt, config, expected_predictions, summary):
    """Reload best.pt into a freshly built QPAF model in this process and re-predict validation."""
    import torch
    from qpaf.m24.checkpoint import load_checkpoint
    from qpaf.m24.dataset import build_records, read_score_rows, read_split_ids
    from qpaf.m24.evaluator import predict
    from qpaf.m24.trainer import build_model

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    best = load_checkpoint(attempt / 'checkpoints/best.pt', config=config, method='QPAF',
                           expected_sha256=summary['checkpoint_sha256']['best'])
    last = load_checkpoint(attempt / 'checkpoints/last.pt', config=config, method='QPAF',
                           expected_sha256=summary['checkpoint_sha256']['last'])
    require(best['epoch'] == summary['selected_epoch'], 'best checkpoint epoch differs')
    require(last['epoch'] == config['training']['epochs'], 'last checkpoint epoch differs')
    records = build_records(read_score_rows(seal / 'inputs/score_cache.parquet'),
                            read(seal / 'inputs/query_texts.json'),
                            read(seal / 'inputs/qrels_development.json'),
                            read_split_ids(seal / 'inputs/splits'), ('validation',),
                            positive_threshold=config['data']['positive_threshold'],
                            max_candidates=config['data']['max_candidates'])['validation']
    model = build_model(config, 'QPAF')
    model.load_state_dict(best['model_state'])
    replay = predict(model, records, config['training']['batch_size'],
                     config['features']['query_length_cap'])
    require(len(replay) == len(expected_predictions), 'reload query count differs')
    score_max = weight_max = 0.0
    for original, fresh in zip(expected_predictions, replay):
        require(original['query_id'] == fresh['query_id'] and original['page_ids'] == fresh['page_ids'],
                'reload query/candidate order differs')
        require(len(original['scores']) == len(fresh['scores']) and
                len(original['weights']) == len(fresh['weights']) and
                all(len(a) == len(b) for a, b in zip(original['weights'], fresh['weights'])),
                'reload score or weight dimensions differ')
        score_max = max(score_max, *(abs(a - b) for a, b in zip(original['scores'], fresh['scores'])))
        weight_max = max(weight_max, *(abs(a - b) for row_a, row_b in zip(original['weights'], fresh['weights'])
                                       for a, b in zip(row_a, row_b)))
    tolerance = config['evaluation']['reload_tolerance']
    require(score_max <= tolerance and weight_max <= tolerance,
            f'checkpoint reload differs: scores {score_max}, weights {weight_max} > {tolerance}')
    return {'best_epoch': best['epoch'], 'last_epoch': last['epoch'],
            'score_max_abs_difference': score_max, 'weight_max_abs_difference': weight_max,
            'tolerance': tolerance, 'status': 'PASS_REVIEW_PROCESS_RELOAD'}


def gate_profile(predictions):
    """Page-level gate facts: weights are a probability vector per page and vary within queries."""
    rows = [w for query in predictions for w in query['weights']]
    require(all(len(w) == len(rows[0]) for w in rows), 'gate weight width differs')
    require(all(min(w) >= 0 for w in rows), 'negative gate weight')
    simplex = max(abs(sum(w) - 1) for w in rows)
    require(simplex <= 1e-12, f'gate weights do not sum to 1 (max deviation {simplex})')
    varying = sum(len({tuple(w) for w in query['weights']}) > 1 for query in predictions)
    require(varying > 0, 'QPAF weights are constant within every query (not a page-level gate)')
    return {'weight_width': len(rows[0]), 'max_simplex_deviation': simplex,
            'queries_with_page_varying_weights': varying, 'queries': len(predictions)}


def compare_with_qarf(qarf_attempt, predictions):
    qarf = read(ROOT / qarf_attempt / 'validation_predictions.json')
    require([(row['query_id'], row['page_ids']) for row in qarf] ==
            [(row['query_id'], row['page_ids']) for row in predictions],
            'QPAF and matched QARF predictions rank different candidate pages')
    require(all(len({tuple(w) for w in row['weights']}) == 1 for row in qarf),
            'matched QARF weights are not constant within queries')
    require(any(a['scores'] != b['scores'] for a, b in zip(qarf, predictions)),
            'QPAF scores equal the QARF scores (copied output)')


def audit(task, checked_utc):
    import numpy
    import pandas
    import pyarrow
    import torch
    from qpaf.m24.config import load_config

    spec = TASKS[task]
    folder = ROOT / 'evidence/revisions' / spec['folder']
    auth_path = folder / 'authorization.json'
    require(sha(auth_path) == spec['auth_sha'], f'{task} QPAF authorization hash differs')
    auth = read(auth_path)
    require(auth['status'] == 'APPROVED' and auth['run_id'] == spec['run_id'] and
            auth['task_id'] == task and auth['method'] == {**auth['method'], 'name': 'QPAF',
                                                           'gate_granularity': 'page', 'seed': spec['seed']},
            'authorization scope differs')
    require(not auth['approval']['approval_text'].startswith('PENDING'), 'authorization lacks approval text')
    versions = {'python': platform.python_version(), 'torch': torch.__version__,
                'numpy': numpy.__version__, 'pandas': pandas.__version__,
                'pyarrow': pyarrow.__version__}
    require(all(versions[key] == auth['runtime'][key] for key in versions),
            f'numerical runtime differs from authorization: {versions}')

    contract = auth['seed_contract']
    for name in ('preregistration', 'preregistration_confirmation', 'cache_receipt', 'method_freeze'):
        require(sha(ROOT / contract[name]['path']) == contract[name]['sha256'], f'{name} pin differs')
    frozen = read(ROOT / contract['method_freeze']['path'])
    for rel, digest in frozen['source_sha256'].items():
        require(sha(ROOT / rel) == digest, f'frozen method source differs: {rel}')
    cache = read(ROOT / contract['cache_receipt']['path'])
    require(cache['status'] == 'TECHNICAL_PASS', 'M5.2 cache receipt is not technical PASS')

    # The matched QARF run must be accepted, and this authorization may differ from it only in the method.
    comparator = auth['comparator']
    qarf_auth_path = ROOT / comparator['authorization_path']
    require(sha(qarf_auth_path) == comparator['authorization_sha256'], 'QARF authorization pin differs')
    qarf_auth = read(qarf_auth_path)
    accepted = [event for event in events(ROOT / comparator['acceptance']['events_path'])
                if event.get('registry_event_id') == comparator['acceptance']['registry_event_id']]
    require(len(accepted) == 1 and accepted[0]['event_type'] == 'ACCEPTANCE_RECORDED' and
            accepted[0]['registry_status'] == 'PASS' and accepted[0]['run_id'] == comparator['run_id'] and
            accepted[0]['authorization_manifest_sha256'] == comparator['authorization_sha256'] and
            sha(ROOT / accepted[0]['verification_ref']) == accepted[0]['verification_sha256'] ==
            comparator['acceptance']['review_sha256'] and
            sha(ROOT / accepted[0]['review_signoff_ref']) == accepted[0]['review_signoff_sha256'],
            'matched QARF run lacks its bound independent acceptance')
    for section in ('sealed_inputs', 'config', 'metric', 'runtime', 'hardware'):
        require(auth[section] == qarf_auth[section], f'{section} differs from the matched QARF authorization')
    require({k: v for k, v in contract.items() if k != 'seed_reference'} ==
            {k: v for k, v in qarf_auth['seed_contract'].items() if k != 'seed_reference'},
            'seed_contract differs from the matched QARF authorization')
    qarf_arguments = list(qarf_auth['command']['arguments'])
    qarf_arguments[qarf_arguments.index('--method') + 1] = 'QPAF'
    require(auth['command']['arguments'] == qarf_arguments, 'command differs from QARF beyond --method')
    require(comparator['attempt_path'] == QARF_ATTEMPTS[spec['seed']], 'comparator attempt path differs')

    seal_pin = auth['sealed_inputs']['seal_pin']
    require(sha(ROOT / seal_pin['path']) == seal_pin['sha256'], 'M3.1 seal pin differs')
    require(read(ROOT / seal_pin['path'])['manifest_sha256'] == SEAL_SHA ==
            auth['sealed_inputs']['manifest_sha256'], 'M3.1 seal manifest pin differs')
    seal = ROOT / auth['sealed_inputs']['run_path']
    seal_replay = json.loads(run_check([sys.executable, str(ROOT / 'scripts/seal_m31_inputs.py'),
                                        '--verify', str(seal), '--expected-manifest-sha256', SEAL_SHA]))
    require(seal_replay['status'] == 'PASS' and seal_replay['parity_identical'], 'M3.1 seal replay differs')

    namespace = ROOT / auth['output']['namespace_root'].replace('<run_id>', spec['run_id'])
    attempted, success = independent.check_supervisor_markers(namespace, spec['auth_sha'])
    require(attempted['comparator_run_id'] == comparator['run_id'], '_ATTEMPTED comparator differs')
    require(success['run_id'] == spec['run_id'] and
            success['wall_seconds'] <= auth['limits']['wall_time_seconds'], 'run identity or wall limit differs')
    require(sorted(path.name for path in namespace.iterdir()) ==
            ['QPAF', '_ATTEMPTED.json', '_SUCCESS.json', 'supervisor.log'], 'run namespace has extra files')
    stage = namespace / 'QPAF'
    require([path.name for path in stage.iterdir() if path.is_dir()] == [spec['attempt']],
            'attempt count or ID differs')
    attempt = stage / spec['attempt']
    require(read(stage / 'complete.json') ==
            {'attempt': spec['attempt'], 'receipt_sha256': success['receipt_sha256']}, 'complete marker differs')
    output_count = independent.check_receipt(attempt, success)
    require(sha(attempt / 'summary.json') == success['summary_sha256'], 'summary hash differs')
    require(read(attempt / 'status.json')['status'] == 'completed', 'runner status is not completed')
    require(success['fresh_process_reload']['status'] == 'PASS', 'supervisor fresh-process reload did not pass')

    verified = [event for event in events(folder / 'governance_events.jsonl')
                if event.get('event_type') == 'VERIFICATION_RECORDED' and event.get('run_id') == spec['run_id']]
    require(len(verified) == 1 and
            sha(folder / 'post_run_verification.json') == verified[0]['verification_sha256'],
            'first-pass report differs from its VERIFICATION_RECORDED event')
    saved_first_pass = read(folder / 'post_run_verification.json')
    first_pass_stdout = run_check([sys.executable, str(folder / 'post_run_check.py')])
    replayed = len(re.findall(r'^PASS\s+', first_pass_stdout, re.MULTILINE))
    require(saved_first_pass['counts'] == {'PASS': replayed, 'FAIL': 0} and replayed == 41,
            'first-pass checker no longer reproduces its saved counts')

    config_path = ROOT / auth['config']['path']
    require(sha(config_path) == auth['config']['file_sha256'], 'seed config hash differs')
    original_config = (seal / 'inputs/shared_base.toml').read_bytes()
    require(original_config.count(b'seed = 20260820') == 1 and
            config_path.read_bytes() == original_config.replace(
                b'seed = 20260820', f'seed = {spec["seed"]}'.encode()),
            'seed config differs from the sealed seed-1 bytes beyond training.seed')
    config = load_config(config_path)
    matrix = [row for row in cache['matrix'] if row['method'] == 'QPAF' and row['seed'] == spec['seed']]
    require(len(matrix) == 1 and matrix[0]['config'] == config and matrix[0]['gate_granularity'] == 'page',
            'M5.2 QPAF config matrix differs')
    require(sha(attempt / 'resolved_config.json') == auth['config']['expected_resolved_config_json_sha256'] ==
            sha(ROOT / QARF_ATTEMPTS[spec['seed']] / 'resolved_config.json'),
            'resolved config differs from the authorization or the matched QARF run')

    summary = read(attempt / 'summary.json')
    require(summary['method'] == 'QPAF' and summary['granularity'] == 'page' and
            summary['seed'] == spec['seed'] and summary['test_split'] == 'not_opened' and
            summary['validation']['query_count'] == 171, 'summary method/seed/validation/test scope differs')
    reference = contract['seed_reference']
    require(sha(attempt / 'data_manifest.json') == reference['data_manifest_sha256'] ==
            comparator['data_manifest_sha256'] == sha(ROOT / reference['attempt_path'] / 'data_manifest.json'),
            'data manifest differs from the seed-1 QPAF or matched QARF run')
    provenance = read(attempt / 'provenance.json')
    require(provenance['source']['git_commit'] == attempted['git_head'] and
            provenance['config_sha256'] == auth['config']['expected_provenance_config_object_hash'],
            'provenance source/config differs')
    require(provenance['inputs'] == read(ROOT / QARF_ATTEMPTS[spec['seed']] / 'provenance.json')['inputs'] ==
            {**read(ROOT / reference['attempt_path'] / 'provenance.json')['inputs'],
             'config': auth['config']['file_sha256']},
            'input provenance differs from the matched QARF run or the seed-1 QPAF run')

    validation_ids = (seal / 'inputs/splits/val_ids.txt').read_text(encoding='utf8').splitlines()
    require(len(validation_ids) == 171, 'validation split size differs')
    candidate_pages = independent.candidate_pages_from_seal(seal / 'inputs/score_cache.parquet', validation_ids)
    predictions = read(attempt / 'validation_predictions.json')
    metrics, per_query = independent.calculate_validation(
        predictions, read(seal / 'inputs/qrels_development.json'), validation_ids, candidate_pages,
        threshold=config['data']['positive_threshold'])
    metric_max = independent.compare_reported_metrics(metrics, per_query, attempt)
    compare_with_qarf(QARF_ATTEMPTS[spec['seed']], predictions)
    gate = gate_profile(predictions)
    reload_result = qpaf_replay(seal, attempt, config, predictions, summary)
    ndcg = epoch_ndcg(QPAF_ATTEMPTS[spec['seed']])
    require(summary['selected_epoch'] == ndcg.index(max(ndcg)) + 1, 'selected epoch is not the earliest maximum')

    seed1_qpaf_attempt = reference['attempt_path']
    observation = {
        'selected_epoch_by_seed': {
            'QARF': {'20260820': read(ROOT / SEED1_QARF_ATTEMPT / 'summary.json')['selected_epoch'],
                     **{str(seed): read(ROOT / path / 'summary.json')['selected_epoch']
                        for seed, path in QARF_ATTEMPTS.items() if seed <= spec['seed']}},
            'QPAF': {'20260820': read(ROOT / seed1_qpaf_attempt / 'summary.json')['selected_epoch'],
                     **{str(seed): read(ROOT / path / 'summary.json')['selected_epoch']
                        for seed, path in QPAF_ATTEMPTS.items() if seed <= spec['seed']}},
        },
        'qarf_epochs_2_to_20_equal_across_seeds': all(
            epoch_ndcg(SEED1_QARF_ATTEMPT)[1:] == epoch_ndcg(path)[1:]
            for seed, path in QARF_ATTEMPTS.items() if seed <= spec['seed']),
        'interpretation': ('Descriptive validation observation only; selected values are validation maxima. '
                           'Paired QPAF-versus-QARF and seed aggregation belong to M5.7.'),
    }
    return {
        'schema_version': 1, 'task_id': spec['review_id'],
        'owner': 'Thanh',
        'technical_reviewer': ("Claude Code at Thanh's request, relayed by Tấn Phát; the same assistant that "
                               'drafted the authorization, executed the run and wrote the first-pass check'),
        'independence_note': ('Not an independent replay by a separate reviewer: the metric, receipt and marker '
                              'checks reuse the M3.3 helpers Thanh wrote, but the QPAF reload, gate checks and '
                              'this report were written by the executor\'s assistant. Thanh\'s acceptance '
                              'must be his own explicit confirmation.'),
        'checked_utc': checked_utc, 'technical_verdict': 'PASS',
        'owner_acceptance': 'PENDING_THANH_CONFIRMATION',
        'run_id': spec['run_id'], 'attempt_id': spec['attempt'],
        'authorization_sha256': spec['auth_sha'], 'seal_manifest_sha256': SEAL_SHA,
        'prediction_sha256': sha(attempt / 'validation_predictions.json'), 'runtime': versions,
        'matched_qarf': {'run_id': comparator['run_id'], 'acceptance_event_id': accepted[0]['registry_event_id'],
                         'review_sha256': accepted[0]['verification_sha256']},
        'm3_1_seal_replay': seal_replay,
        'first_pass': {'pass': replayed, 'fail': 0},
        'receipt_outputs_rehashed': output_count,
        'validation_metrics_recomputed': metrics,
        'validation_queries': len(per_query),
        'validation_candidates': sum(row['candidates'] for row in per_query),
        'metric_max_abs_difference': metric_max,
        'checkpoint_reload': reload_result,
        'page_level_gate': gate,
        'seed_observation': observation,
        'limitations': [
            f'Selected epoch {summary["selected_epoch"]} is the maximum on the same validation split; this is not a test estimate.',
            'M5.2 cache-parity receipt is technical PASS; its human acceptance remains pending.',
            'The frozen config and summary retain the M2.7 experiment_id; authorization and registry bind this run separately.',
            'No seed-averaged, QPAF-versus-QARF or baseline improvement claim is made.',
        ],
        'test_labels_deserialized': False,
        'training_executed_by_review': False,
    }


def same_report(saved, replayed):
    """Equal in every field, except reload differences, which only need to stay within the tolerance."""
    saved, replayed = json.loads(json.dumps(saved)), json.loads(json.dumps(replayed))
    for report in (saved, replayed):
        reload = report['checkpoint_reload']
        if any(reload[field] > reload['tolerance'] for field in RELOAD_FIELDS):
            return False
        for field in RELOAD_FIELDS:
            reload[field] = 'within_tolerance'
    return saved == replayed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--task', choices=sorted(TASKS), required=True)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--output', type=Path)
    actions.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.output is not None:
        require(not args.output.exists(), 'technical review output already exists')
    previous = read(args.verify) if args.verify else None
    timestamp = (previous['checked_utc'] if previous else
                 datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'))
    report = audit(args.task, timestamp)
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')
    if args.verify:
        require(same_report(previous, report), 'saved technical review differs from replay')
        print(f'{args.task} QPAF technical review: PASS')
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
        print(f'{args.task} QPAF technical review created: {args.output}')
    else:
        print(encoded.decode('utf8'))


if __name__ == '__main__':
    try:
        main()
    except (KeyError, OSError, ValueError) as exc:
        raise SystemExit(f'QPAF review refused: {exc}')
