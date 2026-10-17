"""Label-free deterministic document/page sampling from verified M2.1 inputs."""
from collections import Counter, defaultdict
from contextlib import closing
import csv
import hashlib
import importlib.metadata
import math
from pathlib import Path
import time
import zipfile

from qpaf.m11.artifacts import digest, file_manifest, object_hash, read_json, verify_manifest, write_json
from qpaf.m21.data_splits import build_data_split_freeze
from .config import validate


def rank(seed, value):
    return hashlib.sha256(f'{seed}:{value}'.encode()).hexdigest(), value


def length_stratum(count):
    return 'short' if count <= 10 else 'medium' if count <= 18 else 'long'


def select_documents(rows, config):
    groups = defaultdict(list)
    counts = Counter(row['document_id'] for row in rows)
    for document, count in counts.items():
        groups[length_stratum(count)].append(document)
    selected = []
    for index, name in enumerate(('short', 'medium', 'long')):
        ordered = sorted(groups[name], key=lambda value: rank(config['seed'], value))
        take, held = config['sample']['stratum_documents'][index], config['sample']['stratum_holdout_documents'][index]
        if len(ordered) < take:
            raise ValueError(f'Not enough documents in {name}')
        for position, document in enumerate(ordered[:take]):
            selected.append({'document_id': document, 'page_count': counts[document], 'length_stratum': name,
                             'calibration_split': 'holdout' if position < held else 'development',
                             'population_documents_in_stratum': len(ordered)})
    return sorted(selected, key=lambda row: row['document_id'])


def text_signals(text):
    meaningful = ''.join(c for c in text if not c.isspace())
    return {'char_count': len(text), 'nonspace_chars': len(meaningful),
            'printable_ratio': sum(c.isprintable() for c in text) / len(text) if text else 0.,
            'meaningful_printable_ratio': sum(c.isprintable() for c in meaningful) / len(meaningful) if meaningful else 0.,
            'replacement_chars': text.count('\ufffd'), 'cid_markers': text.count('(cid:'),
            'line_count': len(text.splitlines()),
            'text_stratum': 'empty' if not meaningful else 'short' if len(meaningful) < 40 else 'text_present'}


def projected_pixels(page, dpi):
    return math.ceil(page['pdf_width_points'] * dpi / 72) * math.ceil(page['pdf_height_points'] * dpi / 72)


def choose_pages(probes, count, seed):
    """Cover first/last, sparse/rich text; duplicate selections filled by hash."""
    if len(probes) < count:
        raise ValueError('Insufficient probe pages')
    preferred = [min(probes, key=lambda p: p['page_number']), max(probes, key=lambda p: p['page_number']),
                 min(probes, key=lambda p: (p['native_signals']['nonspace_chars'], p['page_id'])),
                 max(probes, key=lambda p: (p['native_signals']['nonspace_chars'], p['page_id']))]
    preferred += sorted(probes, key=lambda p: rank(seed, p['page_id']))
    selected = {}
    for row in preferred:
        selected.setdefault(row['page_id'], row)
        if len(selected) == count:
            break
    return sorted(selected.values(), key=lambda row: row['page_number'])


