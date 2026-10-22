"""M3.7 G2 learned-viability decision from hash-pinned M3.3/M3.5/M3.6 evidence.

Restore the M3.1 development qrels and validation IDs first: the M3.5 paired
comparison is replayed before any decision. Without --output this only prints.
It never reads test qrels, trains, or authorizes a run.
"""
import argparse
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.m36_gpu_worker import read, sha, write_new  # noqa: E402

DECISIONS = ('GO', 'PARTIAL-INVESTIGATE', 'NO-GO-PIVOT', 'BLOCKED')
M4_BRANCH = {'GO': 'continue_qpaf', 'PARTIAL-INVESTIGATE': 'revise_once',
             'NO-GO-PIVOT': 'negative_qpaf_result', 'BLOCKED': None}
REVISIONS = ROOT / 'evidence/revisions'
FILES = {
    'm3_3_acceptance': 'evidence/revisions/m3.3-001/owner_confirmation.json',
    'm3_5_comparison': 'evidence/revisions/m3.5-001/comparison.json',
    'm3_5_acceptance': 'evidence/revisions/m3.5-001/owner_confirmation.json',
    'm3_6_integrity': 'evidence/revisions/m3.6-001/integrity_review.json',
    'm3_6_resources': 'evidence/revisions/m3.6-004/technical_review.json',
    'm3_6_memory': 'evidence/revisions/m3.6-005/technical_review.json',
    'm3_6_owner': 'evidence/revisions/m3.6-005/owner_confirmation.json',
    'm3_6_qa': 'evidence/revisions/m3.6-005/qa_confirmation.json',
}
ACCEPTED = {'M3.3': 'ACCEPTED', 'M3.5': 'ACCEPTED', 'M3.6_technical': 'PASS',
            'M3.6_owner': 'ACCEPTED', 'M3.6_qa': 'ACCEPTED'}
NUMERIC = {'pairing': ('query_count', 'wtl_total', 'metric_replay_max_abs_difference'),
           'quality': ('mean_delta', 'ci95_lower', 'top5_share'),
           'operational': ('median_latency_ms', 'peak_cuda_gib', 'reload_max_abs_diff')}
FLAGS = {'pairing': ('test_labels_opened', 'm35_replay_equal'), 'operational': ('finite_outputs',)}


def _blocked(checks, reasons):
    return {'decision': 'BLOCKED', 'm4_branch': None, 'checks': checks, 'reasons': reasons}


def g2_outcome(evidence, criteria):
    checks, reasons = {}, []
    for kinds, valid in ((NUMERIC, lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
                          and math.isfinite(v)),
                         (FLAGS, lambda v: isinstance(v, bool))):
        for section, keys in kinds.items():
            for key in keys:
                if not valid(evidence.get(section, {}).get(key)):
                    reasons.append(f'EVIDENCE_MISSING_OR_INVALID:{section}.{key}')
    prerequisites = evidence.get('prerequisites', {})
    for name, required in ACCEPTED.items():
        state = 'PASS' if prerequisites.get(name) == required else 'BLOCKED'
        checks[f'prerequisite_{name}'] = state
        if state == 'BLOCKED':
            reasons.append(f'PREREQUISITE_NOT_ACCEPTED:{name}')
    if reasons:
        return _blocked(checks, reasons)
    pairing, quality, ops = evidence['pairing'], evidence['quality'], evidence['operational']
    pairing_ok = (pairing['query_count'] == pairing['wtl_total'] and not pairing['test_labels_opened'] and
                  pairing['metric_replay_max_abs_difference'] == 0 and pairing['m35_replay_equal'])
    checks['pairing'] = 'PASS' if pairing_ok else 'BLOCKED'
    if not pairing_ok:
        return _blocked(checks, ['PAIRING_OR_REPLAY_INVALID'])
    for name, ok, reason in (
            ('mean_delta_min_inclusive', quality['mean_delta'] >= criteria['mean_delta_min_inclusive'],
             'MEAN_DELTA_BELOW_MIN'),
            ('ci95_lower_min_exclusive', quality['ci95_lower'] > criteria['ci95_lower_min_exclusive'],
             'CI95_LOWER_NOT_ABOVE_MIN'),
            ('top5_share_max_exclusive', quality['top5_share'] < criteria['top5_share_max_exclusive'],
             'GAIN_CONCENTRATION_AT_OR_ABOVE_MAX'),
            ('latency_ms_max_inclusive', ops['median_latency_ms'] <= criteria['latency_ms_max_inclusive'],
             'LATENCY_ABOVE_MAX'),
            ('cuda_gib_max_exclusive', ops['peak_cuda_gib'] < criteria['cuda_gib_max_exclusive'],
             'CUDA_AT_OR_ABOVE_MAX'),
            ('reload_abs_tolerance', ops['reload_max_abs_diff'] <= criteria['reload_abs_tolerance'],
             'RELOAD_ABOVE_TOLERANCE'),
            ('finite_outputs', ops['finite_outputs'], 'NONFINITE_OUTPUTS')):
        checks[name] = 'PASS' if ok else 'FAIL'
        if not ok:
            reasons.append(reason)
    if checks['mean_delta_min_inclusive'] == 'FAIL' or checks['ci95_lower_min_exclusive'] == 'FAIL':
        decision = 'NO-GO-PIVOT'
    elif reasons:
        decision = 'PARTIAL-INVESTIGATE'
    else:
        decision = 'GO'
    return {'decision': decision, 'm4_branch': M4_BRANCH[decision], 'checks': checks, 'reasons': reasons}


