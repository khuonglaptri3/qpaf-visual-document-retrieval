"""Verify the frozen M2.1 source and prepare label-free calibration inputs."""
from contextlib import closing
import csv
import hashlib
import importlib.metadata
import io
from pathlib import Path
import zipfile

from qpaf.m11.artifacts import digest, file_manifest, object_hash, read_json, verify_manifest, write_json
from qpaf.m11.dataset import select_queries
from qpaf.m13.vidoseek import format_page_id, parse_vidoseek_annotations
from qpaf.m21.data_splits import build_data_split_freeze
from .config import validate


def select_sample(queries, split_ids, pages, config):
    """No qrels argument; selection depends only on IDs and seed."""
    validate(config)
    for ids in (split_ids, [q['query_id'] for q in queries], [p['page_id'] for p in pages]):
        if not ids or len(ids) != len(set(ids)) or any(not isinstance(x, str) or not x for x in ids):
            raise ValueError('IDs must be nonempty and unique')
    by_query = {q['query_id']: q for q in queries}
    if not set(split_ids) <= by_query.keys():
        raise ValueError('Unknown split IDs')
    policy = config['sample']
    if policy['page_count'] > len(pages):
        raise ValueError('Insufficient pages')
    chosen = select_queries([by_query[q] for q in split_ids], policy['query_count'], config['seed'])
    ranked = sorted(pages, key=lambda p: (
        hashlib.sha256(f"{config['seed']}:{p['page_id']}".encode()).digest(), p['page_id']))
    return chosen, sorted(ranked[:policy['page_count']], key=lambda p: p['page_id'])


def prepare_sample(repo_root, config, output):
    import pypdfium2 as pdfium
    root, output = Path(repo_root), Path(output)
    validate(config)
    if output.exists():
        raise FileExistsError(output)
    if importlib.metadata.version('pypdfium2') != config['text']['parser_version']:
        raise ValueError('PDF parser version mismatch')
    frozen_dir = root/config['sample']['m21_revision']
    with (frozen_dir/'hash_manifest.csv').open(encoding='utf-8', newline='') as stream:
        verify_manifest(frozen_dir, list(csv.DictReader(stream)))
    frozen = read_json(frozen_dir/'data_split_manifest.json')
    actual, verification = build_data_split_freeze(
        repo_root=root, source_manifest_path=root/frozen['dataset']['source_manifest'],
        raw_dir=(root/frozen['data_files']['vidoseek.json']['path']).parent,
        splits_dir=(root/frozen['split_bundle']['manifest_path']).parent)
    if actual != frozen:
        raise ValueError('Live M2.1 inputs differ from selected revision')
    gate = root/config['sample']['gate']
    if 'CONDITIONAL_PASS / PROCEED_TO_M2_DATA_PREP' not in gate.read_text(encoding='utf-8'):
        raise PermissionError('G1 M2 data-preparation decision missing')
    parsed = parse_vidoseek_annotations(root/frozen['data_files']['vidoseek.json']['path'])
    split_ids = (root/frozen['roles'][config['sample']['split']]['id_manifest']).read_text(encoding='utf-8').splitlines()
    page_manifest = root/config['sample']['page_manifest']
    with page_manifest.open(encoding='utf-8', newline='') as stream:
        pages = list(csv.DictReader(stream))
    queries, pages = select_sample(parsed.queries, split_ids, pages, config)
    output.mkdir(parents=True)
    (output/'images').mkdir()
    rendered = []
    archive_path = root/frozen['data_files']['vidoseek_pdf_document.zip']['path']
    with zipfile.ZipFile(archive_path) as archive:
        members = {}
        for name in archive.namelist():
            if name.lower().endswith('.pdf'):
                if Path(name).name in members:
                    raise ValueError('Duplicate PDF filenames')
                members[Path(name).name] = name
        for row in pages:
            filename, page_number = row['document_id']+'.pdf', int(row['page_number'])
            payload = archive.read(members[filename])
            if hashlib.sha256(payload).hexdigest() != row['file_sha256']:
                raise ValueError('Page-manifest PDF hash differs from pinned archive')
            if row['page_id'] != format_page_id(filename, page_number):
                raise ValueError('Canonical page ID mismatch')
            with closing(pdfium.PdfDocument(payload)) as document, closing(document[page_number-1]) as page:
                try:
                    with closing(page.get_textpage()) as textpage:
                        text = textpage.get_text_bounded().strip()
                    native_error = None
                except Exception as exc:
                    text, native_error = '', f'{type(exc).__name__}: {exc}'
                with closing(page.render(scale=config['text']['dpi']/72)) as bitmap:
                    image = bitmap.to_pil().convert('RGB')
                image_path = output/'images'/(row['page_id']+'.png')
                try:
                    width, height = image.size
                    image.save(image_path)
                finally:
                    image.close()
            rendered.append({'page_id': row['page_id'], 'text': text, 'native_error': native_error,
                             'image': image_path.relative_to(output).as_posix(),
                             'image_sha256': digest(image_path), 'pdf_sha256': row['file_sha256'],
                             'native_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                             'width': width, 'height': height})
    write_json(output/'queries.json', queries)
    write_json(output/'pages.json', rendered)
    identity = {'task_id': 'M2.2', 'experiment_class': 'calibration',
                'sample_policy': config['sample'], 'seed': config['seed'], 'selection_uses_qrels': False,
                'query_ids': [q['query_id'] for q in queries], 'page_ids': [p['page_id'] for p in rendered],
                'test_query_overlap': 0, 'm21_manifest_sha256': digest(frozen_dir/'data_split_manifest.json'),
                'm21_verification': verification, 'gate_sha256': digest(gate),
                'page_manifest_sha256': digest(page_manifest), 'dataset': frozen['dataset'],
                'source_archive_sha256': frozen['data_files']['vidoseek_pdf_document.zip']['sha256'],
                'config_sha256': object_hash(config)}
    write_json(output/'sample_manifest.json', identity)
    write_json(output/'hashes.json', file_manifest(output))
    return identity


def validate_inputs(folder, config):
    validate(config)
    folder = Path(folder)
    verify_manifest(folder, read_json(folder/'hashes.json'))
    queries, pages = read_json(folder/'queries.json'), read_json(folder/'pages.json')
    meta = read_json(folder/'sample_manifest.json')
    for rows, key, expected in [(queries, 'query_id', meta['query_ids']), (pages, 'page_id', meta['page_ids'])]:
        ids = [r[key] for r in rows]
        if not ids or ids != expected or len(set(ids)) != len(ids):
            raise ValueError('Sample ID mismatch')
    if len(queries) != config['sample']['query_count'] or len(pages) != config['sample']['page_count']:
        raise ValueError('Sample size mismatch')
    if meta['config_sha256'] != object_hash(config) or meta['test_query_overlap'] != 0:
        raise ValueError('Sample provenance mismatch')
    for row in pages:
        if digest(folder/row['image']) != row['image_sha256']:
            raise ValueError('Sample image checksum mismatch')
        if hashlib.sha256(row['text'].encode()).hexdigest() != row['native_text_sha256']:
            raise ValueError('Sample text checksum mismatch')
    return queries, pages, meta


def pack_folder(folder, max_mb):
    folder = Path(folder)
    if sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) > max_mb*1024**2:
        raise ValueError('Uncompressed artifact size exceeds cap')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(folder).as_posix())
    return buffer.getvalue()
