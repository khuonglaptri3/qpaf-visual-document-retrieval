"""Close bounded M2.3 calibration from preserved artifacts; no OCR/cloud rerun."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m11.artifacts import digest, file_manifest, object_hash, read_json, utc, verify_manifest, write_csv, write_json
from qpaf.m18.ocr_policy import evaluate_page_text
from qpaf.m23.policy import bag_metrics, enforce_failure_cap, resolve_page, tsv_words, extract_native_geometry
from qpaf.m23.review import metrics, review_data, validate_reviews
from qpaf.m23.worker import parse_tsv


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def candidate_configs():
    return ([{'name': 'native', 'method': 'native', 'dpi': 0},
             {'name': 'ocr150', 'method': 'ocr', 'dpi': 150},
             {'name': 'ocr300', 'method': 'ocr', 'dpi': 300},
             {'name': 'legacy40_150', 'method': 'legacy', 'dpi': 150}]
            + [{'name': f'mixed{dpi}_c{conf}', 'method': 'mixed', 'dpi': dpi,
                'supplement_min_confidence': conf, 'warning_mean_confidence': 60.,
                'native_overlap_fraction': .5, 'min_printable_ratio': .85}
               for dpi in (150, 300) for conf in (60, 80)])


def aggregate(rows, configs):
    result = []
    for c in configs:
        for split in ('development', 'holdout'):
            all_rows = [r for r in rows if r['candidate'] == c['name'] and r['split'] == split]
            valid = [r for r in all_rows if r['reference_chars']]
            chars = sum(r['reference_chars'] for r in valid)
            words = sum(r['reference_words'] for r in valid)
            bwe_denom = sum(r['retrieval_bwe']['bag_denominator'] for r in valid)
            strict_denom = sum(r['strict_bwe']['bag_denominator'] for r in valid)
            result.append({'candidate': c['name'], 'split': split, 'text_pages': len(valid),
                           'no_text_pages': len(all_rows) - len(valid),
                           'macro_retrieval_bwe': statistics.mean(r['retrieval_bwe']['bwe'] for r in valid),
                           'micro_retrieval_bwe': sum(r['retrieval_bwe']['bag_edits'] for r in valid) / bwe_denom,
                           'micro_strict_bwe': sum(r['strict_bwe']['bag_edits'] for r in valid) / strict_denom,
                           'micro_cer': sum(r['char_edits'] for r in valid) / chars,
                           'micro_wer': sum(r['word_edits'] for r in valid) / words,
                           'false_positive_chars': sum(r['false_positive_chars'] or 0 for r in all_rows)})
    return result


def percentile(values, quantile):
    values = sorted(values)
    position = (len(values) - 1) * quantile
    low = int(position)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)


def finalize(output):
    if output.exists():
        raise FileExistsError('Create a new package; prior outputs are immutable')
    review_path = ROOT / 'results/m2.3/reviews/2026-10-17-reference-qa-final/human_reviews.corrected.json'
    source = read_json(review_path)
    run = ROOT / 'results/m2.3' / source['source_run']
    verify_manifest(run / 'remote', read_json(run / 'remote/hashes.json'))
    verify_manifest(run / 'inputs', read_json(run / 'inputs/hashes.json'))
    verify_manifest(review_path.parent, read_json(review_path.parent / 'hashes.json'))
    data = review_data(run, output)
    validate_reviews(source, data)
    pages = read_json(run / 'remote/pages.json')
    geometry_path = ROOT / 'results/m2.3/verification/native-geometry-2026-10-17.json'
    geometry = read_json(geometry_path)
    if geometry['source_run'] != run.name or geometry['source_pages_sha256'] != digest(run / 'remote/pages.json'):
        raise ValueError('Geometry does not belong to this run')
    geoms = {p['page_id']: p for p in geometry['pages']}
    # Re-read native rectangles with explicit crop-origin handling; no OCR/render.
    corrected_geometry = []
    for page in pages:
        geom = extract_native_geometry(run / 'inputs' / page['pdf'], page['page_number'], page['native_text_sha256'])
        geom.update(page_id=page['page_id'], pdf_sha256=page['pdf_sha256'])
        corrected_geometry.append(geom)
    geoms = {p['page_id']: p for p in corrected_geometry}
    words, confidence_changes, confidence_derived = {}, [], []
    for page in pages:
        geom = geoms[page['page_id']]
        if geom['native_text_sha256'] != page['native_text_sha256'] or geom['pdf_sha256'] != page['pdf_sha256']:
            raise ValueError('Native geometry identity mismatch')
        for dpi in ('150', '300'):
            ocr = page['ocr'][dpi]
            values = parse_tsv(run / 'remote' / ocr['tsv'])
            words[page['page_id'], dpi] = tsv_words(run / 'remote' / ocr['tsv'])
            if len(words[page['page_id'], dpi]) != values['word_count']:
                raise ValueError('TSV word counts differ')
            if any('\n' in w['text'] or '\t' in w['text'] for w in words[page['page_id'], dpi]):
                raise ValueError('TSV parsing leaked row metadata into text')
            old = {k: ocr[k] for k in values}
            confidence_derived.append({'page_id': page['page_id'], 'dpi': int(dpi), **values})
            if old != values:
                confidence_changes.append({'page_id': page['page_id'], 'dpi': int(dpi), 'old': old, 'corrected': values})
            ocr.update(values)  # In-memory derived view only; never rewrite the run.

    configs = candidate_configs()
    metric_rows, resolved = [], {}
    selected_ids = {r['page_id'] for r in source['pages'] if r['reference']['status'] == 'CONFIRMED'}
    if len(selected_ids) != 18:
        raise ValueError('Keep exactly 18 references')
    for c in configs:
        outputs = []
        for position, (page, review) in enumerate(zip(pages, source['pages']), 1):
            dpi = str(c['dpi'])
            if c['method'] == 'mixed':
                out = resolve_page(page['native_text'], page['ocr'][dpi], words[page['page_id'], dpi],
                                   geoms[page['page_id']], page[f'image{dpi}_size'], c)
            else:
                use_native = c['method'] == 'native'
                if c['method'] == 'legacy':
                    use_native = evaluate_page_text(page['native_text'], min_chars=40).route == 'NATIVE_TEXT_QUALIFIED'
                out = {'text': page['native_text'] if use_native else page['ocr'][dpi]['text'],
                       'text_source': 'native' if use_native else 'ocr'}
            outputs.append(out)
            if review['page_id'] not in selected_ids:
                continue
            ref = review['reference']
            metric_rows.append({'candidate': c['name'], 'position': position, 'page_id': page['page_id'],
                                'split': page['calibration_split'], 'reference_no_text': ref['no_text'],
                                'retrieval_bwe': bag_metrics(out['text'], ref['text'], True),
                                'strict_bwe': bag_metrics(out['text'], ref['text']),
                                **metrics(out['text'], ref['text'])})
        resolved[c['name']] = outputs
    aggregates = aggregate(metric_rows, configs)
    development = [a for a in aggregates if a['split'] == 'development']
    by_name = {c['name']: c for c in configs}
    selected = min(development, key=lambda a: (a['macro_retrieval_bwe'], by_name[a['candidate']]['dpi'],
                                               -by_name[a['candidate']].get('supplement_min_confidence', 0)))
    chosen = by_name[selected['candidate']]
    if chosen['method'] != 'mixed':
        raise ValueError('Unexpected selected method; review operating contract before publishing')

    patch_path = ROOT / 'configs/m2.3/native_qa_closure.json'
    patch = read_json(patch_path)
    if patch['source_review_sha256'] != digest(review_path):
        raise ValueError('Native QA overlay source changed')
    revised = deepcopy(source)
    now, review_changes = utc(), []
    for item in patch['pages']:
        pos = item['position']
        row = revised['pages'][pos - 1]
        old = deepcopy(row['native'])
        row['native'] = {'status': item['status'], 'issues': item['issues'], 'note': item['note'],
                         'image_checked': True, 'reviewer': patch['reviewer'], 'reviewed_at': now}
        review_changes.append({'position': pos, 'page_id': row['page_id'], 'image_sha256': row['image_sha256'],
                               'before': old, 'after': row['native']})
    revised.update(reviewer=patch['reviewer'], exported_at=now)
    validate_reviews(revised, data)
    if any(r['native']['status'] in ('PENDING', 'UNSURE') for r in revised['pages']):
        raise ValueError('Unresolved native review remains')
    if any(a['reference'] != b['reference'] for a, b in zip(source['pages'], revised['pages'])):
        raise ValueError('The 18 references must remain unchanged')

    frozen_config = f'''# M2.3 bounded operating point. See decision.json for evidence and limitations.
schema_version = 1
policy_id = "m23-native-preserving-v1"
quality_status = "FROZEN"
freeze_scope = "bounded_operating_configuration_not_corpus_accuracy_certificate"
source_run = "{run.name}"
dataset_sha256 = "{source['dataset_sha256']}"
reference_count = 18
reference_reviewer = "Codex AI amendments to user-checked references"
selection_metric = "development_macro_retrieval_bwe"
selected_candidate = "{chosen['name']}"

[engine]
parser = "pypdfium2"
parser_version = "4.30.0"
name = "tesseract"
version = "5.3.0"
package = "5.3.0-2"
language_package = "1:4.1.0-2"
traineddata_sha256 = "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"
language = "eng"
dpi = {chosen['dpi']}
oem = 3
psm = 3
preprocessing = "none"
omp_threads = 1
page_ocr_timeout_seconds = 15

[routing]
mode = "native_plus_uncovered_ocr"
min_native_chars = 1
min_ocr_chars = 1
min_printable_ratio = 0.85
printable_denominator = "non_whitespace_characters_excluding_PUA_and_replacement"
supplement_min_confidence = {chosen['supplement_min_confidence']}.0
warning_mean_confidence = 60.0
native_overlap_fraction = 0.5
confidence_action = "warning_not_accuracy_or_page_rejection"
empty_action = "NO_TEXT_DETECTED_preserve_visual_page"
tsv_quoting = "QUOTE_NONE"

[resources]
cpu = 4
workers = 2
ram_mib = 4096
max_pixels = 40000000
retries = 0

[failure]
max_failure_fraction = 0.01
denominator = "all_scheduled_pages"
include = "render_error_parse_error_timeout_ocr_error"
exclude = "successful_no_text_detection_and_quality_warnings"
threshold_basis = "operational_stop_rule_not_estimated_corpus_error_rate"
preserve_rows = true
'''
    outputs = []
    for pos, (page, result, review) in enumerate(zip(pages, resolved[chosen['name']], revised['pages']), 1):
        outputs.append({'page_id': page['page_id'], 'document_id': page['document_id'], 'page_number': page['page_number'],
                        'split': page['calibration_split'], **result, 'text_sha256': sha(result['text']),
                        'native_text_sha256': page['native_text_sha256'],
                        'raw_ocr_text_sha256': page['ocr'][str(chosen['dpi'])]['text_sha256'],
                        'image_sha256': page[f'image{chosen["dpi"]}_sha256'],
                        'pdf_sha256': page['pdf_sha256'], 'policy_sha256': sha(frozen_config),
                        'native_review_status': review['native']['status'],
                        'reference_available': page['page_id'] in selected_ids})
    failure = enforce_failure_cap(outputs, .01)
    native_counts = dict(Counter(r['native']['status'] for r in revised['pages']))
    resources = {'worker': read_json(run / 'remote/resources.json'), 'dpi': {}}
    for dpi in ('150', '300'):
        timing = [p['ocr'][dpi]['seconds'] for p in pages]
        resources['dpi'][dpi] = {'median_seconds': statistics.median(timing), 'p95_seconds': percentile(timing, .95),
                                 'p99_seconds': percentile(timing, .99), 'max_seconds': max(timing),
                                 'total_attempt_seconds': sum(timing),
                                 'max_child_rss_mib': max(p['ocr'][dpi]['peak_tesseract_rss_mib'] for p in pages)}
    if resources['dpi'][str(chosen['dpi'])]['max_seconds'] > 15:
        raise ValueError('Selected OCR cap is below observed runtime')
    limitations = [
        '18 selected references, 15 development and 3 holdout; no new regression transcription.',
        'References amended and remaining native reviews completed by AI under explicit user authorization; no fabricated human sign-off.',
        'Retrospective metric amendment; previously inspected holdout is descriptive, not a fresh independent validation set.',
        'FROZEN fixes an operating configuration, not a corpus OCR accuracy guarantee or proof of less than 1 percent quality error.',
        'Small rotated French cover and scene-text regression remain recognized quality limitations; visual pages are retained.',
        'All OCR/render evidence reuses the original pinned run. New geometry/fusion analysis runs locally without another inference engine.',
    ]
    decision = {'task_id': 'M2.3', 'status': 'COMPLETE_BOUNDED_CALIBRATION', 'completed_at': now,
                'review_authority': patch['reviewer'], 'team_independent_signoff_claimed': False,
                'source_run': run.name, 'dataset_sha256': source['dataset_sha256'],
                'selected_candidate': chosen['name'], 'selection_split': 'development',
                'selection_metric': 'macro_retrieval_bwe', 'selected_policy': chosen,
                'thresholds_frozen': True, 'freeze_scope': 'operating_configuration_and_failure_contract',
                'native_decisions_all_121': native_counts, 'native_unresolved': 0,
                'original_review_records_retained': 121 - len(review_changes), 'ai_native_amendments': len(review_changes),
                'reference_count': 18, 'references_pending_in_user_scope': 0,
                'reference_texts_unchanged': True, 'technical_failure_check': failure,
                'confidence_rows_rederived': len(confidence_derived), 'confidence_rows_changed': len(confidence_changes),
                'quality_warning_pages': sum(bool(p['warnings']) for p in outputs),
                'text_sources': dict(Counter(p['text_source'] for p in outputs)),
                'no_text_detected_pages': [p['page_id'] for p in outputs if p['extraction_status'] == 'NO_TEXT_DETECTED'],
                'aggregates': aggregates, 'limitations': limitations,
                'ready_for': ['M2.4 loader/feature/quality-state contract', 'M2.6 implementation using frozen OCR policy', 'M2.8 shared preprocessing identity'],
                'not_executed': ['full-corpus OCR M2.6', 'retriever cache M2.8', 'learned training']}
    sources = {'original_run_hashes_sha256': digest(run / 'hashes.json'),
               'remote_manifest_sha256': digest(run / 'remote/hashes.json'),
               'original_review_sha256': digest(review_path), 'native_overlay_sha256': digest(patch_path),
               'geometry_sha256': digest(geometry_path),
               'decision_protocol_sha256': digest(ROOT / 'docs/superpowers/specs/2026-10-17-m23-closure-decision-protocol.md'),
               'source_files': [{'path': str(p.relative_to(ROOT)).replace('\\', '/'), 'sha256': digest(p)}
                                for p in [Path(__file__).resolve(), ROOT / 'src/qpaf/m23/policy.py', ROOT / 'src/qpaf/m23/worker.py', ROOT / 'tests/test_m23_policy.py']]}
    data.update(reference_subset_page_ids=sorted(selected_ids), initial_review=revised)
    for page, result in zip(data['pages'], outputs):
        page['policy_text'] = result['text']
    html = (ROOT / 'src/qpaf/m23/review_template.html').read_text(encoding='utf-8')
    html = html.replace("KEY='qpaf:m23:review:'+DATA.dataset_sha256;",
                        "KEY='qpaf:m23:review:'+DATA.dataset_sha256+':closure-v1';\nconst requiresReference=p=>DATA.reference_subset_page_ids.includes(p.page_id);")
    html = html.replace("let state={reviewer:'',reviews:{}},", 'let state=validateImport(DATA.initial_review),')
    html = html.replace('p.reference_required', 'requiresReference(p)')
    html = html.replace('<select id="compare-source" class="source-select">',
                        '<select id="compare-source" class="source-select"><option value="policy">Cấu hình đã chốt</option>')
    html = html.replace("const source=key==='native'?", "const source=key==='policy'?p.policy_text:key==='native'?")
    html = html.replace('Native gốc trước OCR. Hai mức DPI đã chạy độc lập; kết luận chất lượng chờ bạn review.',
                        'Native gốc trước OCR. Đã có kết luận review; phần bổ sung của Codex được ghi trong tên người duyệt.')
    html = html.replace('Sửa bản chữ sẽ hủy xác nhận cũ. Hãy ưu tiên các trang Cần bản chữ đối chiếu; ngưỡng OCR vẫn chờ tổng hợp và review.',
                        'Cấu hình M2.3 đã chốt trong gói bằng chứng. Sửa bản chữ sẽ hủy xác nhận cũ và cần tính lại báo cáo.')
    html = html.replace('render();if(!storageAvailable)',
                        "$('dataset-badge').textContent='M2.3 · REVIEW HOÀN TẤT';"
                        "$('source-description').textContent='121 kết luận native; 18 bản chữ. Có review bổ sung của Codex; xem báo cáo chốt cấu hình.';"
                        "$('page-filter').value=mode==='reference'?'required':'all';applyFilter();if(!storageAvailable)")
    html = html.replace('__M23_DATA__', json.dumps(data, ensure_ascii=False).replace('<', '\\u003c'))
    output.mkdir(parents=True)
    for name, value in [('decision.json', decision), ('provenance.json', sources), ('human_reviews.final.json', revised),
                        ('native_review_changes.json', review_changes), ('confidence_rederived.json', confidence_derived),
                        ('confidence_changes.json', confidence_changes), ('candidate_configs.json', configs),
                        ('candidate_metrics.json', metric_rows), ('resolved_pages.json', outputs), ('resources.json', resources),
                        ('native_geometry.json', corrected_geometry)]:
        write_json(output / name, value)
    write_csv(output / 'candidate_aggregates.csv', aggregates)
    # Preserve the exact bytes hashed into every page, including on Windows.
    (output / 'ocr_policy_frozen.toml').write_bytes(frozen_config.encode('utf-8'))
    (output / 'index.html').write_text(html, encoding='utf-8')
    write_json(output / 'hashes.json', file_manifest(output))
    print(json.dumps({k: decision[k] for k in ('status', 'selected_candidate', 'native_decisions_all_121', 'confidence_rows_changed', 'quality_warning_pages', 'text_sources', 'thresholds_frozen')}, ensure_ascii=False))
    for a in aggregates:
        print(json.dumps(a))
    return decision


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'results/m2.3/closure/2026-10-17-closed')
    args = parser.parse_args()
    finalize(args.output.resolve())
