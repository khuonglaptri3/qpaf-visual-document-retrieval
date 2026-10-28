"""Local, create-once M5.6 CPU execution, fresh-process reload and read-only verification. No cloud SDK."""
import csv
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

from qpaf.m44.common import files_manifest, read, sha, write_json, write_text
from . import ablation, conditioning
from .ablation import ABLATIONS, METRICS, require

SEAL = 'results/m3.1/RUN-QPAF-M3_1-SEAL-001-20261021T142631Z-A01/inputs'
CONFIG = SEAL+'/shared_base.toml'
PILOT = conditioning.RUNS[(20260820, 'QPAF')][0]
AUTHORIZATION_PATH = 'evidence/revisions/m5.6-001/authorization.json'
RUN_ID = re.compile(r'RUN-QPAF-M5_6-ABL-001-\d{8}T\d{6}Z-A\d{2}')
SCOPE = ['R6-00', 'R6-01', 'R6-02', 'R6-03', 'R6-04', 'R6-05']
PERMISSIONS = {'device': 'cpu', 'modal': False, 'gpu': False, 'training': 'diagnostic_only',
               'retriever_inference': False, 'test_labels': False, 'vimdoc': False, 'network': False}
LIMITS = {'wall_time_seconds': 3600, 'invocations': 1, 'automatic_retries': 0}
SOURCE_FILES = ('src/qpaf/m56/__init__.py', 'src/qpaf/m56/ablation.py', 'src/qpaf/m56/conditioning.py',
                'src/qpaf/m56/runner.py', 'scripts/run_m56_ablations.py', 'tests/test_m56_ablations.py',
                'src/qpaf/m12/features.py', 'src/qpaf/m12/model.py', 'src/qpaf/m12/losses.py',
                'src/qpaf/m24/config.py', 'src/qpaf/m24/dataset.py', 'src/qpaf/m24/evaluator.py',
                'src/qpaf/m24/trainer.py', 'src/qpaf/m44/common.py')
AUTHORITY_PINS = {
    'evidence/revisions/m5.1-001/preregistration.json':
        '45269eafe36907f99990027f067e724939da69db5ee351669d1e5e7854bf7e29',
    'evidence/revisions/m5.1-001/owner_confirmation.json':
        'c9fa0a0ef637362a30f6dcc38f86cd59916620bd714b3d6330afa76de4e80bef',
    'evidence/revisions/m4.7-001/g2a_freeze.json':
        '26d9bab6e7d47fe7dd1e89f6bec2c95265641df5cde8d9bd25c867b9d3a73217',
    'evidence/revisions/m4.7-001/owner_confirmation.json':
        '5f80b4312188721dc2c2033a85ce1a9631bffa32479c576e0500471e622b95e6',
    'evidence/revisions/m3.4-001/authorization.json':
        '4be026b852574e7687fdc4b9337f716aa96a64ac39556ae288193bdba99e5365',
    CONFIG: '3e58a867d11cebf72970cf0c141a90822cd7cbbdad65fb1e081cb14fa4889b58',
    SEAL+'/score_cache.parquet': '56d0c82efda9264c117611ddd7135fe2384b68a3ec60fbdfd80fb964c386622b',
    SEAL+'/query_texts.json': 'e7994373c9fd5157cde0fb0c5a1440c37c275b85fa19b2b0b566f61d584c4ab4',
    SEAL+'/qrels_development.json': '691b6bc4ada3bc64fe3c408fe32498b04c7f30900eadb39ae09ddbe29aea302c',
    SEAL+'/splits/train_ids.txt': '61dfe867c27b91a0a96594440b0f0e5ecf51501da0fcecdac94badaf16962191',
    SEAL+'/splits/val_ids.txt': '46f8af5853942f6697cc3a995347a1832206212e93ff8aa87acb1775b3a060b4',
    SEAL+'/splits/test_ids.txt': 'd34210f901759a4f174da0c6c2e9b810616dcb33a71a0bd128a25d5d8d12e6f6',
    PILOT+'/summary.json': 'c932709e43f1ac5b1d6f5f3f0a088be6f6e4931b5e81ce8ce2757f8775eaa556',
}
PREDICTION_TOLERANCE = 1e-12
EXPECTED_COUNTS = {'train': 799, 'validation': 171}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def runtime_versions():
    import numpy
    import pandas
    import pyarrow
    import torch
    return {'python': platform.python_version(), 'torch': torch.__version__, 'numpy': numpy.__version__,
            'pandas': pandas.__version__, 'pyarrow': pyarrow.__version__}


