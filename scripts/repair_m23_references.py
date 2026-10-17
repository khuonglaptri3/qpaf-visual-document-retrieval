"""Apply the image-checked, user-authorized M2.3 reference patch locally.

Creates a new review package; never rewrites source reviews, OCR, or human native
decisions. The CONFIRMED amendments are explicitly attributed to AI visual QA.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import difflib
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m11.artifacts import digest, file_manifest, read_json, utc, write_csv, write_json
from qpaf.m23.review import metrics, review_data, validate_reviews


def text_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def replace_checked(text, before, after):
    if before not in text:
        raise ValueError(f'Patch no longer applies: {before!r}')
    return text.replace(before, after)


def build(patch_path, output):
    patch = read_json(patch_path)
    source = ROOT / patch['source_review']
    if digest(source) != patch['source_review_sha256']:
        raise ValueError('Source review hash changed')
    original = read_json(source)
    run = ROOT / 'results/m2.3' / patch['source_run']
    data = review_data(run, output)
    validate_reviews(original, data)
    if original['dataset_sha256'] != patch['dataset_sha256']:
        raise ValueError('Patch dataset mismatch')
    positions = {i for i, row in enumerate(original['pages'], 1)
                 if row['reference']['text'].strip() or row['reference']['no_text']}
    if (len(positions) != 18 or len(patch['pages']) != 18
            or {p['position'] for p in patch['pages']} != positions):
        raise ValueError('Patch must cover exactly the 18 pages already supplied')
    if output.exists():
        raise FileExistsError('Use a new output directory; prior packages are immutable')

    revised = deepcopy(original)
    timestamp = utc()
    revised.update(exported_at=timestamp, reviewer=patch['reviewer'])
    source_pages = {p['page_id']: p for p in data['pages']}
    changes, selected, metric_rows, diffs, transcripts = [], [], [], [], []
    for instruction in patch['pages']:
        pos = instruction['position']
        old = original['pages'][pos - 1]
        row = revised['pages'][pos - 1]
        page = source_pages[row['page_id']]
        ref = row['reference']
        text = instruction.get('text', ref['text'])
        for before, after in instruction.get('replacements', []):
            text = replace_checked(text, before, after)
        ref.update(text=text, status='CONFIRMED', reviewer=patch['reviewer'], reviewed_at=timestamp)
        changed = text != old['reference']['text']
        changes.append({
            'position': pos, 'page_id': row['page_id'], 'image_sha256': row['image_sha256'],
            'text_changed': changed, 'before': old['reference'], 'after': deepcopy(ref),
            'reason': instruction['reason'], 'notes': instruction.get('notes', []),
            'layout_sensitive': instruction.get('layout_sensitive', False),
        })
        selected.append({
            'position': pos, 'page_id': row['page_id'], 'document_id': page['document_id'],
            'split': page['calibration_split'], 'image_sha256': row['image_sha256'],
            'reference_text_sha256': text_hash(text), 'reference_status': ref['status'],
            'reference_no_text': ref['no_text'],
            'layout_sensitive': instruction.get('layout_sensitive', False),
            'original_reference_required': page['reference_required'],
        })
        diffs.extend(difflib.unified_diff(old['reference']['text'].splitlines(True),
                                       text.splitlines(True), fromfile=f'original/position-{pos}',
                                       tofile=f'corrected/position-{pos}'))
        transcripts += [f'## STT {pos} — {row["page_id"]}', '', instruction['reason'], '',
                        '```text', text if text else '(Trang không chữ; no_text=true)', '```', '']
        for channel in ('native', 'ocr150', 'ocr300'):
            prediction = page['native_text'] if channel == 'native' else page[channel + '_text']
            metric_rows.append({
                'position': pos, 'page_id': row['page_id'], 'split': page['calibration_split'],
                'channel': channel, 'output_available': prediction is not None,
                'layout_sensitive': instruction.get('layout_sensitive', False),
                **(metrics(prediction, text) if prediction is not None else {}),
            })

    validate_reviews(revised, data)
    for old, new in zip(original['pages'], revised['pages']):
        if old['native'] != new['native']:
            raise ValueError('Human native decisions must be preserved')
        if old['page_id'] not in {p['page_id'] for p in selected} and old != new:
            raise ValueError('Unselected page changed')
    groups = defaultdict(list)
    for row in metric_rows:
        groups[row['split'], row['channel']].append(row)
    aggregates = []
    for (split, channel), rows in sorted(groups.items()):
        valid = [r for r in rows if r.get('reference_chars', 0)]
        chars = sum(r['reference_chars'] for r in valid)
        words = sum(r['reference_words'] for r in valid)
        aggregates.append({
            'split': split, 'channel': channel, 'selected_pages': len(rows),
            'text_pages': len(valid), 'no_text_pages': sum(r.get('reference_chars') == 0 for r in rows),
            'reference_chars': chars, 'reference_words': words,
            'char_edits': sum(r['char_edits'] for r in valid),
            'word_edits': sum(r['word_edits'] for r in valid),
            'micro_cer': sum(r['char_edits'] for r in valid) / chars if chars else None,
            'micro_wer': sum(r['word_edits'] for r in valid) / words if words else None,
            'macro_cer': sum(r['cer'] for r in valid) / len(valid) if valid else None,
            'unavailable_outputs': sum(not r['output_available'] for r in rows),
            'false_positive_chars': sum(r.get('false_positive_chars') or 0 for r in rows),
        })
    unresolved = [r['page_id'] for r in revised['pages'] if r['native']['status'] in ('PENDING', 'UNSURE')]
    summary = {
        'task_id': 'M2.3', 'status': 'REFERENCE_QA_COMPLETE_NATIVE_REVIEW_PENDING',
        'source_run': patch['source_run'], 'dataset_sha256': data['dataset_sha256'],
        'source_review_sha256': digest(source), 'created_at': timestamp,
        'selected_reference_count': 18, 'reference_confirmed_count': 18, 'reference_draft_count': 0,
        'text_reference_count': 17, 'no_text_reference_count': 1,
        'changed_text_count': sum(c['text_changed'] for c in changes),
        'formal_references_pending_in_revised_scope': [],
        'reference_reviewer_type': 'AI assistant, amendments authorized by user',
        'user_reported_all_18_checked': True, 'native_decisions_all_121': dict(Counter(r['native']['status'] for r in revised['pages'])),
        'unresolved_native_page_ids': unresolved, 'thresholds_frozen': False,
        'coverage': [{'split': split, 'pages': sum(p['split'] == split for p in selected),
                      'documents': len({p['document_id'] for p in selected if p['split'] == split})}
                     for split in ('development', 'holdout', 'regression')],
        'aggregates': aggregates, 'normalization': original['normalization'],
        'limitations': [
            'CONFIRMED amendments are signed by Codex, not attributed to a human reviewer.',
            'The cohort is the user-selected 18 pages; 15 development, 3 holdout, no regression.',
            'Full-page sequence CER/WER includes reading-order and math/word-cloud serialization effects.',
            'Only complete legible ruler numerals were transcribed; obscured fragments are documented in change_log.json.',
            'Existing human native PASS labels were not rewritten; graphics omitted by native can conflict with a full-page PASS interpretation.',
            'Eight native conclusions remain unresolved; no DPI selection, threshold freeze, or M2.3 acceptance is implied.',
        ],
    }
    manifest = {k: summary[k] for k in ('source_run', 'dataset_sha256', 'source_review_sha256', 'created_at')}
    manifest.update(scope='Exactly the 18 references already supplied by the user', pages=selected)
    provenance = {
        'user_instruction': patch['user_instruction'], 'user_reported_all_18_checked': True,
        'amendments_reviewer': patch['reviewer'], 'reviewed_at': timestamp,
        'policy': patch['policy'], 'patch_sha256': digest(patch_path),
        'source_review': patch['source_review'], 'source_review_sha256': digest(source),
        'human_native_decisions_preserved': True, 'original_browser_storage_modified': False,
        'transport_schema_note': 'm23_human_review is the existing interchange format; reference amendment provenance is explicitly AI, not a new human review.',
    }
    # Seed a separate review workspace so old browser drafts cannot hide the edits.
    data.update(reference_subset_page_ids=[p['page_id'] for p in selected], initial_review=revised)
    html = (ROOT / 'src/qpaf/m23/review_template.html').read_text(encoding='utf-8')
    html = replace_checked(html, "KEY='qpaf:m23:review:'+DATA.dataset_sha256;",
                           "KEY='qpaf:m23:review:'+DATA.dataset_sha256+':reference-qa-v1';\n"
                           "const referenceIds=new Set(DATA.reference_subset_page_ids);\n"
                           "const requiresReference=p=>referenceIds.has(p.page_id);")
    html = replace_checked(html, "let state={reviewer:'',reviews:{}},", "let state=validateImport(DATA.initial_review),")
    html = replace_checked(html, 'p.reference_required', 'requiresReference(p)')
    html = replace_checked(html, 'render();if(!storageAvailable)',
                           "$('dataset-badge').textContent='18 BẢN ĐÃ QA ẢNH';"
                           "$('source-description').textContent='18 trang người dùng đã kiểm tra; bản sửa do Codex đối chiếu ảnh. Ngưỡng chưa chốt.';"
                           "$('page-filter').value=mode==='reference'?'required':'all';"
                           "applyFilter();if(!storageAvailable)")
    html = replace_checked(html, '__M23_DATA__', json.dumps(data, ensure_ascii=False).replace('<', '\\u003c'))

    output.mkdir(parents=True)
    for name, value in [('human_reviews.corrected.json', revised), ('reference_subset.json', manifest),
                        ('provenance.json', provenance), ('change_log.json', changes),
                        ('summary.json', summary), ('page_metrics.json', metric_rows), ('patch.json', patch)]:
        write_json(output / name, value)
    write_csv(output / 'page_metrics.csv', metric_rows)
    (output / 'references.md').write_text('# M2.3 — 18 bản chữ sau QA ảnh\n\n' + '\n'.join(transcripts), encoding='utf-8')
    (output / 'changes.diff').write_text(''.join(diffs), encoding='utf-8')
    (output / 'index.html').write_text(html, encoding='utf-8')
    write_json(output / 'hashes.json', file_manifest(output))
    print(json.dumps({k: summary[k] for k in ('status', 'selected_reference_count', 'reference_confirmed_count', 'changed_text_count', 'thresholds_frozen')}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patch', type=Path, default=ROOT / 'configs/m2.3/reference_qa_18.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/m2.3/reviews/2026-10-17-reference-qa-v1')
    args = parser.parse_args()
    build(args.patch.resolve(), args.output.resolve())
