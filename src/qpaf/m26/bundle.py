"""Independent local hash and policy-replay verification for full OCR bundles."""
from collections import Counter, defaultdict
import csv
import hashlib
import math
from pathlib import Path

from qpaf.m11.artifacts import digest, object_hash, read_json, verify_manifest
from qpaf.m23.policy import enforce_failure_cap, load_frozen_policy, resolve_page, tsv_words
from qpaf.m23.worker import parse_tsv
from .config import relative, validate

PAGE_HASH_FIELDS = ['page_id', 'document_id', 'page_number', 'pdf_sha256', 'source_content_sha256', 'image_sha256',
                    'native_text_sha256', 'raw_ocr_text_sha256', 'text_sha256', 'policy_sha256',
                    'text_source', 'extraction_status', 'technical_failure']


def validate_schedule(inputs, corpus):
    pages, documents = inputs['scheduled_pages'], inputs['documents']
    ids = [p['page_id'] for p in pages]
    if (len(pages) != inputs['page_count'] or len(pages) != corpus['page_count']
            or len(documents) != inputs['document_count'] or len(documents) != corpus['document_count']
            or len(set(ids)) != len(ids) or ids != sorted(ids)
            or object_hash(ids) != inputs['page_ids_sha256']):
        raise ValueError('Actual schedule counts/IDs/hash differ from declared corpus')
    by_doc = defaultdict(list)
    for page in pages:
        if (type(page['page_number']) is not int or page['page_number'] < 1
                or page['page_id'] != f"{page['document_id']}_page_{page['page_number']:04d}"):
            raise ValueError('Noncanonical scheduled page identity')
        by_doc[page['document_id']].append(page)
    doc_ids = [d['document_id'] for d in documents]
    if len(set(doc_ids)) != len(doc_ids) or set(doc_ids) != set(by_doc):
        raise ValueError('Document schedule differs from page records')
    for doc in documents:
        rows = by_doc[doc['document_id']]
        if (len(rows) != doc['page_count'] or sorted(r['page_number'] for r in rows) != list(range(1, len(rows) + 1))
                or any(r['pdf_sha256'] != doc['sha256'] for r in rows)):
            raise ValueError('Document page sequence or PDF identity mismatch')


def validate_metadata(folder, rows, policy, config):
    folder = Path(folder)
    with (folder / 'page_hashes.csv').open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        csv_rows = list(reader)
        if reader.fieldnames != PAGE_HASH_FIELDS:
            raise ValueError('Page hash CSV schema mismatch')
    expected = [{key: '' if row.get(key) is None else str(row[key]) for key in PAGE_HASH_FIELDS} for row in rows]
    if csv_rows != expected:
        raise ValueError('Page hash CSV rows differ from resolved pages')
    environment = read_json(folder / 'environment.json')
    if (environment.get('packages') != {'pypdfium2': '4.30.0', 'Pillow': '11.3.0', 'psutil': '7.0.0'}
            or environment.get('tesseract_version', '').splitlines()[:1] != ['tesseract ' + policy['engine']['version']]
            or environment.get('traineddata_sha256') != policy['engine']['traineddata_sha256']
            or environment.get('gpu_requested') is not False or environment.get('cpu_requested') != 4
            or environment.get('omp_thread_limit') != '1'):
        raise ValueError('Runtime evidence differs from the pinned OCR environment')
    resources = read_json(folder / 'resources.json')
    for key in ('wall_seconds', 'peak_python_and_children_rss_mib'):
        value = resources.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid measured resource: ' + key)
    if (resources.get('workers'), resources.get('cpu'), resources.get('ocr_timeout_seconds')) != (2, 4, 15) or resources.get('gpu_requested') is not False:
        raise ValueError('Measured execution settings differ from frozen policy')
    limits = {'wall': resources['wall_seconds'] <= config['execution']['wall_seconds'],
              'ram': 0 < resources['peak_python_and_children_rss_mib'] <= policy['resources']['ram_mib'],
              'failure_cap': sum(r['technical_failure'] for r in rows) / len(rows) <= policy['failure']['max_failure_fraction']}
    if not all(limits.values()):
        raise ValueError('Measured resources exceed the full-run limits')
    return limits


def checked_path(root, value):
    root = Path(root).resolve()
    path = root.joinpath(*relative(value).parts).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Unsafe artifact path')
    return path


