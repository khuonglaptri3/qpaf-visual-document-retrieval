"""Frozen, label-free fusion resource measurement; one fresh process per method."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import numbers
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

STAGES = ('online_wall_ms', 'cpu_features_ms', 'h2d_wall_ms', 'gate_wall_ms',
          'gate_cuda_ms', 'd2h_wall_ms', 'ranking_wall_ms')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=True, allow_nan=False, indent=2)
        stream.write('\n')


def label_free_records(rows, queries, ids, cap):
    """No qrels argument; copy only query/page IDs, text and the three raw scores."""
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate query IDs')
    grouped = {query_id: {} for query_id in ids}
    for row in rows:
        query_id = row['query_id']
        if query_id not in grouped:
            continue
        page = row['page_id']
        scores = [row[k] for k in ('bm25_score', 'dense_score', 'visual_score')]
        if not all(isinstance(v, numbers.Real) and not isinstance(v, bool) and math.isfinite(v)
                   for v in scores):
            raise ValueError('three finite numeric scores required')
        if not isinstance(page, str) or not page.strip():
            raise ValueError('invalid page ID')
        if page in grouped[query_id]:
            raise ValueError('duplicate candidate')
        grouped[query_id][page] = list(map(float, scores))
    result = []
    for query_id in ids:
        pages, text = grouped[query_id], queries.get(query_id)
        if not pages or not isinstance(text, str) or not text.strip():
            raise ValueError('missing query text or candidates: '+query_id)
        if len(pages) > cap:
            raise ValueError('candidate cap exceeded')
        ordered = sorted(pages)
        result.append({'query_id': query_id, 'text': text, 'page_ids': ordered,
                       'raw_scores': [pages[p] for p in ordered]})
    return result


def percentile(values, q):
    ordered = sorted(values)
    index = (len(ordered)-1)*q
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(index-lo)


def summarize(rows, measured_ids, peak_allocated_bytes):
    if len(measured_ids) < 1000 or len(set(measured_ids)) != len(measured_ids):
        raise ValueError('at least 1000 distinct measured IDs required')
    expected = [(p, q) for p in range(3) for q in measured_ids]
    if [(r['pass_index'], r['query_id']) for r in rows] != expected:
        raise ValueError('incomplete, duplicate or reordered measurement rows')
    if not math.isfinite(peak_allocated_bytes) or peak_allocated_bytes <= 0:
        raise ValueError('positive CUDA allocation evidence required')
    for row in rows:
        if any(not math.isfinite(row[k]) or row[k] < 0 for k in STAGES):
            raise ValueError('nonfinite or negative timing')
        if sum(row[k] for k in ('cpu_features_ms', 'h2d_wall_ms', 'gate_wall_ms',
                                'd2h_wall_ms', 'ranking_wall_ms')) > row['online_wall_ms']+1e-6:
            raise ValueError('stage time exceeds full online wall time')
    count = len(measured_ids)
    output = {'distinct_measured_queries': count, 'measurement_rows': len(rows), 'passes': 3}
    for key in STAGES:
        medians = [statistics.median(rows[p*count+i][key] for p in range(3)) for i in range(count)]
        output[key] = {'median_of_query_medians': statistics.median(medians),
                       'p95_of_query_medians': percentile(medians, .95),
                       'per_pass': [{'p50': statistics.median([r[key] for r in rows[p*count:(p+1)*count]]),
                                     'p95': percentile([r[key] for r in rows[p*count:(p+1)*count]], .95)}
                                    for p in range(3)]}
    output['peak_cuda_allocated_bytes'] = peak_allocated_bytes
    output['peak_cuda_allocated_gib'] = peak_allocated_bytes/2**30
    output['resource_verdict'] = ('PASS' if output['online_wall_ms']['median_of_query_medians'] <= 10.
                                  and peak_allocated_bytes < 1.5*2**30 else 'FAIL')
    return output


def verify_bundle(root):
    manifest = read(root/'bundle_manifest.json')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    if actual != set(manifest['files']) | {'bundle_manifest.json'}:
        raise ValueError('bundle file allowlist mismatch')
    for name, expected in manifest['files'].items():
        path = (root/name).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != expected:
            raise ValueError('bundle hash mismatch: '+name)
    return manifest


def run_method(method, root, output, timeout=410):
    """Keep failure logs as data, including when a worker hits its wall limit."""
    command = [sys.executable, '-u', str(root/'scripts/m36_gpu_worker.py'),
               '--method', method, '--root', str(root), '--output', str(output)]
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        log = {'stdout': process.stdout, 'stderr': process.stderr, 'exit_code': process.returncode}
        if process.returncode:
            return {'status': 'FAILED', 'reason': 'WORKER_EXIT', 'output': None, 'log': log}
        return {'status': 'COMPLETED', 'reason': None, 'output': read(output), 'log': log}
    except subprocess.TimeoutExpired as exc:
        def decoded(value):
            return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else (value or '')
        return {'status': 'FAILED', 'reason': 'WORKER_TIMEOUT', 'output': None,
                'log': {'stdout': decoded(exc.stdout), 'stderr': decoded(exc.stderr),
                        'exit_code': None, 'timeout_seconds': timeout}}


def measure(method, root):
    manifest = verify_bundle(root)
    sys.path.insert(0, str(root/'src'))
    import torch
    from qpaf.m12.features import FeatureBatch, build_features
    from qpaf.m24.checkpoint import load_checkpoint
    from qpaf.m24.config import load_config
    from qpaf.m24.evaluator import rank
    from qpaf.m24.trainer import build_model
    import qpaf.m12.model as model_module
    import qpaf.m12.features as feature_module

    for module in (model_module, feature_module):
        if not Path(module.__file__).resolve().is_relative_to((root/'src').resolve()):
            raise ValueError('imported source outside frozen bundle')
    if platform.python_version() != '3.13.7' or torch.__version__ != '2.11.0+cu126':
        raise ValueError('runtime differs from pinned Python/Torch')
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise ValueError('one CUDA GPU required')
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    config = load_config(root/'input/shared_base.toml')
    workload = read(root/'input/workload.json')
    warmup = [r['query_id'] for r in workload['warmup']]
    measured = [r['query_id'] for r in workload['measured']]
    if len(warmup) != 20 or len(measured) < 1000 or len(set(warmup+measured)) != len(warmup+measured):
        raise ValueError('warmup/measurement coverage differs')
    records_list = read(root/'input/queries_scores.json')
    if [r['query_id'] for r in records_list] != warmup+measured:
        raise ValueError('payload order differs from workload')
    if any(set(r) != {'query_id', 'text', 'page_ids', 'raw_scores'} for r in records_list):
        raise ValueError('unexpected payload fields')
    records = {r['query_id']: r for r in records_list}
    torch.cuda.init()
    baseline = {'allocated': torch.cuda.memory_allocated(), 'reserved': torch.cuda.memory_reserved()}
    torch.cuda.reset_peak_memory_stats()
    cold_start = time.perf_counter()
    checkpoint = load_checkpoint(root/f'input/{method}_best.pt', config=config, method=method,
                                 expected_sha256=manifest['files'][f'input/{method}_best.pt'])
    model = build_model(config, method)
    model.load_state_dict(checkpoint['model_state'])
    model = model.to('cuda').eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter()-cold_start
    event_start, event_end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    # Initialize event handles outside the query wall clock.
    event_start.record()
    event_end.record()
    torch.cuda.synchronize()

    def infer_one(record):
        torch.cuda.synchronize()
        t0 = time.perf_counter_ns()
        raw = torch.tensor([record['raw_scores']], dtype=torch.float64)
        features = build_features(raw, [record['text']], [record['page_ids']],
                                  query_length_cap=config['features']['query_length_cap'])
        t1 = time.perf_counter_ns()
        device_features = FeatureBatch(features.values.to('cuda'), features.scores.to('cuda'),
                                       features.mask.to('cuda'))
        torch.cuda.synchronize()
        t2 = time.perf_counter_ns()
        event_start.record()
        output = model(device_features)
        event_end.record()
        torch.cuda.synchronize()
        t3 = time.perf_counter_ns()
        scores = output.scores[0].cpu().tolist()
        weights = output.weights[0].cpu().tolist()
        torch.cuda.synchronize()
        t4 = time.perf_counter_ns()
        order = rank(record['page_ids'], scores)
        t5 = time.perf_counter_ns()
        cuda_ms = event_start.elapsed_time(event_end)
        del output, device_features, features, raw
        t6 = time.perf_counter_ns()
        if (not all(math.isfinite(s) for s in scores) or
                any(len(w) != 3 or any(not math.isfinite(v) or v < 0 for v in w)
                    or abs(sum(w)-1.) > 1e-7 for w in weights)):
            raise ValueError('nonfinite scores or invalid simplex weights')
        times = dict(zip(STAGES, [(t6-t0)/1e6, (t1-t0)/1e6, (t2-t1)/1e6,
                                  (t3-t2)/1e6, cuda_ms, (t4-t3)/1e6, (t5-t4)/1e6]))
        return scores, weights, order, times

    parity = {'query_count': 0, 'candidate_count': 0, 'max_abs_score_difference': 0.,
              'max_abs_weight_difference': 0., 'ranking_disagreements': 0}
    start = time.perf_counter()
    timings = []
    with torch.inference_mode():
        for expected in read(root/f'input/{method}_validation_predictions.json'):
            record = records[expected['query_id']]
            if expected['page_ids'] != record['page_ids']:
                raise ValueError('parity candidate order differs')
            scores, weights, order, _ = infer_one(record)
            ds = max(abs(a-b) for a, b in zip(scores, expected['scores'], strict=True))
            dw = max(abs(a-b) for wa, wb in zip(weights, expected['weights'], strict=True)
                     for a, b in zip(wa, wb, strict=True))
            parity['max_abs_score_difference'] = max(parity['max_abs_score_difference'], ds)
            parity['max_abs_weight_difference'] = max(parity['max_abs_weight_difference'], dw)
            parity['ranking_disagreements'] += int(order != rank(record['page_ids'], expected['scores']))
            parity['query_count'] += 1
            parity['candidate_count'] += len(scores)
            if max(ds, dw) > 1e-7:
                raise ValueError('CPU/GPU validation parity exceeds frozen tolerance')
        if parity['query_count'] != 171 or parity['candidate_count'] != 82255:
            raise ValueError('validation parity coverage differs')
        parity['seconds'] = time.perf_counter()-start
        for query_id in warmup:
            infer_one(records[query_id])
        for p in range(3):
            for query_id in measured:
                _, _, _, times = infer_one(records[query_id])
                timings.append({'query_id': query_id, 'pass_index': p,
                                'candidate_count': len(records[query_id]['page_ids']), **times})
            print(f'{method}: measured pass {p+1}/3 ({len(measured)} queries)', flush=True)
    peak = torch.cuda.max_memory_allocated()
    result = {'schema_version': 1, 'method': method, 'worker_pid': os.getpid(),
              'checked_utc': datetime.now(timezone.utc).isoformat(),
              'runtime': {'python': platform.python_version(), 'torch': torch.__version__,
                          'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(),
                          'cpu_threads': torch.get_num_threads(),
                          'cublas_workspace_config': os.environ.get('CUBLAS_WORKSPACE_CONFIG')},
              'source_commit': manifest['source_commit'], 'bundle_manifest_sha256': sha(root/'bundle_manifest.json'),
              'warmup_queries': len(warmup), 'parity': parity, 'cold_checkpoint_load_seconds': load_seconds,
              'cuda_baseline_bytes': baseline, 'peak_cuda_reserved_bytes': torch.cuda.max_memory_reserved(),
              'cpu_peak_rss_kib': __import__('resource').getrusage(__import__('resource').RUSAGE_SELF).ru_maxrss,
              'summary': summarize(timings, measured, peak), 'timings': timings,
              'test_labels_deserialized': False, 'training_executed': False,
              'measurement_scope': 'FP64 eager batch1; full online features/H2D/gate/D2H/page ranking; '
                                   'instrumentation and tensor release included; I/O/retrievers excluded'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=('QARF', 'QPAF'), required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    write_new(args.output, measure(args.method, args.root.resolve()))


if __name__ == '__main__':
    main()
