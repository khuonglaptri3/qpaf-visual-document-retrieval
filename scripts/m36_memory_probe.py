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
import re
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
PROBE_LIMIT_MIB = 4096
BELOW_TARGET_MIB = 2048
ABOVE_TARGET_MIB = 4608
HOLD_SECONDS = 5
WATCHDOG_SECONDS = 900  # covers two calls x (120 s startup + 300 s timeout) plus image start
OOM_PATTERN = re.compile(r'\boom(?:[-_ ]?kill(?:ed)?)?\b|out of memory|memory limit|exit ?code[:= ]*137')
RUNNER_KILL_PREFIX = 'Runner killed (SIGKILL)'  # emitted by Modal's runner, not by the probe
COUNT_KEYS = ('input_success_count', 'input_failure_count', 'container_total_count',
              'container_error_count')
REFERENCE_LIMITS_MIB = {'A02': 4096, 'A03': 5120}
# The approver's verbatim words; empty until recorded, so --execute refuses.
APPROVAL_TEXT = ('I approved as Tấn Phát, confirm for m3.6-005 and approved probe run plan. Finally, '
                 'I confirm the m3.7 criteria (frozen threshold-seed20260820)')
# M3.6 owner, or the Research Lead authorizing in their place (M3.2/M3.4 precedent).
AUTHORIZED_STATUSES = ('AUTHORIZED_BY_KHUONG_WORKING_SESSION', 'AUTHORIZED_BY_RESEARCH_LEAD_WORKING_SESSION')
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
    return OOM_PATTERN.search(' '.join(reasons).lower()) is not None


def classify_controls(below, above, provider_stats):
    # A completed above-limit attempt, including a provider retry, defeats the claim.
    successes = provider_stats.get('input_success_count')
    if above['status'] == 'COMPLETED' or (type(successes) is int and successes > 1):
        return NOT_DEMONSTRATED
    counts = [provider_stats.get(key) for key in COUNT_KEYS]
    if any(type(count) is not int for count in counts):
        return INCONCLUSIVE
    successes, failures, containers, errors = counts
    # One input succeeded (below) and one failed (above). Every container beyond the
    # below one must have errored, so provider retries can only be above attempts.
    if (below['status'] != 'COMPLETED' or successes != 1 or failures != 1 or containers < 2 or
            errors != containers - 1):
        return INCONCLUSIVE
    if not oom_attributed(above.get('error_text') or '', provider_stats):
        return INCONCLUSIVE
    return DEMONSTRATED


def classify_with_provider_logs(below, above, provider_stats, log_text):
    """m3.6-006: Modal's own runner-kill lines are provider exit reasons, one per errored container."""
    reasons = [line.strip() for line in log_text.splitlines() if line.strip().startswith(RUNNER_KILL_PREFIX)]
    classification = classify_controls(below, above, {**provider_stats, 'exit_reasons': reasons})
    every_error_attributed = (len(reasons) == provider_stats.get('container_error_count') and
                              all(OOM_PATTERN.search(reason.lower()) for reason in reasons))
    if classification == DEMONSTRATED and not every_error_attributed:
        return INCONCLUSIVE
    return classification


def memory_bound_verdict(classification, runs):
    bounded = {}
    for name, run in runs.items():
        ok = (classification == DEMONSTRATED and run.get('limit_mib') == REFERENCE_LIMITS_MIB.get(name) and
              run.get('success_marker') is True and type(run.get('failed_calls')) is int and
              run['failed_calls'] == 0)
        bounded[name] = {'bound': 'BELOW_LIMIT' if ok else 'UNBOUNDED', 'limit_mib': run.get('limit_mib')}
    resolved = (classification == DEMONSTRATED and set(bounded) == set(REFERENCE_LIMITS_MIB) and
                all(r['bound'] == 'BELOW_LIMIT' for r in bounded.values()))
    return {'classification': classification,
            'issue_status': 'RESOLVED_BY_ENFORCED_BOUND' if resolved else 'OPEN',
            'runs': bounded, 'exact_peak_available': False,
            'claim_scope': 'Provider-enforced upper bound under Modal hard memory limit; not a peak'}


def failed_record(target_mib, error_type, error_text):
    return {'status': 'FAILED', 'target_mib': target_mib, 'error_type': error_type,
            'error_text': error_text, 'in_sandbox': None}


def run_controls(call, write):
    """Below first; if it fails, stop before spending the above-limit invocation."""
    try:
        below = call(BELOW_TARGET_MIB)
    except Exception as exc:
        write('below', failed_record(BELOW_TARGET_MIB, type(exc).__name__, str(exc)))
        raise
    write('below', below)
    try:
        above = call(ABOVE_TARGET_MIB)
    except Exception as exc:  # the above-limit control is expected to land here
        above = failed_record(ABOVE_TARGET_MIB, type(exc).__name__, str(exc))
    write('above', above)


