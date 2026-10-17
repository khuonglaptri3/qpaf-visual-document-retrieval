"""Reproduce diagnostic comparisons of the user's 18 drafts; never signs labels."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m23.review import metrics, normalize
from qpaf.m11.artifacts import digest, verify_manifest


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    validation = HERE / 'raw_validation'
    verify_manifest(validation, read(validation / 'hashes.json'))
    original = HERE / 'human_reviews.original.json'
    raw_summary = read(validation / 'summary.json')
    assert digest(original) == raw_summary['review_sha256']
    payload = read(original)
    assert payload == read(validation / 'human_reviews.json')
    run = ROOT / 'results/m2.3' / payload['source_run']
    pages = {p['page_id']: p for p in read(run / 'remote/pages.json')}
    selected, rows, groups = [], [], defaultdict(list)
    for position, review in enumerate(payload['pages'], 1):
        ref = review['reference']
        if not (ref['text'].strip() or ref['no_text']):
            continue
        page = pages[review['page_id']]
        assert ref['scope'] == 'full_page'
        assert ref['status'] == 'DRAFT'
        assert not (ref['no_text'] and ref['text'].strip())
        selected.append({
            'position': position, 'page_id': page['page_id'],
            'document_id': page['document_id'], 'split': page['calibration_split'],
            'image_sha256': review['image_sha256'],
            'reference_status_as_received': ref['status'],
            'reference_text_sha256': hashlib.sha256(ref['text'].encode()).hexdigest(),
            'reference_no_text': ref['no_text'], 'reference_scope': ref['scope'],
            'native_status_as_received': review['native']['status'],
            'original_reference_required': page['reference_required'],
        })
        for channel in ('native', 'ocr150', 'ocr300'):
            prediction = page['native_text'] if channel == 'native' else page['ocr'][channel[3:]]['text']
            assert prediction is not None
            row = {'position': position, 'page_id': page['page_id'],
                   'split': page['calibration_split'], 'channel': channel,
                   'reference_status': ref['status'], 'diagnostic_only': True,
                   **metrics(prediction, ref['text'])}
            rows.append(row)
            groups[(page['calibration_split'], channel)].append(row)
            groups[('selected_18_descriptive_only', channel)].append(row)
    assert len(selected) == 18, 'Keep exactly the 18 pages received; do not select by metric.'
    output = HERE / 'diagnostic'
    output.mkdir(exist_ok=False)
    aggregate = []
    for (split, channel), entries in sorted(groups.items()):
        valid = [r for r in entries if r['reference_chars']]
        chars = sum(r['reference_chars'] for r in valid)
        words = sum(r['reference_words'] for r in valid)
        aggregate.append({
            'split': split, 'channel': channel, 'selected_pages': len(entries),
            'text_pages': len(valid), 'no_text_pages': len(entries) - len(valid),
            'reference_chars': chars, 'reference_words': words,
            'char_edits': sum(r['char_edits'] for r in valid),
            'word_edits': sum(r['word_edits'] for r in valid),
            'micro_cer': sum(r['char_edits'] for r in valid) / chars if chars else None,
            'micro_wer': sum(r['word_edits'] for r in valid) / words if words else None,
            'macro_cer': sum(r['cer'] for r in valid) / len(valid) if valid else None,
            'false_positive_chars': sum(r['false_positive_chars'] or 0 for r in entries),
        })
    manifest = {
        'source_run': payload['source_run'], 'dataset_sha256': payload['dataset_sha256'],
        'export_sha256': digest(original), 'scope': '18 pages already entered by the user',
        'selection_rule': 'All nonempty reference drafts plus the explicit no_text draft in this export; no metric-based selection.',
        'user_reported_complete_in_chat': True, 'browser_confirmed_count': 0,
        'pages': selected,
    }
    write(output / 'reference_subset.json', manifest)
    write(output / 'page_metrics.json', rows)
    with (output / 'page_metrics.csv').open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    coverage = []
    for split in ('development', 'holdout', 'regression'):
        matching = [p for p in selected if p['split'] == split]
        coverage.append({'split': split, 'pages': len(matching),
                         'documents': len({p['document_id'] for p in matching}),
                         'text_pages': sum(not p['reference_no_text'] for p in matching)})
    summary = {
        'task_id': 'M2.3', 'status': 'DRAFT_DIAGNOSTICS_READY_REFERENCE_QA_PENDING',
        'source_run': payload['source_run'], 'dataset_sha256': payload['dataset_sha256'],
        'export_sha256': digest(original), 'selected_reference_count': len(selected),
        'text_reference_count': 17, 'no_text_reference_count': 1,
        'reference_confirmed_count': 0, 'reference_draft_count': 18,
        'formal_references_pending_in_revised_scope': [p['page_id'] for p in selected],
        'native_decisions_all_121': dict(Counter(p['native']['status'] for p in payload['pages'])),
        'unresolved_native_page_ids': raw_summary['missing_native_reviews'],
        'coverage': coverage, 'aggregates': aggregate, 'thresholds_frozen': False,
        'diagnostic_only': True,
        'normalization': raw_summary['normalization'],
        'limitations': [
            'All 18 references are DRAFT in the source; no human signature was fabricated.',
            'Visual audit found incomplete text in graphics and transcription errors in the references.',
            'All selected native reviews are PASS; none of the six HAS_ERRORS native pages is represented.',
            'Only 3 holdout pages and no regression reference; no corpus-level accuracy claim.',
            'CER/WER against these drafts cannot justify a DPI decision or frozen thresholds.',
        ],
    }
    write(output / 'summary.json', summary)
    print(json.dumps({'status': summary['status'], 'selected_pages': len(selected),
                      'coverage': coverage, 'metric_rows': len(rows)}))


if __name__ == '__main__':
    main()
