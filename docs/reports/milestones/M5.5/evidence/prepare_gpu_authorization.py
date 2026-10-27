"""Bind the owner's successor instruction to one reviewed M5.5 invocation."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from scripts import run_m55_gpu as launcher  # noqa: E402
from scripts.m55_gpu_worker import read, sha, validate_payload, verify_bundle, write_new  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--bundle', type=Path, default=ROOT/'.cache/m55-validation-gpu')
    parser.add_argument('--evidence-dir', type=Path)
    args = parser.parse_args()
    evidence = args.evidence_dir.resolve() if args.evidence_dir else Path(__file__).resolve().parent
    if args.evidence_dir:
        evidence.mkdir(parents=True, exist_ok=False)
    bundle = args.bundle.resolve()
    manifest = verify_bundle(bundle)
    workload = read(bundle/'input/workload.json')
    records = read(bundle/'input/queries_scores.json')
    validate_payload(workload, records)
    ids = (ROOT/'results/m4.2'/launcher.read(ROOT/'configs/m4.4/evaluation.json')['bundle']['run_path'].split('/')[-1]
           /'inputs/splits/val_ids.txt').read_text(encoding='utf-8').splitlines()
    if workload['measured'] != ids:
        raise ValueError('Export does not match the frozen validation ID file')
    checks = {}
    by_id = {r['query_id']: r for r in records}
    for method in ('QARF', 'QPAF'):
        refs = read(bundle/f'input/{method}_validation_predictions.json')
        if len(refs) != 171 or {r['query_id'] for r in refs} != set(ids):
            raise ValueError('Reference coverage differs')
        candidates = 0
        for ref in refs:
            record = by_id[ref['query_id']]
            if (set(ref) != {'query_id', 'page_ids', 'scores', 'weights'} or
                    ref['page_ids'] != record['page_ids'] or
                    len(ref['scores']) != len(record['page_ids']) or
                    len(ref['weights']) != len(record['page_ids']) or
                    any(not math.isfinite(v) for v in ref['scores']) or
                    any(len(w) != 3 or any(not math.isfinite(v) or v < 0 for v in w)
                        or abs(sum(w)-1.) > 1e-7 for w in ref['weights'])):
                raise ValueError('Reference values/shape/coverage invalid')
            candidates += len(ref['scores'])
        if candidates != 82255:
            raise ValueError('Reference candidate count differs')
        checks[method] = {'query_count': 171, 'candidate_count': candidates,
                          'finite_scores_and_simplex_weights': True,
                          'sha256': sha(bundle/f'input/{method}_validation_predictions.json')}
    recorded = datetime.now(timezone.utc)
    run_id = 'RUN-QPAF-M5_5-SYS-001-'+recorded.strftime('%Y%m%dT%H%M%SZ')+f'-A{args.attempt:02d}'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    auth = {'schema_version': 1, 'status': 'AUTHORIZED_BY_KHUONG_WORKING_SESSION',
            'task_id': 'M5.5', 'experiment_id': 'QPAF-M5_5-SYS-001', 'run_id': run_id,
            'scope': 'validation', 'source_commit': head,
            'bundle_manifest_sha256': sha(bundle/'bundle_manifest.json'),
            'workload_sha256': sha(bundle/'input/workload.json'),
            'query_count': 171, 'measurement_events_per_method': 1026,
            'warmup_events': 20, 'warmup_overlaps_measured_ids': True, 'passes': 6,
            'methods': ['QARF', 'QPAF'], 'invocations': 1, 'automatic_retries': 0,
            'previous_completed_gpu_invocations': args.attempt-1,
            'transport': 'durable spawn/get; preserve prior client transport failure',
            'memory_limit_mib': 5120, 'function_timeout_seconds': 900,
            'startup_timeout_seconds': 120, 'worker_timeout_seconds': 410,
            'whole_app_watchdog_seconds': 900, 'gpu': 'A10', 'gpu_count': 1,
            'cpu_limit_cores': 2, 'budget_usd': .5,
            'cost_note': 'Operating target; one bounded container with app watchdog, not a provider dollar cap.',
            'runtime': launcher.RUNTIME, 'base_oci_image': launcher.BASE_IMAGE,
            'source_files_sha256': {p: sha(ROOT/p) for p in
                                     ('scripts/run_m55_gpu.py', 'scripts/m55_gpu_worker.py',
                                      'scripts/m36_memory_telemetry.py')},
            'permissions': {'validation_only': True, 'training': False, 'test_labels': False},
            'output_path': 'results/m5.5/'+run_id,
            'approval': {'approver': 'Khương (task owner; working-session user)',
                         'text': 'Cho phép chạy Modal/GPU để hoàn tất số đo M5.5',
                         'delegation': 'Tự quyết chi tiết và triển khai trong phạm vi validation',
                         'recorded_utc': recorded.isoformat(),
                         'timestamp_basis': 'Instruction recorded now; no user-message server timestamp inferred',
                         'research_lead_signature': 'NOT_RECORDED_NOT_INFERRED'},
            'independent_human_acceptance': 'PENDING',
            'counting_interpretation': '1026 repeated validation events, 171 distinct IDs; not M3.6 distinct-ID protocol',
            'namespace_policy': 'create once; preserve failure; no retry authorized by this record'}
    launcher.validate_authorization(auth, head=head, clean=not launcher.git('status', '--porcelain', '-uno'),
                                    bundle_sha=sha(bundle/'bundle_manifest.json'),
                                    workload_sha=sha(bundle/'input/workload.json'), output_rel=auth['output_path'])
    write_new(evidence/'gpu-authorization.json', auth)
    write_new(evidence/'gpu-bundle-manifest.json', manifest)
    write_new(evidence/'gpu-workload.json', workload)
    write_new(evidence/'gpu-preexecution-receipt.json',
              {'status': 'PASS', 'source_commit': head, 'reference_checks': checks,
               'authorization_sha256': sha(evidence/'gpu-authorization.json'),
               'bundle_manifest_sha256': sha(bundle/'bundle_manifest.json'),
               'query_count': 171, 'candidate_count': 82255,
               'gpu_invocations_so_far': 0, 'qrels_exported': False,
               'label_fields_exported': False, 'validation_only': True})
    request = {'interpreter': sys.executable, 'source_commit': head,
               'command': ['scripts/run_m55_gpu.py', '--bundle', str(bundle),
                           '--authorization', str(evidence/'gpu-authorization.json'),
                           '--expected-authorization-sha256', sha(evidence/'gpu-authorization.json'),
                           '--output', str(ROOT/auth['output_path'])],
               'output_path': auth['output_path'], 'invocations': 1}
    write_new(evidence/'gpu-execution-request.json', request)
    print(json.dumps({'status': 'PASS', 'run_id': run_id,
                      'authorization_sha256': sha(evidence/'gpu-authorization.json'),
                      'bundle_manifest_sha256': sha(bundle/'bundle_manifest.json')}, indent=2))


if __name__ == '__main__':
    main()
