"""Build an offline M2.3 review prototype from existing M2.2 pages, without inference."""
import argparse
import base64
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / 'results/m2.2/RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def build_demo(run, output):
    run, output = Path(run).resolve(), Path(output).resolve()
    inputs = run / 'inputs'
    native = read_json(inputs / 'pages.json')
    prepared = read_json(run / 'remote/prepare/pages.json')
    config = read_json(run / 'resolved_config.json')
    if [p['page_id'] for p in native] != [p['page_id'] for p in prepared]:
        raise ValueError('Prepared/native page IDs or order differ')
    if config['text']['dpi'] != 150:
        raise ValueError('This prototype expects the recorded 150-DPI sample')
    rows = []
    for original, final in zip(native, prepared):
        image = (inputs / original['image']).resolve()
        if not image.is_relative_to(inputs.resolve()) or image.suffix.lower() != '.png':
            raise ValueError('Unexpected image path')
        payload = image.read_bytes()
        if sha(payload) != original['image_sha256']:
            raise ValueError('Image hash mismatch')
        if sha(original['text'].encode()) != original['native_text_sha256']:
            raise ValueError('Native text hash mismatch')
        if sha(final['text'].encode()) != final['text_sha256']:
            raise ValueError('Prepared text hash mismatch')
        document_id, page_number = original['page_id'].rsplit('_page_', 1)
        rows.append({
            'page_id': original['page_id'], 'document_id': document_id,
            'page_number': int(page_number), 'native_text': original['text'],
            'ocr150_text': final['text'] if final['text_source'] == 'ocr' else None,
            'ocr300_text': None, 'extraction_status': final['extraction_status'],
            'image_sha256': original['image_sha256'], 'pdf_sha256': original['pdf_sha256'],
            'native_text_sha256': original['native_text_sha256'],
            'image_width': original['width'], 'image_height': original['height'],
            'image_data': 'data:image/png;base64,' + base64.b64encode(payload).decode('ascii'),
        })
    identity = {'source_run': run.name, 'pages': [{k: v for k, v in p.items() if k != 'image_data'} for p in rows]}
    dataset_hash = sha(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode())
    data = {'schema_version': 1, 'demo': True, 'dataset_id': 'm23-review-ui-v1',
            'dataset_sha256': dataset_hash, 'source_run': run.name, 'pages': rows}
    template = (ROOT / 'src/qpaf/m23/review_template.html').read_text(encoding='utf-8')
    if template.count('__M23_DATA__') != 1:
        raise ValueError('Template data marker is missing or ambiguous')
    html = template.replace('__M23_DATA__', json.dumps(data, ensure_ascii=False).replace('<', '\\u003c'))
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(html, encoding='utf-8')
    manifest = {k: v for k, v in data.items() if k != 'pages'}
    manifest.update(page_count=len(rows), html_sha256=sha(html.encode()),
                    note='UI prototype using M2.2 pages; no new OCR, reference labels, or M2.3 calibration run.')
    (output / 'demo_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output / 'index.html'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-folder', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--output', type=Path, default=ROOT / 'results/m2.3/review-demo-2026-10-17')
    args = parser.parse_args()
    print(build_demo(args.run_folder, args.output))


if __name__ == '__main__':
    main()
