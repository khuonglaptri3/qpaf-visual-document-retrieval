"""Demonstrate that Modal's hard memory limit OOM-kills the M3.6 GPU function shape.

Two controls run in fresh containers under memory=(4096, 4096): one touches 2 GiB
and must complete; one touches 4.6 GiB and must be killed with an attributable
out-of-memory error. Only that pair turns the A02/A03 completions into
provider-enforced upper bounds. It never measures or claims an exact peak.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
PROBE_LIMIT_MIB = 4096
BELOW_TARGET_MIB = 2048
ABOVE_TARGET_MIB = 4608
HOLD_SECONDS = 5
WATCHDOG_SECONDS = 600
OOM_MARKERS = ('oom', 'out of memory', 'memory limit', 'exit code 137')
# Khương's verbatim approval; empty until recorded, so --execute refuses.
APPROVAL_TEXT = ''
DEMONSTRATED = 'ENFORCEMENT_DEMONSTRATED'
NOT_DEMONSTRATED = 'ENFORCEMENT_NOT_DEMONSTRATED'
INCONCLUSIVE = 'INCONCLUSIVE'


def touch_allocation(target_mib):
    import numpy as np
    block = np.empty(target_mib * 2**20, dtype=np.uint8)
    block.fill(1)  # commit every page, not just reserve address space
    try:
        import resource
        maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    except ImportError:
        maxrss = 0
    return {'allocated_bytes': int(block.nbytes), 'ru_maxrss_bytes': maxrss}


def oom_attributed(error_text, provider_stats):
    reasons = [error_text or '']
    if provider_stats:
        reasons += [str(r) for r in provider_stats.get('exit_reasons', [])]
    text = ' '.join(reasons).lower()
    return any(marker in text for marker in OOM_MARKERS)


def classify_controls(below, above, provider_stats):
    # A completed above-limit attempt, including a provider retry, defeats the claim.
    if above['status'] == 'COMPLETED' or provider_stats.get('input_success_count', 0) > 1:
        return NOT_DEMONSTRATED
    if below['status'] != 'COMPLETED' or not oom_attributed(above.get('error_text') or '', provider_stats):
        return INCONCLUSIVE
    return DEMONSTRATED


def memory_bound_verdict(classification, runs):
    bounded = {}
    for name, run in runs.items():
        ok = classification == DEMONSTRATED and run['success_marker'] and run['failed_calls'] == 0
        bounded[name] = {'bound': 'BELOW_LIMIT' if ok else 'UNBOUNDED', 'limit_mib': run['limit_mib']}
    resolved = classification == DEMONSTRATED and all(r['bound'] == 'BELOW_LIMIT' for r in bounded.values())
    return {'classification': classification,
            'issue_status': 'RESOLVED_BY_ENFORCED_BOUND' if resolved else 'OPEN',
            'runs': bounded, 'exact_peak_available': False,
            'claim_scope': 'Provider-enforced upper bound under Modal hard memory limit; not a peak'}


def probe_body(target_mib):
    """Runs inside the Modal container: same CUDA import footprint, then a touched allocation."""
    import torch
    from scripts.m36_memory_telemetry import snapshot
    limit = PROBE_LIMIT_MIB * 2**20
    torch.cuda.init()
    before = snapshot('probe_before', limit)
    allocation = touch_allocation(target_mib)
    time.sleep(HOLD_SECONDS)
    return {'status': 'COMPLETED', 'target_mib': target_mib, 'error_type': None, 'error_text': None,
            'in_sandbox': {'allocation': allocation, 'before': before,
                           'after': snapshot('probe_after', limit)}}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def build_app():
    import modal
    from scripts.run_m36_gpu import BASE_IMAGE, ENV
    if modal.__version__ != '1.5.5':
        raise ValueError('Modal SDK pin differs')
    image = (modal.Image.from_registry(BASE_IMAGE)
             .run_commands('timeout 240s python -m pip install --no-cache-dir torch==2.11.0+cu126 '
                           '--index-url https://download.pytorch.org/whl/cu126',
                           'timeout 90s python -m pip install --no-cache-dir '
                           'numpy==2.5.4 pandas==3.0.6 pyarrow==26.0.0')
             .env(ENV).workdir('/workspace')
             .add_local_file(ROOT/'scripts/m36_memory_probe.py', '/workspace/scripts/m36_memory_probe.py',
                             copy=True)
             .add_local_file(ROOT/'scripts/m36_memory_telemetry.py',
                             '/workspace/scripts/m36_memory_telemetry.py', copy=True))
    app = modal.App('qpaf-m36-memory-probe', include_source=False)

    @app.function(image=image, gpu='A10', cpu=(2., 2.), memory=(PROBE_LIMIT_MIB, PROBE_LIMIT_MIB),
                  timeout=300, startup_timeout=120, retries=0, max_containers=1,
                  min_containers=0, buffer_containers=0, scaledown_window=2,
                  single_use_containers=True, serialized=True,
                  block_network=True, restrict_modal_access=True)
    def probe(target_mib):
        from scripts.m36_memory_probe import probe_body
        return probe_body(target_mib)

    return app, image, probe


def check_authorization(auth, output):
    if (not APPROVAL_TEXT or
            auth['status'] != 'AUTHORIZED_BY_KHUONG_WORKING_SESSION' or
            auth['source_commit'] != git('rev-parse', 'HEAD') or
            git('status', '--porcelain', '--untracked-files=no') or
            auth['invocations'] != 2 or auth['automatic_retries'] != 0 or
            auth['output_path'] != output.relative_to(ROOT).as_posix() or
            auth['approval']['text'] != APPROVAL_TEXT or
            auth['memory_limit_mib'] != PROBE_LIMIT_MIB):
        raise ValueError('source, authorization, namespace or invocation contract differs')


def execute(authorization, expected_authorization_sha256, output):
    from scripts.m36_gpu_worker import read, sha, write_new
    if sha(authorization) != expected_authorization_sha256:
        raise ValueError('external authorization SHA256 pin differs')
    check_authorization(read(authorization), output)
    app, image, probe = build_app()
    output.mkdir(parents=True, exist_ok=False)
    write_new(output/'_ATTEMPTED.json', {'authorization_sha256': expected_authorization_sha256,
                                      'started_utc': datetime.now(timezone.utc).isoformat(),
                                      'invocation_limit': 2, 'automatic_retries': 0})
    started = time.monotonic()

    def watchdog():
        write_new(output/'_WATCHDOG.json', {'elapsed_seconds': time.monotonic()-started,
                                           'status': 'KILLED_WALL_TIME_LIMIT', 'app_id': app.app_id})
        try:
            if app.app_id:
                subprocess.run([sys.executable, '-m', 'modal', 'app', 'stop', '--yes', app.app_id], timeout=30)
        finally:
            os._exit(124)

    timer = threading.Timer(WATCHDOG_SECONDS, watchdog)
    timer.daemon = True
    timer.start()
    import modal
    try:
        with modal.enable_output(), app.run(detach=False):
            write_new(output/'runtime_binding.json', {
                'app_id': app.app_id, 'image_id': image.object_id, 'function_id': probe.object_id,
                'authorization_sha256': expected_authorization_sha256,
                'source_commit': git('rev-parse', 'HEAD'),
                'memory_request_and_limit_mib': PROBE_LIMIT_MIB,
                'bound_utc': datetime.now(timezone.utc).isoformat(), 'gpu_invocations_before_binding': 0})
            for name, target in (('below', BELOW_TARGET_MIB), ('above', ABOVE_TARGET_MIB)):
                try:
                    record = probe.remote(target)
                except Exception as exc:  # the above-limit control is expected to land here
                    record = {'status': 'FAILED', 'target_mib': target, 'error_type': type(exc).__name__,
                              'error_text': str(exc), 'in_sandbox': None}
                record['finished_utc'] = datetime.now(timezone.utc).isoformat()
                write_new(output/f'{name}.json', record)
        write_new(output/'_SUCCESS.json', {'status': 'EXECUTION_COMPLETE',
                  'below_sha256': sha(output/'below.json'), 'above_sha256': sha(output/'above.json'),
                  'elapsed_seconds_including_build': time.monotonic()-started,
                  'labels_deserialized': False, 'training_executed': False})
    except BaseException as exc:
        write_new(output/'_FAILURE.json', {'error_type': type(exc).__name__, 'message': str(exc),
                  'elapsed_seconds': time.monotonic()-started, 'app_id': app.app_id,
                  'automatic_retry_performed': False})
        raise
    finally:
        timer.cancel()


def classify(output, provider_stats_path, runs_path, review_output):
    from scripts.m36_gpu_worker import read, sha, write_new
    below, above = read(output/'below.json'), read(output/'above.json')
    provider_stats, runs = read(provider_stats_path), read(runs_path)
    verdict = memory_bound_verdict(classify_controls(below, above, provider_stats), runs)
    prior = read(ROOT/'evidence/revisions/m3.6-004/technical_review.json')
    prior_pass = (prior['integrity_verdict'] == 'PASS' and
                  prior['operational_latency_cuda_parity_verdict'] == 'PASS')
    review = {'schema_version': 1, 'task_id': 'M3.6',
              'recorded_utc': datetime.now(timezone.utc).isoformat(),
              'technical_verdict': 'PASS' if prior_pass and verdict['issue_status'] ==
              'RESOLVED_BY_ENFORCED_BOUND' else 'BLOCKED',
              'memory_issue_status': verdict['issue_status'], 'classification': verdict['classification'],
              'runs': verdict['runs'], 'exact_peak_available': False, 'claim_scope': verdict['claim_scope'],
              'controls': {'below': {k: below.get(k) for k in ('status', 'target_mib', 'error_type')},
                           'above': {k: above.get(k) for k in ('status', 'target_mib', 'error_type',
                                                               'error_text')}},
              'below_in_sandbox_ru_maxrss_bytes': ((below.get('in_sandbox') or {}).get('allocation') or {})
              .get('ru_maxrss_bytes'),
              'provider_counts': {k: provider_stats.get(k) for k in (
                  'input_success_count', 'input_failure_count', 'container_total_count',
                  'container_error_count')},
              'prior_m3_6_004_verdicts_pass': prior_pass,
              'inputs_sha256': {'below': sha(output/'below.json'), 'above': sha(output/'above.json'),
                                'provider_stats': sha(provider_stats_path), 'runs': sha(runs_path)},
              'g2_decision_made': False, 'labels_deserialized': False, 'training_executed': False}
    write_new(review_output, review)
    return review


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    sys.path.insert(0, str(ROOT))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--expected-authorization-sha256')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--classify', type=Path)
    parser.add_argument('--provider-stats', type=Path)
    parser.add_argument('--runs', type=Path)
    parser.add_argument('--review-output', type=Path)
    args = parser.parse_args()
    if args.execute and args.authorization and args.expected_authorization_sha256 and args.output:
        execute(args.authorization.resolve(), args.expected_authorization_sha256, args.output.resolve())
    elif args.classify and args.provider_stats and args.runs and args.review_output:
        print(json.dumps(classify(args.classify.resolve(), args.provider_stats.resolve(), args.runs.resolve(),
                                  args.review_output.resolve()), ensure_ascii=False, indent=2))
    else:
        parser.error('use --execute with --authorization/--expected-authorization-sha256/--output, '
                     'or --classify with --provider-stats/--runs/--review-output')


if __name__ == '__main__':
    main()
