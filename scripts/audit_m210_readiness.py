"""Independent, read-only M2.10 audit of frozen metadata and available payloads.

This script never opens sealed test ranking labels, trains a model, or rewrites an
upstream revision. It records checks that cannot be replayed from a Git pull.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m25.leakage import verify_frozen_splits
from qpaf.m27.matched import check_parity, load_manifest

RUN_ID = 'RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01'
M28 = Path('evidence/revisions/m2.8-001')
M27 = Path('evidence/revisions/m2.7-002')
M26 = Path('evidence/revisions/m2.6-001')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def audit_revision_bytes(directory):
    """Replay every size/hash entry in an immutable revision snapshot."""
    directory = Path(directory)
    rows = read_json(directory/'hashes.json')
    require(isinstance(rows, list) and rows, f'{directory}: empty hash manifest')
    seen = set()
    for row in rows:
        relative = Path(row['path'])
        target = (directory/relative).resolve()
        require(not relative.is_absolute() and target.is_relative_to(directory.resolve()) and
                relative.as_posix() not in seen, f'{directory}: unsafe/duplicate hash path')
        seen.add(relative.as_posix())
        require(target.is_file() and target.stat().st_size == row['size_bytes'] and
                sha256(target) == row['sha256'], f'{directory}: byte/hash drift at {relative}')
    return {'status': 'PASS', 'files_rehashed': len(rows),
            'manifest_sha256': sha256(directory/'hashes.json')}


def summarize_coverage(rows):
    require(bool(rows), 'Empty coverage subset')
    uncovered = [r['query_id'] for r in rows if r['captured_relevant'] == 0]
    recall = math.fsum(r['captured_relevant']/r['relevant_total'] for r in rows)/len(rows)
    return {'query_count': len(rows), 'candidate_count': sum(r['candidate_count'] for r in rows),
            'relevant_total': sum(r['relevant_total'] for r in rows),
            'captured_relevant': sum(r['captured_relevant'] for r in rows),
            'macro_recall': recall, 'uncovered_query_ids': uncovered,
            'status': 'BLOCKED' if uncovered or recall < .95 else 'PASS'}


def audit_coverage(coverage, splits):
    """Recompute every published aggregate from 1,142 per-query rows."""
    owner = {q: role for role, ids in splits.items() for q in ids}
    require(len(owner) == sum(len(ids) for ids in splits.values()), 'Split overlap')
    rows = coverage['per_query']
    require(len(rows) == len(owner) and {r['query_id'] for r in rows} == set(owner),
            'Coverage query identity/size mismatch')
    require(len({r['query_id'] for r in rows}) == len(rows), 'Duplicate coverage query')
    for row in rows:
        require(type(row['candidate_count']) is int and 200 <= row['candidate_count'] <= 600,
                'Candidate count outside frozen range')
        require(type(row['relevant_total']) is int and row['relevant_total'] > 0 and
                type(row['captured_relevant']) is int and
                0 <= row['captured_relevant'] <= row['relevant_total'], 'Invalid relevance count')
        require(math.isclose(row['recall'], row['captured_relevant']/row['relevant_total'],
                             abs_tol=1e-12, rel_tol=0), 'Per-query recall mismatch')
    total = summarize_coverage(rows)
    for key, value in total.items():
        if key == 'macro_recall':
            require(math.isclose(coverage[key], value, abs_tol=1e-12, rel_tol=0),
                    'Global macro recall mismatch')
        else:
            require(coverage[key] == value, f'Global coverage mismatch: {key}')
    by_split = {}
    for role in ('train', 'validation', 'test'):
        subset = summarize_coverage([r for r in rows if owner[r['query_id']] == role])
        for key, value in subset.items():
            actual = coverage['by_split'][role][key]
            require(math.isclose(actual, value, abs_tol=1e-12, rel_tol=0) if key == 'macro_recall'
                    else actual == value, f'{role} coverage mismatch: {key}')
        by_split[role] = subset
    require(coverage['require_zero_uncovered_queries'] is True and
            coverage['minimum_macro_recall'] == .95, 'Coverage gate drift')
    return {'status': 'PASS_REPLAY_BLOCKED_GATE', 'overall': total, 'by_split': by_split}


def audit_matched_config(root):
    manifest_path = root/'configs/m2.7/matched.json'
    manifest = load_manifest(manifest_path)
    prior = read_json(root/M27/'verification.json')
    require(sha256(manifest_path) == prior['manifest_sha256'], 'M2.7 manifest drift')
    base_path = root/manifest['base_config']['path']
    require(sha256(base_path) == manifest['base_config']['sha256'] == prior['base_config_sha256'],
            'M2.7 base config drift')
    with base_path.open('rb') as stream:
        base = tomllib.load(stream)
    with (root/'configs/m2.4/pipeline.toml').open('rb') as stream:
        m24 = tomllib.load(stream)
    require(base.pop('experiment_id') == manifest['experiment_id'] and
            m24.pop('experiment_id') != manifest['experiment_id'] and base == m24,
            'M2.7 base differs from M2.4 beyond experiment_id')
    require(manifest['methods'] == {'QARF': {'gate_granularity': 'query'},
                                    'QPAF': {'gate_granularity': 'page'}} and
            manifest['allowed_semantic_diff'] == ['gate_granularity'],
            'Matched method semantics drift')
    require(manifest['seeds']['robustness'] == [20260820, 20260821, 20260822] and
            manifest['run_order'] == ['QARF', 'independent_review', 'QPAF'],
            'Matched seed/order drift')
    for ref in manifest['shared_inputs'].values():
        if isinstance(ref, dict):
            require(sha256(root/ref['path']) == ref['sha256'], 'M2.7 shared input hash drift')
    for name, expected in prior['source_sha256'].items():
        require(sha256(root/name) == expected, f'M2.7 training-path code drift: {name}')
    require(prior['data_order']['identical'] is True and
            set(prior['initialization']) == {'20260820', '20260821', '20260822'} and
            all(x['identical'] and x['parameter_count'] == 42 for x in prior['initialization'].values()) and
            all(prior['pairs'][str(seed)] == {'gate_granularity': ['query', 'page']}
                for seed in manifest['seeds']['robustness']),
            'Archived M2.7 parity receipt is incomplete')
    replay = check_parity(manifest, root)
    for key in ('base_config_sha256', 'm24_drift', 'pairs', 'methods_match_runner',
                'initialization', 'data_order', 'shared_inputs', 'pending_inputs'):
        require(replay[key] == prior[key], f'M2.7 dynamic parity replay differs: {key}')
    return {'status': 'PASS_STRUCTURAL_AND_SYNTHETIC_PARITY',
            'manifest_sha256': sha256(manifest_path),
            'source_files_rehashed': len(prior['source_sha256']),
            'synthetic_parity_replay': {'initialization': replay['initialization'],
                                        'data_order': replay['data_order'],
                                        'method_diff': replay['pairs']},
            'real_cache_binding': 'PENDING_M2.8_IN_FROZEN_MANIFEST'}


def audit_reload_evidence(root):
    summaries = {}
    for method, run in [('QARF', '20261018T081405-c46dbcd9'),
                        ('QPAF', '20261018T081516-e008bcb1')]:
        path = root/'results/m2.4/synthetic-verification'/method/run/'summary.json'
        data = read_json(path)
        parity = data['reload_parity']
        require(data['kind'] == 'synthetic_software_verification' and
                data['method'] == method and data['test_split'] == 'not_opened' and
                data['parameter_count'] == 42 and
                set(data['checkpoint_sha256']) == {'best', 'last'} and
                all(len(value) == 64 for value in data['checkpoint_sha256'].values()) and
                parity['passed'] is True and
                parity['max_abs_difference'] <= parity['tolerance'],
                f'{method} synthetic reload receipt failed')
        summaries[method] = {'summary_sha256': sha256(path),
                             'max_abs_difference': parity['max_abs_difference'],
                             'scope': parity['scope']}
    return {'status': 'ARCHIVED_IN_PROCESS_ONLY', 'methods': summaries,
            'fresh_process_real_checkpoint': 'NOT_RUN'}


def audit(root):
    root = Path(root)
    revisions = {name: audit_revision_bytes(root/path)
                 for name, path in [('m2.6', M26), ('m2.8', M28)]}
    freeze = read_json(root/'configs/m2.5/freeze.json')
    split = verify_frozen_splits(root, freeze)
    split.pop('roles')
    matched = audit_matched_config(root)
    handover = read_json(root/M28/'handover.json')
    coverage_path = root/M28/'coverage_report.json'
    coverage = read_json(coverage_path)
    candidate_path = root/M28/'candidate_freeze.json'
    candidate = read_json(candidate_path)
    input_manifest = read_json(root/M28/'input_manifest.json')
    prior_review = read_json(root/M28/'artifact_review.json')
    closure = read_json(root/M28/'closure_verification.json')
    require(handover['run_id'] == RUN_ID and handover['status'] == 'BLOCKED_COVERAGE',
            'M2.8 handover identity/status mismatch')
    require(handover['candidate_freeze_sha256'] == sha256(candidate_path) and
            handover['coverage_report_sha256'] == sha256(coverage_path),
            'M2.8 handover child hash mismatch')
    require(candidate['provenance']['uses_qrels'] is False and
            input_manifest['uses_qrels'] is False and handover['training_executed'] is False,
            'Candidate freeze label or training boundary drift')
    require(candidate['provenance']['m27_manifest_sha256'] == matched['manifest_sha256'] ==
            input_manifest['m27_manifest_sha256'], 'M2.7/M2.8 identity mismatch')
    m26_handover = read_json(root/M26/'handover.json')
    require(candidate['provenance']['m26_preprocessing_identity_sha256'] ==
            m26_handover['preprocessing_identity_sha256'] ==
            input_manifest['preprocessing_identity_sha256'], 'M2.6/M2.8 OCR identity mismatch')
    require(input_manifest['m21_manifest_sha256'] == sha256(root/freeze['split_manifest']) and
            input_manifest['m25_freeze_sha256'] == sha256(root/'configs/m2.5/freeze.json'),
            'M2.1/M2.5 identity mismatch')
    require(handover['split_role_sha256'] == split['role_sha256'] and
            handover['query_count'] == 1142 and handover['candidate_count'] == 549689,
            'M2.8 split/count mismatch')
    require(candidate['counts']['candidate_count'] == handover['candidate_count'] and
            candidate['counts']['query_count'] == handover['query_count'] and
            candidate['counts']['page_count'] == handover['page_count'],
            'Candidate freeze counts differ from handover')
    coverage_audit = audit_coverage(coverage, verify_frozen_splits(root, freeze)['roles'])
    require(handover['uncovered_query_ids'] == coverage_audit['overall']['uncovered_query_ids'] and
            math.isclose(handover['macro_candidate_recall'],
                         coverage_audit['overall']['macro_recall'], abs_tol=1e-12, rel_tol=0),
            'Handover coverage differs from independent aggregate')
    require(prior_review['status'] == 'PASS' and
            prior_review['scientific_handover_status'] == 'BLOCKED_COVERAGE' and
            prior_review['independent_replay']['all_channel_top_lists_and_union'] is True and
            prior_review['independent_replay']['all_raw_rows_and_normalization'] is True and
            closure['status'] == 'PASS' and closure['scientific_handover_status'] == 'BLOCKED_COVERAGE',
            'Earlier full-payload replay receipt incomplete')
    bundle_manifest = read_json(root/M28/'bundle_hashes.json')
    bundle_by_path = {row['path']: row for row in bundle_manifest}
    require(len(bundle_manifest) == len(bundle_by_path) == 15 and
            set(bundle_by_path) >= {'raw_scores.parquet', 'candidate_set.parquet',
                                    'handover.json', 'coverage_report.json'},
            'Portable bundle manifest incomplete')
    for name, expected in [('raw_scores.parquet', handover['score_cache_sha256']),
                           ('candidate_freeze.json', handover['candidate_freeze_sha256']),
                           ('coverage_report.json', handover['coverage_report_sha256'])]:
        require(bundle_by_path[name]['sha256'] == expected,
                f'Portable bundle/handover hash mismatch: {name}')
    payload = root/'results/m2.8'/RUN_ID/'bundle/raw_scores.parquet'
    payload_status = 'PASS_REHASHED' if payload.is_file() and sha256(payload) == handover['score_cache_sha256'] else (
        'FAIL_HASH' if payload.is_file() else 'UNAVAILABLE_AFTER_PULL')
    require(payload_status != 'FAIL_HASH', 'Local M2.8 raw Parquet hash mismatch')
    return {
        'schema_version': 1, 'task_id': 'M2.10', 'owner': 'Thanh', 'audit_date': '2026-10-21',
        'status': 'AUDIT_COMPLETED_READINESS_BLOCKED',
        'source_run_id': RUN_ID, 'revision_bytes': revisions,
        'frozen_splits': split, 'matched_config': matched,
        'coverage_replay': coverage_audit,
        'candidate_freeze': {'status': 'PASS_METADATA', 'candidate_freeze_sha256': sha256(candidate_path),
                             'label_free': True, 'candidate_count': candidate['counts']['candidate_count']},
        'prior_full_payload_replay': {'status': 'PASS_ARCHIVED_RECEIPT_ONLY',
                                      'artifact_review_sha256': sha256(root/M28/'artifact_review.json'),
                                      'closure_verification_sha256': sha256(root/M28/'closure_verification.json')},
        'current_raw_parquet_rehash': payload_status,
        'reload': audit_reload_evidence(root),
        'pilot_blockers': ['M2.8_ZERO_UNCOVERED_GATE_FAILED',
                           'M2.7_REAL_INPUT_BINDING_NOT_FROZEN',
                           'NAMED_HUMAN_REVIEW_PENDING'],
        'independent_human_review': 'PENDING',
        'test_ranking_metrics_computed': False,
        'scientific_claim': 'NONE',
    }


def run_tests(root):
    results = {}
    env = os.environ.copy()
    env['PYTHONPATH'] = str(root/'src')
    for label, pattern in [('m2.4', 'test_m24*.py'), ('m2.5', 'test_m25*.py'),
                           ('m2.7', 'test_m27*.py'), ('m2.8', 'test_m28*.py'),
                           ('m2.10', 'test_m210*.py')]:
        command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-q']
        completed = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
        results[label] = {'command': command[1:], 'exit_code': completed.returncode,
                          'output': (completed.stdout+completed.stderr).strip()}
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Create-once JSON report path')
    parser.add_argument('--skip-tests', action='store_true', help='Audit inputs without running local tests')
    args = parser.parse_args(argv)
    report = audit(ROOT)
    report['local_tests'] = 'NOT_RUN' if args.skip_tests else run_tests(ROOT)
    report['audit_source_sha256'] = sha256(Path(__file__))
    if isinstance(report['local_tests'], dict):
        failed = {name: item['output'] for name, item in report['local_tests'].items()
                  if item['exit_code'] != 0}
        require(not failed, f'Local audit tests failed: {failed}')
    output = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)+'\n'
    if args.output:
        target = args.output if args.output.is_absolute() else ROOT/args.output
        require(not target.exists(), f'Create-once report already exists: {target}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding='utf-8', newline='\n')
    else:
        print(output, end='')


if __name__ == '__main__':
    main()
