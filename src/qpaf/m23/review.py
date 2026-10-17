"""Build a real-data review workspace and validate exported human decisions."""
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata

from qpaf.m11.artifacts import digest, object_hash, read_json, utc, verify_manifest, write_csv, write_json


def review_data(run, destination):
    run, destination = Path(run).resolve(), Path(destination).resolve()
    verify_manifest(run / 'remote', read_json(run / 'remote/hashes.json'))
    pages = read_json(run / 'remote/pages.json')
    rows = []
    identities = []
    for page in pages:
        dpi = 300 if page.get('image300') else 150
        if not page.get(f'image{dpi}'):
            raise ValueError(f"Page cannot be reviewed without an image: {page['page_id']}")
        image = (run / 'remote' / page[f'image{dpi}']).resolve()
        if not image.is_relative_to((run / 'remote').resolve()) or digest(image) != page[f'image{dpi}_sha256']:
            raise ValueError('Review image identity mismatch')
        ocr150, ocr300 = page['ocr'].get('150', {}), page['ocr'].get('300', {})
        row = {'page_id': page['page_id'], 'document_id': page['document_id'], 'page_number': page['page_number'],
               'native_text': page['native_text'], 'native_text_sha256': page['native_text_sha256'],
               'ocr150_text': ocr150.get('text'), 'ocr300_text': ocr300.get('text'),
               'ocr150_status': ocr150.get('status', 'NOT_RUN'), 'ocr300_status': ocr300.get('status', 'NOT_RUN'),
               'image_data': os.path.relpath(image, destination).replace('\\', '/'),
               'image_sha256': page[f'image{dpi}_sha256'], 'pdf_sha256': page['pdf_sha256'],
               'image_width': page[f'image{dpi}_size'][0], 'image_height': page[f'image{dpi}_size'][1],
               'image_dpi': dpi, 'reference_required': page['reference_required'],
               'calibration_split': page['calibration_split'], 'length_stratum': page['length_stratum'],
               'extraction_status': 'M23_REVIEW_PENDING'}
        identities.append({k: v for k, v in row.items() if k != 'image_data'})
        rows.append(row)
    identity = {'source_run': run.name, 'sample_manifest_sha256': digest(run / 'inputs/sample_manifest.json'), 'pages': identities}
    return {'schema_version': 1, 'demo': False, 'dataset_id': 'm23-calibration-review-v1',
            'dataset_sha256': object_hash(identity), 'source_run': run.name, 'image_dpi': 300,
            'pages': rows, 'human_review_status': 'PENDING'}


def build_review(run, destination, template):
    destination = Path(destination)
    data = review_data(run, destination)
    html = Path(template).read_text(encoding='utf-8')
    if html.count('__M23_DATA__') != 1:
        raise ValueError('Ambiguous review data marker')
    html = html.replace('__M23_DATA__', json.dumps(data, ensure_ascii=False).replace('<', '\\u003c'))
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'index.html').write_text(html, encoding='utf-8')
    write_json(destination / 'workspace.json', {k: v for k, v in data.items() if k != 'pages'} | {
        'page_count': len(data['pages']), 'reference_required_count': sum(p['reference_required'] for p in data['pages']),
        'html_sha256': hashlib.sha256(html.encode()).hexdigest(), 'template_sha256': digest(template)})
    return destination / 'index.html'


def normalize(text):
    # Match ECMAScript \s in the browser, including BOM but excluding NEL/C0 separators.
    return re.sub(r'[\t-\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+',
                  ' ', unicodedata.normalize('NFC', text)).strip(' ')


def distance(actual, reference):
    """Exact Levenshtein distance using a bit-vector recurrence (Unicode/tokens)."""
    if len(actual) < len(reference):
        actual, reference = reference, actual
    if not reference:
        return len(actual)
    positions = {}
    for index, token in enumerate(reference):
        positions[token] = positions.get(token, 0) | (1 << index)
    mask = (1 << len(reference)) - 1
    positive, negative, score, top = mask, 0, len(reference), 1 << (len(reference) - 1)
    for token in actual:
        matches = positions.get(token, 0)
        vertical = matches | negative
        horizontal = (((matches & positive) + positive) ^ positive) | matches | negative
        plus = negative | ~(horizontal | positive)
        minus = positive & horizontal
        score += bool(plus & top) - bool(minus & top)
        plus = (plus << 1) | 1
        minus <<= 1
        positive = (minus | ~(horizontal | plus)) & mask
        negative = (horizontal & plus) & mask
    return score


