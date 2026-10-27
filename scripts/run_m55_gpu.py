"""Prepare an allowlisted bundle or execute one authorized Modal GPU invocation."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))
from scripts.m55_gpu_worker import label_free_records, read, sha, verify_bundle, write_new

MEMORY_MIB = 5120
RUNTIME = {'python': '3.13.7', 'torch': '2.11.0+cu126', 'numpy': '2.5.4',
           'pandas': '3.0.6', 'pyarrow': '26.0.0', 'modal': '1.5.5',
           'dtype': 'float64', 'threads': 1}
BASE_IMAGE = ('python:3.13.7-slim-bookworm@sha256:'
              'adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d')
ENV = {key: '1' for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                             'BLIS_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}
ENV.update({'PYTHONPATH': '/workspace/src:/workspace', 'PYTHONDONTWRITEBYTECODE': '1',
            'CUBLAS_WORKSPACE_CONFIG': ':4096:8'})


def configure_console():
    """Modal/Rich emits Unicode symbols even when Windows defaults to cp1252."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def prepare_bundle(destination):
    from qpaf.m24.config import load_config
    from qpaf.m24.dataset import read_score_rows
    from qpaf.m55.runner import AUTHORITY_PINS, BUNDLE_NAME, BUNDLE_MANIFEST_SHA256, validate_bindings
    from scripts.m55_gpu_worker import make_workload, validate_payload
    if git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('tracked source must be committed before preparation')
    cpu_auth = read(ROOT/'evidence/revisions/m5.5-001/authorization.json')
    validate_bindings(ROOT, cpu_auth)
    bundle = ROOT/'results/m4.2'/BUNDLE_NAME
    if sha(bundle/'manifest.json') != BUNDLE_MANIFEST_SHA256:
        raise ValueError('frozen M4.2 manifest differs')
    pins = {entry['path']: entry['sha256'] for entry in read(bundle/'manifest.json')['files']}
    inputs = ('inputs/raw_scores.parquet', 'inputs/candidate_set.parquet',
              'inputs/queries.json', 'inputs/splits/val_ids.txt')
    for rel in inputs:
        if sha(bundle/rel) != pins[rel]:
            raise ValueError('frozen input differs: '+rel)
    ids = (bundle/'inputs/splits/val_ids.txt').read_text(encoding='utf-8').splitlines()
    workload = make_workload(ids)
    config_path = ROOT/'results/m3.1/RUN-QPAF-M3_1-MTH-001-20261022T021241Z-A01/inputs/shared_base.toml'
    # Same numerical/config contract used by the frozen seed-one checkpoints.
    prior = read(ROOT/'evidence/revisions/m3.6-004/authorization.json')
    if not config_path.is_file():
        config_path = bundle/'inputs/shared_base.toml'
    if sha(config_path) != prior['input_hashes']['inputs/shared_base.toml']:
        raise ValueError('frozen shared feature/model config differs')
    config = load_config(config_path)
    records = label_free_records(read_score_rows(bundle/'inputs/raw_scores.parquet'),
                                 read(bundle/'inputs/queries.json'), ids, config['data']['max_candidates'])
    validate_payload(workload, records)
    if sum(len(r['page_ids']) for r in records) != 82255:
        raise ValueError('validation candidate count differs')
    import pandas as pd
    frame = pd.read_parquet(bundle/'inputs/candidate_set.parquet', columns=['query_id', 'page_id'])
    candidates = {}
    selected = set(ids)
    for row in frame.itertuples(index=False):
        if row.query_id in selected:
            candidates.setdefault(row.query_id, set()).add(row.page_id)
    if any(set(r['page_ids']) != candidates.get(r['query_id']) for r in records):
        raise ValueError('validation candidates differ from frozen union')
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'input').mkdir()
    (destination/'scripts').mkdir()
    for rel in git('ls-files', 'src').splitlines():
        path = ROOT/rel
        if path.suffix == '.py':
            target = destination/rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    for name in ('m55_gpu_worker.py', 'm36_memory_telemetry.py'):
        git('ls-files', '--error-unmatch', 'scripts/'+name)
        shutil.copyfile(ROOT/'scripts'/name, destination/'scripts'/name)
    shutil.copyfile(config_path, destination/'input/shared_base.toml')
    write_new(destination/'input/workload.json', workload)
    write_new(destination/'input/queries_scores.json', records)
    # Historical authorization is an input hash catalog only; it grants no M5.5 execution permission.
    for method, spec in prior['checkpoint_inputs'].items():
        checkpoint = ROOT/spec['path']
        predictions = checkpoint.parents[1]/'validation_predictions.json'
        if sha(checkpoint) != spec['sha256'] or sha(predictions) != spec['predictions_sha256']:
            raise ValueError('frozen checkpoint/reference differs: '+method)
        refs = read(predictions)
        if {r['query_id'] for r in refs} != selected or len(refs) != 171:
            raise ValueError('reference predictions are not validation-only')
        if any(set(r) != {'query_id', 'page_ids', 'scores', 'weights'} for r in refs):
            raise ValueError('reference predictions carry unexpected fields')
        shutil.copyfile(checkpoint, destination/f'input/{method}_best.pt')
        shutil.copyfile(predictions, destination/f'input/{method}_validation_predictions.json')
    manifest = {'schema_version': 1, 'task_id': 'M5.5', 'scope': 'validation',
                'source_commit': git('rev-parse', 'HEAD'), 'query_count': 171,
                'candidate_count': 82255, 'contains_qrels': False,
                'workload_sha256': sha(destination/'input/workload.json'),
                'authority_pins': AUTHORITY_PINS,
                'files': {p.relative_to(destination).as_posix(): sha(p)
                          for p in sorted(destination.rglob('*')) if p.is_file()}}
    write_new(destination/'bundle_manifest.json', manifest)
    verify_bundle(destination)
    return manifest


