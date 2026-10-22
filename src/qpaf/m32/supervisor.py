"""Run the authorized M3.2 command once: pinned approval, git state, seal check, wall limit, markers."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

RUN_ID = re.compile(r'RUN-QPAF-M3_2-MTH-001-\d{8}T\d{6}Z-A\d{2}')
REQUIRED = ('status.json', 'receipt.json', 'hashes.csv', 'summary.json', 'resolved_config.json',
            'provenance.json', 'data_manifest.json')


class Refused(ValueError):
    """The run must not start; no attempt has been consumed."""


class AlreadyAttempted(Refused):
    """The output namespace exists, so an attempt was already made or the path is taken."""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _environment():
    return {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}


def _git(root, *args, check=True):
    done = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, encoding='utf-8')
    if check and done.returncode:
        raise Refused(f'git {args[0]} failed: {done.stderr.strip()}')
    return done


def load_authorization(path, expected_sha256, run_id):
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
    return auth


def build_command(root, auth, run_id):
    command = auth['command']
    arguments = [argument.replace('<run_id>', run_id) for argument in command['arguments']]
    if any(argument.split('=')[0] in command['forbidden_arguments'] for argument in arguments):
        raise Refused('Authorization command contains a forbidden argument')
    interpreter = Path(command['interpreter'])
    interpreter = interpreter if interpreter.is_absolute() else root/interpreter
    return [str(interpreter), command['script'], *arguments], interpreter


def check_git(root, git):
    """Return HEAD after proving it is the approved base plus only allowed paths, with a clean tree."""
    head = _git(root, 'rev-parse', 'HEAD').stdout.strip()
    if _git(root, 'merge-base', '--is-ancestor', git['code_base_commit'], head, check=False).returncode:
        raise Refused('HEAD does not descend from the authorized base commit')
    changed = [p for p in _git(root, 'diff', '--name-only', '-z', git['code_base_commit'], head).stdout.split('\0') if p]
    outside = [p for p in changed if not any(p.startswith(prefix) for prefix in git['allowed_diff_from_base'])]
    if outside:
        raise Refused(f'Changes since the base commit are outside the authorized paths: {outside}')
    status = _git(root, 'status', '--porcelain', '-z', '--untracked-files=all').stdout
    for entry in (e for e in status.split('\0') if e):
        if entry[:2] != '??':
            raise Refused(f'A tracked file is modified: {entry[3:]}')
        if entry[3:] not in git['allowed_untracked']:
            raise Refused(f'An untracked file is not on the allowlist: {entry[3:]}')
    return head


def verify_seal(root, interpreter, sealed):
    command = [str(interpreter), 'scripts/seal_m31_inputs.py', '--verify', sealed['run_path'],
               '--expected-manifest-sha256', sealed['manifest_sha256']]
    done = subprocess.run(command, cwd=root, capture_output=True, text=True, env=_environment())
    if done.returncode:
        raise Refused(f'M3.1 seal verification failed (exit {done.returncode})')


def _namespace(root, auth, run_id):
    path = (root/auth['output']['namespace_root'].replace('<run_id>', run_id)).resolve()
    if not path.is_relative_to((root/'results/m3.2').resolve()):
        raise Refused('Output namespace must be inside results/m3.2')
    return path


def _kill_tree(process):
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _execute(root, command, namespace, seconds):
    """Return (exit_code, reason); reason is None only for a clean exit within the wall limit."""
    group = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    with (namespace/'supervisor.log').open('xb') as log:
        process = subprocess.Popen(command, cwd=root, stdout=log, stderr=subprocess.STDOUT,
                                   env=_environment(), **group)
        try:
            code = process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            return None, 'wall_time_exceeded'
    return code, None if code == 0 else f'runner_exit_{code}'


def check_attempt(namespace, auth, head):
    """Problems found in the finished attempt; an empty list means every post-run check passed."""
    stage = namespace/auth['method']['name']
    problems = []
    extra = sorted(p.name for p in namespace.iterdir() if p.name not in ('_ATTEMPTED.json', 'supervisor.log', stage.name))
    if extra:
        problems.append(f'unexpected entries in the namespace: {extra}')
    attempts = [p for p in stage.glob('*') if p.is_dir()]
    if len(attempts) != 1:
        return problems+[f'expected exactly one attempt directory, found {len(attempts)}']
    attempt = attempts[0]
    if sorted(p.name for p in stage.iterdir() if p != attempt) not in ([], ['complete.json']):
        problems.append('unexpected entries next to the attempt directory')
    missing = [name for name in REQUIRED if not (attempt/name).is_file()]
    if missing or not (stage/'complete.json').is_file():
        return problems+[f'missing outputs: {missing+([] if (stage/"complete.json").is_file() else ["complete.json"])}']
    try:
        if _read(attempt/'status.json').get('status') != 'completed':
            problems.append('the runner did not report status completed')
        if sha(attempt/'resolved_config.json') != auth['config']['expected_resolved_config_json_sha256']:
            problems.append('resolved_config.json differs from the authorized config')
        provenance = _read(attempt/'provenance.json')
        if provenance.get('config_sha256') != auth['config']['expected_provenance_config_object_hash']:
            problems.append('provenance config hash differs from the authorized config')
        if provenance.get('source', {}).get('git_commit') != head:
            problems.append('the run recorded a different git commit than the supervised HEAD')
        if _read(attempt/'summary.json').get('reload_parity', {}).get('passed') is not True:
            problems.append('checkpoint reload parity did not pass')
        if _read(attempt/'data_manifest.json').get('test', {}).get('state') != 'not_opened':
            problems.append('the test split was not reported as not_opened')
        if _read(stage/'complete.json').get('attempt') != attempt.name:
            problems.append('complete.json names a different attempt')
    except (OSError, ValueError, AttributeError) as exc:
        problems.append(f'unreadable outputs: {exc}')
    return problems


def supervise(root, authorization_path, expected_sha256, run_id, *, actor):
    """Run the approved command exactly once. Refusals leave nothing behind; later outcomes leave a marker."""
    root = Path(root).resolve()
    auth = load_authorization(authorization_path, expected_sha256, run_id)
    command, interpreter = build_command(root, auth, run_id)
    namespace = _namespace(root, auth, run_id)
    head = check_git(root, auth['git'])
    if namespace.exists():
        raise AlreadyAttempted(f'Output namespace already exists: {namespace}')
    verify_seal(root, interpreter, auth['sealed_inputs'])
    try:
        namespace.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise AlreadyAttempted(f'Output namespace already exists: {namespace}') from None
    started = time.monotonic()
    _write(namespace/'_ATTEMPTED.json', {'run_id': run_id, 'actor': actor, 'git_head': head,
                                         'authorization_sha256': expected_sha256, 'started_utc': _now(),
                                         'command': command})
    code, attempt = None, None
    try:
        code, reason = _execute(root, command, namespace, auth['limits']['wall_time_seconds'])
        if reason is None:
            problems = check_attempt(namespace, auth, head)
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
