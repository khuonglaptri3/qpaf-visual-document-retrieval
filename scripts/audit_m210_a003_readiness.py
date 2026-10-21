"""Read-only M2.10 readiness replay of the A003 candidate revision (m2.8-002).

Successor to ``audit_m210_readiness.py``, which stays byte-identical because
M2.10-001 records its hash. This replay reuses its checks unchanged, adds the
A003 lineage, label-order, coverage and M2.7 binding checks, and opens no test
ranking labels. It is not the independent M2.10 owner's sign-off.
"""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))

from scripts.audit_m210_readiness import (M26, audit_coverage, audit_matched_config,
                                          audit_reload_evidence, audit_revision_bytes, read_json,
                                          require, run_tests, sha256, summarize_coverage)
from qpaf.m25.leakage import verify_frozen_splits
from qpaf.m27.binding import load_binding, verify_binding
from qpaf.m28 import expansion

BASELINE_RUN = 'RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01'
RUN_ID = 'RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01'
M28_BASE = Path('evidence/revisions/m2.8-001')
M28 = Path('evidence/revisions/m2.8-002')
M27 = Path('evidence/revisions/m2.7-003')
BINDING = Path('configs/m2.7/input_binding.json')
EXPANSION_CONFIG = Path('configs/m2.8/expansion.json')
PREVIOUSLY_UNCOVERED = '04450a0f59f81025574451222aa26322ae7ede42_2'
PARQUET = ('raw_scores.parquet', 'normalized_scores.parquet', 'channel_top_lists.parquet',
           'candidate_set.parquet', 'candidate_expansion_log.parquet',
           'candidate_expansion_queries.parquet')


def _time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def replay_coverage(coverage, splits):
    """Recompute every aggregate from per-query rows; status follows the evidence."""
    replay = audit_coverage(coverage, splits)
    by_split = {role: summarize_coverage([r for r in coverage['per_query'] if r['query_id'] in set(ids)])
                for role, ids in splits.items()}
    status = 'PASS' if replay['overall']['status'] == 'PASS' and all(
        value['status'] == 'PASS' for value in by_split.values()) else 'BLOCKED'
    require(coverage['status'] == status, 'Published coverage status differs from replay')
    return {'status': status, 'overall': replay['overall'], 'by_split': by_split}


def check_label_order(freeze, development, handover):
    """Freeze before any label; development qrels before test qrels; no ranking metric."""
    require(freeze['provenance']['uses_qrels'] is False and freeze['policy']['uses_labels'] is False
            and freeze['policy']['reads_query_id_content'] is False,
            'Candidate freeze is not label-free')
    require(development['test_qrels_opened'] is False and development['status'] == 'PASS'
            and development['roles'] == ['train', 'validation'],
            'Development phase opened test labels or did not pass')
    require(_time(freeze['created_utc']) < _time(development['created_utc']),
            'Development coverage was recorded before the candidate freeze')
    require(development['candidate_freeze_sha256'] == handover['candidate_freeze_sha256'],
            'Development and final phases audited different freezes')
    require(handover['test_ranking_metrics_computed'] is False and handover['training_executed'] is False
            and handover['test_labels_used_only_for_frozen_candidate_coverage'] is True,
            'Test labels were used beyond frozen-candidate coverage')
    return {'status': 'PASS', 'freeze_utc': freeze['created_utc'],
            'development_utc': development['created_utc']}