def validate_authorization(auth, *, head, clean, bundle_sha, workload_sha, output_rel):
    fixed = {'status': 'AUTHORIZED_BY_KHUONG_WORKING_SESSION', 'task_id': 'M5.5',
             'scope': 'validation', 'query_count': 171, 'measurement_events_per_method': 1026,
             'warmup_events': 20, 'passes': 6, 'invocations': 1, 'automatic_retries': 0,
             'memory_limit_mib': 5120, 'function_timeout_seconds': 900,
             'whole_app_watchdog_seconds': 900, 'gpu': 'A10', 'gpu_count': 1,
             'startup_timeout_seconds': 120, 'worker_timeout_seconds': 410,
             'runtime': RUNTIME, 'base_oci_image': BASE_IMAGE,
             'cpu_limit_cores': 2, 'budget_usd': .5,
             'permissions': {'validation_only': True, 'training': False, 'test_labels': False}}
    if any(auth.get(k) != v for k, v in fixed.items()):
        raise ValueError('M5.5 validation/count/resource authorization differs')
    if (not clean or auth.get('source_commit') != head or
            auth.get('bundle_manifest_sha256') != bundle_sha or
            auth.get('workload_sha256') != workload_sha or auth.get('output_path') != output_rel or
            not output_rel.startswith('results/m5.5/RUN-QPAF-M5_5-SYS-001-')):
        raise ValueError('source/bundle/workload/namespace binding differs')
    approval = auth.get('approval') or {}
    if not approval.get('text') or not approval.get('delegation'):
        raise ValueError('owner GPU authorization and validation delegation required')


def build_app(bundle):
    import modal
    if modal.__version__ != '1.5.5':
        raise ValueError('Modal SDK pin differs')
    image = (modal.Image.from_registry(BASE_IMAGE)
             .run_commands('timeout 240s python -m pip install --no-cache-dir torch==2.11.0+cu126 '
                           '--index-url https://download.pytorch.org/whl/cu126',
                           'timeout 90s python -m pip install --no-cache-dir '
                           'numpy==2.5.4 pandas==3.0.6 pyarrow==26.0.0')
             .env(ENV).workdir('/workspace')
             .add_local_dir(bundle, '/workspace', copy=True))
    app = modal.App('qpaf-m55-validation-resource', include_source=False)

    @app.function(image=image, gpu='A10', cpu=(2., 2.), memory=(MEMORY_MIB, MEMORY_MIB),
                  timeout=900, startup_timeout=120, retries=0, max_containers=1,
                  min_containers=0, buffer_containers=0, scaledown_window=2,
                  single_use_containers=True, serialized=True,
                  block_network=True, restrict_modal_access=True)
    def benchmark_pair():
        import importlib.metadata
        import subprocess
        import tempfile
        import time
        from pathlib import Path
        from scripts.m55_gpu_worker import run_method, verify_bundle
        from scripts.m36_memory_telemetry import snapshot
        started = time.perf_counter()
        verify_bundle(Path('/workspace'))
        outputs, logs = {}, {}
        container_memory = [snapshot('container_before_workers')]
        with tempfile.TemporaryDirectory(prefix='m55-output-') as output:
            for method in ('QARF', 'QPAF'):
                path = Path(output)/f'{method}.json'
                worker = run_method(method, Path('/workspace'), path)
                container_memory.append(snapshot('container_after_'+method))
                logs[method] = worker['log']
                if worker['status'] != 'COMPLETED':
                    return {'status': 'FAILED', 'outputs': outputs, 'logs': logs,
                            'failed_method': method, 'reason': worker['reason'],
                            'seconds': time.perf_counter()-started, 'container_memory': container_memory}
                outputs[method] = worker['output']
        return {'status': 'COMPLETED', 'outputs': outputs, 'logs': logs,
                'memory_request_and_limit_mib': MEMORY_MIB, 'container_memory': container_memory,
                'seconds': time.perf_counter()-started,
                'packages': {p: importlib.metadata.version(p) for p in ('torch', 'numpy', 'pandas', 'pyarrow')},
                'pip_freeze': subprocess.check_output(['python', '-m', 'pip', 'freeze'], text=True),
                'nvidia_smi': subprocess.check_output(['nvidia-smi'], text=True)}

    return app, image, benchmark_pair


