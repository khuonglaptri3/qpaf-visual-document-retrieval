"""Deterministic native-preserving OCR policy and order-insensitive diagnostics.

Routing has no access to references, qrels, review labels, or page identities.
OCR evidence is retained separately; confidence is an engine signal, not accuracy.
"""
from collections import Counter
from contextlib import closing
import csv
import hashlib
import math
import re
import unicodedata
import tomllib

from .review import normalize


def load_frozen_policy(path, expected_sha256):
    """Load the exact policy bytes named by the downstream handoff manifest."""
    with open(path, 'rb') as stream:
        raw = stream.read()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Frozen policy hash mismatch')
    config = tomllib.loads(raw.decode('utf-8'))
    if config.get('schema_version') != 1 or config.get('quality_status') != 'FROZEN':
        raise ValueError('Policy is not a supported frozen configuration')
    if config['routing']['mode'] != 'native_plus_uncovered_ocr' or config['engine']['dpi'] not in (150, 300):
        raise ValueError('Unsupported frozen extraction method')
    return config


def tokens(text, retrieval=False):
    text = normalize(text)
    return (re.findall(r'[^\W_]+', text.casefold(), flags=re.UNICODE)
            if retrieval else text.split(' ') if text else [])


def bag_metrics(prediction, reference, retrieval=False):
    predicted, gold = Counter(tokens(prediction, retrieval)), Counter(tokens(reference, retrieval))
    missing, extra = sum((gold - predicted).values()), sum((predicted - gold).values())
    total = sum(gold.values()) + sum(predicted.values())
    return {'bag_edits': missing + extra, 'bag_denominator': total,
            'bwe': (missing + extra) / total if total else None,
            'missing_tokens': missing, 'extra_tokens': extra,
            'reference_tokens': sum(gold.values()), 'prediction_tokens': sum(predicted.values())}


def tsv_words(path):
    with open(path, encoding='utf-8', newline='') as stream:
        # Tesseract TSV contains literal quotes, not CSV-quoted fields.
        rows = csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE)
        words = []
        for row in rows:
            if None in row:
                raise ValueError('Unexpected TSV columns')
            if row['level'] != '5' or not row['text'].strip():
                continue
            x, y, w, h = (int(row[k]) for k in ('left', 'top', 'width', 'height'))
            confidence = float(row['conf'])
            if not math.isfinite(confidence) or not 0 <= confidence <= 100:
                raise ValueError('Invalid OCR word confidence')
            if w <= 0 or h <= 0 or x < 0 or y < 0:
                raise ValueError('Invalid OCR word bounds')
            words.append({'text': row['text'], 'confidence': confidence,
                          'box': [x, y, x + w, y + h],
                          'line': [int(row[k]) for k in ('block_num', 'par_num', 'line_num')]})
    return words


def rectangles_to_pixels(geometry, image_size):
    """PDF bottom-left rectangles to rendered top-left pixels, including rotation.

    geometry width/height describe the unrotated, crop-relative PDF coordinate
    space. A downstream extractor must supply that coordinate contract.
    """
    width, height = geometry['width'], geometry['height']
    rotation = geometry.get('rotation', 0)
    if rotation not in (0, 90, 180, 270) or min(width, height, *image_size) <= 0:
        raise ValueError('Invalid native geometry')
    out_width, out_height = (height, width) if rotation in (90, 270) else (width, height)
    sx, sy = image_size[0] / out_width, image_size[1] / out_height
    def point(x, y):
        x, y = ({0: (x, height - y), 90: (y, x),
                 180: (width - x, y), 270: (height - y, width - x)})[rotation]
        return x * sx, y * sy
    result = []
    for left, bottom, right, top in geometry['native_rectangles']:
        if not all(math.isfinite(v) for v in (left, bottom, right, top)):
            raise ValueError('Nonfinite native bounds')
        if not (0 <= left < right <= width and 0 <= bottom < top <= height):
            raise ValueError('Native rectangles must be clipped to the crop')
        points = [point(x, y) for x in (left, right) for y in (bottom, top)]
        result.append([min(p[0] for p in points), min(p[1] for p in points),
                       max(p[0] for p in points), max(p[1] for p in points)])
    return result


def extract_native_geometry(pdf_path, page_number, expected_native_sha256):
    """Read crop-relative native rectangles with the pinned PDFium extractor."""
    import importlib.metadata
    import pypdfium2 as pdfium
    if importlib.metadata.version('pypdfium2') != '4.30.0':
        raise ValueError('Native geometry parser differs from the pinned version')
    with closing(pdfium.PdfDocument(str(pdf_path))) as document:
        with closing(document[page_number - 1]) as page:
            with closing(page.get_textpage()) as textpage:
                native = textpage.get_text_bounded().strip()
                if hashlib.sha256(native.encode('utf-8')).hexdigest() != expected_native_sha256:
                    raise ValueError('Geometry native text hash mismatch')
                x0, y0, x1, y1 = page.get_bbox()
                rectangles = []
                for index in range(textpage.count_rects()):
                    left, bottom, right, top = textpage.get_rect(index)
                    left, right = max(x0, left), min(x1, right)
                    bottom, top = max(y0, bottom), min(y1, top)
                    if left < right and bottom < top:
                        rectangles.append([left - x0, bottom - y0, right - x0, top - y0])
                return {'width': x1 - x0, 'height': y1 - y0, 'rotation': page.get_rotation(),
                        'crop_box': [x0, y0, x1, y1], 'native_rectangles': rectangles,
                        'native_text_sha256': expected_native_sha256}


