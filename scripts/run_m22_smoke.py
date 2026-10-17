"""Bounded M2.2 smoke runner; --prepare-only never imports Modal or PyTorch."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import shutil
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m11.artifacts import (digest, file_manifest, read_json, source_provenance, utc, write_json)
from qpaf.m11.dataset import extract_zip
from qpaf.m18.namespace import format_canonical_run_id, parse_canonical_run_id
from qpaf.m22.config import load_config
from qpaf.m22.evidence import publish_revision, verify_run
from qpaf.m22.sample import prepare_sample, pack_folder, validate_inputs
from qpaf.m22.telemetry import failure_record


def write_report(folder, summary):
    lines = ['# M2.2 — Three-retriever smoke report', '', f"Status: **{summary['status']}**", '',
             f"Run: `{folder.name}`. Validation/training sample only; no test queries.", '',
             '| Stage | Status | Seconds | Peak RSS MiB | Peak reserved VRAM MiB |',
             '|---|---|---:|---:|---:|']
    for name, result in summary['stages'].items():
        r = result.get('resources', {})
        lines.append(f"| {name} | {result['status']} | {r.get('elapsed_seconds', 0):.3f} | "
                     f"{r.get('peak_rss_mb', 0):.1f} | {r.get('peak_cuda_reserved_mb', 0):.1f} |")
    lines.extend(['', 'Model: ColQwen2.5 (`vidore/colqwen2.5-v0.2`), BGE-M3, frozen BM25.',
                  'See resolved_config.json for full model/base/tokenizer/processor commits and predeclared tolerances.',
                  'See remote/<stage>/checks.json, resources.json, environment.json and model_files.json.', '',
                  'Limits: small ID-selected page sample, provisional OCR thresholds, 256 visual-token cap. '
                  'No claim about full-corpus recall, OCR calibration or learned retrieval quality.', ''])
    (folder/'report.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'configs/m2.2/retriever_smoke.toml')
    parser.add_argument('--run-id')
    parser.add_argument('--retry-of', help='Previous canonical run ID; records lineage without overwriting it')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--execute-prepared', type=Path, help='Execute an existing prepare-only run exactly once')
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--publish', type=Path, help='Create evidence revision from --verify run')
    args = parser.parse_args(argv)
    if args.verify:
        print(verify_run(args.verify), flush=True)
        if args.publish:
            publish_revision(args.verify, args.publish, ROOT)
            print(f'Evidence revision: {args.publish}', flush=True)
        return 0
    config = load_config(args.config)
    if args.execute_prepared:
        folder = args.execute_prepared.resolve()
        run_id = folder.name
        parse_canonical_run_id(run_id)
        if read_json(folder/'resolved_config.json') != config:
            raise ValueError('Prepared-run config mismatch')
        if (folder/'execution_started.json').exists():
            raise FileExistsError('Prepared run already executed; use a new run ID')
        validate_inputs(folder/'inputs', config)
    else:
        run_id = args.run_id or format_canonical_run_id(config['experiment_id'], datetime.now(timezone.utc))
        if parse_canonical_run_id(run_id)['experiment_id'] != config['experiment_id']:
            raise ValueError('Run ID/experiment mismatch')
        folder = ROOT/config['output']['local_dir']/run_id
        folder.mkdir(parents=True, exist_ok=False)
        write_json(folder/'resolved_config.json', config)
        source = source_provenance(ROOT, config['modal']['requirements_file'])
        write_json(folder/'source.json', source)
        with zipfile.ZipFile(folder/'source_snapshot.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for row in source['files']:
                path = ROOT/row['path']
                if path.is_file():
                    archive.write(path, row['path'])
            archive.write(args.config, 'configs/m2.2/retriever_smoke.toml')
        print(f'Preparing {run_id}', flush=True)
        try:
            prepare_sample(ROOT, config, folder/'inputs')
        except Exception as exc:
            write_json(folder/'preparation_failure.json', failure_record(exc))
            raise
    print(f'Run directory: {folder}', flush=True)
    if args.prepare_only:
        print('Sample prepared and verified; no cloud execution.', flush=True)
        return 0
    payload = pack_folder(folder/'inputs', config['caps']['input_mb'])
    # A prepared sample may only run with the exact implementation it was prepared for.
    if read_json(folder/'source.json')['digest'] != source_provenance(ROOT, config['modal']['requirements_file'])['digest']:
        raise ValueError('Source changed after preparation; create a new run')
    if args.retry_of and parse_canonical_run_id(args.retry_of)['experiment_id'] != config['experiment_id']:
        raise ValueError('Retry lineage must refer to the same experiment')
    write_json(folder/'execution_started.json', {'started_utc': utc(), 'command': [sys.executable, *sys.argv],
                                               'retry_of': args.retry_of})
    from qpaf.m22.worker import build_app
    import modal
    app, init, cpu, gpu, fetch = build_app(config, ROOT)
    results = {}
    cloud_error = None
    with modal.enable_output(), app.run():
        try:
            init.remote(config, run_id, payload, read_json(folder/'source.json'))
            for stage in ('prepare', 'bm25', 'dense', 'visual'):
                if stage != 'prepare' and results.get('prepare', {}).get('status') != 'PASS':
                    results[stage] = {'status': 'NOT_RUN', 'reason': 'Text preparation did not pass'}
                    continue
                print(f'Starting {stage}', flush=True)
                try:
                    results[stage] = (gpu if stage in ('dense', 'visual') else cpu).remote(stage, config, run_id)
                except Exception as exc:
                    results[stage] = failure_record(exc)
                print(f"{stage}: {results[stage]['status']}", flush=True)
        except Exception as exc:
            cloud_error = failure_record(exc)
        finally:
            try:
                data = fetch.remote(config, run_id)
                (folder/'remote').mkdir(exist_ok=False)
                extract_zip(io.BytesIO(data), folder/'remote')
            except Exception as exc:
                cloud_error = failure_record(exc)
    summary = {'schema_version': 1, 'task_id': 'M2.2', 'run_id': run_id,
               'status': 'PASS' if cloud_error is None and len(results) == 4 and all(r['status'] == 'PASS' for r in results.values()) else 'FAIL',
               'completed_utc': utc(), 'stages': results, 'cloud_error': cloud_error,
               'modal_volume': config['modal']['volume_name'], 'modal_path': f'runs/{run_id}',
               'retry_of': args.retry_of,
               'sample_manifest_sha256': digest(folder/'inputs'/'sample_manifest.json')}
    write_json(folder/'summary.json', summary)
    write_report(folder, summary)
    write_json(folder/'hashes.json', file_manifest(folder, exclude=('hashes.json',)))
    if summary['status'] == 'PASS':
        print(verify_run(folder), flush=True)
    print(f"M2.2 {summary['status']}: {folder/'report.md'}", flush=True)
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
