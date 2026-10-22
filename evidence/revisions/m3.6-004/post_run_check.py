"""Offline, read-only replay of the 5 GiB run's binding, coverage and arithmetic."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
REV = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    auth = read(REV/'authorization.json')
    request = read(REV/'execution_request.json')
    bundle = read(REV/'bundle_manifest.json')
    run = ROOT/auth['output_path']
    result, binding = read(run/'gpu_result.json'), read(run/'runtime_binding.json')
    success, attempt = read(run/'_SUCCESS.json'), read(run/'_ATTEMPTED.json')
    assert sha(REV/'authorization.json') == request['authorization_sha256']
    assert attempt['authorization_sha256'] == binding['authorization_sha256'] == request['authorization_sha256']
    assert bundle['source_commit'] == binding['source_commit'] == auth['source_commit']
    assert sha(REV/'bundle_manifest.json') == binding['bundle_manifest_sha256'] == auth['bundle_manifest_sha256']
    assert result['status'] == 'COMPLETED' and success['status'] == 'EXECUTION_COMPLETE'
    assert success['gpu_result_sha256'] == sha(run/'gpu_result.json')
    assert auth['memory_limit_mib'] == binding['memory_request_and_limit_mib'] == result['memory_request_and_limit_mib'] == 5120
    assert auth['invocations'] == 1 and auth['automatic_retries'] == 0
    assert binding['gpu_invocations_before_binding'] == 0
    assert binding['image_id'] and binding['app_id']
    old = read(ROOT/'evidence/revisions/m3.6-003/bundle_manifest.json')
    for name, digest in old['files'].items():
        if name.startswith(('input/', 'src/')):
            assert bundle['files'][name] == digest, name
    for name, digest in bundle['files'].items():
        if name.startswith(('src/', 'scripts/')):
            data = subprocess.check_output(['git', 'show', auth['source_commit']+':'+name], cwd=ROOT)
            assert hashlib.sha256(data).hexdigest() == digest, name
    workload = read(ROOT/'evidence/revisions/m3.6-001/gpu_protocol_review/gpu_workload.json')
    ids = [row['query_id'] for row in workload['measured']]
    warm = [row['query_id'] for row in workload['warmup']]
    assert len(ids) == len(set(ids)) == 1122 and len(warm) == len(set(warm)) == 20
    assert not set(ids) & set(warm)
    methods = {}
    for method in ('QARF', 'QPAF'):
        output = result['outputs'][method]
        rows, summary, parity = output['timings'], output['summary'], output['parity']
        assert output['source_commit'] == auth['source_commit']
        assert output['bundle_manifest_sha256'] == auth['bundle_manifest_sha256']
        assert [(r['pass_index'], r['query_id']) for r in rows] == [(p, q) for p in range(3) for q in ids]
        assert output['warmup_queries'] == 20
        assert not output['test_labels_deserialized'] and not output['training_executed']
        for key in ('online_wall_ms', 'cpu_features_ms', 'h2d_wall_ms', 'gate_wall_ms',
                    'gate_cuda_ms', 'd2h_wall_ms', 'ranking_wall_ms'):
            data = np.array([row[key] for row in rows]).reshape(3, 1122)
            assert np.isfinite(data).all() and (data >= 0).all()
            medians = np.median(data, axis=0)
            assert math.isclose(float(np.median(medians)), summary[key]['median_of_query_medians'], abs_tol=1e-12)
            assert math.isclose(float(np.percentile(medians, 95)), summary[key]['p95_of_query_medians'], abs_tol=1e-12)
        assert summary['online_wall_ms']['median_of_query_medians'] <= 10
        assert 0 < summary['peak_cuda_allocated_bytes'] < 1.5*2**30
        assert parity['query_count'] == 171 and parity['candidate_count'] == 82255
        assert max(parity['max_abs_score_difference'], parity['max_abs_weight_difference']) <= 1e-7
        assert parity['ranking_disagreements'] == 0
        snapshots = output['memory_telemetry']
        assert len(snapshots) == 10 and all(s['pid'] == output['worker_pid'] for s in snapshots)
        methods[method] = {'median_online_ms': summary['online_wall_ms']['median_of_query_medians'],
                           'p95_query_medians_ms': summary['online_wall_ms']['p95_of_query_medians'],
                           'peak_cuda_allocated_gib': summary['peak_cuda_allocated_bytes']/2**30,
                           'reported_ru_maxrss_gib': output['cpu_peak_rss_kib']/2**20,
                           'final_memory_assessment': snapshots[-1]['assessment'], 'timed_rows': len(rows)}
    assert result['outputs']['QARF']['worker_pid'] != result['outputs']['QPAF']['worker_pid']
    for group in result['container_memory']:
        assert group['assessment']['physical_container_peak_verified'] is False
    assert sha(ROOT/'results/m3.6/RUN-QPAF-M3_6-SYS-001-20261022T154348Z-A02/gpu_result.json') == '76ed5466b4c4202c551c31c55fd24a580d8d6273e65c1221a19d56134dd66943'
    return {'schema_version': 1, 'checked_utc': datetime.now(timezone.utc).isoformat(),
            'offline_verification': 'PASS', 'operational_latency_cuda_parity_verdict': 'PASS',
            'result_sha256': sha(run/'gpu_result.json'), 'authorization_sha256': sha(REV/'authorization.json'),
            'source_commit': auth['source_commit'], 'image_id': binding['image_id'], 'app_id': binding['app_id'],
            'methods': methods, 'all_frozen_inputs_and_core_source_match_original_bundle': True,
            'original_4gib_result_preserved': True, 'summary_arithmetic': 'NumPy independent median/linear p95',
            'human_owner_acceptance': 'PENDING', 'g2_decision_made': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = verify()
    if args.output:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=True, allow_nan=False, indent=2)
            stream.write('\n')
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))