def prepare_sample(root, config, output):
    import pypdfium2 as pdfium
    validate(config)
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if importlib.metadata.version('pypdfium2') != config['text']['parser_version']:
        raise ValueError('Local PDF parser version mismatch')
    frozen_dir = root / config['sample']['m21_revision']
    with (frozen_dir / 'hash_manifest.csv').open(encoding='utf-8', newline='') as stream:
        verify_manifest(frozen_dir, list(csv.DictReader(stream)))
    frozen = read_json(frozen_dir / 'data_split_manifest.json')
    actual, verified = build_data_split_freeze(repo_root=root,
        source_manifest_path=root / frozen['dataset']['source_manifest'],
        raw_dir=(root / frozen['data_files']['vidoseek.json']['path']).parent,
        splits_dir=(root / frozen['split_bundle']['manifest_path']).parent)
    if actual != frozen:
        raise ValueError('Live data differs from the M2.1 freeze')
    gate = root / 'evidence/M1_FINAL/06_G1/G1_final_decision.md'
    if 'CONDITIONAL_PASS / PROCEED_TO_M2_DATA_PREP' not in gate.read_text(encoding='utf-8'):
        raise ValueError('Missing G1 data-preparation decision')
    manifest_path = root / config['sample']['page_manifest']
    manifest_record = {'path': manifest_path.name, **read_json(manifest_path.parent / 'hash_manifest.json')[manifest_path.name]}
    verify_manifest(manifest_path.parent, [manifest_record])
    with manifest_path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len({r['page_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate page IDs in source manifest')
    for row in rows:
        if row['page_id'] != f"{row['document_id']}_page_{int(row['page_number']):04d}":
            raise ValueError('Noncanonical page ID in source manifest')
    by_doc = defaultdict(list)
    for row in rows:
        by_doc[row['document_id']].append(row)
    documents = select_documents(rows, config)
    regression = next((r for r in rows if r['page_id'] == config['sample']['regression_page']), None)
    if regression is None:
        raise ValueError('Regression page is absent')
    output.mkdir(parents=True)
    (output / 'pdfs').mkdir()
    pages, probe_records = [], []
    archive_path = root / frozen['data_files']['vidoseek_pdf_document.zip']['path']
    with zipfile.ZipFile(archive_path) as archive:
        members = {}
        for member in archive.namelist():
            if member.lower().endswith('.pdf'):
                if Path(member).name in members:
                    raise ValueError('Ambiguous PDF filename')
                members[Path(member).name] = member

        def probe_document(info, only=None):
            docid = info['document_id']
            candidates = sorted(by_doc[docid], key=lambda r: int(r['page_number']))
            payload = archive.read(members[docid + '.pdf'])
            if digest_bytes(payload) != candidates[0]['file_sha256']:
                raise ValueError('PDF hash differs from page manifest')
            pdf_path = output / 'pdfs' / (docid + '.pdf')
            if not pdf_path.exists():
                pdf_path.write_bytes(payload)
            if only:
                candidates = [only]
            else:
                picks = [candidates[0], candidates[-1]] + sorted(candidates[1:-1], key=lambda r: rank(config['seed'], r['page_id']))
                candidates = picks[:config['sample']['probe_pages_per_document']]
            probes = []
            with closing(pdfium.PdfDocument(payload)) as document:
                for row in candidates:
                    started = time.perf_counter()
                    number = int(row['page_number'])
                    error = None
                    with closing(document[number - 1]) as page:
                        width, height = page.get_size()
                        try:
                            with closing(page.get_textpage()) as textpage:
                                text = textpage.get_text_bounded().strip()
                        except Exception as exc:
                            text, error = '', f'{type(exc).__name__}: {exc}'
                    item = {'page_id': row['page_id'], 'document_id': docid, 'page_number': number,
                            'pdf': pdf_path.relative_to(output).as_posix(), 'pdf_sha256': row['file_sha256'],
                            'native_text': text, 'native_text_sha256': digest_bytes(text.encode()),
                            'native_signals': text_signals(text), 'native_error': error,
                            'native_seconds': time.perf_counter() - started, 'pdf_width_points': width,
                            'pdf_height_points': height, 'length_stratum': info['length_stratum'],
                            'calibration_split': info['calibration_split'], 'reference_required': False,
                            'sample_group': 'regression' if only else 'calibration'}
                    probes.append(item)
                    probe_records.append({k: v for k, v in item.items() if k != 'native_text'})
            return probes

        for info in documents:
            pages.extend(choose_pages(probe_document(info), config['sample']['pages_per_document'], config['seed']))
        # Reference subset: one page from every document + second page from ten dev documents.
        for info in documents:
            chosen = sorted([p for p in pages if p['document_id'] == info['document_id']],
                            key=lambda p: rank(config['seed'] + 1, p['page_id']))
            chosen[0]['reference_required'] = True
        extra_docs = sorted([d for d in documents if d['calibration_split'] == 'development'],
                            key=lambda d: rank(config['seed'] + 2, d['document_id']))[:10]
        for info in extra_docs:
            remaining = [p for p in pages if p['document_id'] == info['document_id'] and not p['reference_required']]
            min(remaining, key=lambda p: rank(config['seed'] + 3, p['page_id']))['reference_required'] = True
        existing = next((p for p in pages if p['page_id'] == regression['page_id']), None)
        if existing:
            existing['regression_case'] = True
            existing['reference_required'] = True
        else:
            info = {'document_id': regression['document_id'], 'length_stratum': length_stratum(len(by_doc[regression['document_id']])),
                    'calibration_split': 'regression'}
            item = probe_document(info, regression)[0]
            item.update(reference_required=True, regression_case=True)
            pages.append(item)
    pages.sort(key=lambda p: p['page_id'])
    for page in pages:
        page['projected_pixels'] = {str(dpi): projected_pixels(page, dpi) for dpi in config['text']['dpis']}
        if max(page['projected_pixels'].values()) > config['caps']['max_pixels']:
            raise ValueError(f"Page exceeds render cap before cloud execution: {page['page_id']}")
    if len(pages) > config['caps']['max_pages'] or len({p['document_id'] for p in pages}) > config['caps']['max_documents']:
        raise ValueError('Selected sample exceeds bounds')
    # Up to 240 bounded primary probes plus one explicit regression probe.
    if sum(p['sample_group'] == 'calibration' for p in probe_records) > config['caps']['max_probe_pages']:
        raise ValueError('Probe cap exceeded')
    write_json(output / 'pages.json', pages)
    write_json(output / 'probe_manifest.json', probe_records)
    write_json(output / 'sample_manifest.json', {
        'task_id': 'M2.3', 'seed': config['seed'], 'dataset': frozen['dataset'], 'documents': documents,
        'page_ids': [p['page_id'] for p in pages], 'page_count': len(pages),
        'reference_required_count': sum(p['reference_required'] for p in pages),
        'sampling': 'document-length quotas; bounded page probes; first/last/sparse/rich with hash fill',
        'uses_query_text': False, 'uses_qrels': False, 'test_queries_used': 0,
        'shared_document_corpus': True, 'population_rate_estimate': False,
        'config_sha256': object_hash(config), 'm21_manifest_sha256': digest(frozen_dir / 'data_split_manifest.json'),
        'page_manifest_sha256': digest(manifest_path), 'm21_verification': verified,
        'native_environment': {'parser': importlib.metadata.version('pypdfium2'), 'pdfium': str(pdfium.PDFIUM_INFO)}})
    write_json(output / 'hashes.json', file_manifest(output))
    return pages


def digest_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def validate_inputs(folder, config):
    validate(config)
    folder = Path(folder)
    verify_manifest(folder, read_json(folder / 'hashes.json'))
    pages, meta = read_json(folder / 'pages.json'), read_json(folder / 'sample_manifest.json')
    ids = [p['page_id'] for p in pages]
    if not ids or len(ids) != len(set(ids)) or ids != meta['page_ids'] or len(ids) > config['caps']['max_pages']:
        raise ValueError('Sample ID/count/order mismatch')
    if meta['config_sha256'] != object_hash(config) or meta['uses_qrels'] or meta['test_queries_used']:
        raise ValueError('Sample provenance mismatch')
    for page in pages:
        pdf = (folder / page['pdf']).resolve()
        if not pdf.is_relative_to(folder.resolve()) or digest(pdf) != page['pdf_sha256']:
            raise ValueError('PDF input identity mismatch')
        if digest_bytes(page['native_text'].encode()) != page['native_text_sha256']:
            raise ValueError('Native text identity mismatch')
    return pages, meta