def audit_a003_lineage(root):
    """Bind amendment, config, baseline freeze, new revision and the M2.7 binding."""
    root = Path(root)
    config = read_json(root/EXPANSION_CONFIG)
    amendment = root/config['amendment']['path']
    require(sha256(amendment) == config['amendment']['sha256'], 'A003 amendment drift')
    handover = read_json(root/M28/'handover.json')
    freeze = read_json(root/M28/'candidate_freeze.json')
    base_freeze_path = root/M28_BASE/'candidate_freeze.json'
    require(handover['run_id'] == RUN_ID and handover['status'] == 'PASS'
            and handover['policy_id'] == expansion.POLICY_ID
            and handover['amendment_id'] == expansion.AMENDMENT_ID
            and handover['amendment_sha256'] == config['amendment']['sha256']
            and handover['source_run_id'] == BASELINE_RUN
            and handover['baseline_candidate_freeze_sha256'] == sha256(base_freeze_path)
            == config['source_run']['candidate_freeze_sha256'], 'M2.8-002 handover lineage mismatch')
    require(handover['candidate_freeze_sha256'] == sha256(root/M28/'candidate_freeze.json')
            and handover['coverage_report_sha256'] == sha256(root/M28/'coverage_report.json'),
            'M2.8-002 handover child hash mismatch')
    require(freeze['policy'] == expansion.policy(config['policy']['top_k'])
            and freeze['counts']['candidate_count'] == handover['candidate_count']
            and freeze['counts']['base_candidate_count'] == read_json(base_freeze_path)['counts']['candidate_count']
            and freeze['score_arrays_sha256'] == read_json(base_freeze_path)['score_arrays_sha256'],
            'A003 freeze does not extend the M2.8-001 arrays and baseline')
    bundle = {row['path']: row for row in read_json(root/M28/'bundle_hashes.json')}
    for name, expected in (('raw_scores.parquet', handover['score_cache_sha256']),
                           ('candidate_freeze.json', handover['candidate_freeze_sha256']),
                           ('coverage_report.json', handover['coverage_report_sha256'])):
        require(bundle[name]['sha256'] == expected, f'Bundle/handover hash mismatch: {name}')
    require(set(PARQUET) <= set(bundle), 'Bundle manifest lacks a Parquet artifact')
    baseline = read_json(root/M28/'baseline_replay.json')
    require(baseline['status'] == 'PASS' and all(baseline['checks'].values()),
            'Rebuilt C0 did not match the M2.8-001 freeze')
    import csv
    with (root/M28/'candidate_expansion_log.csv').open(encoding='utf-8', newline='') as stream:
        log = list(csv.DictReader(stream))
    require(len(log) == freeze['counts']['added_page_count'] and all(
        row['reason'] == expansion.REASON and expansion.document_ids([row['page_id']])[0] == row['document_id']
        for row in log), 'Expansion log differs from the freeze counts or document mapping')
    per_query = {row['query_id']: row for row in read_json(root/M28/'coverage_report.json')['per_query']}
    binding = load_binding(root/BINDING)
    prior = read_json(root/M27/'verification.json')
    require(binding['handover']['sha256'] == sha256(root/M28/'handover.json')
            and binding['policy_id'] == expansion.POLICY_ID and binding['source_run_id'] == RUN_ID
            and prior['status'] == 'PASS' and prior['binding_sha256'] == sha256(root/BINDING)
            and prior['real_row_parity']['identical'] is True
            and prior['real_row_parity']['training_executed'] is False,
            'M2.7 real-input binding does not bind the accepted M2.8-002 handover')
    return {'status': 'PASS', 'amendment_sha256': config['amendment']['sha256'],
            'baseline_replay_checks': baseline['checks'],
            'added_page_count': len(log), 'binding_sha256': prior['binding_sha256'],
            'previously_uncovered': {PREVIOUSLY_UNCOVERED: 'COVERED' if
                                     per_query[PREVIOUSLY_UNCOVERED]['captured_relevant'] > 0 else 'UNCOVERED'}}


