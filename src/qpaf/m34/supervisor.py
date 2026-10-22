"""Run the authorized M3.4 QPAF command once, matched to the accepted M3.2 QARF run.

The single-attempt mechanics (pin, git state, seal check, wall limit, markers) are the M3.2 ones,
reused unchanged so that the M3.2 source pinned by its approved authorization stays byte-stable.
This module adds what makes the run matched: the QARF run must carry an accepted independent review,
the QPAF authorization may differ from the QARF one only in the method, and the finished QPAF run must
have consumed exactly the inputs and rows the QARF run consumed.
"""
import json
from pathlib import Path
import re
import time

from qpaf.m32.supervisor import (AlreadyAttempted, Refused, _execute, _now, _read, _write, build_command,
                                 check_attempt as check_single_attempt, check_git, sha, verify_seal)

__all__ = ['AlreadyAttempted', 'Refused', 'load_authorization', 'check_comparator', 'check_attempt', 'supervise']

RUN_ID = re.compile(r'RUN-QPAF-M3_4-MTH-001-\d{8}T\d{6}Z-A\d{2}')
OUTPUT_ROOT = 'results/m3.4'
# Sections that matched.json requires to be identical for QARF and QPAF; only gate_granularity differs.
SHARED = ('sealed_inputs', 'config', 'metric', 'runtime', 'hardware')
SHARED_LIMITS = ('wall_time_seconds', 'paid_compute_cost_cap', 'invocations', 'automatic_retries')


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


def _matched_arguments(arguments, method):
    """The QARF command with only the method and the output root replaced."""
    swapped = list(arguments)
    swapped[swapped.index('--method')+1] = method
    swapped[swapped.index('--output')+1] = f'{OUTPUT_ROOT}/<run_id>'
    return swapped


def check_comparator(root, auth):
    """Return the QARF comparator after proving it was accepted and that this run differs only in method."""
    pinned = auth['comparator']
    path = root/pinned['authorization_path']
    if sha(path) != pinned['authorization_sha256']:
        raise Refused('QARF authorization differs from its pin')
    qarf = _read(path)
    if qarf.get('status') != 'APPROVED' or qarf.get('run_id') != pinned['run_id']:
        raise Refused('QARF authorization is not the approved comparator run')
    events = [json.loads(line) for line in (root/pinned['acceptance']['events_path']).read_text(
        encoding='utf-8').splitlines() if line.strip()]
    accepted = [e for e in events if e.get('registry_event_id') == pinned['acceptance']['registry_event_id']]
    if len(accepted) != 1 or (accepted[0].get('event_type'), accepted[0].get('registry_status'),
                              accepted[0].get('run_id'), accepted[0].get('authorization_manifest_sha256')) != (
            'ACCEPTANCE_RECORDED', 'PASS', pinned['run_id'], pinned['authorization_sha256']):
        raise Refused('QARF run has no accepted independent review (M3.3 PASS)')
    if sha(root/accepted[0]['verification_ref']) != accepted[0]['verification_sha256']:
        raise Refused('M3.3 validation report differs from the hash in its acceptance event')
    for section in SHARED:
        if auth.get(section) != qarf.get(section):
            raise Refused(f'{section} differs from the matched QARF authorization')
    if any(auth['limits'].get(key) != qarf['limits'].get(key) for key in SHARED_LIMITS):
        raise Refused('limits differ from the matched QARF authorization')
    if auth['method'].get('seed') != qarf['method'].get('seed'):
        raise Refused('seed differs from the matched QARF authorization')
    methods = _read(root/auth['sealed_inputs']['run_path']/'inputs/matched.json')['methods']
    name = auth['method']['name']
    if name == qarf['method']['name'] or methods.get(name, {}).get('gate_granularity') != auth['method'].get(
            'gate_granularity'):
        raise Refused('method is not the matched counterpart named in the sealed matched.json')
    command, other = auth['command'], qarf['command']
    if (command['interpreter'], command['script'], command['forbidden_arguments']) != (
            other['interpreter'], other['script'], other['forbidden_arguments']) or \
            command['arguments'] != _matched_arguments(other['arguments'], name):
        raise Refused('command differs from the matched QARF command in more than the method')
    attempt = root/pinned['attempt_path']
    for filename, key in (('data_manifest.json', 'data_manifest_sha256'), ('provenance.json', 'provenance_sha256')):
        if sha(attempt/filename) != pinned[key]:
            raise Refused(f'QARF {filename} differs from its pin')
    return attempt


def check_attempt(namespace, auth, head, comparator):
    """Problems found in the finished attempt, including any row or input that differs from the QARF run."""
    problems = check_single_attempt(namespace, auth, head)
    if problems:
        return problems
    attempt = next(p for p in (namespace/auth['method']['name']).glob('*') if p.is_dir())
    try:
        if sha(attempt/'data_manifest.json') != auth['comparator']['data_manifest_sha256']:
            problems.append('data_manifest.json differs from the QARF run (rows, order or counts)')
        if _read(attempt/'provenance.json').get('inputs') != _read(comparator/'provenance.json').get('inputs'):
            problems.append('the run consumed inputs other than those of the QARF run')
        summary = _read(attempt/'summary.json')
        if (summary.get('method'), summary.get('granularity'), summary.get('seed')) != (
                auth['method']['name'], auth['method']['gate_granularity'], auth['method']['seed']):
            problems.append('summary method, granularity or seed differs from the authorization')
    except (OSError, ValueError, AttributeError) as exc:
        problems.append(f'unreadable outputs: {exc}')
    return problems


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
        comparator = check_comparator(root, auth)
    except Refused:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Refused(f'QARF comparator could not be checked: {exc}') from None
    verify_seal(root, interpreter, auth['sealed_inputs'])
    try:
        namespace.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise AlreadyAttempted(f'Output namespace already exists: {namespace}') from None
    started = time.monotonic()
    _write(namespace/'_ATTEMPTED.json', {'run_id': run_id, 'actor': actor, 'git_head': head,
                                         'authorization_sha256': expected_sha256, 'started_utc': _now(),
                                         'command': command, 'comparator_run_id': auth['comparator']['run_id']})
    code, attempt = None, None
    try:
        code, reason = _execute(root, command, namespace, auth['limits']['wall_time_seconds'])
        if reason is None:
            problems = check_attempt(namespace, auth, head, comparator)
            reason = '; '.join(problems) if problems else None
            attempt = next((namespace/auth['method']['name']).glob('*/')).name if not problems else None
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
                                           'summary_sha256': sha(stage/'summary.json')})
    return result