def text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def validate_records(rows, scheduled, folder, policy, policy_sha256, *, maximum_fraction=.01):
    expected = {r['page_id']: r for r in scheduled}
    ids = [r['page_id'] for r in rows]
    if not rows or len(expected) != len(scheduled) or len(set(ids)) != len(ids) or set(ids) != set(expected):
        raise ValueError('Missing, duplicate or orphan scheduled page records')
    replayed, failure_replayed, seen_paths = 0, 0, set()
    for row in rows:
        identity = expected[row['page_id']]
        if any(row.get(key) != identity[key] for key in ('document_id', 'page_number', 'pdf_sha256', 'source_content_sha256')):
            raise ValueError('Wrong document/page/source identity: ' + row['page_id'])
        if row['policy_sha256'] != policy_sha256:
            raise ValueError('Page policy hash mismatch')
        if type(row['technical_failure']) is not bool or not row.get('reason'):
            raise ValueError('Page requires explicit failure state and reason')
        artifacts = row['artifacts']
        required = {'native_text', 'text'}
        if not row['technical_failure']:
            required |= {'image', 'geometry', 'raw_ocr_txt', 'raw_ocr_tsv', 'raw_ocr_stderr'}
            if row['render_status'] != 'OK' or row['ocr']['status'] not in ('OK', 'NO_TEXT_DETECTED'):
                raise ValueError('Successful page has failed extraction stages')
        if not required.issubset(artifacts):
            raise ValueError('Required raw page artifact missing')
        for item in artifacts.values():
            path = checked_path(folder, item['path'])
            if (not item['path'].startswith('pages/' + row['page_id'] + '/') or item['path'] in seen_paths):
                raise ValueError('Page artifact has wrong namespace or duplicate path')
            seen_paths.add(item['path'])
            if not path.is_file() or path.stat().st_size != item['size_bytes'] or digest(path) != item['sha256']:
                raise ValueError('Artifact checksum mismatch: ' + item['path'])
        for field in ('native_text', 'text'):
            value = checked_path(folder, artifacts[field]['path']).read_bytes().decode('utf-8')
            if value != row[field] or text_hash(value) != row[field + '_sha256']:
                raise ValueError('Page text/hash mismatch: ' + field)
        if 'image' in artifacts:
            from PIL import Image
            image = checked_path(folder, artifacts['image']['path'])
            if row.get('image_sha256') != artifacts['image']['sha256']:
                raise ValueError('Image hash mismatch')
            with Image.open(image) as im:
                if list(im.size) != row.get('image_size'):
                    raise ValueError('Image dimensions mismatch')
                im.verify()
        if not row['technical_failure']:
            raw = checked_path(folder, artifacts['raw_ocr_txt']['path']).read_text(encoding='utf-8').strip()
            if raw != row['ocr']['text'] or text_hash(raw) != row['raw_ocr_text_sha256']:
                raise ValueError('Raw OCR text hash mismatch')
            tsv = checked_path(folder, artifacts['raw_ocr_tsv']['path'])
            signals = parse_tsv(tsv)
            if signals['mean_word_confidence'] != row['ocr']['mean_word_confidence']:
                raise ValueError('OCR confidence metadata differs from raw TSV')
            if (signals['word_count'] == 0) != (row['ocr']['status'] == 'NO_TEXT_DETECTED'):
                raise ValueError('No-text state differs from raw TSV')
            geometry = read_json(checked_path(folder, artifacts['geometry']['path']))
            if geometry.get('native_text_sha256') != row['native_text_sha256']:
                raise ValueError('Native geometry/text identity mismatch')
            resolved = resolve_page(row['native_text'], row['ocr'], tsv_words(tsv), geometry,
                                    row['image_size'], policy['routing'])
            for key in ('text', 'text_source', 'extraction_status', 'technical_failure', 'reason', 'warnings'):
                if row[key] != resolved[key]:
                    raise ValueError('Frozen policy replay differs: ' + key + ' / ' + row['page_id'])
            replayed += 1
        else:
            if row['extraction_status'] not in {'RENDER_ERROR', 'NATIVE_PARSE_ERROR', 'GEOMETRY_ERROR',
                                                 'OCR_ERROR', 'OCR_TIMEOUT', 'OCR_PARSE_ERROR', 'NOT_RUN'}:
                raise ValueError('Failed page has an unsupported terminal failure status')
            fallback = resolve_page(row['native_text'], {'status': 'ERROR', 'error': row['reason']}, [], {},
                                    row.get('image_size') or [1, 1], policy['routing'])
            if any(row[key] != fallback[key] for key in ('text', 'text_source', 'warnings')):
                raise ValueError('Failed-page policy fallback differs from retained text')
            failure_replayed += 1
    result = enforce_failure_cap(rows, maximum_fraction)
    result.update(policy_replayed_pages=replayed, failure_fallback_replayed_pages=failure_replayed,
                  artifacts_verified=len(seen_paths),
                  extraction_statuses=dict(sorted(Counter(r['extraction_status'] for r in rows).items())),
                  text_sources=dict(sorted(Counter(r['text_source'] for r in rows).items())),
                  warnings=dict(sorted(Counter(w for r in rows for w in r['warnings']).items())))
    return result


