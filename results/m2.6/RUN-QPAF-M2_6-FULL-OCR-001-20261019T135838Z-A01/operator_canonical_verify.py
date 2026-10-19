"""Run the unchanged full verifier with progress and durable exit diagnostics."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m11 import artifacts
from qpaf.m26 import bundle

RUN = ROOT / 'results/m2.6/RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01'
WORK = ROOT / '.superpowers/m26'


def worker():
    state = {'stage': 'starting', 'hash_calls_completed': 0,
             'page_replays_completed': 0, 'last_hashed_path': None}
    stop = threading.Event()
    started = time.monotonic()

    def progress():
        while not stop.wait(15):
            print(json.dumps({**state, 'elapsed_seconds': round(time.monotonic() - started, 1)}), flush=True)

    thread = threading.Thread(target=progress, daemon=True)
    thread.start()
    original_digest = artifacts.digest
    original_manifest = bundle.verify_manifest
    original_records = bundle.validate_records
    original_resolve = bundle.resolve_page

    def logged_digest(path):
        result = original_digest(path)
        state['hash_calls_completed'] += 1
        state['last_hashed_path'] = str(path)
        return result

    def logged_manifest(*args, **kwargs):
        state['stage'] = 'full_file_manifest'
        result = original_manifest(*args, **kwargs)
        print(json.dumps({'event': 'FULL_FILE_MANIFEST_PASSED', 'files': len(args[1])}), flush=True)
        return result

    def logged_records(*args, **kwargs):
        state['stage'] = 'page_artifacts_images_and_policy_replay'
        result = original_records(*args, **kwargs)
        print(json.dumps({'event': 'PAGE_VALIDATION_PASSED', 'pages': result['pages']}), flush=True)
        state['stage'] = 'final_metadata_and_handover'
        return result

    def logged_resolve(*args, **kwargs):
        result = original_resolve(*args, **kwargs)
        state['page_replays_completed'] += 1
        return result

    # These wrappers only report progress; every original call still runs.
    artifacts.digest = logged_digest
    bundle.digest = logged_digest
    bundle.verify_manifest = logged_manifest
    bundle.validate_records = logged_records
    bundle.resolve_page = logged_resolve
    try:
        source = artifacts.read_json(RUN / 'source.json')
        config = artifacts.read_json(RUN / 'resolved_config.json')
        assert artifacts.source_provenance(ROOT, config['modal']['requirements_file'])['digest'] == source['digest']
        result = bundle.verify_bundle(RUN)
        receipt = RUN / 'verification.json'
        if receipt.exists():
            assert artifacts.read_json(receipt) == result, 'Existing verification receipt differs'
        else:
            artifacts.write_json(receipt, result)
        print(json.dumps({'event': 'VERIFIED_FULL_OCR_BUNDLE', 'result': result}), flush=True)
        print('Saved full OCR bundle: ' + str(RUN / 'output'), flush=True)
    finally:
        stop.set()
        thread.join(timeout=2)


def supervise():
    stdout = WORK / 'canonical-verify.log'
    stderr = WORK / 'canonical-verify.stderr.log'
    exit_path = WORK / 'canonical-verify-exit.json'
    if stdout.exists() or stderr.exists() or exit_path.exists():
        raise RuntimeError('Diagnostic attempt already exists; refusing to overwrite it')
    started = artifacts.utc()
    with stdout.open('x', encoding='utf-8') as output, stderr.open('x', encoding='utf-8') as errors:
        process = subprocess.Popen([sys.executable, '-X', 'utf8', '-X', 'faulthandler',
                                    str(Path(__file__).resolve()), '--worker'],
                                   cwd=ROOT, stdout=output, stderr=errors)
        artifacts.write_json(WORK / 'canonical-verify-launch.json', {
            'supervisor_pid': os.getpid(), 'worker_pid': process.pid, 'started_utc': started,
            'source_script': str(Path(__file__).resolve()), 'run_id': RUN.name,
            'mode': 'canonical_verify_bundle_with_call_through_progress_wrappers'})
        code = process.wait()
    artifacts.write_json(exit_path, {
        'started_utc': started, 'ended_utc': artifacts.utc(), 'worker_exit_code': code,
        'verification_receipt_exists': (RUN / 'verification.json').is_file(),
        'stdout_sha256': artifacts.digest(stdout), 'stderr_sha256': artifacts.digest(stderr)})
    return code


if __name__ == '__main__':
    if '--worker' in sys.argv:
        worker()
    else:
        sys.exit(supervise())