def metrics(prediction, reference):
    pred, gold = normalize(prediction), normalize(reference)
    if not gold:
        return {'cer': None, 'wer': None, 'reference_chars': 0, 'reference_words': 0,
                'char_edits': None, 'word_edits': None, 'false_positive_chars': len(pred)}
    words = gold.split(' ')
    chars, tokens = distance(pred, gold), distance(pred.split(' ') if pred else [], words)
    return {'cer': chars / len(gold), 'wer': tokens / len(words), 'reference_chars': len(gold),
            'reference_words': len(words), 'char_edits': chars, 'word_edits': tokens, 'false_positive_chars': None}


def validate_reviews(payload, data):
    if (payload.get('schema_version') != 1 or payload.get('artifact_type') != 'm23_human_review'
            or payload.get('demo') is not False or payload.get('dataset_sha256') != data['dataset_sha256']
            or payload.get('dataset_id') != data['dataset_id'] or payload.get('source_run') != data['source_run']):
        raise ValueError('Review file does not belong to this real calibration run')
    rows = payload.get('pages', [])
    expected = {p['page_id']: p for p in data['pages']}
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError('Incomplete review page namespace')
    seen = set()
    for row in rows:
        pid = row.get('page_id')
        if pid not in expected or pid in seen or row.get('image_sha256') != expected[pid]['image_sha256']:
            raise ValueError('Review ID/hash mismatch')
        seen.add(pid)
        native, ref = row.get('native', {}), row.get('reference', {})
        if native.get('status') not in ('PENDING', 'PASS', 'HAS_ERRORS', 'NO_TEXT', 'UNSURE'):
            raise ValueError('Invalid native review status')
        if not isinstance(native.get('issues'), list) or not isinstance(native.get('note'), str):
            raise ValueError('Invalid native issues/note')
        if native['status'] != 'PENDING':
            if not native.get('reviewer', '').strip() or not native.get('reviewed_at') or native.get('image_checked') is not True:
                raise ValueError('Native review is not signed/confirmed')
            if native['status'] == 'HAS_ERRORS' and not native['issues'] and not native['note'].strip():
                raise ValueError('Native error needs a reason')
        if ref.get('status') not in ('DRAFT', 'CONFIRMED') or not isinstance(ref.get('text'), str):
            raise ValueError('Invalid reference status/text')
        if ref.get('scope') not in ('full_page', 'excerpt') or type(ref.get('no_text')) is not bool:
            raise ValueError('Invalid reference scope/no-text flag')
        if ref['status'] == 'CONFIRMED':
            if not ref.get('reviewer', '').strip() or not ref.get('reviewed_at'):
                raise ValueError('Reference is not signed')
            if not ref['text'].strip() and not ref['no_text']:
                raise ValueError('Empty reference requires an explicit no-text confirmation')
            if ref['no_text'] and (ref['text'].strip() or ref['scope'] != 'full_page'):
                raise ValueError('Conflicting no-text reference')
            if ref['scope'] == 'excerpt' and not ref.get('region', '').strip():
                raise ValueError('Excerpt reference requires a region')
    return {row['page_id']: row for row in rows}