def load_controls(output):
    """A record lost to the watchdog or a crash reads as a failed, unattributed control."""
    from scripts.m36_gpu_worker import read
    note = 'watchdog stopped app' if (output/'_WATCHDOG.json').exists() else 'record not written'
    return tuple(read(output/f'{name}.json') if (output/f'{name}.json').exists()
                 else failed_record(target, 'MISSING_RECORD', note)
                 for name, target in (('below', BELOW_TARGET_MIB), ('above', ABOVE_TARGET_MIB)))


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


def contract_errors(auth, *, head, dirty, output_rel, profile, approval_text):
    """Names every authorization field that does not match this exact invocation."""
    checks = {
        'status': auth.get('status') in AUTHORIZED_STATUSES,
        'source_commit': auth.get('source_commit') == head,
        'dirty_tree': not dirty,
        'invocations': auth.get('invocations') == 2 and auth.get('automatic_retries') == 0,
        'output_path': auth.get('output_path') == output_rel,
        'approval': bool(approval_text) and auth.get('approval', {}).get('text') == approval_text,
        'memory_limit_mib': auth.get('memory_limit_mib') == PROBE_LIMIT_MIB,
        'modal_profile': profile is not None and auth.get('modal_profile') == profile,
    }
    return [name for name, ok in checks.items() if not ok]


def check_authorization(auth, output):
    errors = contract_errors(auth, head=git('rev-parse', 'HEAD'),
                             dirty=git('status', '--porcelain', '--untracked-files=no'),
                             output_rel=output.relative_to(ROOT).as_posix(),
                             profile=os.environ.get('MODAL_PROFILE'), approval_text=APPROVAL_TEXT)
    if errors:
        raise ValueError('authorization contract differs: ' + ', '.join(errors))


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
            run_controls(probe.remote, lambda name, record: write_new(
                output/f'{name}.json', {**record, 'finished_utc': datetime.now(timezone.utc).isoformat()}))
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


def classify(output, provider_stats_path, runs_path, review_output, provider_logs_path=None):
    from scripts.m36_gpu_worker import read, sha, write_new
    below, above = load_controls(output)
    if (output/'_SUCCESS.json').exists():
        marker = read(output/'_SUCCESS.json')
        if marker['below_sha256'] != sha(output/'below.json') or marker['above_sha256'] != sha(output/'above.json'):
            raise ValueError('control records differ from _SUCCESS.json hashes')
    provider_stats, runs = read(provider_stats_path), read(runs_path)
    if provider_logs_path is None:
        classification = classify_controls(below, above, provider_stats)
    else:
        classification = classify_with_provider_logs(below, above, provider_stats,
                                                     provider_logs_path.read_text(encoding='utf-8'))
    verdict = memory_bound_verdict(classification, runs)
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
              'provider_retries_of_above_control': max(0, (provider_stats.get('container_total_count') or 0) - 2),
              'criteria_revision_ref': ('evidence/revisions/m3.6-005/criteria_revision.md' if provider_logs_path
                                        is None else 'evidence/revisions/m3.6-006/criteria_revision.md'),
              'provider_exit_reason_source': ('provider stats export only' if provider_logs_path is None else
                                              f"Modal runner-kill lines ('{RUNNER_KILL_PREFIX}') in provider app "
                                              'logs, one required per errored container'),
              'inputs_sha256': {**{name: sha(output/f'{name}.json') for name in ('below', 'above')
                                   if (output/f'{name}.json').exists()},
                                'provider_stats': sha(provider_stats_path), 'runs': sha(runs_path),
                                **({} if provider_logs_path is None else
                                   {'provider_logs': sha(provider_logs_path)})},
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
    parser.add_argument('--provider-logs', type=Path, help='m3.6-006: Modal app logs as provider exit reasons')
    args = parser.parse_args()
    if args.execute and args.authorization and args.expected_authorization_sha256 and args.output:
        execute(args.authorization.resolve(), args.expected_authorization_sha256, args.output.resolve())
    elif args.classify and args.provider_stats and args.runs and args.review_output:
        print(json.dumps(classify(args.classify.resolve(), args.provider_stats.resolve(), args.runs.resolve(),
                                  args.review_output.resolve(),
                                  args.provider_logs.resolve() if args.provider_logs else None),
                         ensure_ascii=False, indent=2))
    else:
        parser.error('use --execute with --authorization/--expected-authorization-sha256/--output, '
                     'or --classify with --provider-stats/--runs/--review-output')


if __name__ == '__main__':
    main()
