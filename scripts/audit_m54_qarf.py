"""Independent read-only audit of the authorized M5.4 QARF seed-3 run.

Requires the M3.1 inputs restored at their sealed paths and the authorized
Python/Torch/NumPy/pandas/PyArrow runtime. Never opens test qrels or trains.
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


AUTH_REL = 'evidence/revisions/m5.4-001/authorization.json'
AUTH_SHA = 'b3bd04004bf8503aca6d703f20d3405738e50aa41028bc3ce699cd2a540173f9'
RUN_ID = 'RUN-QPAF-M5_4-MTH-001-20261025T154818Z-A01'
ATTEMPT_ID = '20261025T155859-f0aefa1c'
SEAL_SHA = '0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893'
FIRST_PASS_SHA = 'dbadec1283f79c984bcbecd5dd0369ee7c037486caeaf44c17f682c7c071802c'
PREDICTIONS_SHA = '43e05c4b12bf4bed1f45f72a940d94e3f09375f9774c7415d8b9ea0e8e6c1e9d'
SEED2_REVIEW_SHA = 'd3061e42be7537f23a9dfb0323e717ed115c10fbc7e21fedd2674225abf0d22f'


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


def run_check(command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf8')
    require(result.returncode == 0,
            f'read-only check failed: {result.stderr.strip() or result.stdout[-500:]}')
    return result.stdout


def observe_seed2(seed3_attempt, seed3_predictions):
    seed2_attempt = (ROOT / 'results/m5.3/RUN-QPAF-M5_3-MTH-001-20261025T135954Z-A01'
                     / 'QARF/20261025T140512-0de4dd1d')
    seed2_predictions = read(seed2_attempt / 'validation_predictions.json')
    require(len(seed2_predictions) == len(seed3_predictions) == 171,
            'seed-2/seed-3 prediction count differs')
    score_max = weight_max = 0.0
    same_top10 = 0
    for earlier, later in zip(seed2_predictions, seed3_predictions):
        require(earlier['query_id'] == later['query_id'] and
                earlier['page_ids'] == later['page_ids'],
                'seed-2/seed-3 query or candidate pages differ')
        require(len(earlier['scores']) == len(later['scores']) ==
                len(earlier['page_ids']) and
                len(earlier['weights']) == len(later['weights']) ==
                len(earlier['page_ids']) and
                all(len(a) == len(b) for a, b in zip(
                    earlier['weights'], later['weights'])),
                'seed-2/seed-3 score or weight dimensions differ')
        score_max = max(score_max, *(abs(a - b) for a, b in zip(
            earlier['scores'], later['scores'])))
        weight_max = max(weight_max, *(abs(a - b) for row_a, row_b in zip(
            earlier['weights'], later['weights']) for a, b in zip(row_a, row_b)))
        def top10(row):
            return tuple(row['page_ids'][index] for index in sorted(
                range(len(row['page_ids'])),
                key=lambda index: (-row['scores'][index], row['page_ids'][index]))[:10])
        same_top10 += top10(earlier) == top10(later)
    require(score_max > 0 and weight_max > 0,
            'seed-3 predictions or weights appear copied from seed 2')
    def epoch_ndcg(attempt):
        with (attempt / 'epochs.csv').open(encoding='utf8', newline='') as stream:
            return [float(row['validation_ndcg_at_10']) for row in csv.DictReader(stream)]
    earlier_epochs, later_epochs = epoch_ndcg(seed2_attempt), epoch_ndcg(seed3_attempt)
    require(len(earlier_epochs) == len(later_epochs) == 20, 'epoch count differs')
    return {
        'seed2_review_sha256': SEED2_REVIEW_SHA,
        'max_score_difference': score_max,
        'max_weight_difference': weight_max,
        'same_ordered_top10_queries': same_top10,
        'equal_ndcg_epoch_numbers': [index + 1 for index, (a, b) in
                                     enumerate(zip(earlier_epochs, later_epochs)) if a == b],
        'interpretation': 'Descriptive validation observation only; aggregation belongs to M5.7.',
    }


def audit(checked_utc):
    import numpy
    import pandas
    import pyarrow
    import torch
    from qpaf.m24.config import load_config

    auth_path = ROOT / AUTH_REL
    require(sha(auth_path) == AUTH_SHA, 'M5.4 authorization hash differs')
    auth = read(auth_path)
    require(auth['status'] == 'APPROVED' and auth['run_id'] == RUN_ID and
            auth['method']['name'] == 'QARF' and auth['method']['seed'] == 20260822 and
            auth['method']['gate_granularity'] == 'query', 'authorization scope differs')
    versions = {'python': platform.python_version(), 'torch': torch.__version__,
                'numpy': numpy.__version__, 'pandas': pandas.__version__,
                'pyarrow': pyarrow.__version__}
    require(all(versions[key] == auth['runtime'][key] for key in versions),
            f'numerical runtime differs from authorization: {versions}')

    for name in ('preregistration', 'preregistration_confirmation', 'cache_receipt',
                 'method_freeze'):
        item = auth['seed_contract'][name]
        require(sha(ROOT / item['path']) == item['sha256'], f'{name} pin differs')
    frozen = read(ROOT / auth['seed_contract']['method_freeze']['path'])
    for rel, digest in frozen['source_sha256'].items():
        require(sha(ROOT / rel) == digest, f'frozen method source differs: {rel}')
    cache = read(ROOT / auth['seed_contract']['cache_receipt']['path'])
    require(cache['status'] == 'TECHNICAL_PASS', 'M5.2 cache receipt is not technical PASS')
    seed2_events = [json.loads(line) for line in (ROOT /
                    'evidence/revisions/m5.3-001/governance_events.jsonl').read_text(
                        encoding='utf8').splitlines()]
    accepted_seed2 = [event for event in seed2_events if
                      event.get('registry_status') == 'PASS' and
                      event.get('event_type') == 'ACCEPTANCE_RECORDED' and
                      event.get('verification_sha256') == SEED2_REVIEW_SHA]
    require(len(accepted_seed2) == 1 and sha(ROOT / accepted_seed2[0]['verification_ref']) ==
            SEED2_REVIEW_SHA and sha(ROOT / accepted_seed2[0]['review_signoff_ref']) ==
            accepted_seed2[0]['review_signoff_sha256'],
            'accepted independent seed-2 QARF review is missing or unbound')

    seal_pin = auth['sealed_inputs']['seal_pin']
    require(sha(ROOT / seal_pin['path']) == seal_pin['sha256'], 'M3.1 seal pin differs')
    require(read(ROOT / seal_pin['path'])['manifest_sha256'] == SEAL_SHA ==
            auth['sealed_inputs']['manifest_sha256'], 'M3.1 seal manifest pin differs')
    seal = ROOT / auth['sealed_inputs']['run_path']
    seal_output = run_check([sys.executable, str(ROOT / 'scripts/seal_m31_inputs.py'),
                             '--verify', str(seal), '--expected-manifest-sha256', SEAL_SHA])
    seal_replay = json.loads(seal_output)
    require(seal_replay['status'] == 'PASS' and seal_replay['parity_identical'],
            'M3.1 seal replay differs')

    namespace = ROOT / 'results/m5.4' / RUN_ID
    attempted, success = independent.check_supervisor_markers(namespace, AUTH_SHA)
    require(success['run_id'] == RUN_ID and success['wall_seconds'] <=
            auth['limits']['wall_time_seconds'], 'run identity or wall limit differs')
    require(sorted(path.name for path in namespace.iterdir()) ==
            ['QARF', '_ATTEMPTED.json', '_SUCCESS.json', 'supervisor.log'],
            'run namespace has missing or extra files')
    stage = namespace / 'QARF'
    require([path.name for path in stage.iterdir() if path.is_dir()] == [ATTEMPT_ID],
            'attempt count or ID differs')
    attempt = stage / ATTEMPT_ID
    require(read(stage / 'complete.json') ==
            {'attempt': ATTEMPT_ID, 'receipt_sha256': success['receipt_sha256']},
            'complete marker differs')
    output_count = independent.check_receipt(attempt, success)
    require(sha(attempt / 'summary.json') == success['summary_sha256'],
            'summary hash differs')
    require(sha(attempt / 'validation_predictions.json') == PREDICTIONS_SHA,
            'saved predictions hash differs')
    require(read(attempt / 'status.json')['status'] == 'completed',
            'runner status is not completed')

    saved_first_pass = ROOT / 'evidence/revisions/m5.4-001/post_run_verification.json'
    require(sha(saved_first_pass) == FIRST_PASS_SHA and
            read(saved_first_pass)['counts'] == {'PASS': 35, 'FAIL': 0},
            'committed first-pass report differs')
    first_pass_stdout = run_check([sys.executable,
                                   str(ROOT / 'evidence/revisions/m5.4-001/post_run_check.py')])
    require(len(re.findall(r'^PASS\s+', first_pass_stdout, re.MULTILINE)) == 35,
            'M5.4 first-pass checker no longer reproduces 35 checks')

    config_path = ROOT / auth['config']['path']
    require(sha(config_path) == auth['config']['file_sha256'], 'seed-3 config hash differs')
    original_config = (seal / 'inputs/shared_base.toml').read_bytes()
    require(original_config.count(b'seed = 20260820') == 1 and
            config_path.read_bytes() == original_config.replace(
                b'seed = 20260820', b'seed = 20260822'),
            'seed-3 config differs from sealed seed-1 bytes beyond training.seed')
    config = load_config(config_path)
    require(config['training']['seed'] == 20260822, 'loaded config seed differs')
    matrix = [row for row in cache['matrix']
              if row['method'] == 'QARF' and row['seed'] == 20260822]
    require(len(matrix) == 1 and matrix[0]['config'] == config,
            'M5.2 seed-3 QARF config matrix differs')
    require(sha(attempt / 'resolved_config.json') ==
            auth['config']['expected_resolved_config_json_sha256'],
            'resolved config hash differs')

    summary = read(attempt / 'summary.json')
    require(summary['method'] == 'QARF' and summary['granularity'] == 'query' and
            summary['seed'] == 20260822 and summary['test_split'] == 'not_opened' and
            summary['validation']['query_count'] == 171,
            'summary method/seed/validation/test scope differs')
    require(sha(attempt / 'data_manifest.json') ==
            auth['seed_contract']['seed_reference']['data_manifest_sha256'],
            'seed-2 data manifest differs from seed 1')
    provenance = read(attempt / 'provenance.json')
    require(provenance['source']['git_commit'] == attempted['git_head'] and
            provenance['config_sha256'] ==
            auth['config']['expected_provenance_config_object_hash'],
            'provenance source/config differs')
    reference = ROOT / auth['seed_contract']['seed_reference']['attempt_path']
    require(provenance['inputs'] ==
            {**read(reference / 'provenance.json')['inputs'],
             'config': auth['config']['file_sha256']},
            'seed-2 input provenance differs from seed 1 beyond config')

    validation_ids = (seal / 'inputs/splits/val_ids.txt').read_text(
        encoding='utf8').splitlines()
    require(len(validation_ids) == 171, 'validation split size differs')
    candidate_pages = independent.candidate_pages_from_seal(
        seal / 'inputs/score_cache.parquet', validation_ids)
    predictions = read(attempt / 'validation_predictions.json')
    require([(row['query_id'], row['page_ids']) for row in predictions] ==
            [(row['query_id'], row['page_ids']) for row in
             read(reference / 'validation_predictions.json')],
            'seed-2 query/candidate pages differ from seed 1')
    development_qrels = read(seal / 'inputs/qrels_development.json')
    metrics, per_query = independent.calculate_validation(
        predictions, development_qrels, validation_ids, candidate_pages,
        threshold=config['data']['positive_threshold'])
    metric_max = independent.compare_reported_metrics(metrics, per_query, attempt)
    reload_result = independent.fresh_checkpoint_replay(
        seal, attempt, config, predictions, summary)
    seed2_observation = observe_seed2(attempt, predictions)

    return {
        'schema_version': 1, 'task_id': 'M5.4-QARF-independent-review',
        'owner': 'Thanh', 'technical_reviewer': 'Codex at Thanh request',
        'checked_utc': checked_utc, 'technical_verdict': 'PASS',
        'owner_acceptance': 'PENDING_THANH_CONFIRMATION',
        'run_id': RUN_ID, 'attempt_id': ATTEMPT_ID,
        'authorization_sha256': AUTH_SHA, 'seal_manifest_sha256': SEAL_SHA,
        'prediction_sha256': PREDICTIONS_SHA, 'runtime': versions,
        'm3_1_seal_replay': seal_replay,
        'm5_4_first_pass': {'pass': 35, 'fail': 0},
        'receipt_outputs_rehashed': output_count,
        'validation_metrics_recomputed': metrics,
        'validation_queries': len(per_query),
        'validation_candidates': sum(row['candidates'] for row in per_query),
        'metric_max_abs_difference': metric_max,
        'fresh_checkpoint_reload': reload_result,
        'seed2_output_observation': seed2_observation,
        'limitations': [
            'Selected epoch 1 is the maximum on the same validation split; this is not a test estimate.',
            'M5.2 cache-parity receipt is technical PASS; its human acceptance remains pending.',
            'The frozen config and summary retain the M2.7 experiment_id; authorization and registry bind this M5.4 run separately.',
            'No seed-averaged, QPAF comparison or baseline improvement claim is made.'
        ],
        'test_labels_deserialized': False,
        'training_executed_by_review': False,
        'matched_qpaf_run_authorized_by_review': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--output', type=Path)
    actions.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.output is not None:
        require(not args.output.exists(), 'independent review output already exists')
    previous = read(args.verify) if args.verify else None
    timestamp = (previous['checked_utc'] if previous else
                 datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'))
    report = audit(timestamp)
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')
    if args.verify:
        require(args.verify.read_bytes() == encoded, 'saved independent review differs from replay')
        print('M5.4 QARF independent review: PASS')
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
        print(f'M5.4 QARF technical review created: {args.output}')
    else:
        print(encoded.decode('utf8'))


if __name__ == '__main__':
    try:
        main()
    except (KeyError, OSError, ValueError) as exc:
        raise SystemExit(f'M5.4 QARF review refused: {exc}')
