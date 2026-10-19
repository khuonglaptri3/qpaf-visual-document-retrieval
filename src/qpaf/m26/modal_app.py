"""Single-container, two-worker full OCR with durable page checkpoints."""
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
import time
import zipfile

from qpaf.m11.artifacts import digest, file_manifest, object_hash, read_json, utc, write_csv, write_json
from qpaf.m18.namespace import parse_canonical_run_id
from qpaf.m23.policy import load_frozen_policy
from qpaf.m23.worker import MemoryMonitor, runtime_identity
from .bundle import PAGE_HASH_FIELDS, validate_records, validate_schedule
from .config import validate
from .engine import finish_page, prepare_page, recover_page


def execute_run(config, run_id, source):
    import modal
    import qpaf
    validate(config)
    if parse_canonical_run_id(run_id)['experiment_id'] != config['experiment_id']:
        raise ValueError('M2.6 run ID differs from configured experiment')
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    volume.reload()
    run = Path(config['modal']['mount_path']) / 'runs' / run_id
    inputs = read_json(run / 'input_manifest.json')
    if read_json(run / 'source.json') != source or read_json(run / 'resolved_config.json') != config:
        raise ValueError('Uploaded config/source differs from invocation')
    policy = load_frozen_policy(run / 'ocr_policy_frozen.toml', config['policy']['sha256'])
    scheduled = inputs['scheduled_pages']
    validate_schedule(inputs, config['corpus'])
    if (inputs['page_count'], inputs['document_count']) != (5385, 292) or len(scheduled) != 5385:
        raise ValueError('Incomplete full-corpus input schedule')
    output = run / 'output'
    output.mkdir(exist_ok=False)
    for name in ('input_manifest.json', 'source.json', 'resolved_config.json', 'ocr_policy_frozen.toml'):
        (output / name).write_bytes((run / name).read_bytes())
    started, rows, worker_error = time.perf_counter(), [], None
    monitor = MemoryMonitor()
    write_json(run / 'progress.json', {'status': 'RUNNING', 'completed': 0, 'scheduled': len(scheduled), 'utc': utc()})
    volume.commit()

    def checkpoint():
        progress = {'status': 'RUNNING', 'completed': len(rows), 'scheduled': len(scheduled),
                    'technical_failures': sum(r['technical_failure'] for r in rows),
                    'wall_seconds': time.perf_counter() - started, 'utc': utc()}
        write_json(run / 'progress.json', progress)
        volume.commit()  # All page futures and PDF handles are closed at this barrier.
        print(f"M2.6 {len(rows)}/{len(scheduled)} pages; failures={progress['technical_failures']}; "
              f"elapsed={progress['wall_seconds']:.1f}s", flush=True)

    try:
        with monitor:
            package = Path(qpaf.__file__).parent
            for item in source['files']:
                if item['path'].startswith('src/qpaf/') and digest(package / item['path'][len('src/qpaf/'):]) != item['sha256']:
                    raise ValueError('Remote source differs from snapshot: ' + item['path'])
            engine = policy['engine']
            identity_config = {'text': {'language': engine['language'], 'traineddata_sha256': engine['traineddata_sha256'],
                                        'engine_version': engine['version'], 'parser_version': engine['parser_version']},
                               'modal': {'cpu': config['execution']['cpu']}}
            identity = runtime_identity(identity_config)
            if identity['packages'] != {'pypdfium2': '4.30.0', 'Pillow': '11.3.0', 'psutil': '7.0.0'}:
                raise ValueError('Worker packages differ from the pinned OCR runtime')
            write_json(output / 'environment.json', identity)
            for doc in inputs['documents']:
                pdf = run / 'inputs/pdfs' / (doc['document_id'] + '.pdf')
                if pdf.stat().st_size != doc['size_bytes'] or digest(pdf) != doc['sha256']:
                    raise ValueError('Uploaded PDF hash differs: ' + doc['document_id'])
            workers = policy['resources']['workers']
            with ThreadPoolExecutor(max_workers=workers) as pool:
                size = config['execution']['checkpoint_pages']
                for offset in range(0, len(scheduled), size):
                    pending = set()
                    for page in scheduled[offset:offset + size]:
                        if time.perf_counter() - started > config['execution']['wall_seconds'] - 60:
                            raise TimeoutError('Full-run wall budget exhausted')
                        if len(pending) >= workers * 2:
                            done, pending = wait(pending, return_when=FIRST_COMPLETED)
                            rows.extend(f.result() for f in done)
                        pdf = run / 'inputs/pdfs' / (page['document_id'] + '.pdf')
                        prepared = prepare_page(page, pdf, output, policy, config)
                        remaining = config['execution']['wall_seconds'] - (time.perf_counter() - started) - 30
                        pending.add(pool.submit(finish_page, prepared, output, policy, remaining))
                    rows.extend(f.result() for f in pending)
                    checkpoint()
                    if sum(r['technical_failure'] for r in rows) > len(scheduled) * policy['failure']['max_failure_fraction']:
                        raise RuntimeError('Technical failure cap cannot be satisfied; preserve all remaining rows as NOT_RUN')
    except Exception as exc:
        import traceback
        worker_error = {'error': f'{type(exc).__name__}: {exc}', 'traceback': traceback.format_exc()}
        write_json(output / 'worker_error.json', worker_error)
        print(worker_error['error'], flush=True)
    # A partial worker attempt still accounts for every scheduled page explicitly.
    known = {r['page_id'] for r in rows}
    for page in scheduled:
        if page['page_id'] in known:
            continue
        rows.append(recover_page(page, output, policy, config['policy']['sha256']))
    rows.sort(key=lambda r: r['page_id'])
    write_json(output / 'resolved_pages.json', rows)
    write_json(output / 'failures.json', [r for r in rows if r['technical_failure']])
    fields = PAGE_HASH_FIELDS
    write_csv(output / 'page_hashes.csv', [{k: r.get(k) for k in fields} for r in rows], fields)
    checks = validate_records(rows, scheduled, output, policy, config['policy']['sha256'], maximum_fraction=1.)
    by_doc = defaultdict(list)
    for row in rows:
        by_doc[row['document_id']].append(row)
    (output / 'archives').mkdir()
    for doc, pages in sorted(by_doc.items()):
        with zipfile.ZipFile(output / 'archives' / (doc + '.zip'), 'x', compression=zipfile.ZIP_STORED) as archive:
            for row in pages:
                for path in sorted((output / 'pages' / row['page_id']).iterdir()):
                    if path.is_file():
                        archive.write(path, path.relative_to(output).as_posix())
    resources = {'wall_seconds': time.perf_counter() - started,
                 'peak_python_and_children_rss_mib': monitor.peak_mib,
                 'workers': workers if 'workers' in locals() else 2, 'cpu': 4, 'gpu_requested': False,
                 'ocr_timeout_seconds': engine['page_ocr_timeout_seconds'] if 'engine' in locals() else 15,
                 'render_seconds_sum': sum(r.get('render_seconds', 0) for r in rows),
                 'ocr_subprocess_seconds_sum': sum(r['ocr'].get('seconds', 0) for r in rows),
                 'artifact_bytes_before_manifests': sum(p.stat().st_size for p in output.rglob('*') if p.is_file())}
    write_json(output / 'resources.json', resources)
    limits = {'wall': resources['wall_seconds'] <= config['execution']['wall_seconds'],
              'ram': monitor.peak_mib <= policy['resources']['ram_mib'],
              'failure_cap': checks['failure_fraction'] <= policy['failure']['max_failure_fraction']}
    summary = {'status': 'COMPLETE' if worker_error is None and all(limits.values()) else 'FAIL',
               'task_id': 'M2.6', 'run_id': run_id, 'completed_utc': utc(), **checks,
               'resource_checks': limits, 'worker_error': worker_error, 'gpu_requested': False,
               'training_executed': False, 'corpus_accuracy_certified': False}
    write_json(output / 'summary.json', summary)
    write_json(output / 'handover.json', {
        'schema_version': 1, 'task_id': 'M2.6', 'run_id': run_id, 'status': summary['status'],
        'policy_sha256': config['policy']['sha256'], 'page_count': len(rows), 'document_count': len(by_doc),
        'page_ids_sha256': inputs['page_ids_sha256'], 'input_manifest_sha256': digest(output / 'input_manifest.json'),
        'resolved_pages_path': 'resolved_pages.json', 'resolved_pages_sha256': digest(output / 'resolved_pages.json'),
        'page_hashes_path': 'page_hashes.csv', 'page_hashes_sha256': digest(output / 'page_hashes.csv'),
        'preprocessing_identity_sha256': object_hash([(r['page_id'], r['text_sha256'], r['policy_sha256']) for r in rows]),
        'm24_score_schema': 'qpaf_score_rows_v1', 'm24_candidate_cap': 600,
        'm28_contract': 'shared canonical page IDs, text hashes and policy hash for all retrievers and both gates',
        'failed_pages_preserved': True, 'no_text_visual_pages_preserved': True,
        'limitations': ['Frozen policy is not a corpus OCR accuracy certificate.',
                        'No retrieval scores, learned training or quality metrics are produced by this OCR task.']})
    write_json(output / 'hashes.json', file_manifest(output, exclude=('hashes.json',)))
    write_json(run / 'progress.json', {'status': summary['status'], 'completed': len(rows),
                                      'scheduled': len(scheduled), 'technical_failures': checks['technical_failures'],
                                      'wall_seconds': resources['wall_seconds'], 'utc': utc()})
    volume.commit()
    print(summary, flush=True)
    return summary


def build_app(config, root):
    import modal
    validate(config)
    root = Path(root)
    policy = load_frozen_policy(root / config['policy']['path'], config['policy']['sha256'])
    engine = policy['engine']
    image = (modal.Image.debian_slim(python_version=config['modal']['python_version'])
             .apt_install('tesseract-ocr=' + engine['package'], 'tesseract-ocr-eng=' + engine['language_package'])
             .pip_install_from_requirements(str(root / config['modal']['requirements_file']))
             .env({'OMP_THREAD_LIMIT': '1', 'OMP_NUM_THREADS': '1'})
             .add_local_python_source('qpaf'))
    volume = modal.Volume.from_name(config['modal']['volume_name'], create_if_missing=True)
    app = modal.App(config['modal']['app_name'])
    worker = app.function(image=image, cpu=config['execution']['cpu'], memory=config['execution']['ram_mib'],
                          timeout=config['execution']['wall_seconds'] + 60, retries=0, max_containers=1,
                          volumes={config['modal']['mount_path']: volume})(execute_run)
    return app, worker, volume