def acceptance_state(confirmation, root, task_id):
    """An acceptance counts only for its task and the exact report bytes it names."""
    if confirmation is None:
        return 'MISSING'
    if confirmation.get('task_id') != task_id:
        return 'WRONG_TASK'
    if confirmation.get('decision') != 'ACCEPTED':
        return confirmation.get('decision') or 'MISSING'
    report = root / confirmation.get('technical_report_ref', '')
    if not report.is_file() or sha(report) != confirmation.get('technical_report_sha256'):
        return 'REPORT_MISMATCH'
    return 'ACCEPTED'


def replay_m35(comparison):
    from scripts.audit_m35_paired import audit
    report, _ = audit()
    return report['metrics'] == comparison['metrics']


def collect_evidence(root, inputs):
    pins = inputs['files']
    for rel, expected in pins.items():
        if not (root / rel).is_file() or sha(root / rel) != expected:
            raise ValueError('pin drift: ' + rel)
    loaded = {}
    for name, rel in FILES.items():
        if (root / rel).is_file():
            if rel not in pins:
                raise ValueError('unpinned evidence: ' + rel)
            loaded[name] = read(root / rel)
    decision = lambda name, task: acceptance_state(loaded.get(name), root, task)  # noqa: E731
    comparison = loaded.get('m3_5_comparison', {})
    ndcg = comparison.get('metrics', {}).get('ndcg_at_10', {})
    resources = loaded.get('m3_6_resources', {}).get('methods', {}).get('QPAF', {})
    integrity = loaded.get('m3_6_integrity', {})
    reload_run = integrity.get('runs', {}).get('QPAF', {}).get('fresh_checkpoint_reload', {})
    return {
        'prerequisites': {'M3.3': decision('m3_3_acceptance', 'M3.3'), 'M3.5': decision('m3_5_acceptance', 'M3.5'),
                          'M3.6_technical': loaded.get('m3_6_memory', {}).get('technical_verdict', 'MISSING'),
                          'M3.6_owner': decision('m3_6_owner', 'M3.6'), 'M3.6_qa': decision('m3_6_qa', 'M3.6')},
        'pairing': {'query_count': comparison.get('validation_query_count'),
                    'wtl_total': sum(ndcg['wtl'].values()) if 'wtl' in ndcg else None,
                    'test_labels_opened': comparison.get('test_labels_opened'),
                    'metric_replay_max_abs_difference': comparison.get('metric_replay_max_abs_difference'),
                    'm35_replay_equal': replay_m35(comparison) if comparison else None},
        'quality': {'mean_delta': ndcg.get('mean_delta'),
                    'ci95_lower': ndcg['ci95'][0] if 'ci95' in ndcg else None,
                    'top5_share': ndcg.get('top_5pct_positive_gain_share')},
        'operational': {'median_latency_ms': resources.get('median_online_ms'),
                        'peak_cuda_gib': resources.get('peak_cuda_allocated_gib'),
                        'reload_max_abs_diff': reload_run.get('score_max_abs_difference'),
                        'finite_outputs': integrity.get('integrity_verdict') == 'PASS' if integrity else None},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--expected-inputs-sha256', required=True)
    parser.add_argument('--criteria', type=Path, required=True)
    parser.add_argument('--expected-criteria-sha256', required=True)
    parser.add_argument('--output', type=Path, help='new create-once decision.json')
    args = parser.parse_args()
    if sha(args.inputs) != args.expected_inputs_sha256 or sha(args.criteria) != args.expected_criteria_sha256:
        raise ValueError('inputs or criteria SHA-256 pin differs')
    if args.output is not None and args.output.exists():
        raise ValueError('output already exists')
    inputs, criteria = read(args.inputs), read(args.criteria)
    evidence = collect_evidence(ROOT, inputs)
    result = g2_outcome(evidence, criteria)
    record = {'schema_version': 1, 'task_id': 'M3.7', 'gate': 'G2_LEARNED_VIABILITY',
              'question': 'Does learned QPAF outperform matched learned QARF?', **result,
              'evidence': evidence, 'run_ids': inputs.get('run_ids'),
              'criteria_sha256': args.expected_criteria_sha256, 'inputs_sha256': args.expected_inputs_sha256,
              'owner_confirmation': 'PENDING_RESEARCH_LEAD', 'seed': 20260820, 'multi_seed_claim': False,
              'baseline_comparison_done': False, 'test_labels_opened': False, 'authorizes_execution': False}
    if args.output is None:
        import json
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        write_new(args.output, record)
        print(f"G2 {result['decision']}: {args.output}")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, FileNotFoundError) as exc:
        print(f'G2 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