def source_hashes(root):
    return {p: sha(Path(root)/p) for p in SOURCE_FILES}


def _git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf8').strip()


def deterministic():
    import random
    import numpy
    import torch
    random.seed(20260820)
    numpy.random.seed(20260820)
    torch.manual_seed(20260820)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


def load_records(root, roles=('train', 'validation')):
    """M3.1 sealed development inputs; test IDs are read only for disjointness, test qrels never."""
    from qpaf.m24.config import load_config
    from qpaf.m24.dataset import build_records, read_score_rows, read_split_ids
    root = Path(root)
    config = load_config(root/CONFIG)
    records = build_records(read_score_rows(root/SEAL/'score_cache.parquet'),
                            read(root/SEAL/'query_texts.json'), read(root/SEAL/'qrels_development.json'),
                            read_split_ids(root/SEAL/'splits'), roles,
                            positive_threshold=config['data']['positive_threshold'],
                            max_candidates=config['data']['max_candidates'])
    require(all(len(records[role]) == EXPECTED_COUNTS[role] for role in roles), 'Development split counts differ')
    return config, records


def check_approval(auth, *, run_id, clean, source_hashes, authority_pins, runtime):
    require(auth.get('status') == 'APPROVED' and auth.get('task_id') == 'M5.6', 'M5.6 approval missing')
    require(RUN_ID.fullmatch(run_id) and auth.get('run_id') == run_id, 'Run ID differs from authorization')
    require(auth.get('scope') == SCOPE, 'Only the preregistered R6 scope plus the R6-00 control is authorized')
    require(auth.get('permissions') == PERMISSIONS, 'Authorization is not strictly CPU/offline/validation-only')
    approval = auth.get('approval') or {}
    require(all(isinstance(approval.get(k), str) and approval[k].strip() and 'PENDING' not in approval[k]
                for k in ('approver', 'approval_text', 'approved_utc')), 'Explicit approval text/time required')
    require(datetime.fromisoformat(approval['approved_utc'].replace('Z', '+00:00')).tzinfo is not None,
            'Approval time must include a timezone')
    require(re.fullmatch('[0-9a-f]{40}', auth.get('source_commit', '')), 'Source commit missing')
    require(clean, 'Tracked working tree must be clean')
    require(auth.get('source_files_sha256') == source_hashes, 'Implementation source hashes differ')
    require(auth.get('authority_pins') == authority_pins, 'Authority pins differ')
    require(auth.get('runtime') == runtime, 'CPU numerical runtime differs from authorization')
    require(auth.get('limits') == LIMITS, 'Only one bounded invocation without retries is authorized')


def validate_bindings(root, auth):
    require(auth['source_files_sha256'] == source_hashes(root), 'Pinned implementation source differs')
    require(auth['authority_pins'] == AUTHORITY_PINS, 'Authority set differs')
    for relative, digest in AUTHORITY_PINS.items():
        require(sha(root/relative) == digest, f'Authority hash differs: {relative}')