def covered_fraction(box, rectangles):
    """Exact union area of native rectangles inside an OCR word (no double count)."""
    left, top, right, bottom = box
    if right <= left or bottom <= top:
        raise ValueError('Invalid word bounds')
    overlaps = [(max(left, a), max(top, b), min(right, c), min(bottom, d))
                for a, b, c, d in rectangles if a < right and c > left and b < bottom and d > top]
    edges = sorted({x for a, _, c, _ in overlaps for x in (a, c)})
    area = 0.
    for x0, x1 in zip(edges, edges[1:]):
        intervals = sorted((b, d) for a, b, c, d in overlaps if a < x1 and c > x0)
        last, length = -math.inf, 0.
        for y0, y1 in intervals:
            length += max(0., y1 - max(last, y0))
            last = max(last, y1)
        area += (x1 - x0) * length
    return min(1., area / ((right - left) * (bottom - top)))


def usable_native(text, minimum_printable=.85):
    meaningful = [c for c in text if not c.isspace()]
    if not meaningful:
        return False
    valid = sum(c.isprintable() and unicodedata.category(c) != 'Co' and c != '\ufffd' for c in meaningful)
    return valid / len(meaningful) >= minimum_printable and '(cid:' not in text


def resolve_page(native_text, ocr, words, geometry, image_size, policy):
    """Resolve existing outputs; never turns an engine failure into a blank success."""
    for name in ('supplement_min_confidence', 'warning_mean_confidence'):
        if not math.isfinite(policy[name]) or not 0 <= policy[name] <= 100:
            raise ValueError('Invalid confidence threshold')
    if not 0 <= policy['native_overlap_fraction'] <= 1 or not 0 <= policy['min_printable_ratio'] <= 1:
        raise ValueError('Invalid ratio threshold')
    good_native = usable_native(native_text, policy['min_printable_ratio'])
    warnings = []
    if any(unicodedata.category(c) == 'Co' or c == '\ufffd' for c in native_text):
        warnings.append('suspected_native_encoding')
    if not good_native and native_text.strip():
        warnings.append('native_quality_rejected')
    ok = ocr.get('status') in ('OK', 'NO_TEXT_DETECTED')
    if not ok:
        return {'text': native_text if good_native else '', 'text_source': 'native' if good_native else 'none',
                'extraction_status': 'NATIVE_TEXT_OCR_FAILED' if good_native else 'EXTRACTION_FAILED',
                'technical_failure': True, 'reason': ocr.get('error') or ocr.get('status', 'NOT_RUN'),
                'warnings': warnings, 'supplement_words': 0}
    raw = ocr.get('text')
    if not isinstance(raw, str):
        raise ValueError('Successful OCR must include text, including explicit empty text')
    if ocr.get('status') == 'NO_TEXT_DETECTED' and raw.strip():
        raise ValueError('No-text OCR status conflicts with nonempty output')
    confidence = ocr.get('mean_word_confidence')
    if raw.strip() and (confidence is None or not math.isfinite(confidence)
                        or confidence < policy['warning_mean_confidence']):
        warnings.append('low_ocr_confidence')
    if not good_native:
        return {'text': raw, 'text_source': 'ocr',
                'extraction_status': 'OCR_TEXT_USED' if raw.strip() else 'NO_TEXT_DETECTED',
                'technical_failure': False, 'reason': 'native_unusable_ocr_fallback' if raw.strip() else 'ocr_found_no_words_not_proof_of_blank_page',
                'warnings': warnings + ([] if raw.strip() else ['no_text_requires_visual_channel']),
                'supplement_words': 0}
    rectangles = rectangles_to_pixels(geometry, image_size)
    additions, current, lines = [], None, []
    for word in words:
        if word['confidence'] < policy['supplement_min_confidence'] or not any(c.isalnum() for c in word['text']):
            continue
        if covered_fraction(word['box'], rectangles) >= policy['native_overlap_fraction']:
            continue
        if word['line'] != current and additions:
            lines.append(' '.join(additions)); additions = []
        current = word['line']
        additions.append(word['text'])
    if additions:
        lines.append(' '.join(additions))
    added = '\n'.join(lines)
    return {'text': native_text + ('\n' + added if added else ''),
            'text_source': 'native+ocr' if added else 'native',
            'extraction_status': 'NATIVE_PLUS_OCR' if added else 'NATIVE_TEXT_USED',
            'technical_failure': False, 'reason': 'preserve_native_add_uncovered_ocr' if added else 'native_preserved',
            'warnings': warnings, 'supplement_words': sum(len(line.split()) for line in lines)}


def enforce_failure_cap(rows, maximum_fraction):
    if not rows or not math.isfinite(maximum_fraction) or not 0 <= maximum_fraction <= 1:
        raise ValueError('Invalid failure cap or empty run')
    failed = sum(bool(row['technical_failure']) for row in rows)
    if failed / len(rows) > maximum_fraction:
        raise ValueError(f'Technical failure cap exceeded: {failed}/{len(rows)}')
    return {'pages': len(rows), 'technical_failures': failed, 'failure_fraction': failed / len(rows)}