def audit_payloads(root):
    """Replay what the local checkout holds; report what a Git pull cannot provide."""
    root = Path(root)
    run = root/'results/m2.8'/RUN_ID
    bundle = {row['path']: row for row in read_json(root/M28/'bundle_hashes.json')}
    present = [name for name in PARQUET if (run/'bundle'/name).is_file()]
    if len(present) != len(PARQUET):
        return {'parquet': 'UNAVAILABLE_AFTER_PULL', 'binding_replay': 'NOT_RUN',
                'full_array_replay': 'NOT_RUN'}
    for name in PARQUET:
        require(sha256(run/'bundle'/name) == bundle[name]['sha256'], f'Local Parquet hash mismatch: {name}')
    live = verify_binding(load_binding(root/BINDING), root)
    prior = read_json(root/M27/'verification.json')
    for key in ('status', 'bound_files', 'real_row_parity', 'synthetic_parity', 'handover_sha256'):
        require(live[key] == prior[key], f'M2.7 binding replay differs from m2.7-003: {key}')
    arrays = [root/'results/m2.8'/BASELINE_RUN/'remote'/c/'scores.npy' for c in expansion.CHANNELS]
    full = 'NOT_RUN_SCORE_MATRICES_UNAVAILABLE'
    if all(path.is_file() for path in arrays):
        from contextlib import redirect_stdout
        import io
        from scripts.run_m28_expansion import finalize
        with redirect_stdout(io.StringIO()):
            replayed = finalize(run, verify_only=True)
        require(replayed == read_json(root/M28/'handover.json'), 'Full-array replay differs from handover')
        full = 'PASS_FULL_ARRAY_REPLAY'
    return {'parquet': 'PASS_REHASHED', 'binding_replay': 'PASS_MATCHES_M2.7-003',
            'full_array_replay': full}


def audit(root):
    root = Path(root)
    revisions = {name: audit_revision_bytes(root/path) for name, path in
                 (('m2.6', M26), ('m2.8-001', M28_BASE), ('m2.8-002', M28), ('m2.7-003', M27))}
    freeze = read_json(root/'configs/m2.5/freeze.json')
    split = verify_frozen_splits(root, freeze)
    roles = split.pop('roles')
    handover = read_json(root/M28/'handover.json')
    require(handover['split_role_sha256'] == split['role_sha256'] and handover['query_count'] == 1142,
            'M2.8-002 split/count mismatch')
    coverage = replay_coverage(read_json(root/M28/'coverage_report.json'), roles)
    require(handover['uncovered_query_ids'] == coverage['overall']['uncovered_query_ids'] and
            math.isclose(handover['macro_candidate_recall'], coverage['overall']['macro_recall'],
                         abs_tol=1e-12, rel_tol=0), 'Handover coverage differs from replay')
    order = check_label_order(read_json(root/M28/'candidate_freeze.json'),
                              read_json(root/M28/'development_report.json'), handover)
    lineage = audit_a003_lineage(root)
    ready = coverage['status'] == 'PASS'
    return {
        'schema_version': 1, 'task_id': 'M2.10', 'owner': 'Thanh',
        'executed_by': 'Tấn Phát (Research Lead) via Claude Code; not the independent M2.10 owner',
        'audit_date': datetime.now().date().isoformat(),
        'status': ('AUDIT_REPLAY_PREPARED_READINESS_PENDING_REVIEW' if ready
                   else 'AUDIT_REPLAY_PREPARED_READINESS_BLOCKED'),
        'source_run_id': RUN_ID, 'baseline_run_id': BASELINE_RUN, 'revision_bytes': revisions,
        'frozen_splits': split, 'matched_config': audit_matched_config(root),
        'coverage_replay': coverage, 'label_order': order, 'a003_lineage': lineage,
        'payload_replay': audit_payloads(root), 'reload': audit_reload_evidence(root),
        'resolved_blockers': ['M2.8_ZERO_UNCOVERED_GATE_FAILED', 'M2.7_REAL_INPUT_BINDING_NOT_FROZEN'],
        'remaining_blockers': ['A003_INDEPENDENT_REVIEW_PENDING', 'M2.10_OWNER_CONFIRMATION_PENDING',
                               'NAMED_HUMAN_REVIEW_PENDING'],
        'independent_human_review': 'PENDING', 'test_ranking_metrics_computed': False,
        'scientific_claim': 'NONE',
    }


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
