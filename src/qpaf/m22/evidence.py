"""Read-only run verification and create-once lightweight handover revisions."""
import shutil
from pathlib import Path

from qpaf.m11.artifacts import digest, file_manifest, read_json, verify_manifest, write_json
from qpaf.m11.retrieval import load_score_cache
from .sample import validate_inputs


def verify_run(folder):
    folder = Path(folder)
    verify_manifest(folder, read_json(folder/'hashes.json'))
    config = read_json(folder/'resolved_config.json')
    queries, pages, meta = validate_inputs(folder/'inputs', config)
    remote = folder/'remote'
    validate_inputs(remote/'inputs', config)
    if read_json(remote/'resolved_config.json') != config:
        raise ValueError('Remote configuration differs from local run')
    if read_json(remote/'source.json') != read_json(folder/'source.json'):
        raise ValueError('Remote source identity mismatch')
    for stage in ('prepare', 'bm25', 'dense', 'visual'):
        verify_manifest(remote/stage, read_json(remote/stage/'hashes.json'))
        summary = read_json(remote/stage/'summary.json')
        if summary['status'] != 'PASS':
            raise ValueError(f'{stage} did not pass')
        if not all(summary['resource_checks'].values()):
            raise ValueError('A resource check failed')
        if stage != 'prepare':
            load_score_cache(remote/stage, meta['query_ids'], meta['page_ids'], stage)
            if not all(c['passed'] for c in summary['checks'].values()):
                raise ValueError('A parity check failed')
    if read_json(folder/'summary.json')['status'] != 'PASS':
        raise ValueError('Run summary did not pass')
    return {'status': 'VERIFIED', 'run_id': folder.name, 'queries': len(queries), 'pages': len(pages),
            'run_hash_manifest_sha256': digest(folder/'hashes.json')}


def publish_revision(run_folder, output, repo_root):
    run_folder, output = Path(run_folder), Path(output)
    verification = verify_run(run_folder)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    for name in ('resolved_config.json', 'source.json', 'summary.json', 'hashes.json', 'report.md'):
        shutil.copyfile(run_folder/name, output/('run_hashes.json' if name == 'hashes.json' else name))
    shutil.copyfile(run_folder/'inputs'/'sample_manifest.json', output/'sample_manifest.json')
    for stage in ('prepare', 'bm25', 'dense', 'visual'):
        target = output/stage
        target.mkdir()
        for name in ('summary.json', 'resources.json', 'hashes.json', 'checks.json', 'environment.json', 'model_files.json'):
            source = run_folder/'remote'/stage/name
            if source.exists():
                shutil.copyfile(source, target/name)
    location = run_folder.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    write_json(output/'verification.json', {**verification, 'run_location': location,
        'large_payload_policy': 'Scores/embeddings remain in local results and the named Modal Volume; hashes bind them.'})
    (output/'README.md').write_text(
        '# M2.2 — Bounded three-retriever calibration\n\n'
        f"Status: PASS; run `{run_folder.name}`.\n\n"
        'BM25, BGE-M3 and ColQwen2.5 passed the recorded checks on the same bounded sample. '
        'This is engineering calibration, not full-corpus retrieval quality or learned evaluation.\n\n'
        f'Local run: `{location}`. Modal Volume and remote paths are recorded in summary.json. '
        'The artifact hashes in run_hashes.json include large payloads excluded from Git.\n', encoding='utf-8')
    write_json(output/'hash_manifest.json', file_manifest(output))
