"""Local, create-once M5.5 CPU execution and read-only replay. No cloud SDK."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import time
from zipfile import ZipFile

from qpaf.m44.common import files_manifest, load_context, read, sha, write_json, write_text
from .diagnostics import (DiagnosticError, METRICS, METHODS, TOLERANCE, compute_diagnostics,
                          require, specifications)

BUNDLE_NAME = 'RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01'
BUNDLE_MANIFEST_SHA256 = '4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86'
ARCHIVE_SHA256 = '45e764f6bfe081063ea2488dbf5e26ffcaacf2e6f43ea3ad47f56a10c331d2d8'
REFERENCE = 'results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01'
RESOURCE_STATUS = 'NOT_RUN_DEFERRED_MODAL_NETWORK_BLOCKED'
PERMISSIONS = {'device': 'cpu', 'modal': False, 'gpu': False, 'training': False,
               'retriever_inference': False, 'test_labels': False, 'vimdoc': False, 'network': False}
SOURCE_FILES = ('src/qpaf/m55/__init__.py', 'src/qpaf/m55/diagnostics.py', 'src/qpaf/m55/runner.py',
                'scripts/run_m55_diagnostics.py', 'tests/test_m55_diagnostics.py',
                'src/qpaf/m44/common.py', 'src/qpaf/m42/active_primary.py',
                'src/qpaf/m24/dataset.py', 'src/qpaf/m24/evaluator.py', 'src/qpaf/m25/baselines.py')
AUTHORITY_PINS = {
    'configs/m4.4/evaluation.json':
        '799fc3e1e65a8961c4deb77eed2e6ae296f0bae853ba24293a11506e8b477db1',
    'evidence/revisions/m4.3-001/method_freeze.json':
        '4015c74b54f5ac3d2cbce54f8424c0e9329c009595e81ced5eab0039af7761cc',
    'evidence/revisions/m5.1-001/preregistration.json':
        '45269eafe36907f99990027f067e724939da69db5ee351669d1e5e7854bf7e29',
    'evidence/revisions/m5.1-001/owner_confirmation.json':
        'c9fa0a0ef637362a30f6dcc38f86cd59916620bd714b3d6330afa76de4e80bef',
    'evidence/revisions/m4.7-001/g2a_freeze.json':
        '26d9bab6e7d47fe7dd1e89f6bec2c95265641df5cde8d9bd25c867b9d3a73217',
    'evidence/revisions/m4.7-001/owner_confirmation.json':
        '5f80b4312188721dc2c2033a85ce1a9631bffa32479c576e0500471e622b95e6',
    'evidence/revisions/m5.2-001/cache_identity.json':
        '960aed613336e5f6faa8335881306ffc340bceff3094836eb6e3f135babc3291',
    'results/m5.2/verification/owner_confirmation.json':
        '2515fc38ec1001c8afeac90c4ff92fc255b65141980fd31edddc4d72a513c530',
    'evidence/M1_FINAL/02_protocol/metric_policy.md':
        '4ce926201bb38b975c3eb43b83b0c719dea48267ff20e8fffa7e7329c0b5579a',
    REFERENCE+'/manifest.json': 'aa2ab51814c883b5552b1b45136c1f25dd7d9921a074891f4ae0397f4b03e4a7',
    REFERENCE+'/baseline_table.json': 'ef5840cfb2334ebfdbef5694aaa628e8aff35df6feda606d1ab0f7166af57c09',
    REFERENCE+'/per_query_metrics.csv': '590934eb3d5e34976b6b3fc52739f79d9725730ea3acd5ad08758bafecfc9ecf',
}
AUTHORIZATION_PATH = 'evidence/revisions/m5.5-001/authorization.json'
RUN_ID = re.compile(r'RUN-QPAF-M5_5-ABL-001-\d{8}T\d{6}Z-A\d{2}')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def runtime_versions():
    import numpy
    import pandas
    import pyarrow
    return {'python': platform.python_version(), 'numpy': numpy.__version__,
            'pandas': pandas.__version__, 'pyarrow': pyarrow.__version__}


def source_hashes(root):
    return {p: sha(Path(root)/p) for p in SOURCE_FILES}


def _git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf8').strip()


def _inside(directory, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute()
            and '..' not in Path(relative).parts, 'Unsafe artifact path')
    target = (Path(directory)/relative).resolve()
    require(target.is_relative_to(Path(directory).resolve()), 'Artifact escapes its namespace')
    return target


def restore_inputs(root, archive):
    """Restore the reviewed archive locally, checking every existing byte first."""
    root, archive = Path(root).resolve(), Path(archive)
    require(sha(archive) == ARCHIVE_SHA256, 'M4.2 archive SHA-256 differs')
    base = root/'results/m4.2'
    payloads = {}
    with ZipFile(archive) as z:
        require(z.testzip() is None, 'Archive CRC differs')
        require(len(z.namelist()) == len(set(z.namelist())), 'Duplicate archive members')
        for name in z.namelist():
            require(name.startswith(BUNDLE_NAME+'/'), 'Unexpected archive namespace')
            target = _inside(base, name)
            data = z.read(name)
            require(not target.exists() or target.read_bytes() == data, f'Existing artifact differs: {name}')
            payloads[target] = data
    restored = []
    for target, data in payloads.items():
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
            restored.append(target.relative_to(root).as_posix())
    return {'status': 'PASS', 'archive_sha256': ARCHIVE_SHA256, 'restored': restored,
            'gpu_executed': False, 'network_used_by_restore': False}


def check_approval(auth, *, run_id, clean, source_hashes, authority_pins, runtime):
    require(auth.get('status') == 'APPROVED' and auth.get('task_id') == 'M5.5', 'M5.5 approval missing')
    require(RUN_ID.fullmatch(run_id) and auth.get('run_id') == run_id, 'Run ID differs from authorization')
    require(auth.get('scope') == ['R5-01', 'R5-02', 'R5-03'], 'Only the CPU R5 scope is authorized')
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
    require(auth.get('limits') == {'wall_time_seconds': 1800, 'invocations': 1, 'automatic_retries': 0},
            'Only one bounded invocation without retries is authorized')


def validate_bindings(root, auth):
    require(auth['source_files_sha256'] == source_hashes(root), 'Pinned implementation source differs')
    require(auth['authority_pins'] == AUTHORITY_PINS, 'Authority set differs')
    for relative, digest in AUTHORITY_PINS.items():
        require(sha(root/relative) == digest, f'Authority hash differs: {relative}')
    freeze = read(root/'evidence/revisions/m4.3-001/method_freeze.json')
    for relative, digest in freeze['source_sha256'].items():
        require(sha(root/relative) == digest, f'Frozen method source differs: {relative}')


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
    require(committed == Path(path).read_bytes(),
            'Authorization must be committed before execution')
    return auth, head


def load_inputs(root):
    from qpaf.m24.dataset import SCORE_COLUMNS, read_score_rows
    config = read(root/'configs/m4.4/evaluation.json')
    require(config['bundle'] == {'run_path': 'results/m4.2/'+BUNDLE_NAME,
                                  'manifest_sha256': BUNDLE_MANIFEST_SHA256},
            'Only the prescribed frozen M4.2 bundle is permitted')
    context = load_context(root)
    records = context['records']
    require(len(records) == 171 and sum(len(r.page_ids) for r in records) == 82255,
            'Validation scope differs from 171 queries / 82,255 candidates')
    require([r.query_id for r in records] == context['splits']['validation'], 'Validation order differs')
    selected = {r.query_id for r in records}
    cache = {r.query_id: {'page_ids': [], 'scores': []} for r in records}
    for row in read_score_rows(context['bundle']/'inputs/normalized_scores.parquet'):
        if row['query_id'] in selected:
            entry = cache[row['query_id']]
            entry['page_ids'].append(row['page_id'])
            entry['scores'].append(tuple(float(row[c]) for c in SCORE_COLUMNS[2:]))
    return context, cache


def load_reference(root):
    with (root/REFERENCE/'per_query_metrics.csv').open(encoding='utf8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    return read(root/REFERENCE/'baseline_table.json'), rows


def reference_parity(result, table, per_query):
    actual = {r['method']: r for r in result['metrics']}
    baseline = {r['method']: r for r in table['deployable']}
    current = {(r['method'], r['query_id']): r for r in result['per_query'] if r['method'] in METHODS[:4]}
    previous_rows = [r for r in per_query if r['method'] in METHODS[:4]]
    previous = {(r['method'], r['query_id']): r for r in previous_rows}
    require(len(previous) == len(previous_rows) and set(current) == set(previous), 'Reference query keys differ')
    maximum = 0.
    for method in METHODS[:4]:
        require(method in actual and method in baseline and
                actual[method]['query_count'] == baseline[method]['query_count'], 'Reference aggregate scope differs')
        for metric in METRICS:
            delta = abs(actual[method][metric]-float(baseline[method][metric]))
            require(delta <= TOLERANCE, f'M4.4 aggregate parity differs: {method}/{metric}')
            maximum = max(maximum, delta)
    for key, row in current.items():
        for metric in METRICS:
            delta = abs(row[metric]-float(previous[key][metric]))
            require(delta <= TOLERANCE, f'M4.4 per-query parity differs: {key}/{metric}')
            maximum = max(maximum, delta)
    return {'status': 'PASS', 'methods': list(METHODS[:4]), 'query_method_pairs': len(current),
            'max_abs_difference': maximum, 'absolute_tolerance': TOLERANCE}


def deferred_systems():
    return {'roster_id': 'R5-04', 'status': RESOURCE_STATUS, 'new_gpu_measurement': False,
            'modal_called': False, 'latency_ms': None, 'peak_cuda_gib': None,
            'reason': 'User deferred Modal/GPU because Modal is blocked on this machine.',
            'measurement_scope_unresolved': {'validation_query_ids': 171, 'policy_warmups': 20,
                                           'metric_policy_minimum_measured_queries': 1000,
                                           'historical_m36_minimum_distinct_measured_queries': 1000,
                                           'counting_interpretation_requires_review': True,
                                           'repetitions_create_new_query_ids': False},
            'historical_reference': 'evidence/revisions/m3.6-004/README.md',
            'historical_measurement_is_new_m55_result': False,
            'next_machine_requires': ['Reviewed measurement-scope decision', 'New M5.5 authorization',
                                      'Pinned runtime/source/checkpoint/input hashes',
                                      'New create-once namespace; do not reuse M3.6 authorization']}


def _csv(path, rows):
    with path.open('x', encoding='utf8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def _summary(result, parity):
    return {'task_id': 'M5.5', 'cpu_status': 'TECHNICAL_PASS',
            'status': 'PARTIAL_GPU_DEFERRED_PENDING_REVIEW', 'resource_status': RESOURCE_STATUS,
            'm55_complete': False, 'independent_human_review': 'PENDING',
            'split': 'validation', 'query_count': result['query_count'], 'candidate_count': result['candidate_count'],
            'diagnostic_rows': len(result['metrics']), 'reference_parity': parity,
            'confirmatory_claim': False, 'primary_method_changed': False,
            'training_executed': False, 'gpu_executed': False, 'modal_called': False,
            'test_labels_opened': False, 'vimdoc_confirmation_accessed': False}


def execute(root, authorization, expected_sha256, run_id):
    root, authorization = Path(root).resolve(), Path(authorization).resolve()
    require(RUN_ID.fullmatch(run_id), 'Invalid run namespace')
    output = root/'results/m5.5'/run_id
    require(not output.exists(), 'Run namespace exists; no overwrite/retry permitted')
    auth, head = check_authorization(root, authorization, expected_sha256, run_id)
    context, normalized = load_inputs(root)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'_ATTEMPTED.json', {'run_id': run_id, 'started_utc': now(), 'git_head': head,
                                         'authorization_sha256': expected_sha256})
    started = time.monotonic()
    try:
        result = compute_diagnostics(context['records'], normalized)
        parity = reference_parity(result, *load_reference(root))
        summary = _summary(result, parity)
        write_json(output/'diagnostics.json', result)
        write_json(output/'summary.json', summary)
        write_json(output/'systems_deferred.json', deferred_systems())
        write_json(output/'access.json', {**context['access'], 'training_executed': False,
                                          'checkpoints_loaded': False, 'gpu_executed': False, 'modal_called': False})
        _csv(output/'metrics.csv', result['metrics'])
        _csv(output/'per_query_metrics.csv', result['per_query'])
        _csv(output/'top10.csv', result['top10'])
        write_text(output/'authorization.json', authorization.read_text(encoding='utf8'))
        write_json(output/'provenance.json', {'implementation_commit': auth['source_commit'], 'execution_head': head,
                                             'runtime': runtime_versions(), 'source_files_sha256': auth['source_files_sha256'],
                                             'authority_pins': auth['authority_pins'], 'methods': specifications(),
                                             'bundle_manifest_sha256': sha(context['bundle']/'manifest.json'),
                                             'elapsed_analysis_seconds': time.monotonic()-started,
                                             'elapsed_time_is_fusion_latency': False})
        lines = ['# M5.5 CPU diagnostics', '', 'Validation only; no refit or primary-method change.', '',
                 '| Method | nDCG@10 | R@1 | R@3 | MRR@10 |', '| --- | ---: | ---: | ---: | ---: |']
        lines.extend('| '+r['method']+' | '+' | '.join(f'{r[m]:.9f}' for m in METRICS)+' |' for r in result['metrics'])
        lines.extend(['', 'R5-01/02/03: technical PASS; independent human review pending.',
                      'R5-04: '+RESOURCE_STATUS+'. Full M5.5 remains partial.',
                      'Historical M3.6 measurements are context, not a new M5.5 result.'])
        write_text(output/'report.md', '\n'.join(lines)+'\n')
        require(time.monotonic()-started <= auth['limits']['wall_time_seconds'], 'CPU wall-time cap exceeded')
        manifest = {'schema_version': 1, 'task_id': 'M5.5', 'run_id': run_id,
                    'authorization_sha256': expected_sha256, 'files': files_manifest(output)}
        write_json(output/'manifest.json', manifest)
        write_json(output/'_SUCCESS.json', {'status': 'CPU_SUCCESS_GPU_DEFERRED', 'finished_utc': now(),
                                           'manifest_sha256': sha(output/'manifest.json'), 'm55_complete': False})
        return {**summary, 'output': str(output), 'manifest_sha256': sha(output/'manifest.json')}
    except Exception as exc:
        write_json(output/'_FAILED.json', {'status': 'FAILED', 'finished_utc': now(),
                                          'reason': f'{type(exc).__name__}: {exc}', 'retry_authorized': False})
        raise


def _equivalent(actual, expected):
    if isinstance(actual, float) or isinstance(expected, float):
        return isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and abs(actual-expected) <= TOLERANCE
    if isinstance(actual, dict) and isinstance(expected, dict):
        return set(actual) == set(expected) and all(_equivalent(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(_equivalent(a, b) for a, b in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def verify(root, output, expected_manifest_sha256):
    """Check the external manifest, every artifact and the complete numerical replay; write nothing."""
    root, output = Path(root).resolve(), Path(output).resolve()
    require(re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or '') and
            sha(output/'manifest.json') == expected_manifest_sha256, 'External manifest pin differs')
    manifest, marker = read(output/'manifest.json'), read(output/'_SUCCESS.json')
    require(marker['manifest_sha256'] == expected_manifest_sha256 and
            marker['status'] == 'CPU_SUCCESS_GPU_DEFERRED' and marker.get('m55_complete') is False
            and not (output/'_FAILED.json').exists(),
            'CPU completion marker differs or failure marker exists')
    entries = manifest['files']
    names = [row['path'] for row in entries]
    require(len(names) == len(set(names)), 'Duplicate manifest paths')
    for entry in entries:
        path = _inside(output, entry['path'])
        require(path.is_file() and path.stat().st_size == entry['size_bytes'] and sha(path) == entry['sha256'],
                f'Artifact differs: {entry["path"]}')
    require(set(p.name for p in output.iterdir()) == set(names) | {'manifest.json', '_ATTEMPTED.json', '_SUCCESS.json'},
            'Run file set differs')
    require(sha(output/'authorization.json') == manifest['authorization_sha256'] ==
            read(output/'_ATTEMPTED.json')['authorization_sha256'], 'Authorization/attempt pin differs')
    attempt = read(output/'_ATTEMPTED.json')
    require(attempt['git_head'] == read(output/'provenance.json')['execution_head'] and
            attempt['run_id'] == manifest['run_id'] and manifest['task_id'] == 'M5.5',
            'Attempt source/run binding differs')
    auth = read(output/'authorization.json')
    validate_bindings(root, auth)
    require(auth['runtime'] == runtime_versions(), 'Replay requires the recorded numerical runtime')
    context, normalized = load_inputs(root)
    replay = compute_diagnostics(context['records'], normalized)
    parity = reference_parity(replay, *load_reference(root))
    require(_equivalent(read(output/'diagnostics.json'), replay), 'CPU diagnostic replay differs')
    require(_equivalent(read(output/'summary.json'), _summary(replay, parity)), 'Summary differs from replay')
    require(read(output/'systems_deferred.json') == deferred_systems(), 'Deferred-resource boundary differs')
    return {'status': 'PASS', 'run_id': manifest['run_id'], 'query_count': replay['query_count'],
            'candidate_count': replay['candidate_count'], 'manifest_sha256': expected_manifest_sha256,
            'read_only': True, 'resource_status': RESOURCE_STATUS, 'm55_complete': False}
