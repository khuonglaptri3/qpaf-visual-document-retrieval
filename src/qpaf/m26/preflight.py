"""Verify the frozen corpus and page IDs before scheduling any OCR."""
from collections import defaultdict
from contextlib import closing
import csv
from pathlib import Path
import re

from qpaf.m11.artifacts import digest, object_hash, read_json, utc, write_json
from qpaf.m23.policy import load_frozen_policy
from qpaf.m25.leakage import verify_frozen_splits
from .config import validate


def prepare_inputs(root, config, run):
    import pypdfium2 as pdfium
    root, run = Path(root), Path(run)
    validate(config)
    handover = read_json(root / config['policy']['handover'])
    if handover['policy']['sha256'] != config['policy']['sha256']:
        raise ValueError('M2.3 handover and selected policy differ')
    policy = load_frozen_policy(root / config['policy']['path'], config['policy']['sha256'])
    if (policy['engine']['page_ocr_timeout_seconds'], policy['resources']['workers']) != (15, 2):
        raise ValueError('Frozen runtime settings differ')
    freeze = read_json(root / config['corpus']['split_freeze'])
    if freeze['split_manifest_sha256'] != 'ea5a19f93dce07cce375d6fb6afed630606e00916c5daa10938562aee9cddfad':
        raise ValueError('M2.1 active manifest identity changed')
    split_check = verify_frozen_splits(root, freeze)
    split_check.pop('roles')
    m21 = read_json(root / freeze['split_manifest'])
    inputs = []
    for name, item in m21['data_files'].items():
        path = root / config['corpus']['raw_directory'] / name
        if path.stat().st_size != item['size_bytes'] or digest(path) != item['sha256']:
            raise ValueError('Source payload differs from M2.1: ' + name)
        inputs.append({'path': path.relative_to(root).as_posix(), 'sha256': item['sha256'],
                       'size_bytes': item['size_bytes']})
    page_manifest = root / config['corpus']['page_manifest']
    with page_manifest.open(encoding='utf-8', newline='') as stream:
        raw_pages = list(csv.DictReader(stream))
    scheduled, documents = [], defaultdict(list)
    for row in raw_pages:
        doc, number = row['document_id'], int(row['page_number'])
        if not re.fullmatch(r'[0-9a-f]{40}', doc) or row['page_id'] != f'{doc}_page_{number:04d}' or number < 1:
            raise ValueError('Noncanonical page identity')
        item = {'page_id': row['page_id'], 'document_id': doc, 'page_number': number,
                'pdf_sha256': row['file_sha256'], 'source_content_sha256': row['content_sha256']}
        scheduled.append(item)
        documents[doc].append(item)
    scheduled.sort(key=lambda r: r['page_id'])
    if (len(scheduled) != config['corpus']['page_count'] or len(documents) != config['corpus']['document_count']
            or len({r['page_id'] for r in scheduled}) != len(scheduled)):
        raise ValueError('Incomplete or duplicate full-corpus page manifest')
    pdfs = []
    for doc, pages in sorted(documents.items()):
        path = root / config['corpus']['pdf_directory'] / (doc + '.pdf')
        expected = {r['pdf_sha256'] for r in pages}
        if len(expected) != 1 or digest(path) not in expected:
            raise ValueError('PDF hash mismatch: ' + doc)
        with closing(pdfium.PdfDocument(str(path))) as pdf:
            count = len(pdf)
        if sorted(r['page_number'] for r in pages) != list(range(1, count + 1)):
            raise ValueError('Page manifest lacks a complete PDF page sequence')
        pdfs.append({'document_id': doc, 'path': path.relative_to(root).as_posix(),
                     'sha256': next(iter(expected)), 'size_bytes': path.stat().st_size,
                     'page_count': count})
    manifest = {'schema_version': 1, 'task_id': 'M2.6', 'created_utc': utc(),
                'dataset': m21['dataset'], 'source_files': inputs, 'documents': pdfs,
                'scheduled_pages': scheduled, 'page_count': len(scheduled),
                'document_count': len(documents), 'policy_sha256': config['policy']['sha256'],
                'm21_manifest_sha256': digest(root / freeze['split_manifest']),
                'page_manifest_sha256': digest(page_manifest),
                'page_ids_sha256': object_hash([r['page_id'] for r in scheduled]),
                'split_verification': split_check, 'uses_qrels': False, 'training_executed': False}
    write_json(run / 'input_manifest.json', manifest)
    (run / 'ocr_policy_frozen.toml').write_bytes((root / config['policy']['path']).read_bytes())
    return manifest
