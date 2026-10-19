"""Main-thread PDFium preparation and isolated, bounded OCR subprocess jobs."""
from contextlib import closing
import math
from pathlib import Path
import time

from qpaf.m11.artifacts import digest, read_json, write_json
from qpaf.m23.policy import extract_native_geometry, resolve_page, tsv_words
from qpaf.m23.worker import run_ocr
from .bundle import text_hash


def base_page(scheduled, output, policy_sha256):
    directory = Path(output) / 'pages' / scheduled['page_id']
    directory.mkdir(parents=True, exist_ok=False)
    return initial_record(scheduled, policy_sha256)


def initial_record(scheduled, policy_sha256):
    return {**scheduled, 'policy_sha256': policy_sha256, 'native_text': '', 'text': '',
            'native_text_sha256': text_hash(''), 'text_sha256': text_hash(''),
            'raw_ocr_text_sha256': None, 'image_sha256': None, 'image_size': None,
            'render_status': 'NOT_RUN', 'technical_failure': True, 'extraction_status': 'NOT_RUN',
            'text_source': 'none', 'reason': 'not_scheduled', 'warnings': [], 'stage_errors': [],
            'ocr': {'status': 'NOT_RUN', 'text': None, 'error': 'Render not available'},
            'artifacts': {}, 'render_seconds': 0., 'native_seconds': 0.}


def prepare_page(scheduled, pdf_path, output, policy, config):
    """Only this calling thread may touch PDFium; OCR workers receive disk paths."""
    import pypdfium2 as pdfium
    row = base_page(scheduled, output, config['policy']['sha256'])
    directory = Path(output) / 'pages' / row['page_id']
    started = time.perf_counter()
    try:
        with closing(pdfium.PdfDocument(str(pdf_path))) as document:
            with closing(document[row['page_number'] - 1]) as page:
                native_start = time.perf_counter()
                try:
                    with closing(page.get_textpage()) as textpage:
                        row['native_text'] = textpage.get_text_bounded().strip()
                except Exception as exc:
                    row['stage_errors'].append({'stage': 'native', 'error': f'{type(exc).__name__}: {exc}'})
                row['native_seconds'] = time.perf_counter() - native_start
                width, height = page.get_size()
                dpi = policy['engine']['dpi']
                if math.ceil(width * dpi / 72) * math.ceil(height * dpi / 72) > policy['resources']['max_pixels']:
                    raise ValueError('Rendered image exceeds frozen pixel cap')
                with closing(page.render(scale=dpi / 72)) as bitmap:
                    image = bitmap.to_pil().convert('RGB')
                try:
                    row['image_size'] = list(image.size)
                    image.save(directory / 'image.png', compress_level=config['execution']['png_compress_level'])
                finally:
                    image.close()
                row['image_sha256'] = digest(directory / 'image.png')
                row['render_status'] = 'OK'
    except Exception as exc:
        row['render_status'] = 'ERROR'
        row['stage_errors'].append({'stage': 'render', 'error': f'{type(exc).__name__}: {exc}'})
    row['render_seconds'] = time.perf_counter() - started
    row['native_text_sha256'] = text_hash(row['native_text'])
    (directory / 'native.txt').write_bytes(row['native_text'].encode('utf-8'))
    if row['render_status'] == 'OK':
        try:
            geometry = extract_native_geometry(pdf_path, row['page_number'], row['native_text_sha256'])
            write_json(directory / 'geometry.json', geometry)
        except Exception as exc:
            row['stage_errors'].append({'stage': 'geometry', 'error': f'{type(exc).__name__}: {exc}'})
    return row


