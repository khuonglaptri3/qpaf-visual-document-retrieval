"""Pinned full-corpus preflight; only query IDs/text are accessed before freeze."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from qpaf.m11.artifacts import digest, object_hash, read_json, write_json
from qpaf.m25.leakage import verify_frozen_splits


def read_query_texts(path, expected_sha256, expected_ids):
    if digest(path) != expected_sha256:
        raise ValueError('ViDoSeek annotation hash mismatch')
    rows = read_json(path)['examples']
    result = {}
    for row in rows:
        qid, text = row['uid'], row['query']
        if (not isinstance(qid, str) or not qid.strip() or qid in result
                or not isinstance(text, str) or not text.strip()):
            raise ValueError('Duplicate or malformed query ID/text')
        result[qid] = text.strip()
    if set(result) != set(expected_ids) or len(result) != len(expected_ids):
        raise ValueError('Query IDs differ from frozen split union')
    return {qid: result[qid] for qid in expected_ids}


def validate_pages(pages, handover):
    seen, docs = set(), set()
    for row in pages:
        pid, doc, number = row['page_id'], row['document_id'], row['page_number']
        if (not isinstance(pid, str) or pid != f'{doc}_page_{number:04d}' or number < 1
                or not re.fullmatch(r'[A-Za-z0-9_-]+', pid) or pid in seen):
            raise ValueError('Duplicate/noncanonical page namespace')
        if (not isinstance(row['text'], str)
                or hashlib.sha256(row['text'].encode('utf-8')).hexdigest() != row['text_sha256']
                or row['policy_sha256'] != handover['policy_sha256']):
            raise ValueError('Text/policy hash mismatch')
        image = row['artifacts']['image']
        if (not isinstance(row.get('image_sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', row['image_sha256'])
                or image['sha256'] != row['image_sha256'] or image['size_bytes'] <= 0
                or PurePosixPath(image['path']) != PurePosixPath('pages') / pid / 'image.png'):
            raise ValueError('Image hash/path mismatch')
        seen.add(pid)
        docs.add(doc)
    if len(seen) != handover['page_count'] or len(docs) != handover['document_count']:
        raise ValueError('Incomplete page/document namespace')
    return {'page_count': len(seen), 'document_count': len(docs),
            'preprocessing_identity_sha256': object_hash(sorted(
                (r['page_id'], r['text_sha256'], r['policy_sha256']) for r in pages)),
            'technical_failure_pages_preserved': sum(bool(r.get('technical_failure')) for r in pages),
            'empty_text_pages_preserved': sum(not r['text'] for r in pages)}


def load_config(path):
    config = read_json(path)
    if (config['schema_version'] != 1 or config['task_id'] != 'M2.8'
            or config['execution']['gpu'] != 'A10' or config['execution']['retries'] != 0
            or config['candidates'] != {'top_k_per_channel': 200, 'max_union': 600,
                                        'normalization_epsilon': 1e-15}):
        raise ValueError('M2.8 fixed execution/candidate contract changed')
    return config


def prepare_inputs(root, config, run):
    import tomllib
    root, run = Path(root), Path(run)
    model_source = root / config['model_source']['path']
    if digest(model_source) != config['model_source']['sha256']:
        raise ValueError('Calibrated M2.2 model configuration changed')
    original = tomllib.loads(model_source.read_text(encoding='utf-8'))
    if config['retrievers'] != {k: original[k] for k in ('bm25', 'dense', 'visual')}:
        raise ValueError('Retriever settings drift from M2.2')
    freeze = read_json(root / 'configs/m2.5/freeze.json')
    split_check = verify_frozen_splits(root, freeze)
    splits = split_check.pop('roles')
    qids = sorted(q for ids in splits.values() for q in ids)
    m21 = read_json(root / freeze['split_manifest'])
    annotation = m21['data_files']['vidoseek.json']
    queries = read_query_texts(root / annotation['path'], annotation['sha256'], qids)
    output = root / config['ocr']['local_output']
    if digest(output / 'handover.json') != config['ocr']['handover_sha256']:
        raise ValueError('M2.6 handover identity changed')
    handover = read_json(output / 'handover.json')
    if handover['status'] != 'COMPLETE' or (handover['page_count'], handover['document_count']) != (5385, 292):
        raise ValueError('M2.6 full-corpus run is not complete')
    if digest(output / handover['resolved_pages_path']) != handover['resolved_pages_sha256']:
        raise ValueError('M2.6 resolved text payload hash mismatch')
    if digest(output / handover['page_hashes_path']) != handover['page_hashes_sha256']:
        raise ValueError('M2.6 per-page hash table mismatch')
    pages = read_json(output / handover['resolved_pages_path'])
    pages.sort(key=lambda r: r['page_id'])
    checks = validate_pages(pages, handover)
    if checks['preprocessing_identity_sha256'] != handover['preprocessing_identity_sha256']:
        raise ValueError('M2.6 preprocessing identity mismatch')
    manifest = {'schema_version': 1, 'task_id': 'M2.8', 'query_ids': qids,
                'page_ids': [r['page_id'] for r in pages], 'query_count': len(qids),
                **checks, 'm26_handover': handover, 'split_verification': split_check,
                'annotation': annotation, 'm21_manifest_sha256': digest(root / freeze['split_manifest']),
                'm25_freeze_sha256': digest(root / 'configs/m2.5/freeze.json'),
                'm27_manifest_sha256': digest(root / 'configs/m2.7/matched.json'),
                'uses_qrels': False, 'training_executed': False,
                'query_texts_sha256': object_hash(queries)}
    write_json(run / 'input_manifest.json', manifest)
    write_json(run / 'queries.json', queries)
    write_json(run / 'split_ids.json', splits)
    return manifest
