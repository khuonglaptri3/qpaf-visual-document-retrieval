"""Independently recompute R5-04 counts/statistics from immutable raw GPU rows."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(ok, message):
    if not ok:
        raise ValueError(message)


def p95(values):
    ordered = sorted(values)
    pos = .95*(len(ordered)-1)
    lo = int(pos)
    return ordered[lo]+(ordered[math.ceil(pos)]-ordered[lo])*(pos-lo)


def main():
    global EVIDENCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, default=EVIDENCE)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    EVIDENCE = args.evidence_dir.resolve()
    request = read(EVIDENCE/'gpu-execution-request.json')
    output = ROOT/request['output_path']
    before = {p.name: sha(p) for p in output.iterdir() if p.is_file()}
    recovery_path = EVIDENCE/'gpu-recovery-receipt.json'
    if recovery_path.exists():
        recovery = read(recovery_path)
        result_path = ROOT/recovery['result_ref']
        check(result_path.resolve().is_relative_to(EVIDENCE), 'recovery artifact namespace')
        check(sha(result_path) == recovery['result_sha256'], 'recovered result pin')
        check(sha(output/'result_transport.json') == recovery['transport_metadata_sha256'], 'transport receipt pin')
        check(sha(EVIDENCE/'provider-call-log.json') == recovery['provider_log_sha256'], 'provider log pin')
        calls = read(EVIDENCE/'provider-function-calls.json')
        check(len(calls) == 1 and calls[0]['function_call_id'] == recovery['function_call_id']
              and calls[0]['status'] == 'success' and recovery['new_gpu_invocations'] == 0, 'existing successful provider call')
        check(recovery['function_call_id'] == read(output/'function_call.json')['function_call_id'], 'durable call identity')
        result = read(result_path)
        canonical = json.dumps(result, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()
        transport = read(output/'result_transport.json')
        check(hashlib.sha256(canonical).hexdigest() == transport['sha256']
              and len(canonical) == transport['uncompressed_bytes'], 'canonical raw transport hash')
        check((output/'_FAILURE.json').exists() and not (output/'_SUCCESS.json').exists(), 'original client failure preserved')
    else:
        result_path = output/'gpu_result.json'
        result, marker = read(result_path), read(output/'_SUCCESS.json')
        check(marker['gpu_result_sha256'] == sha(result_path), 'result marker pin')
    auth = read(EVIDENCE/'gpu-authorization.json')
    binding = read(output/'runtime_binding.json')
    check(result['status'] == 'COMPLETED' and set(result['outputs']) == {'QARF', 'QPAF'}, 'method coverage')
    check(binding['authorization_sha256'] == sha(EVIDENCE/'gpu-authorization.json'), 'authorization pin')
    check(binding['bundle_manifest_sha256'] == auth['bundle_manifest_sha256'], 'bundle pin')
    check(binding['source_commit'] == request['source_commit'] == auth['source_commit'], 'source pin')
    ids = read(EVIDENCE/'gpu-workload.json')['measured']
    check(len(ids) == len(set(ids)) == 171, 'distinct IDs')
    stages = ['online_wall_ms', 'cpu_features_ms', 'h2d_wall_ms', 'gate_wall_ms',
              'gate_cuda_ms', 'd2h_wall_ms', 'ranking_wall_ms']
    summaries, raw_csv = {}, []
    for method, data in result['outputs'].items():
        rows, summary = data['timings'], data['summary']
        check([(r['pass_index'], r['query_id']) for r in rows] ==
              [(p, q) for p in range(6) for q in ids], 'ordered event coverage')
        check(Counter(r['query_id'] for r in rows) == Counter({q: 6 for q in ids}), 'event repetitions')
        check(summary['distinct_measured_queries'] == 171 and summary['measurement_rows'] == 1026
              and summary['passes'] == 6 and not summary['meets_m36_1000_distinct_id_protocol'], 'counts')
        parity = data['parity']
        check(parity['query_count'] == 171 and parity['candidate_count'] == 82255, 'parity coverage')
        check(all(math.isfinite(parity[k]) and parity[k] <= 1e-7
                  for k in ('max_abs_score_difference', 'max_abs_weight_difference')), 'parity tolerance')
        check(parity['ranking_disagreements'] == 0, 'ranking parity')
        check(data['warmup_queries'] == 20 and not data['test_labels_deserialized']
              and not data['training_executed'], 'scope flags')
        check(data['source_commit'] == auth['source_commit'] and
              data['bundle_manifest_sha256'] == auth['bundle_manifest_sha256'], 'worker source/bundle')
        check(data['runtime']['python'] == '3.13.7' and data['runtime']['torch'] == '2.11.0+cu126'
              and 'A10' in data['runtime']['gpu'], 'GPU runtime')
        check(all(result['packages'][k] == auth['runtime'][k] for k in ('torch', 'numpy', 'pandas', 'pyarrow')),
              'package runtime')
        groups = defaultdict(list)
        for row in rows:
            check(type(row['candidate_count']) is int and 1 <= row['candidate_count'] <= 600, 'candidate count')
            check(all(math.isfinite(row[k]) and row[k] >= 0 for k in stages), 'finite nonnegative timings')
            check(row['gate_cuda_ms'] <= row['gate_wall_ms']+.001, 'CUDA versus wall duration')
            check(sum(row[k] for k in ('cpu_features_ms', 'h2d_wall_ms', 'gate_wall_ms',
                                       'd2h_wall_ms', 'ranking_wall_ms')) <= row['online_wall_ms']+1e-6,
                  'stage sum')
            groups[row['query_id']].append(row)
            raw_csv.append({'method': method, **row})
        check(all(sum(row['candidate_count'] for row in rows if row['pass_index'] == p) == 82255
                  for p in range(6)), 'candidate coverage per pass')
        check(all(len({row['candidate_count'] for row in group}) == 1 for group in groups.values()),
              'candidate coverage stable across passes')
        for key in stages:
            query_medians = [statistics.median(row[key] for row in groups[q]) for q in ids]
            expected = {'median_of_query_medians': statistics.median(query_medians),
                        'p95_of_query_medians': p95(query_medians),
                        'event_p50': statistics.median(row[key] for row in rows),
                        'event_p95': p95([row[key] for row in rows])}
            check(all(abs(summary[key][k]-v) <= 1e-12 for k, v in expected.items()), 'statistic '+key)
        peak = summary['peak_cuda_allocated_bytes']
        check(math.isfinite(peak) and peak > 0 and abs(summary['peak_cuda_allocated_gib']-peak/2**30) <= 1e-12,
              'allocation units')
        verdict = 'PASS' if summary['online_wall_ms']['median_of_query_medians'] <= 10. and peak < 1.5*2**30 else 'FAIL'
        check(verdict == summary['resource_verdict'], 'resource verdict')
        process_peaks = [s['process']['ru_maxrss_bytes'] for s in data['memory_telemetry']]
        summaries[method] = {'resource_verdict': verdict, 'query_count': 171, 'measurement_events': 1026,
                             'online_median_ms': summary['online_wall_ms']['median_of_query_medians'],
                             'online_p95_query_medians_ms': summary['online_wall_ms']['p95_of_query_medians'],
                             'online_event_p95_ms': summary['online_wall_ms']['event_p95'],
                             'peak_cuda_allocated_gib': peak/2**30,
                             'peak_cuda_reserved_gib': data['peak_cuda_reserved_bytes']/2**30,
                             'process_peak_rss_gib': max(process_peaks)/2**30, 'parity': parity,
                             'stages': {k: summary[k] for k in stages}, 'worker_pid': data['worker_pid']}
    check(summaries['QARF']['worker_pid'] != summaries['QPAF']['worker_pid'], 'isolated method processes')
    check(before == {p.name: sha(p) for p in output.iterdir() if p.is_file()}, 'read-only verification')
    receipt = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(),
               'output_ref': request['output_path'], 'run_files_sha256': before,
               'result_ref': result_path.relative_to(ROOT).as_posix(), 'result_sha256': sha(result_path),
               'transport_recovery': recovery_path.exists(),
               'run_bytes_unchanged': True, 'summaries': summaries,
               'counting_scope': '171 distinct validation IDs, 1026 timed events per method',
               'independent_human_acceptance': 'PENDING', 'verification_kind': 'independent arithmetic recomputation'}
    if not args.check_only:
        with (EVIDENCE/'gpu-offline-verification.json').open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
        with (EVIDENCE/'gpu-timings.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(raw_csv[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(raw_csv)
    print(json.dumps({'status': 'PASS', 'summaries': {m: {k: v for k, v in s.items() if k != 'stages'}
                                                    for m, s in summaries.items()}}, indent=2))


if __name__ == '__main__':
    main()