def finish_page(row, output, policy, remaining_seconds):
    """Run OCR and replay the frozen policy without calling PDFium from a thread."""
    directory = Path(output) / 'pages' / row['page_id']
    started = time.perf_counter()
    try:
        if row['render_status'] == 'OK' and remaining_seconds > 0:
            engine = policy['engine']
            config = {'text': {'language': engine['language'], 'oem': engine['oem'], 'psm': engine['psm'],
                               'page_timeout_seconds': engine['page_ocr_timeout_seconds']}}
            try:
                row['ocr'] = run_ocr(directory / 'image.png', directory / 'ocr', engine['dpi'], config,
                                     remaining_seconds)
                if row['ocr']['status'] not in ('OK', 'NO_TEXT_DETECTED'):
                    row['stage_errors'].append({'stage': 'ocr', 'error': row['ocr']['error'] or row['ocr']['status']})
                else:
                    row['raw_ocr_text_sha256'] = row['ocr']['text_sha256']
            except Exception as exc:
                row['ocr'] = {'status': 'PARSE_ERROR', 'text': None, 'error': f'{type(exc).__name__}: {exc}'}
                row['stage_errors'].append({'stage': 'ocr_parse', 'error': row['ocr']['error']})
        elif row['render_status'] == 'OK':
            row['stage_errors'].append({'stage': 'scheduler', 'error': 'Remaining wall-time budget exhausted'})
        if row['stage_errors']:
            error = '; '.join(e['stage'] + ': ' + e['error'] for e in row['stage_errors'])
            result = resolve_page(row['native_text'], {'status': 'ERROR', 'error': error}, [], {},
                                  row['image_size'] or [1, 1], policy['routing'])
            first = row['stage_errors'][0]['stage']
            result['extraction_status'] = {'render': 'RENDER_ERROR', 'native': 'NATIVE_PARSE_ERROR',
                                           'geometry': 'GEOMETRY_ERROR', 'ocr_parse': 'OCR_PARSE_ERROR',
                                           'scheduler': 'NOT_RUN'}.get(first, 'OCR_' + row['ocr']['status'])
        else:
            words = tsv_words(directory / 'ocr.tsv')
            result = resolve_page(row['native_text'], row['ocr'], words, read_json(directory / 'geometry.json'),
                                  row['image_size'], policy['routing'])
        row.update(result)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        row['stage_errors'].append({'stage': 'resolve', 'error': error})
        row.update(resolve_page(row['native_text'], {'status': 'ERROR', 'error': error}, [], {},
                                row['image_size'] or [1, 1], policy['routing']))
        row['extraction_status'] = 'OCR_PARSE_ERROR'
    row['text_sha256'] = text_hash(row['text'])
    (directory / 'text.txt').write_bytes(row['text'].encode('utf-8'))
    if not (directory / 'native.txt').exists():
        (directory / 'native.txt').write_bytes(row['native_text'].encode('utf-8'))
    names = {'native_text': 'native.txt', 'text': 'text.txt', 'image': 'image.png',
             'geometry': 'geometry.json', 'raw_ocr_txt': 'ocr.txt', 'raw_ocr_tsv': 'ocr.tsv',
             'raw_ocr_stderr': 'ocr.stderr.txt', 'partial_native_text': 'native.partial.bin'}
    if row['render_status'] != 'OK':
        names['partial_image'] = names.pop('image')
    row['artifacts'] = {key: {'path': (directory / name).relative_to(output).as_posix(),
                              'sha256': digest(directory / name), 'size_bytes': (directory / name).stat().st_size}
                        for key, name in names.items() if (directory / name).is_file()}
    row['ocr_and_resolve_seconds'] = time.perf_counter() - started
    write_json(directory / 'record.json', row)
    return row


def recover_page(scheduled, output, policy, policy_sha256):
    """Retain an interrupted attempt without running its OCR subprocess again."""
    directory = Path(output) / 'pages' / scheduled['page_id']
    if (directory / 'record.json').is_file():
        return read_json(directory / 'record.json')
    if directory.exists():
        row = initial_record(scheduled, policy_sha256)
        if (directory / 'native.txt').is_file():
            try:
                row['native_text'] = (directory / 'native.txt').read_bytes().decode('utf-8')
            except UnicodeDecodeError as exc:
                (directory / 'native.txt').rename(directory / 'native.partial.bin')
                row['stage_errors'].append({'stage': 'native', 'error': f'Interrupted UTF-8 output: {exc}'})
            row['native_text_sha256'] = text_hash(row['native_text'])
        if (directory / 'image.png').is_file():
            from PIL import Image
            try:
                with Image.open(directory / 'image.png') as image:
                    row['image_size'] = list(image.size)
                    image.verify()
                row['image_sha256'] = digest(directory / 'image.png')
                row['render_status'] = 'OK'
            except Exception as exc:
                row['render_status'] = 'ERROR'
                row['stage_errors'].append({'stage': 'render', 'error': f'Interrupted image: {exc}'})
    else:
        row = base_page(scheduled, output, policy_sha256)
    row['stage_errors'].append({'stage': 'scheduler', 'error': 'Worker stopped before terminal page completion'})
    return finish_page(row, output, policy, 0.)