def check_authorization(root, path, pin, run_id):
    require(re.fullmatch('[0-9a-f]{64}', pin or '') and sha(path) == pin, 'Authorization external pin differs')
    auth = read(path)
    check_approval(auth, run_id=run_id, clean=not _git(root, 'status', '--porcelain', '-uno'),
                   source_hashes=source_hashes(root), authority_pins=AUTHORITY_PINS, runtime=runtime_versions())
    validate_bindings(root, auth)
    head = _git(root, 'rev-parse', 'HEAD')
    ancestry = subprocess.run(['git', 'merge-base', '--is-ancestor', auth['source_commit'], head], cwd=root)
    require(ancestry.returncode == 0, 'Implementation commit is not an ancestor of execution HEAD')
    changed = _git(root, 'diff', '--name-only', auth['source_commit'], head).splitlines()
    require(set(changed) <= {AUTHORIZATION_PATH}, 'Changes after implementation include more than authorization')
    require(Path(path).resolve() == (root/AUTHORIZATION_PATH).resolve(), 'Authorization namespace differs')
    committed = subprocess.check_output(['git', 'show', head+':'+AUTHORIZATION_PATH], cwd=root)
    require(committed == Path(path).read_bytes(), 'Authorization must be committed before execution')
    return auth, head


def _csv(path, rows, fields=None):
    with path.open('x', encoding='utf8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path):
    with path.open(encoding='utf8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_predictions(path, predictions):
    # No stored name and mtime=0 keep the archive bytes a function of the content only.
    with open(path, 'xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
        stream.write(json.dumps(predictions, separators=(',', ':'), allow_nan=False).encode('utf8'))


def read_predictions(path):
    with gzip.open(path, 'rb') as stream:
        return json.loads(stream.read().decode('utf8'))


def prediction_difference(expected, actual):
    """Largest |score| or |weight| difference; query and candidate order must match exactly."""
    require(len(expected) == len(actual) and expected, 'Prediction query count differs')
    worst = 0.
    for saved, fresh in zip(expected, actual):
        require((saved['query_id'], saved['page_ids']) == (fresh['query_id'], fresh['page_ids']),
                'Prediction query or candidate order differs')
        values = [*fresh['scores'], *(w for row in fresh['weights'] for w in row)]
        require(ablation.finite(values), 'Non-finite prediction')
        worst = max(worst, *(abs(a-b) for a, b in zip(saved['scores'], fresh['scores'])),
                    *(abs(a-b) for old, new in zip(saved['weights'], fresh['weights']) for a, b in zip(old, new)))
    return worst


def run_ablation(output, rid, config, records, log):
    """Train one masked diagnostic gate, reload its best checkpoint in-process and keep its evidence."""
    from qpaf.m24.evaluator import evaluate, predict
    factor, omitted = ABLATIONS[rid]
    stage = output/rid
    stage.mkdir()
    started = time.monotonic()
    result = ablation.train(config, omitted, records['train'], records['validation'], stage/'checkpoints',
                            log=lambda line: log(f'{rid} {line}'))
    payload = ablation.load_checkpoint(stage/'checkpoints/best.pt', config=config, omitted=omitted,
                                       expected_sha256=result['checkpoint_sha256']['best'])
    model = ablation.build_model(config, omitted)
    model.load_state_dict(payload['model_state'])
    batch, cap = config['training']['batch_size'], config['features']['query_length_cap']
    predictions = predict(model, records['validation'], batch, cap)
    aggregate, per_query = evaluate(predictions, records['validation'])
    require(abs(aggregate[result['best']['metric']]-result['best']['value']) <= PREDICTION_TOLERANCE,
            f'{rid}: reloaded best checkpoint does not reproduce its selection metric')
    masked = ablation.masked_weights_unchanged(config, omitted, payload['model_state'])
    require(masked, f'{rid}: omitted-feature weights moved during training')
    _csv(stage/'epochs.csv', result['history'])
    _csv(stage/'validation_per_query.csv', per_query)
    write_predictions(stage/'validation_predictions.json.gz', predictions)
    summary = {'roster_id': rid, 'factor': factor, 'omitted_features': list(omitted),
               'active_feature_count': 13-len(omitted), 'method': ablation.METHOD, 'granularity': 'page',
               'seed': config['training']['seed'], 'epochs': config['training']['epochs'],
               'selected_epoch': result['best']['epoch'], 'selection_metric': result['best']['metric'],
               'validation': aggregate, 'omitted_weights_unchanged': masked,
               'checkpoint_sha256': result['checkpoint_sha256'], 'train_seconds': time.monotonic()-started,
               'test_split': 'not_opened', 'selection_is_optimistic': True}
    write_json(stage/'summary.json', summary)
    return summary, per_query, predictions


def pilot_parity(root, predictions, per_query, summary):
    """The R6-00 control must reproduce the accepted M3.4 pilot exactly: same epoch, metrics and outputs."""
    pilot = Path(root)/PILOT
    saved = read(pilot/'summary.json')
    difference = prediction_difference(read(pilot/'validation_predictions.json'), predictions)
    rows = _read_csv(pilot/'validation_per_query.csv')
    metric = max(abs(float(a[m])-b[m]) for a, b in zip(rows, per_query) for m in METRICS)
    require([r['query_id'] for r in rows] == [r['query_id'] for r in per_query], 'Pilot query order differs')
    parity = {'pilot_run': PILOT, 'selected_epoch': [saved['selected_epoch'], summary['selected_epoch']],
              'prediction_max_abs_difference': difference, 'per_query_metric_max_abs_difference': metric,
              'tolerance': PREDICTION_TOLERANCE}
    require(saved['selected_epoch'] == summary['selected_epoch'] and difference <= PREDICTION_TOLERANCE
            and metric <= PREDICTION_TOLERANCE, f'R6-00 control does not reproduce the M3.4 pilot: {parity}')
    return {'status': 'PASS', **parity}


def compare_ablations(per_query):
    """Each R6-01..04 diagnostic minus the R6-00 full-feature control, paired by validation query."""
    reference = per_query['R6-00']
    return {rid: {'factor': ABLATIONS[rid][0], 'omitted_features': list(ABLATIONS[rid][1]),
                  'contrast': f'{rid} - R6-00', 'paired': ablation.paired_statistics(
                      ablation.per_query_deltas(per_query[rid], reference))}
            for rid in SCOPE[1:5]}


def fresh_reload(root, output):
    """Child interpreter: reload every best/last checkpoint, re-predict and compare to the saved outputs."""
    command = [sys.executable, str(Path(root)/'scripts/run_m56_ablations.py'), 'reload', '--output', str(output)]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf8')
    require(completed.returncode == 0, f'Fresh-process reload failed: {completed.stderr[-800:]}')
    return json.loads(completed.stdout)


def reload_outputs(root, output):
    """Run only inside the child started by fresh_reload; writes nothing."""
    import os
    from qpaf.m24.evaluator import evaluate, predict
    deterministic()
    root, output = Path(root).resolve(), Path(output).resolve()
    config, records = load_records(root, ('validation',))
    batch, cap = config['training']['batch_size'], config['features']['query_length_cap']
    checks = {}
    for rid in SCOPE[:5]:
        stage, omitted = output/rid, ABLATIONS[rid][1]
        summary = read(stage/'summary.json')
        payloads = {name: ablation.load_checkpoint(stage/f'checkpoints/{name}.pt', config=config, omitted=omitted,
                                                   expected_sha256=summary['checkpoint_sha256'][name])
                    for name in ('best', 'last')}
        require(payloads['best']['epoch'] == summary['selected_epoch'] and
                payloads['last']['epoch'] == config['training']['epochs'], f'{rid}: checkpoint epoch differs')
        model = ablation.build_model(config, omitted)
        model.load_state_dict(payloads['best']['model_state'])
        require(all(bool(p.isfinite().all()) for p in model.parameters()), f'{rid}: non-finite checkpoint')
        actual = predict(model, records['validation'], batch, cap)
        difference = prediction_difference(read_predictions(stage/'validation_predictions.json.gz'), actual)
        aggregate, _ = evaluate(actual, records['validation'])
        metric = max(abs(aggregate[m]-summary['validation'][m]) for m in METRICS)
        tolerance = config['evaluation']['reload_tolerance']
        require(difference <= tolerance and metric <= tolerance, f'{rid}: fresh reload differs')
        checks[rid] = {'prediction_max_abs_difference': difference, 'metric_max_abs_difference': metric,
                       'tolerance': tolerance}
    return {'status': 'PASS', 'worker_pid': os.getpid(), 'checks': checks}


def _summary(summaries, comparisons, conditioning_result, parity, reload):
    return {'task_id': 'M5.6', 'roster_id': 'R6', 'status': 'TECHNICAL_PASS_PENDING_INDEPENDENT_REVIEW',
            'split': 'validation', 'query_count': 171,
            'diagnostics': {rid: {'omitted_features': s['omitted_features'], 'selected_epoch': s['selected_epoch'],
                                  'validation': s['validation']} for rid, s in summaries.items()},
            'ablation_vs_control_ndcg_at_10': {rid: c['paired']['ndcg_at_10'] for rid, c in comparisons.items()},
            'conditioning_three_seed_ndcg_at_10': conditioning_result['three_seed_query_mean']['ndcg_at_10'],
            'control_reproduces_pilot': parity['status'], 'fresh_process_reload': reload['status'],
            'confirmatory_claim': False, 'primary_method_changed': False, 'gpu_executed': False,
            'modal_called': False, 'test_labels_opened': False, 'vimdoc_confirmation_accessed': False,
            'independent_human_review': 'PENDING'}


def _report(summary, comparisons, conditioning_result):
    lines = ['# M5.6 / R6 — feature-group and conditioning ablations', '',
             'Validation only (171 queries), seed 20260820, exploratory. Selected epochs maximise validation',
             'nDCG@10, so every absolute value is optimistic; read the paired deltas.', '',
             '| Run | Omitted | Epoch | nDCG@10 | R@1 | R@3 | MRR@10 |', '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for rid, row in summary['diagnostics'].items():
        lines.append(f'| {rid} | {", ".join(row["omitted_features"]) or "none (control)"} | {row["selected_epoch"]} | '
                     + ' | '.join(f'{row["validation"][m]:.6f}' for m in METRICS)+' |')
    lines += ['', '| Contrast | Mean ΔnDCG@10 | 95% CI | W/T/L |', '| --- | ---: | --- | --- |']
    stats = [(c['contrast'], c['paired']['ndcg_at_10']) for c in comparisons.values()]
    stats.append(('QPAF − QARF, three-seed query mean', conditioning_result['three_seed_query_mean']['ndcg_at_10']))
    for name, s in stats:
        lines.append(f'| {name} | {s["mean_delta"]:+.6f} | [{s["ci95"][0]:+.6f}, {s["ci95"][1]:+.6f}] | '
                     f'{s["wtl"]["wins"]}/{s["wtl"]["ties"]}/{s["wtl"]["losses"]} |')
    lines += ['', f'R6-00 reproduces the M3.4 pilot: {summary["control_reproduces_pilot"]}. '
              f'Fresh-process reload: {summary["fresh_process_reload"]}.',
              'No test label, primary-method change, GPU or Modal call. Independent review pending.']
    return '\n'.join(lines)+'\n'


def execute(root, authorization, expected_sha256, run_id, *, log=print):
    root, authorization = Path(root).resolve(), Path(authorization).resolve()
    require(RUN_ID.fullmatch(run_id), 'Invalid run namespace')
    output = root/'results/m5.6'/run_id
    require(not output.exists(), 'Run namespace exists; no overwrite/retry permitted')
    auth, head = check_authorization(root, authorization, expected_sha256, run_id)
    deterministic()
    config, records = load_records(root)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'_ATTEMPTED.json', {'run_id': run_id, 'started_utc': now(), 'git_head': head,
                                         'authorization_sha256': expected_sha256})
    started = time.monotonic()
    try:
        summaries, per_query, predictions = {}, {}, {}
        for rid in SCOPE[:5]:
            summaries[rid], per_query[rid], predictions[rid] = run_ablation(output, rid, config, records, log)
            require(time.monotonic()-started <= LIMITS['wall_time_seconds'], 'CPU wall-time cap exceeded')
        parity = pilot_parity(root, predictions['R6-00'], per_query['R6-00'], summaries['R6-00'])
        comparisons = compare_ablations(per_query)
        conditioning_result, conditioning_rows = conditioning.compare(root, records['validation'], sha)
        reload = fresh_reload(root, output)
        summary = _summary(summaries, comparisons, conditioning_result, parity, reload)
        write_json(output/'pilot_parity.json', parity)
        write_json(output/'ablation_comparisons.json', comparisons)
        write_json(output/'conditioning.json', conditioning_result)
        _csv(output/'conditioning_per_query.csv', conditioning_rows)
        write_json(output/'reload.json', reload)
        write_json(output/'summary.json', summary)
        write_text(output/'report.md', _report(summary, comparisons, conditioning_result))
        write_text(output/'authorization.json', authorization.read_text(encoding='utf8'))
        write_json(output/'provenance.json', {'implementation_commit': auth['source_commit'], 'execution_head': head,
                                             'runtime': runtime_versions(), 'source_files_sha256': auth['source_files_sha256'],
                                             'authority_pins': auth['authority_pins'],
                                             'ablations': {k: list(v[1]) for k, v in ABLATIONS.items()},
                                             'elapsed_seconds': time.monotonic()-started})
        require(time.monotonic()-started <= LIMITS['wall_time_seconds'], 'CPU wall-time cap exceeded')
        write_json(output/'manifest.json', {'schema_version': 1, 'task_id': 'M5.6', 'run_id': run_id,
                                            'authorization_sha256': expected_sha256,
                                            'files': files_manifest(output)})
        write_json(output/'_SUCCESS.json', {'status': 'SUCCESS', 'finished_utc': now(),
                                           'manifest_sha256': sha(output/'manifest.json')})
        return {**summary, 'output': str(output), 'manifest_sha256': sha(output/'manifest.json')}
    except Exception as exc:
        write_json(output/'_FAILED.json', {'status': 'FAILED', 'finished_utc': now(),
                                          'reason': f'{type(exc).__name__}: {exc}', 'retry_authorized': False})
        raise


def verify(root, output, expected_manifest_sha256):
    """Check every artifact, reload all checkpoints in a fresh process and replay every statistic; write nothing."""
    root, output = Path(root).resolve(), Path(output).resolve()
    require(re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or '') and
            sha(output/'manifest.json') == expected_manifest_sha256, 'External manifest pin differs')
    manifest, marker = read(output/'manifest.json'), read(output/'_SUCCESS.json')
    require(marker['manifest_sha256'] == expected_manifest_sha256 and not (output/'_FAILED.json').exists(),
            'Completion marker differs or failure marker exists')
    names = [row['path'] for row in manifest['files']]
    require(len(names) == len(set(names)), 'Duplicate manifest paths')
    for entry in manifest['files']:
        path = (output/entry['path']).resolve()
        require(path.is_relative_to(output) and path.is_file() and path.stat().st_size == entry['size_bytes']
                and sha(path) == entry['sha256'], f'Artifact differs: {entry["path"]}')
    present = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    require(present == set(names) | {'manifest.json', '_ATTEMPTED.json', '_SUCCESS.json'}, 'Run file set differs')
    require(sha(output/'authorization.json') == manifest['authorization_sha256'] ==
            read(output/'_ATTEMPTED.json')['authorization_sha256'], 'Authorization/attempt pin differs')
    validate_bindings(root, read(output/'authorization.json'))
    _, records = load_records(root, ('validation',))
    per_query = {rid: [{k: v if k == 'query_id' else float(v) for k, v in row.items()}
                       for row in _read_csv(output/rid/'validation_per_query.csv')] for rid in SCOPE[:5]}
    require(read(output/'ablation_comparisons.json') == json.loads(json.dumps(compare_ablations(per_query))),
            'Ablation statistics differ from replay')
    replay, _ = conditioning.compare(root, records['validation'], sha)
    require(read(output/'conditioning.json') == json.loads(json.dumps(replay)), 'Conditioning statistics differ')
    reload = fresh_reload(root, output)
    return {'status': 'PASS', 'run_id': manifest['run_id'], 'manifest_sha256': expected_manifest_sha256,
            'files': len(names), 'fresh_reload': reload['checks'], 'read_only': True}
