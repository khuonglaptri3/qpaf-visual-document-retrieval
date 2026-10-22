"""Read-only M3.6 integrity review; --output writes one new review record.

The CPU audit never trains, launches a GPU job, or deserializes test qrels.
Resource gates remain BLOCKED until a separately reviewed GPU workload is run.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))
from scripts import audit_m33_qarf as prior  # noqa: E402
from scripts import audit_m35_paired as paired  # noqa: E402


class AuditError(ValueError):
    """The reviewed bytes or replay violate the frozen contract."""


def require(condition, message):
    if not condition:
        raise AuditError(message)


def check_finite_tree(value):
    """Reject nonfinite persisted tensors/numbers; return the scalar count checked."""
    import torch
    if isinstance(value, torch.Tensor):
        require(bool(torch.isfinite(value).all()), 'nonfinite persisted checkpoint tensor')
        return value.numel()
    if isinstance(value, dict):
        return sum(check_finite_tree(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(check_finite_tree(item) for item in value)
    if type(value) in (int, float):
        require(math.isfinite(value), 'nonfinite persisted numeric value')
        return 1
    return 0


def compare_predictions(expected, actual, tolerance):
    """Bind query/page order, finite simplex weights, scores and replay error."""
    require(type(tolerance) in (int, float) and math.isfinite(tolerance) and tolerance > 0,
            'invalid reload tolerance')
    require(expected and len(expected) == len(actual), 'fresh reload query count differs')
    seen, candidates, rankings = set(), 0, 0
    score_max = weight_max = 0.0
    for original, fresh in zip(expected, actual):
        query_id, pages = original['query_id'], original['page_ids']
        require(query_id not in seen and pages and len(pages) == len(set(pages)),
                'empty or duplicated query/candidate identity')
        seen.add(query_id)
        require(query_id == fresh['query_id'] and pages == fresh['page_ids'],
                'fresh reload query/candidate order differs')
        candidates += len(pages)
        for prediction in (original, fresh):
            require(len(prediction['scores']) == len(pages) == len(prediction['weights']),
                    'prediction dimensions differ')
            require(all(type(x) in (int, float) and math.isfinite(x) for x in prediction['scores']),
                    'nonfinite or nonnumeric prediction score')
            for weights in prediction['weights']:
                require(len(weights) == 3 and all(type(x) in (int, float) and math.isfinite(x)
                                                and x >= 0 for x in weights),
                        'nonfinite or invalid fusion weights')
                require(abs(sum(weights)-1) <= tolerance, 'fusion weights are not simplex vectors')
        score_max = max(score_max, *(abs(a-b) for a, b in zip(original['scores'], fresh['scores'])))
        weight_max = max(weight_max, *(abs(a-b) for old, new in zip(original['weights'], fresh['weights'])
                                      for a, b in zip(old, new)))
        old_rank = sorted(range(len(pages)), key=lambda i: (-original['scores'][i], pages[i]))
        new_rank = sorted(range(len(pages)), key=lambda i: (-fresh['scores'][i], pages[i]))
        rankings += old_rank != new_rank
    require(score_max <= tolerance, f'fresh checkpoint scores differ by {score_max} > {tolerance}')
    require(weight_max <= tolerance, f'fresh checkpoint weights differ by {weight_max} > {tolerance}')
    return {'query_count': len(seen), 'candidate_count': candidates,
            'score_max_abs_difference': score_max, 'weight_max_abs_difference': weight_max,
            'tolerance': tolerance, 'ranking_disagreements': rankings}


def review_resources(auth, success, telemetry):
    """Separate authorized CPU run limits from unmeasured scientific GPU gates."""
    check_finite_tree(telemetry)
    require(auth['runtime']['device'] == telemetry['device'] == 'cpu', 'recorded device differs')
    for key in ('dtype', 'threads'):
        require(telemetry[key] == auth['runtime'][key], f'recorded {key} differs')
    wall = success['wall_seconds']
    require(type(wall) in (int, float) and math.isfinite(wall) and
            0 <= wall <= auth['limits']['wall_time_seconds'], 'authorized wall-time cap violated')
    require(telemetry['peak_rss_mb'] > 0 and telemetry['phases'], 'missing process memory/phase telemetry')
    require(all(phase['seconds'] >= 0 for phase in telemetry['phases']), 'negative phase duration')
    counts = auth['sealed_inputs']['split']['counts']
    return {'verdict': 'BLOCKED', 'authorized_cpu_runtime_limits': 'PASS',
            'recorded_wall_seconds': wall, 'recorded_peak_rss_mb': telemetry['peak_rss_mb'],
            'telemetry_scope': 'historical CPU phase timings and process RSS, not per-query GPU measurements',
            'development_unique_queries': counts['train']+counts['validation'],
            'latency_gate': 'NOT_MEASURED', 'cuda_gate': 'NOT_MEASURED',
            'required_warmup_queries': 20, 'required_measured_label_free_queries': 1000,
            'maximum_median_added_fusion_latency_ms': 10.0,
            'maximum_peak_learned_fusion_cuda_gib_exclusive': 1.50,
            'reason': 'CPU phase telemetry cannot certify per-query latency or learned-fusion CUDA allocation.'}


def runtime_versions():
    import numpy
    import pandas
    import pyarrow
    import torch
    return {'python': platform.python_version(), 'torch': torch.__version__, 'numpy': numpy.__version__,
            'pandas': pandas.__version__, 'pyarrow': pyarrow.__version__}


def check_step_telemetry(epochs, steps):
    """Verify persisted per-step loss/norm and coverage against epoch telemetry."""
    expected = {int(row['epoch']): int(row['train_steps']) for row in epochs}
    require(len(expected) == len(epochs) and steps, 'missing or duplicated epoch/step telemetry')
    seen, counts, losses, norms = set(), Counter(), [], []
    for row in steps:
        require(all(math.isfinite(float(value)) for value in row.values()), 'nonfinite step telemetry')
        key = (int(row['epoch']), int(row['step']))
        require(key not in seen and key[0] in expected and key[1] >= 0, 'duplicate or invalid training step')
        seen.add(key)
        counts[key[0]] += 1
        loss, norm = float(row['loss']), float(row['grad_norm'])
        require(loss >= 0 and norm >= 0 and int(row['valid_queries']) > 0 and
                int(row['skipped_queries']) >= 0 and int(row['pairs']) > 0, 'invalid step counters/loss/norm')
        losses.append(loss)
        norms.append(norm)
    require(dict(counts) == expected, 'persisted step coverage differs from epoch train_steps')
    return {'step_count': len(steps), 'epoch_count': len(epochs), 'loss_min': min(losses),
            'loss_max': max(losses), 'grad_norm_min': min(norms), 'grad_norm_max': max(norms)}


def check_comparison_acceptance(event, comparison, signoff, run_ids, pins):
    """An acceptance must refer to exactly this pair and the accepted report bytes."""
    require(event.get('run_id') == run_ids['QPAF'] and event.get('comparator_run_id') == run_ids['QARF'] and
            event.get('authorization_manifest_sha256') == pins['qpaf_authorization'],
            'M3.5 acceptance is for a different run pair/authorization')
    require(comparison.get('task_id') == 'M3.5' and comparison.get('technical_verdict') == 'PASS' and
            comparison.get('run_ids') == run_ids and comparison.get('pins_sha256') == pins,
            'M3.5 comparison verdict/pair/pins differ')
    require(signoff.get('task_id') == 'M3.5' and signoff.get('decision') == 'ACCEPTED' and
            signoff.get('reviewer') == event.get('independent_reviewer') and
            signoff.get('technical_report_ref') == event.get('verification_ref') and
            signoff.get('technical_report_sha256') == event.get('verification_sha256'),
            'M3.5 owner acceptance does not bind this comparison report')


def checked_run(method):
    """Verify external authorization/prediction pins, markers and every receipt output."""
    key = method.lower()
    auth_rel, auth_sha = paired.PINS[key+'_authorization']
    pred_rel, pred_sha = paired.PINS[key+'_predictions']
    require(prior.sha(ROOT/auth_rel) == auth_sha, f'{method}: authorization pin differs')
    require(prior.sha(ROOT/pred_rel) == pred_sha, f'{method}: prediction handoff pin differs')
    auth = prior.read(ROOT/auth_rel)
    require(auth['status'] == 'APPROVED' and auth['method']['name'] == method,
            f'{method}: authorization method/status differs')
    require(all(runtime_versions()[k] == v for k, v in auth['runtime'].items()
                if k in runtime_versions()), f'{method}: numerical runtime differs from approved pin')
    attempt = ROOT/pred_rel
    attempt = attempt.parent
    namespace = ROOT/f'results/{auth["task_id"].lower()}'/auth['run_id']
    attempted, success = prior.check_supervisor_markers(namespace, auth_sha)
    require(success['run_id'] == auth['run_id'], f'{method}: supervised run ID differs')
    require(success['attempt'] == attempt.name, f'{method}: supervised attempt differs')
    require(sorted(p.name for p in namespace.iterdir()) ==
            [method, '_ATTEMPTED.json', '_SUCCESS.json', 'supervisor.log'], 'unexpected run namespace entry')
    require(prior.read(attempt.parent/'complete.json') ==
            {'attempt': attempt.name, 'receipt_sha256': success['receipt_sha256']}, 'complete marker differs')
    count = prior.check_receipt(attempt, success)
    require(prior.sha(attempt/'summary.json') == success['summary_sha256'], 'summary pin differs')
    summary, provenance = prior.read(attempt/'summary.json'), prior.read(attempt/'provenance.json')
    require(prior.read(attempt/'status.json')['status'] == 'completed', 'runner did not complete')
    require(summary['method'] == method and summary['seed'] == auth['method']['seed'] and
            summary['granularity'] == auth['method']['gate_granularity'] and
            summary['test_split'] == 'not_opened', 'summary method/seed/scope differs')
    require(provenance['source']['git_commit'] == attempted['git_head'], 'run source commit differs')
    require(provenance['config_sha256'] == auth['config']['expected_provenance_config_object_hash'],
            'run provenance config digest differs')
    for key, rel in [('config', 'inputs/shared_base.toml'), ('scores', 'inputs/score_cache.parquet'),
                     ('queries', 'inputs/query_texts.json'), ('qrels', 'inputs/qrels_development.json')]:
        require(provenance['inputs'][key] == auth['sealed_inputs']['files_relative_to_run_path'][rel],
                f'{method}: provenance {key} differs from seal')
    for name in ('train_ids.txt', 'val_ids.txt', 'test_ids.txt'):
        require(provenance['inputs']['splits'][name] ==
                auth['sealed_inputs']['files_relative_to_run_path']['inputs/splits/'+name],
                f'{method}: provenance split differs')
    check_finite_tree(summary)
    epochs = list(csv.DictReader((attempt/'epochs.csv').open(encoding='utf-8', newline='')))
    require(len(epochs) == auth['config']['frozen_values']['epochs'], 'epoch telemetry count differs')
    for row in epochs:
        for name, value in row.items():
            if name != 'selected':
                require(math.isfinite(float(value)), f'{method}: nonfinite epoch telemetry')
    with (attempt/'steps.csv').open(encoding='utf-8', newline='') as stream:
        step_review = check_step_telemetry(epochs, list(csv.DictReader(stream)))
    return auth, attempt, summary, success, count, step_review


def replay_worker(method):
    """Executed only in a separate child interpreter; reconstruct validation predictions."""
    import torch
    from qpaf.m24.checkpoint import load_checkpoint
    from qpaf.m24.config import load_config
    from qpaf.m24.dataset import build_records, read_score_rows, read_split_ids
    from qpaf.m24.evaluator import predict
    from qpaf.m24.trainer import build_model
    import qpaf.m24.evaluator as evaluator_source
    import qpaf.m12.model as model_source

    for module in (evaluator_source, model_source):
        require(Path(module.__file__).resolve().is_relative_to((ROOT/'src').resolve()),
                'replay imported model/evaluator outside the reviewed checkout')

    auth, attempt, summary, _, _, _ = checked_run(method)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    seal = ROOT/auth['sealed_inputs']['run_path']
    config = load_config(seal/'inputs/shared_base.toml')
    require(prior.sha(seal/'inputs/shared_base.toml') == auth['config']['file_sha256'], 'config pin differs')
    checkpoint_values, checkpoints = 0, {}
    for name in ('best', 'last'):
        checkpoint = load_checkpoint(attempt/f'checkpoints/{name}.pt', config=config, method=method,
                                     expected_sha256=summary['checkpoint_sha256'][name])
        checkpoint_values += check_finite_tree(checkpoint)
        checkpoints[name] = checkpoint
    require(checkpoints['best']['epoch'] == summary['selected_epoch'], 'best checkpoint epoch differs')
    require(checkpoints['last']['epoch'] == config['training']['epochs'], 'last checkpoint epoch differs')
    records = build_records(read_score_rows(seal/'inputs/score_cache.parquet'),
                            prior.read(seal/'inputs/query_texts.json'),
                            prior.read(seal/'inputs/qrels_development.json'),
                            read_split_ids(seal/'inputs/splits'), ('validation',),
                            positive_threshold=config['data']['positive_threshold'],
                            max_candidates=config['data']['max_candidates'])['validation']
    model = build_model(config, method)
    model.load_state_dict(checkpoints['best']['model_state'])
    actual = predict(model, records, config['training']['batch_size'], config['features']['query_length_cap'])
    expected = prior.read(attempt/'validation_predictions.json')
    comparison = compare_predictions(expected, actual, config['evaluation']['reload_tolerance'])
    candidates = {record.query_id: list(record.page_ids) for record in records}
    metrics, per_query = prior.calculate_validation(actual, prior.read(seal/'inputs/qrels_development.json'),
                                                   [r.query_id for r in records], candidates,
                                                   threshold=config['data']['positive_threshold'])
    metric_difference = prior.compare_reported_metrics(metrics, per_query, attempt)
    return {'method': method, 'status': 'PASS_FRESH_PROCESS', 'worker_pid': os.getpid(),
            'parent_pid': os.getppid(), 'runtime': runtime_versions(),
            'loaded_source_sha256': {Path(module.__file__).resolve().relative_to(ROOT).as_posix():
                                      prior.sha(module.__file__) for module in (evaluator_source, model_source)},
            **comparison,
            'checkpoint_numeric_values_checked': checkpoint_values,
            'validation_metrics_recomputed': metrics, 'metric_max_abs_difference': metric_difference}


def audit():
    for name, (rel, expected) in paired.PINS.items():
        require(prior.sha(ROOT/rel) == expected, f'{name} pin differs before seal access')
    auth_path, auth_sha = paired.PINS['qpaf_authorization']
    require(prior.sha(ROOT/auth_path) == auth_sha, 'QPAF authorization pin differs before seal access')
    auth = prior.read(ROOT/auth_path)
    pin_file = ROOT/auth['sealed_inputs']['seal_pin']['path']
    require(prior.sha(pin_file) == auth['sealed_inputs']['seal_pin']['sha256'], 'seal pin file differs')
    pin = prior.read(pin_file)
    require(pin['manifest_sha256'] == auth['sealed_inputs']['manifest_sha256'], 'seal manifest pin differs')
    seal = ROOT/auth['sealed_inputs']['run_path']
    seal_replay = json.loads(prior.run_read_only([sys.executable, str(ROOT/'scripts/seal_m31_inputs.py'),
                            '--verify', str(seal), '--expected-manifest-sha256', pin['manifest_sha256']]))
    require(seal_replay['status'] == 'PASS' and seal_replay['parity_identical'], 'M3.1 seal replay failed')
    events = [json.loads(line) for line in (ROOT/'evidence/revisions/m3.4-001/governance_events.jsonl').read_text(
        encoding='utf-8').splitlines() if line.strip()]
    accepted = [event for event in events if event.get('task_id') == 'M3.5' and
                event.get('event_type') == 'ACCEPTANCE_RECORDED' and event.get('registry_status') == 'PASS']
    require(len(accepted) == 1, 'M3.5 accepted comparison is missing or ambiguous')
    for key, hash_key in [('verification_ref', 'verification_sha256'), ('per_query_ref', 'per_query_sha256'),
                          ('review_signoff_ref', 'review_signoff_sha256')]:
        require(prior.sha(ROOT/accepted[0][key]) == accepted[0][hash_key], f'M3.5 {key} hash differs')
    run_ids = {method: prior.read(ROOT/paired.PINS[method.lower()+'_authorization'][0])['run_id']
               for method in ('QARF', 'QPAF')}
    check_comparison_acceptance(accepted[0], prior.read(ROOT/accepted[0]['verification_ref']),
                                prior.read(ROOT/accepted[0]['review_signoff_ref']), run_ids,
                                {key: pin for key, (_, pin) in paired.PINS.items()})
    runs = {}
    for method, first_pass_count in [('QARF', 30), ('QPAF', 39)]:
        run_auth, attempt, summary, success, receipt_count, steps = checked_run(method)
        checker = ROOT/f'evidence/revisions/{run_auth["task_id"].lower()}-001/post_run_check.py'
        output = prior.run_read_only([sys.executable, str(checker)])
        require(f"verdict: ALL CHECKS PASS {{'PASS': {first_pass_count}, 'FAIL': 0, 'SKIPPED': 0}}" in output,
                f'{method}: first-pass audit no longer reproduces')
        worker = json.loads(prior.run_read_only([sys.executable, str(Path(__file__).resolve()),
                                               '--replay-method', method]))
        require(worker['parent_pid'] == os.getpid() and worker['worker_pid'] != os.getpid(),
                'replay was not performed in a fresh child process')
        runs[method] = {'run_id': run_auth['run_id'], 'attempt': attempt.relative_to(ROOT).as_posix(),
                        'authorization_sha256': paired.PINS[method.lower()+'_authorization'][1],
                        'receipt_outputs_rehashed': receipt_count, 'first_pass_checks': first_pass_count,
                        'persisted_step_telemetry': steps,
                        'fresh_checkpoint_reload': worker,
                        'resources': review_resources(run_auth, success, prior.read(attempt/'telemetry.json'))}
    policy = ROOT/'evidence/M1_FINAL/02_protocol/metric_policy.md'
    return {'schema_version': 1, 'task_id': 'M3.6', 'owner': 'Khương',
            'executed_by': 'Codex at Khương request; independent of the M3.2/M3.4 run operators',
            'checked_utc': datetime.now(timezone.utc).isoformat(), 'integrity_verdict': 'PASS',
            'resource_verdict': 'BLOCKED', 'technical_verdict': 'BLOCKED',
            'owner_acceptance': 'PENDING_KHUONG_REVIEW', 'seal_manifest_sha256': pin['manifest_sha256'],
            'm3_1_seal_replay': seal_replay, 'm3_5_acceptance_event': accepted[0]['registry_event_id'],
            'operational_policy': {'path': policy.relative_to(ROOT).as_posix(), 'sha256': prior.sha(policy)},
            'audit_source_sha256': prior.sha(Path(__file__)), 'runtime': runtime_versions(), 'runs': runs,
            'limitations': ['Historical gradients were not individually persisted; the training source has '
                            'fail-fast finite checks. Persisted optimizer/model state and epoch telemetry are rechecked.',
                            'CPU RSS and whole-phase times do not establish the CUDA or per-query latency gates.',
                            'One selected development seed does not establish confirmation or robustness.'],
            'test_labels_deserialized': False, 'training_executed_by_audit': False,
            'gpu_execution_performed': False, 'g2_decision_made': False,
            'next_action': 'Review the separate label-free GPU workload and execution package before any GPU run.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new create-once JSON review path')
    parser.add_argument('--replay-method', choices=('QARF', 'QPAF'), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.output is not None:
        require(not args.output.exists(), f'output already exists: {args.output}')
    require(not (args.output and args.replay_method), 'worker cannot create review output')
    report = replay_worker(args.replay_method) if args.replay_method else audit()
    if args.output is None:
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        print(f'M3.6 integrity {report["integrity_verdict"]}; resources {report["resource_verdict"]}; {args.output}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AuditError, prior.AuditError) as exc:
        print(f'M3.6 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
