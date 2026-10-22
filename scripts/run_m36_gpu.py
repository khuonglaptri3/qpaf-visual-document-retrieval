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
from scripts.m36_gpu_worker import label_free_records, read, sha, verify_bundle, write_new

REVIEW = ROOT/'evidence/revisions/m3.6-001/gpu_protocol_review'
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
    plan = read(REVIEW/'gpu_review_plan.json')
    if sha(REVIEW/'gpu_review_plan.json') != '7d46b9abe8633dba6236f7e6b9e4026d43f60e4b13a36e756c9ad96ff1dd99f5':
        raise ValueError('reviewed plan drift')
    if sha(REVIEW/'gpu_workload.json') != '3356630bfbf84aa7d984dccf22c1c81ca22bb8a65dc5cfe904896a43ae00ddf7':
        raise ValueError('reviewed workload drift')
    if git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('tracked source must be committed before preparation')
    git('ls-files', '--error-unmatch', 'scripts/m36_gpu_worker.py', 'scripts/run_m36_gpu.py')
    auth = read(ROOT/plan['checkpoint_inputs']['QPAF']['authorization'])
    seal = ROOT/auth['sealed_inputs']['run_path']
    for rel, expected in plan['source_inputs'].items():
        if 'qrels' not in rel and sha(seal/rel) != expected:
            raise ValueError('sealed input differs: '+rel)
    if sha(seal/'manifest.json') != plan['seal_manifest_sha256']:
        raise ValueError('external seal manifest pin differs')
    workload = read(REVIEW/'gpu_workload.json')
    ids = [r['query_id'] for r in workload['warmup']+workload['measured']]
    config = load_config(seal/'inputs/shared_base.toml')
    records = label_free_records(read_score_rows(seal/'inputs/score_cache.parquet'),
                                 read(seal/'inputs/query_texts.json'), ids,
                                 config['data']['max_candidates'])
    # Cross-check the sealed candidate contract without opening a label column.
    import pandas as pd
    frame = pd.read_parquet(seal/'inputs/candidate_set.parquet', columns=['query_id', 'page_id'])
    candidates = {}
    for row in frame.itertuples(index=False):
        candidates.setdefault(row.query_id, set()).add(row.page_id)
    if any(set(r['page_ids']) != candidates.get(r['query_id']) for r in records):
        raise ValueError('score rows differ from frozen candidate set')
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'input').mkdir()
    (destination/'scripts').mkdir()
    # Source-only snapshot. No repository root, .env, user files or result tree is mounted.
    for rel in git('ls-files', 'src').splitlines():
        path = ROOT/rel
        if path.suffix != '.py':
            continue
        target = destination/path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for name in ('m36_gpu_worker.py',):
        shutil.copyfile(ROOT/'scripts'/name, destination/'scripts'/name)
    shutil.copyfile(seal/'inputs/shared_base.toml', destination/'input/shared_base.toml')
    shutil.copyfile(REVIEW/'gpu_workload.json', destination/'input/workload.json')
    write_new(destination/'input/queries_scores.json', records)
    for method, spec in plan['checkpoint_inputs'].items():
        for rel, expected in ((spec['path'], spec['sha256']),
                              (spec['authorization'], spec['authorization_sha256'])):
            if sha(ROOT/rel) != expected:
                raise ValueError('checkpoint/authorization pin differs: '+method)
        predictions = (ROOT/spec['path']).parents[1]/'validation_predictions.json'
        if sha(predictions) != spec['predictions_sha256']:
            raise ValueError('prediction pin differs: '+method)
        shutil.copyfile(ROOT/spec['path'], destination/f'input/{method}_best.pt')
        shutil.copyfile(predictions, destination/f'input/{method}_validation_predictions.json')
    manifest = {'schema_version': 1, 'source_commit': git('rev-parse', 'HEAD'),
                'seal_manifest_sha256': plan['seal_manifest_sha256'],
                'workload_sha256': sha(REVIEW/'gpu_workload.json'),
                'query_count': len(records), 'candidate_count': sum(len(r['page_ids']) for r in records),
                'contains_qrels': False, 'held_out_text_score_access_authority':
                'User: Chay di roi bao cao ket qua ve day nho deepsearch truoc khi lam',
                'files': {p.relative_to(destination).as_posix(): sha(p)
                          for p in sorted(destination.rglob('*')) if p.is_file()}}
    write_new(destination/'bundle_manifest.json', manifest)
    verify_bundle(destination)
    return manifest


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
    app = modal.App('qpaf-m36-resource', include_source=False)

    @app.function(image=image, gpu='A10', cpu=(2., 2.), memory=(4096, 4096),
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
        from scripts.m36_gpu_worker import run_method, verify_bundle
        started = time.perf_counter()
        verify_bundle(Path('/workspace'))
        outputs, logs = {}, {}
        with tempfile.TemporaryDirectory(prefix='m36-output-') as output:
            for method in ('QARF', 'QPAF'):
                path = Path(output)/f'{method}.json'
                worker = run_method(method, Path('/workspace'), path)
                logs[method] = worker['log']
                if worker['status'] != 'COMPLETED':
                    return {'status': 'FAILED', 'outputs': outputs, 'logs': logs,
                            'failed_method': method, 'reason': worker['reason'],
                            'seconds': time.perf_counter()-started}
                outputs[method] = worker['output']
        return {'status': 'COMPLETED', 'outputs': outputs, 'logs': logs,
                'seconds': time.perf_counter()-started,
                'packages': {p: importlib.metadata.version(p) for p in ('torch', 'numpy', 'pandas', 'pyarrow')},
                'pip_freeze': subprocess.check_output(['python', '-m', 'pip', 'freeze'], text=True),
                'nvidia_smi': subprocess.check_output(['nvidia-smi'], text=True)}

    return app, image, benchmark_pair


def execute(bundle, authorization, expected_authorization_sha256, output):
    if sha(authorization) != expected_authorization_sha256:
        raise ValueError('external authorization SHA256 pin differs')
    auth = read(authorization)
    manifest = verify_bundle(bundle)
    if (auth['status'] != 'AUTHORIZED_BY_KHUONG_WORKING_SESSION' or
            auth['source_commit'] != git('rev-parse', 'HEAD') or
            git('status', '--porcelain', '--untracked-files=no') or
            sha(bundle/'bundle_manifest.json') != auth['bundle_manifest_sha256'] or
            manifest['source_commit'] != auth['source_commit'] or
            auth['invocations'] != 1 or auth['automatic_retries'] != 0 or
            auth['output_path'] != output.relative_to(ROOT).as_posix() or
            auth['approval']['text'] != 'Chạy đi  rồi báo cáo kết quả về đây nhớ deepsearch trước khi làm'):
        raise ValueError('source, authorization, namespace or invocation contract differs')
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
                       'bound_utc': datetime.now(timezone.utc).isoformat(),
                       'gpu_invocations_before_binding': 0})
            result = function.remote()
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