def summarize(run, review_path, output):
    run, output = Path(run).resolve(), Path(output).resolve()
    data = review_data(run, run / 'review')
    payload = read_json(review_path)
    reviews = validate_reviews(payload, data)
    if output.exists():
        raise FileExistsError('Use a new summary directory; prior reviews are immutable')
    output.mkdir(parents=True)
    write_json(output / 'human_reviews.json', payload)
    evaluated, native_counts, missing_native, missing_refs = [], Counter(), [], []
    for page in data['pages']:
        review = reviews[page['page_id']]
        native, ref = review['native'], review['reference']
        native_counts[native['status']] += 1
        if native['status'] in ('PENDING', 'UNSURE'):
            missing_native.append(page['page_id'])
        confirmed = ref['status'] == 'CONFIRMED' and ref['scope'] == 'full_page'
        if page['reference_required'] and not confirmed:
            missing_refs.append(page['page_id'])
        if not confirmed:
            continue
        for channel in ('native', 'ocr150', 'ocr300'):
            text = page['native_text'] if channel == 'native' else page[channel + '_text']
            values = metrics(text, ref['text']) if text is not None else {}
            evaluated.append({'page_id': page['page_id'], 'split': page['calibration_split'], 'channel': channel,
                              'output_available': text is not None, 'reference_required': page['reference_required'], **values})
    groups = defaultdict(list)
    for row in evaluated:
        groups[(row['split'], row['channel'])].append(row)
    aggregate = []
    for (split, channel), rows in sorted(groups.items()):
        valid = [r for r in rows if r.get('reference_chars', 0)]
        chars, words = sum(r['reference_chars'] for r in valid), sum(r['reference_words'] for r in valid)
        aggregate.append({'split': split, 'channel': channel, 'reviewed_pages': len(rows),
                          'unavailable_outputs': sum(not r['output_available'] for r in rows),
                          'micro_cer': sum(r['char_edits'] for r in valid) / chars if chars else None,
                          'micro_wer': sum(r['word_edits'] for r in valid) / words if words else None,
                          'macro_cer': sum(r['cer'] for r in valid) / len(valid) if valid else None,
                          'no_text_pages': sum(r.get('reference_chars') == 0 for r in rows),
                          'false_positive_chars': sum(r.get('false_positive_chars') or 0 for r in rows)})
    summary = {'task_id': 'M2.3', 'status': 'REVIEW_COMPLETE_THRESHOLDS_PENDING' if not missing_native and not missing_refs else 'HUMAN_REVIEW_INCOMPLETE',
               'source_run': run.name, 'review_sha256': digest(review_path), 'summarized_utc': utc(),
               'dataset_sha256': data['dataset_sha256'], 'native_decisions': dict(native_counts),
               'missing_native_reviews': missing_native, 'missing_required_full_page_references': missing_refs,
               'thresholds_frozen': False, 'aggregates': aggregate,
               'normalization': 'NFC + whitespace collapse; case/punctuation/digits preserved; WER whitespace tokens',
               'note': 'Development/holdout/regression reported separately. No pooled corpus error-rate claim or automatic threshold freeze.'}
    write_json(output / 'summary.json', summary)
    write_json(output / 'page_metrics.json', evaluated)
    if evaluated:
        fields = sorted({key for row in evaluated for key in row})
        write_csv(output / 'page_metrics.csv', [{key: row.get(key) for key in fields} for row in evaluated], fields)
    lines = ['# M2.3 — Tổng hợp review thủ công', '', f"Trạng thái: **{summary['status']}**.", '',
             f"Còn {len(missing_native)} trang native và {len(missing_refs)} bản chữ bắt buộc cần hoàn tất.",
             'Ngưỡng OCR chưa được đóng băng; cần review kết quả và quyết định riêng.', '',
             '| Split | Kênh | Số trang | Micro CER | Micro WER | Output thiếu |', '|---|---|---:|---:|---:|---:|']
    for row in aggregate:
        fmt = lambda value: 'N/A' if value is None else f'{100 * value:.3f}%'
        lines.append(f"| {row['split']} | {row['channel']} | {row['reviewed_pages']} | {fmt(row['micro_cer'])} | {fmt(row['micro_wer'])} | {row['unavailable_outputs']} |")
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    write_json(output / 'hashes.json', file_manifest_for(output))
    return summary


def file_manifest_for(folder):
    from qpaf.m11.artifacts import file_manifest
    return file_manifest(folder, exclude=('hashes.json',))