def invoke_once(function, output):
    """Submit one durable input; a failed wait must never cause resubmission."""
    call = function.spawn()
    write_new(output/'function_call.json', {'function_call_id': call.object_id,
                                          'retrieval_mode': 'durable_spawn_get',
                                          'new_function_invocations': 1})
    return call.get(timeout=900)


def execute(bundle, authorization, expected_authorization_sha256, output):
    if output.exists():
        raise FileExistsError('Run namespace exists; no overwrite or retry permitted')
    if sha(authorization) != expected_authorization_sha256:
        raise ValueError('external authorization SHA256 pin differs')
    auth = read(authorization)
    manifest = verify_bundle(bundle)
    validate_authorization(auth, head=git('rev-parse', 'HEAD'),
                           clean=not git('status', '--porcelain', '--untracked-files=no'),
                           bundle_sha=sha(bundle/'bundle_manifest.json'),
                           workload_sha=sha(bundle/'input/workload.json'),
                           output_rel=output.relative_to(ROOT).as_posix())
    if manifest['source_commit'] != auth['source_commit']:
        raise ValueError('bundle source commit differs')
    import modal
    app, image, function = build_app(bundle)
    output.mkdir(parents=True, exist_ok=False)
    write_new(output/'_ATTEMPTED.json', {'authorization_sha256': sha(authorization),
                                      'started_utc': datetime.now(timezone.utc).isoformat(),
                                      'invocation_limit': 1, 'automatic_retries': 0})
    started = time.monotonic()

    def watchdog():
        write_new(output/'_WATCHDOG.json', {'elapsed_seconds': time.monotonic()-started,
                                           'status': 'KILLED_WALL_TIME_LIMIT', 'app_id': app.app_id})
        try:
            if app.app_id:
                subprocess.run([sys.executable, '-m', 'modal', 'app', 'stop', '--yes', app.app_id], timeout=30)
        finally:
            os._exit(124)

    timer = threading.Timer(900, watchdog)
    timer.daemon = True
    timer.start()
    try:
        with modal.enable_output(), app.run(detach=False):
            write_new(output/'runtime_binding.json', {'app_id': app.app_id, 'image_id': image.object_id,
                       'authorization_sha256': expected_authorization_sha256,
                       'base_image': BASE_IMAGE, 'source_commit': auth['source_commit'],
                       'bundle_manifest_sha256': sha(bundle/'bundle_manifest.json'),
                       'memory_request_and_limit_mib': MEMORY_MIB,
                       'bound_utc': datetime.now(timezone.utc).isoformat(),
                       'gpu_invocations_before_binding': 0})
            result = invoke_once(function, output)
            write_new(output/'gpu_result.json', result)
            if result['status'] != 'COMPLETED':
                raise RuntimeError('remote worker failed; see immutable gpu_result.json')
        summaries = {m: result['outputs'][m]['summary'] for m in ('QARF', 'QPAF')}
        if result['outputs']['QARF']['worker_pid'] == result['outputs']['QPAF']['worker_pid']:
            raise ValueError('method workers are not isolated processes')
        verdict = 'PASS' if all(s['resource_verdict'] == 'PASS' for s in summaries.values()) else 'FAIL'
        write_new(output/'_SUCCESS.json', {'status': 'EXECUTION_COMPLETE', 'resource_verdict': verdict,
                  'gpu_result_sha256': sha(output/'gpu_result.json'), 'summaries': summaries,
                  'elapsed_seconds_including_build': time.monotonic()-started,
                  'test_labels_deserialized': False, 'training_executed': False})
        print('GPU resource verdict:', verdict, flush=True)
    except BaseException as exc:
        write_new(output/'_FAILURE.json', {'error_type': type(exc).__name__, 'message': str(exc),
                  'elapsed_seconds': time.monotonic()-started, 'app_id': app.app_id,
                  'automatic_retry_performed': False})
        raise
    finally:
        timer.cancel()


def main():
    configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--expected-authorization-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare_bundle(args.bundle.resolve()), ensure_ascii=True, indent=2))
    elif args.authorization and args.expected_authorization_sha256 and args.output:
        execute(args.bundle.resolve(), args.authorization.resolve(), args.expected_authorization_sha256,
                args.output.resolve())
    else:
        parser.error('use --prepare or supply --authorization and --output')


if __name__ == '__main__':
    main()
