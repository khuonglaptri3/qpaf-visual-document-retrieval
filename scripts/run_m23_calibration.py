"""Prepare/run/verify a CPU-only OCR calibration and build the human review workspace."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m11.artifacts import digest, file_manifest, read_json, source_provenance, utc, verify_manifest, write_json
from qpaf.m11.dataset import extract_zip
from qpaf.m18.namespace import format_canonical_run_id
from qpaf.m22.sample import pack_folder
from qpaf.m23.config import load_config
from qpaf.m23.review import build_review
from qpaf.m23.sample import prepare_sample, validate_inputs


def verify_run(folder):
    folder = Path(folder)
    if (folder / 'hashes.json').exists():
        verify_manifest(folder, read_json(folder / 'hashes.json'))
    config = read_json(folder / 'resolved_config.json')
    validate_inputs(folder / 'inputs', config)
    verify_manifest(folder / 'remote', read_json(folder / 'remote/hashes.json'))
    if read_json(folder / 'remote/source.json') != read_json(folder / 'source.json'):
        raise ValueError('Source provenance differs on remote')
    if read_json(folder / 'remote/resolved_config.json') != config:
        raise ValueError('Remote config mismatch')
    remote = read_json(folder / 'remote/summary.json')
    if remote['status'] not in ('DATA_READY_REVIEW_PENDING', 'DATA_READY_WITH_ERRORS_REVIEW_PENDING'):
        raise ValueError('OCR data is not ready')
    if not all(remote['resource_checks'].values()):
        raise ValueError('Resource check failed')
    pages = read_json(folder / 'remote/pages.json')
    if [p['page_id'] for p in pages] != read_json(folder / 'inputs/sample_manifest.json')['page_ids']:
        raise ValueError('Output page namespace/order mismatch')
    return {'status': 'VERIFIED_ENGINEERING_DATA', 'pages': len(pages), 'human_review_status': 'PENDING',
            'remote_hash_manifest_sha256': digest(folder / 'remote/hashes.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/m2.3/ocr_calibration.toml')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--execute-prepared', type=Path)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--build-review', type=Path)
    args = parser.parse_args()
    if args.verify:
        print(verify_run(args.verify))
        return 0
    if args.build_review:
        verify_run(args.build_review)
        config = read_json(args.build_review / 'resolved_config.json')
        print(build_review(args.build_review, ROOT / config['output']['review_directory'], ROOT / 'src/qpaf/m23/review_template.html'))
        return 0
    config = load_config(args.config)
    if args.execute_prepared:
        folder = args.execute_prepared.resolve()
        if (folder / 'execution_started.json').exists():
            raise ValueError('Run already executed; create a new run')
        if read_json(folder / 'resolved_config.json') != config:
            raise ValueError('Prepared config changed')
        if read_json(folder / 'source.json')['digest'] != source_provenance(ROOT, config['modal']['requirements_file'])['digest']:
            raise ValueError('Implementation changed since preparation')
        validate_inputs(folder / 'inputs', config)
    else:
        run_id = format_canonical_run_id(config['experiment_id'], datetime.now(timezone.utc))
        folder = ROOT / config['output']['directory'] / run_id
        folder.mkdir(parents=True, exist_ok=False)
        write_json(folder / 'resolved_config.json', config)
        source = source_provenance(ROOT, config['modal']['requirements_file'])
        source['review_template_sha256'] = digest(ROOT / 'src/qpaf/m23/review_template.html')
        write_json(folder / 'source.json', source)
        with zipfile.ZipFile(folder / 'source_snapshot.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for row in source['files']:
                path = ROOT / row['path']
                if path.is_file():
                    archive.write(path, row['path'])
            archive.write(args.config, 'configs/m2.3/ocr_calibration.toml')
            archive.write(ROOT / 'src/qpaf/m23/review_template.html', 'src/qpaf/m23/review_template.html')
        print('Preparing ' + folder.name, flush=True)
        prepare_sample(ROOT, config, folder / 'inputs')
    print('Run directory: ' + str(folder), flush=True)
    if args.prepare_only:
        return 0
    from qpaf.m23.worker import build_app
    import modal
    payload = pack_folder(folder / 'inputs', config['caps']['input_mib'])
    write_json(folder / 'execution_started.json', {'started_utc': utc(), 'command': [sys.executable, *sys.argv]})
    app, work, fetch = build_app(config, ROOT)
    error, result = None, None
    with modal.enable_output(), app.run():
        try:
            result = work.remote(config, folder.name, payload, read_json(folder / 'source.json'))
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        finally:
            try:
                archive = fetch.remote(config, folder.name)
                extract_zip(io.BytesIO(archive), folder / 'remote')
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
    summary = {'task_id': 'M2.3', 'run_id': folder.name, 'completed_utc': utc(), 'worker': result,
               'cloud_error': error, 'status': result['status'] if result and not error else 'FAIL',
               'human_review_status': 'PENDING', 'thresholds_frozen': False,
               'modal_volume': config['modal']['volume_name'], 'modal_path': f'runs/{folder.name}',
               'app_id': app.app_id}
    write_json(folder / 'summary.json', summary)
    if not error and summary['status'].startswith('DATA_READY'):
        write_json(folder / 'verification.json', verify_run(folder))
        template = ROOT / 'src/qpaf/m23/review_template.html'
        build_review(folder, folder / 'review', template)
        review_path = build_review(folder, ROOT / config['output']['review_directory'], template)
        print('Review workspace: ' + str(review_path), flush=True)
    write_json(folder / 'hashes.json', file_manifest(folder, exclude=('hashes.json',)))
    print(summary['status'], flush=True)
    return 0 if summary['status'].startswith('DATA_READY') else 1


if __name__ == '__main__':
    raise SystemExit(main())