def verify_bundle(folder):
    folder = Path(folder)
    output = folder / 'output'
    config = validate(read_json(folder / 'resolved_config.json'))
    inputs = read_json(folder / 'input_manifest.json')
    validate_schedule(inputs, config['corpus'])
    repo_root = Path(__file__).resolve().parents[3]
    canonical_file = repo_root / config['corpus']['page_manifest']
    if digest(canonical_file) != inputs['page_manifest_sha256']:
        raise ValueError('Canonical page manifest differs from prepared inputs')
    with canonical_file.open(encoding='utf-8', newline='') as stream:
        canonical = [{'page_id': r['page_id'], 'document_id': r['document_id'], 'page_number': int(r['page_number']),
                      'pdf_sha256': r['file_sha256'], 'source_content_sha256': r['content_sha256']} for r in csv.DictReader(stream)]
    if sorted(canonical, key=lambda r: r['page_id']) != inputs['scheduled_pages']:
        raise ValueError('Prepared schedule differs from the frozen canonical page manifest')
    if inputs != read_json(output / 'input_manifest.json') or read_json(folder / 'source.json') != read_json(output / 'source.json'):
        raise ValueError('Remote input/source identity differs from the prepared run')
    if read_json(output / 'resolved_config.json') != config:
        raise ValueError('Remote config differs from the prepared run')
    if inputs['page_count'] != config['corpus']['page_count'] or inputs['document_count'] != config['corpus']['document_count']:
        raise ValueError('Prepared input count differs from the full corpus')
    policy_sha = config['policy']['sha256']
    if inputs['policy_sha256'] != policy_sha:
        raise ValueError('Prepared policy hash mismatch')
    policy = load_frozen_policy(output / 'ocr_policy_frozen.toml', policy_sha)
    records = read_json(output / 'hashes.json')
    verify_manifest(output, records)
    listed = {r['path'] for r in records}
    required = {'resolved_pages.json', 'summary.json', 'failures.json', 'page_hashes.csv', 'source.json',
                'input_manifest.json', 'resolved_config.json', 'environment.json', 'resources.json',
                'handover.json', 'ocr_policy_frozen.toml'}
    if len(listed) != len(records) or not required.issubset(listed):
        raise ValueError('Output manifest omits mandatory bundle metadata')
    rows = read_json(output / 'resolved_pages.json')
    for row in rows:
        if not {item['path'] for item in row['artifacts'].values()}.issubset(listed):
            raise ValueError('Output manifest omits raw page artifacts')
    checks = validate_records(rows, inputs['scheduled_pages'], output, policy, policy_sha,
                              maximum_fraction=policy['failure']['max_failure_fraction'])
    measured_limits = validate_metadata(output, rows, policy, config)
    summary, handover = read_json(output / 'summary.json'), read_json(output / 'handover.json')
    if (summary['status'] != 'COMPLETE' or summary['resource_checks'] != measured_limits
            or summary.get('task_id') != 'M2.6' or summary.get('run_id') != folder.name):
        raise ValueError('Worker did not complete within resource/failure limits')
    if any(summary[key] != value for key, value in checks.items()):
        raise ValueError('Summary differs from verified page records')
    if read_json(output / 'failures.json') != [r for r in rows if r['technical_failure']]:
        raise ValueError('Explicit failure listing differs from page records')
    for key, file in [('resolved_pages_sha256', 'resolved_pages.json'), ('page_hashes_sha256', 'page_hashes.csv')]:
        if handover[key] != digest(output / file):
            raise ValueError('Handover hash differs: ' + key)
    if handover['policy_sha256'] != policy_sha or handover['page_ids_sha256'] != inputs['page_ids_sha256']:
        raise ValueError('Handover preprocessing namespace differs')
    preprocessing_sha = object_hash([(r['page_id'], r['text_sha256'], policy_sha) for r in rows])
    if (handover['preprocessing_identity_sha256'] != preprocessing_sha
            or handover['input_manifest_sha256'] != digest(output / 'input_manifest.json')
            or handover['page_count'] != len(rows) or handover['document_count'] != len(inputs['documents'])
            or handover['status'] != 'COMPLETE' or handover['run_id'] != folder.name):
        raise ValueError('Handover counts or preprocessing identity differ from verified evidence')
    return {'status': 'VERIFIED_FULL_OCR_BUNDLE', 'run_id': folder.name, **checks,
            'policy_sha256': policy_sha, 'hash_manifest_sha256': digest(output / 'hashes.json'),
            'preprocessing_identity_sha256': preprocessing_sha,
            'manifest_files_verified': len(records), 'manifest_bytes_verified': sum(r['size_bytes'] for r in records),
            'training_executed': False, 'retrieval_results_claimed': False}
