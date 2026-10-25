"""Run one authorized M5.3 seed-2 command (QARF, then the matched QPAF) once, under the M3.2 markers.

The single-attempt mechanics (pin, git state, seal check, wall limit, markers) are the M3.2 ones, reused
unchanged so that the sources pinned by earlier approved authorizations stay byte-stable. This module adds
what M5.1 requires of a seed run: the M5.1/M5.2/M4.3 pins hold, the config is the M5.2 receipt's config for
this seed, the run equals its seed-1 counterpart in everything but the seed, QPAF waits for an accepted
review of the seed-2 QARF run, and each checkpoint passes a finite check and a fresh-process reload.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import time

from qpaf.m32.supervisor import (AlreadyAttempted, Refused, _environment, _execute, _now, _read, _write,
                                 build_command, check_attempt as check_single_attempt, check_git, sha, verify_seal)
from qpaf.m34.supervisor import SHARED, SHARED_LIMITS

__all__ = ['AlreadyAttempted', 'Refused', 'load_authorization', 'check_seed_contract', 'check_comparator',
           'check_attempt', 'fresh_reload', 'supervise']

RUN_ID = re.compile(r'RUN-QPAF-M5_3-MTH-00[12]-\d{8}T\d{6}Z-A\d{2}')
OUTPUT_ROOT = 'results/m5.3'
SEED, TASK = 20260821, 'M5.3'
CONTRACT_PINS = ('preregistration', 'preregistration_confirmation', 'cache_receipt', 'method_freeze')
RELOAD_SCRIPT = 'scripts/reload_m53_checkpoint.py'


def load_authorization(path, expected_sha256, run_id, actor):
    """Accept only the exact, approved authorization whose hash was pinned outside the file."""
    if not isinstance(expected_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise Refused('An external 64-character authorization SHA-256 pin is required')
    if sha(path) != expected_sha256:
        raise Refused('Authorization differs from the external pin')
    auth = _read(path)
    approval = auth.get('approval', {})
    if auth.get('status') != 'APPROVED' or any(
            not str(approval.get(key, 'PENDING')).strip() or str(approval.get(key, 'PENDING')).startswith('PENDING')
            for key in ('approval_text', 'approved_utc')):
        raise Refused('Authorization is not approved by its approver')
    if auth.get('run_id') != run_id or not RUN_ID.fullmatch(run_id):
        raise Refused('Run ID differs from the approved authorization')
    if str(auth.get('actor', 'PENDING')).startswith('PENDING') or auth['actor'] != actor:
        raise Refused('Actor differs from the one named in the approved authorization')
    return auth


def _replace_argument(arguments, flag, value):
    swapped = list(arguments)
    swapped[swapped.index(flag)+1] = value
    return swapped


def _events(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def check_seed_contract(root, auth):
    """Prove the M5.1/M5.2/M4.3 pins hold and that this run is its seed-1 counterpart with only the seed changed."""
    contract = auth['seed_contract']
    for name in CONTRACT_PINS:
        if sha(root/contract[name]['path']) != contract[name]['sha256']:
            raise Refused(f'{name} differs from its pin')
    method, seed = auth['method']['name'], auth['method'].get('seed')
    if (seed, contract.get('seed'), auth.get('task_id')) != (SEED, SEED, TASK):
        raise Refused(f'M5.3 runs seed {SEED} only')
    plan = _read(root/contract['preregistration']['path'])
    if not any(row['seed'] == SEED and row['task'].startswith(TASK) and method in row['methods']
               for row in plan['seed_matrix']) or plan['matched_run_rule']['only_seed_change'] != 'training.seed':
        raise Refused('The preregistered seed matrix does not assign this seed and method to M5.3')
    from qpaf.m24.config import load_config
    config_path = root/auth['config']['path']
    if sha(config_path) != auth['config']['file_sha256']:
        raise Refused('Seed config differs from its pin')
    receipt = _read(root/contract['cache_receipt']['path'])
    rows = [row for row in receipt['matrix'] if (row['seed'], row['method']) == (SEED, method)]
    if receipt.get('status') != 'TECHNICAL_PASS' or len(rows) != 1 or load_config(config_path) != rows[0]['config'] \
            or rows[0]['gate_granularity'] != auth['method']['gate_granularity']:
        raise Refused('Seed config is not the M5.2 receipt config for this seed and method')
    freeze = _read(root/contract['method_freeze']['path'])
    drifted = [path for path, digest in freeze['source_sha256'].items() if sha(root/path) != digest]
    if drifted or freeze['source_sha256'] != receipt['frozen_method_sources_sha256']:
        raise Refused(f'Frozen method sources differ from the M4.3 freeze: {drifted}')
    reference = contract['seed_reference']
    if sha(root/reference['authorization_path']) != reference['authorization_sha256']:
        raise Refused('Seed-1 authorization differs from its pin')
    first = _read(root/reference['authorization_path'])
    if (first.get('run_id'), first['method']['name'], first['method']['seed']) != (
            reference['run_id'], method, freeze['frozen_method']['seed']):
        raise Refused('Seed reference is not the seed-1 run of the same method')
    if first['config']['file_sha256'] != freeze['frozen_method']['config']['file_sha256']:
        raise Refused('Seed-1 run did not use the frozen config')
    for section in ('sealed_inputs', 'metric', 'runtime', 'hardware'):
        if auth.get(section) != first.get(section):
            raise Refused(f'{section} differs from the seed-1 run')
    if any(auth['limits'].get(key) != first['limits'].get(key) for key in SHARED_LIMITS):
        raise Refused('limits differ from the seed-1 run')
    command, other = auth['command'], first['command']
    expected = _replace_argument(_replace_argument(other['arguments'], '--config', auth['config']['path']),
                                 '--output', f'{OUTPUT_ROOT}/<run_id>')
    if (command['interpreter'], command['script'], command['forbidden_arguments']) != (
            other['interpreter'], other['script'], other['forbidden_arguments']) or command['arguments'] != expected:
        raise Refused('command differs from the seed-1 command in more than the config and output root')
    attempt = root/reference['attempt_path']
    for filename, key in (('data_manifest.json', 'data_manifest_sha256'), ('provenance.json', 'provenance_sha256')):
        if sha(attempt/filename) != reference[key]:
            raise Refused(f'Seed-1 {filename} differs from its pin')
    return attempt


def check_comparator(root, auth):
    """Return the seed-2 QARF attempt after proving it was accepted and that this QPAF run differs only in method."""
    pinned = auth['comparator']
    path = root/pinned['authorization_path']
    if sha(path) != pinned['authorization_sha256']:
        raise Refused('QARF authorization differs from its pin')
    qarf = _read(path)
    if qarf.get('status') != 'APPROVED' or qarf.get('run_id') != pinned['run_id'] or qarf['method']['name'] != 'QARF':
        raise Refused('QARF authorization is not the approved seed-2 comparator run')
    accepted = [e for e in _events(root/pinned['acceptance']['events_path'])
                if e.get('registry_event_id') == pinned['acceptance']['registry_event_id']]
    if len(accepted) != 1 or (accepted[0].get('event_type'), accepted[0].get('registry_status'),
                              accepted[0].get('run_id'), accepted[0].get('authorization_manifest_sha256')) != (
            'ACCEPTANCE_RECORDED', 'PASS', pinned['run_id'], pinned['authorization_sha256']):
        raise Refused('Seed-2 QARF run has no accepted independent review')
    if sha(root/accepted[0]['verification_ref']) != accepted[0]['verification_sha256']:
        raise Refused('QARF review report differs from the hash in its acceptance event')
    for section in (*SHARED, 'seed_contract'):
        if section == 'seed_contract':
            mine = {k: v for k, v in auth[section].items() if k != 'seed_reference'}
            theirs = {k: v for k, v in qarf[section].items() if k != 'seed_reference'}
        else:
            mine, theirs = auth.get(section), qarf.get(section)
        if mine != theirs:
            raise Refused(f'{section} differs from the matched QARF authorization')
    if any(auth['limits'].get(key) != qarf['limits'].get(key) for key in SHARED_LIMITS):
        raise Refused('limits differ from the matched QARF authorization')
    if auth['method'].get('seed') != qarf['method'].get('seed'):
        raise Refused('seed differs from the matched QARF authorization')
    methods = _read(root/auth['sealed_inputs']['run_path']/'inputs/matched.json')['methods']
    name = auth['method']['name']
    if name != 'QPAF' or methods.get(name, {}).get('gate_granularity') != auth['method'].get('gate_granularity'):
        raise Refused('method is not the matched counterpart named in the sealed matched.json')
    command, other = auth['command'], qarf['command']
    if (command['interpreter'], command['script'], command['forbidden_arguments']) != (
            other['interpreter'], other['script'], other['forbidden_arguments']) or \
            command['arguments'] != _replace_argument(other['arguments'], '--method', name):
        raise Refused('command differs from the matched QARF command in more than the method')
    attempt = root/pinned['attempt_path']
    for filename, key in (('data_manifest.json', 'data_manifest_sha256'), ('provenance.json', 'provenance_sha256')):
        if sha(attempt/filename) != pinned[key]:
            raise Refused(f'QARF {filename} differs from its pin')
    return attempt


def check_attempt(namespace, auth, head, reference, comparator=None):
    """Problems found in the finished attempt, including any row or input that differs from the matched runs."""
    problems = check_single_attempt(namespace, auth, head)
    if problems:
        return problems
    attempt = next(p for p in (namespace/auth['method']['name']).glob('*') if p.is_dir())
    try:
        if sha(attempt/'data_manifest.json') != auth['seed_contract']['seed_reference']['data_manifest_sha256']:
            problems.append('data_manifest.json differs from the seed-1 run (rows, order or counts)')
        inputs = _read(attempt/'provenance.json').get('inputs')
        expected = {**_read(reference/'provenance.json')['inputs'], 'config': auth['config']['file_sha256']}
        if inputs != expected:
            problems.append('the run consumed inputs other than the seed-1 inputs with the seed-2 config')
        if comparator is not None and inputs != _read(comparator/'provenance.json').get('inputs'):
            problems.append('the run consumed inputs other than those of the seed-2 QARF run')
        summary = _read(attempt/'summary.json')
        if (summary.get('method'), summary.get('granularity'), summary.get('seed')) != (
                auth['method']['name'], auth['method']['gate_granularity'], auth['method']['seed']):
            problems.append('summary method, granularity or seed differs from the authorization')
    except (OSError, ValueError, AttributeError, KeyError) as exc:
        problems.append(f'unreadable outputs: {exc}')
    return problems


def fresh_reload(root, interpreter, auth, attempt):
    """Reload both checkpoints in a separate interpreter and return its report; raise on any failure."""
    command = [str(interpreter), RELOAD_SCRIPT, '--attempt', attempt.relative_to(root).as_posix(),
               '--config', auth['config']['path'], '--method', auth['method']['name'],
               '--seal', auth['sealed_inputs']['run_path']]
    done = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf-8', env=_environment())
    if done.returncode:
        raise RuntimeError(f'fresh-process reload failed (exit {done.returncode}): {done.stderr.strip()[-500:]}')
    report = json.loads(done.stdout)
    if report.get('status') != 'PASS' or report.get('worker_pid') == os.getpid():
        raise RuntimeError('fresh-process reload did not pass in a separate process')
    return report


def _namespace(root, auth, run_id):
    path = (root/auth['output']['namespace_root'].replace('<run_id>', run_id)).resolve()
    if not path.is_relative_to((root/OUTPUT_ROOT).resolve()):
        raise Refused(f'Output namespace must be inside {OUTPUT_ROOT}')
    return path


def supervise(root, authorization_path, expected_sha256, run_id, *, actor):
    """Run the approved command exactly once. Refusals leave nothing behind; later outcomes leave a marker."""
    root = Path(root).resolve()
    auth = load_authorization(authorization_path, expected_sha256, run_id, actor)
    command, interpreter = build_command(root, auth, run_id)
    namespace = _namespace(root, auth, run_id)
    head = check_git(root, auth['git'])
    if namespace.exists():
        raise AlreadyAttempted(f'Output namespace already exists: {namespace}')
    try:
        reference = check_seed_contract(root, auth)
        comparator = check_comparator(root, auth) if auth['method']['name'] == 'QPAF' else None
    except Refused:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Refused(f'Seed contract or comparator could not be checked: {exc}') from None
    verify_seal(root, interpreter, auth['sealed_inputs'])
    try:
        namespace.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise AlreadyAttempted(f'Output namespace already exists: {namespace}') from None
    started = time.monotonic()
    _write(namespace/'_ATTEMPTED.json', {'run_id': run_id, 'actor': actor, 'git_head': head,
                                         'authorization_sha256': expected_sha256, 'started_utc': _now(),
                                         'command': command, 'seed': auth['method']['seed'],
                                         'comparator_run_id': (auth.get('comparator') or {}).get('run_id')})
    code, attempt, reload = None, None, None
    try:
        code, reason = _execute(root, command, namespace, auth['limits']['wall_time_seconds'])
        if reason is None:
            problems = check_attempt(namespace, auth, head, reference, comparator)
            reason = '; '.join(problems) if problems else None
            if not problems:
                stage = next(p for p in (namespace/auth['method']['name']).glob('*') if p.is_dir())
                reload = fresh_reload(root, interpreter, auth, stage)
                attempt = stage.name
    except Exception as exc:
        reason = f'supervisor_error: {type(exc).__name__}: {exc}'
    result = {'status': 'FAILED' if reason else 'SUCCESS', 'reason': reason, 'run_id': run_id, 'exit_code': code,
              'wall_seconds': round(time.monotonic()-started, 3), 'attempt': attempt, 'namespace': str(namespace)}
    record = {'run_id': run_id, 'actor': actor, 'exit_code': code, 'finished_utc': _now(),
              'wall_seconds': result['wall_seconds'], 'authorization_sha256': expected_sha256}
    if reason:
        _write(namespace/'_FAILED.json', {**record, 'reason': reason})
    else:
        stage = namespace/auth['method']['name']/attempt
        _write(namespace/'_SUCCESS.json', {**record, 'attempt': attempt, 'receipt_sha256': sha(stage/'receipt.json'),
                                           'summary_sha256': sha(stage/'summary.json'),
                                           'fresh_process_reload': reload})
    return result
