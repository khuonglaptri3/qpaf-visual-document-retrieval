"""Portable small evidence package with a verifiable upstream provenance chain."""
import io
from pathlib import Path
import zipfile

from .artifacts import digest, read_json, verify_manifest
from .pipeline import resolve_stage


UPSTREAM_METADATA = frozenset({
    'receipt.json', 'resolved_config.json', 'provenance.json', 'run.log',
    'status.json', 'hashes.csv', 'compute.json', 'dataset.json',
    'scores.json', 'page_manifest.csv', 'queries.json', 'qrels.json',
})


def pack_evidence(root, config, source):
    memo = {}
    oracle = resolve_stage(root, 'oracle', config, source, memo)
    if oracle is None:
        raise ValueError('Oracle stage has not completed')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(oracle.iterdir()):
            if path.is_file():
                archive.write(path, path.name)
        for stage in ('prepare', 'bm25', 'dense', 'visual'):
            for path in sorted(memo[stage].iterdir()):
                if path.is_file() and path.name in UPSTREAM_METADATA:
                    archive.write(path, f'upstream/{stage}/{path.name}')
    return stream.getvalue()


def verify_evidence(root):
    root = Path(root)
    receipt = read_json(root/'receipt.json')
    verify_manifest(root, receipt['outputs'])
    for stage in ('prepare', 'bm25', 'dense', 'visual'):
        folder = root/'upstream'/stage
        if digest(folder/'receipt.json') != receipt['inputs'][stage]:
            raise ValueError(f'{stage}: upstream receipt hash mismatch')
        upstream = read_json(folder/'receipt.json')
        files = {path.name for path in folder.iterdir() if path.is_file() and path.name != 'receipt.json'}
        # Derive required metadata from the receipt, not the surviving files.
        expected = [row for row in upstream['outputs'] if row['path'] in UPSTREAM_METADATA]
        if {row['path'] for row in expected} != files:
            raise ValueError(f'{stage}: missing or unexpected upstream metadata file')
        verify_manifest(folder, expected)
        if stage != 'prepare' and upstream['inputs']['prepare'] != receipt['inputs']['prepare']:
            raise ValueError(f'{stage}: upstream dataset chain mismatch')
