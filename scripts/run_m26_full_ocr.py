"""Prepare, execute, collect and independently verify the full ViDoSeek OCR run."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m11.artifacts import digest, read_json, source_provenance, utc, write_json
from qpaf.m18.namespace import format_canonical_run_id
from qpaf.m26.bundle import checked_path, verify_bundle
from qpaf.m26.config import load_config, validate
from qpaf.m26.collection import atomic_payload, collect_partial
from qpaf.m26.preflight import prepare_inputs


def prepare(config, config_path):
    run_id = format_canonical_run_id(config['experiment_id'], datetime.now(timezone.utc))
    folder = ROOT / config['output']['directory'] / run_id
    folder.mkdir(parents=True, exist_ok=False)
    write_json(folder / 'resolved_config.json', config)
    source = source_provenance(ROOT, config['modal']['requirements_file'])
    write_json(folder / 'source.json', source)
    print('Verifying all source PDFs and frozen splits...', flush=True)
    inputs = prepare_inputs(ROOT, config, folder)
    with zipfile.ZipFile(folder / 'source_snapshot.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for item in source['files']:
            path = ROOT / item['path']
            if path.is_file():
                archive.write(path, item['path'])
        archive.write(config_path, 'configs/m2.6/full_ocr.toml')
        archive.write(folder / 'ocr_policy_frozen.toml', 'configs/m2.3/ocr_policy_frozen.toml')
    print(f"Prepared {inputs['document_count']} documents / {inputs['page_count']} pages: {folder}", flush=True)
    return folder


def upload(volume, folder, inputs):
    remote = '/runs/' + folder.name
    print(f"Uploading verified schedule/source/policy; {len(inputs['documents'])} PDFs will be fetched by hash in cloud...", flush=True)
    with volume.batch_upload() as batch:
        for name in ('input_manifest.json', 'source.json', 'resolved_config.json',
                     'ocr_policy_frozen.toml', 'source_snapshot.zip'):
            batch.put_file(folder / name, remote + '/' + name)


def collect(folder):
    import modal
    folder = Path(folder).resolve()
    config = validate(read_json(folder / 'resolved_config.json'))
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    remote = '/runs/' + folder.name + '/output/'
    output = folder / 'output'
    output.mkdir(exist_ok=True)
    manifest_path = output / 'hashes.json'
    try:
        data = b''.join(volume.read_file(remote + 'hashes.json'))
    except FileNotFoundError:
        return collect_partial(folder, volume)
    if manifest_path.exists() and manifest_path.read_bytes() != data:
        raise ValueError('Completed remote manifest changed')
    if not manifest_path.exists():
        atomic_payload(manifest_path, data)
    records = read_json(manifest_path)
    lookup = {r['path']: r for r in records}
    if len(lookup) != len(records):
        raise ValueError('Duplicate remote manifest paths')
    downloads = [r for r in records if not r['path'].startswith('pages/')]

    def fetch(item):
        path = checked_path(output, item['path'])
        if path.is_file():
            if path.stat().st_size != item['size_bytes'] or digest(path) != item['sha256']:
                raise ValueError('Existing local artifact differs: ' + item['path'])
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.part')
        with temporary.open('wb') as stream:
            volume.read_file_into_fileobj(remote + item['path'], stream)
        if temporary.stat().st_size != item['size_bytes'] or digest(temporary) != item['sha256']:
            raise ValueError('Downloaded artifact checksum mismatch: ' + item['path'])
        temporary.replace(path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, item) for item in downloads]
        for count, future in enumerate(as_completed(futures), 1):
            future.result()
            if count % 25 == 0 or count == len(futures):
                print(f'Collected metadata/archives {count}/{len(futures)}', flush=True)
    for archive_path in sorted((output / 'archives').glob('*.zip')):
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                item = lookup.get(info.filename)
                if item is None or not info.filename.startswith('pages/'):
                    raise ValueError('Archive member is not a declared page artifact')
                path = checked_path(output, info.filename)
                if path.is_file():
                    if path.stat().st_size != item['size_bytes'] or digest(path) != item['sha256']:
                        raise ValueError('Existing extracted artifact differs: ' + info.filename)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = archive.read(info)
                import hashlib
                if len(payload) != item['size_bytes'] or hashlib.sha256(payload).hexdigest() != item['sha256']:
                    raise ValueError('Archive member checksum mismatch: ' + info.filename)
                atomic_payload(path, payload)
    print('Recomputing local hashes and replaying the frozen policy...', flush=True)
    result = verify_bundle(folder)
    path = folder / 'verification.json'
    if path.exists() and read_json(path) != result:
        raise ValueError('Existing verification receipt differs; never overwrite completed evidence')
    if not path.exists():
        write_json(path, result)
    print(result, flush=True)
    print('Saved full OCR bundle: ' + str(output), flush=True)
    return result


def execute(folder):
    import modal
    from qpaf.m26.modal_app import build_app
    folder = Path(folder).resolve()
    config = validate(read_json(folder / 'resolved_config.json'))
    if (folder / 'execution.json').exists() or (folder / 'upload_started.json').exists():
        raise ValueError('Run was already submitted; use --status/--collect or a new run ID')
    source = read_json(folder / 'source.json')
    if source['digest'] != source_provenance(ROOT, config['modal']['requirements_file'])['digest']:
        raise ValueError('Implementation changed after preparation; create a new run')
    inputs = read_json(folder / 'input_manifest.json')
    if digest(folder / 'ocr_policy_frozen.toml') != config['policy']['sha256']:
        raise ValueError('Prepared policy changed')
    app, worker, volume = build_app(config, ROOT)
    with modal.enable_output():
        write_json(folder / 'upload_started.json', {'utc': utc(), 'volume': config['modal']['volume_name']})
        upload(volume, folder, inputs)
        with app.run(detach=True):
            call = worker.spawn(config, folder.name, source)
            write_json(folder / 'execution.json', {'started_utc': utc(), 'app_id': app.app_id,
                                                  'function_call_id': call.object_id,
                                                  'volume': config['modal']['volume_name'],
                                                  'remote_path': '/runs/' + folder.name})
            print('Submitted full OCR run: ' + folder.name, flush=True)
            print('App: ' + app.app_id + '; call: ' + call.object_id, flush=True)
            try:
                result = call.get()
            except Exception as exc:
                write_json(folder / 'execution_error.json', {'utc': utc(), 'error': f'{type(exc).__name__}: {exc}'})
                collect_partial(folder, volume)
                raise
            write_json(folder / 'worker_result.json', result)
    return collect(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/m2.6/full_ocr.toml')
    parser.add_argument('--prepare-only', action='store_true')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--execute-prepared', type=Path)
    modes.add_argument('--collect', type=Path)
    modes.add_argument('--verify', type=Path)
    modes.add_argument('--status', type=Path)
    args = parser.parse_args()
    if args.status:
        import modal
        config = validate(read_json(args.status / 'resolved_config.json'))
        volume = modal.Volume.from_name(config['modal']['volume_name'])
        print(b''.join(volume.read_file('/runs/' + args.status.name + '/progress.json')).decode(), flush=True)
        return 0
    if args.verify:
        print(verify_bundle(args.verify), flush=True)
        return 0
    if args.collect:
        result = collect(args.collect)
        return 0 if result['status'] == 'VERIFIED_FULL_OCR_BUNDLE' else 2
    if args.execute_prepared:
        execute(args.execute_prepared)
        return 0
    config = load_config(args.config)
    folder = prepare(config, args.config)
    if not args.prepare_only:
        execute(folder)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
