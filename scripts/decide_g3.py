"""M5.9 G3 robustness decision from hash-pinned three-seed R7/R8 evidence.

Reads only committed review records and the accepted M5.7 summary; it never
reads test qrels, trains, evaluates or authorizes a run. Without --output this
only prints.
"""
import argparse
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.m36_gpu_worker import read, sha, write_new  # noqa: E402

DECISIONS = ('GO', 'LIMITED-CLAIM', 'NO-GO', 'BLOCKED')
REV = 'evidence/revisions/'
# name -> (confirmation file, task_id it must carry, field naming the accepted report)
ACCEPTANCES = {
    'M5.1': (REV + 'm5.1-001/owner_confirmation.json', 'M5.1', 'preregistration'),
    'M5.2': ('results/m5.2/verification/owner_confirmation.json', 'M5.2', 'receipt'),
    'M5.3_QARF': (REV + 'm5.3-r01/owner_confirmation.json', 'M5.3-QARF-independent-review', 'technical_report'),
    'M5.3_QPAF': (REV + 'm5.3-r02/owner_confirmation.json', 'M5.3-QPAF-technical-review', 'technical_report'),
    'M5.4_QARF': (REV + 'm5.4-r01/owner_confirmation.json', 'M5.4-QARF-independent-review', 'technical_report'),
    'M5.4_QPAF': (REV + 'm5.4-r02/owner_confirmation.json', 'M5.4-QPAF-technical-review', 'technical_report'),
    'R7': (REV + 'r7-r01/owner_confirmation.json', 'R7-TEST-172-independent-review', 'technical_report'),
    'M5.7': (REV + 'm5.7-001/owner_confirmation.json', 'M5.7', 'summary'),
    'M5.5': (REV + 'm5.5-r01/owner_confirmation.json', 'M5.5', None),
}
CORE = ('M5.1', 'M5.2', 'M5.3_QARF', 'M5.3_QPAF', 'M5.4_QARF', 'M5.4_QPAF', 'R7', 'M5.7')
FILES = {
    'g2a': REV + 'm4.7-001/g2a_freeze.json',
    'preregistration': REV + 'm5.1-001/preregistration.json',
    'summary': REV + 'm5.7-001/summary.json',
    'r7_review': REV + 'r7-r01/verification.json',
    'm55_review': REV + 'm5.5-r01/validation.json',
    'reload_m53_qarf': REV + 'm5.3-r01/validation.json',
    'reload_m53_qpaf': REV + 'm5.3-r02/validation.json',
    'reload_m54_qarf': REV + 'm5.4-r01/validation.json',
    'reload_m54_qpaf': REV + 'm5.4-r02/validation.json',
    'reload_seed1_qpaf': REV + 'm3.6-001/integrity_review.json',
}
POST_RUN = tuple(REV + f'{task}/post_run_verification.json'
                 for task in ('m3.2-001', 'm3.4-001', 'm5.3-001', 'm5.3-002', 'm5.4-001', 'm5.4-002'))
NUMERIC = {'coverage': ('query_count', 'r7_query_count', 'r7_per_query_metric_max_abs_difference'),
           'quality': ('mean_delta', 'ci95_lower', 'top5_share'),
           'operational': ('reload_max_abs_diff',)}
FLAGS = {'coverage': ('seeds_match_preregistration', 'wtl_totals_match', 'summary_pins_r7_review',
                      'r7_review_pass', 'baselines_present'),
         'operational': ('finite_outputs',)}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _blocked(checks, reasons):
    return {'decision': 'BLOCKED', 'checks': checks, 'reasons': reasons}


def g3_outcome(evidence, criteria):
    checks, reasons = {}, []
    for kinds, valid in ((NUMERIC, _number), (FLAGS, lambda v: isinstance(v, bool))):
        for section, keys in kinds.items():
            for key in keys:
                if not valid(evidence.get(section, {}).get(key)):
                    reasons.append(f'EVIDENCE_MISSING_OR_INVALID:{section}.{key}')
    baselines = evidence.get('quality', {}).get('baseline_mean_delta', {})
    if not baselines or not all(_number(v) for v in baselines.values()):
        reasons.append('EVIDENCE_MISSING_OR_INVALID:quality.baseline_mean_delta')
    prerequisites = evidence.get('prerequisites', {})
    for name in CORE:
        state = 'PASS' if prerequisites.get(name) == 'ACCEPTED' else 'BLOCKED'
        checks[f'prerequisite_{name}'] = state
        if state == 'BLOCKED':
            reasons.append(f'PREREQUISITE_NOT_ACCEPTED:{name}')
    if reasons:
        return _blocked(checks, reasons)
    coverage, quality, ops = evidence['coverage'], evidence['quality'], evidence['operational']
    coverage_ok = (coverage['query_count'] == coverage['r7_query_count'] == criteria['query_count'] and
                   coverage['r7_per_query_metric_max_abs_difference'] == 0 and
                   all(coverage[key] for key in FLAGS['coverage']))
    checks['coverage'] = 'PASS' if coverage_ok else 'BLOCKED'
    if not coverage_ok:
        return _blocked(checks, ['SEED_PAIRING_OR_COVERAGE_INVALID'])

    def gate(name, ok, reason):
        checks[name] = 'PASS' if ok else 'FAIL'
        if not ok:
            reasons.append(reason)

    gate('mean_delta_min_inclusive', quality['mean_delta'] >= criteria['mean_delta_min_inclusive'],
         'MEAN_DELTA_BELOW_MIN')
    gate('ci95_lower_min_exclusive', quality['ci95_lower'] > criteria['ci95_lower_min_exclusive'],
         'CI95_LOWER_NOT_ABOVE_MIN')
    if reasons:
        return {'decision': 'NO-GO', 'checks': checks, 'reasons': reasons}
    gate('strongest_baselines_beaten',
         all(v > criteria['baseline_mean_delta_min_exclusive'] for v in baselines.values()), 'BASELINE_NOT_BEATEN')
    gate('top5_share_max_exclusive', quality['top5_share'] < criteria['top5_share_max_exclusive'],
         'GAIN_CONCENTRATION_AT_OR_ABOVE_MAX')
    # A latency/memory value only counts when the accepted M5.5 measurement meets the metric policy.
    latency, cuda, measured = ops.get('median_latency_ms'), ops.get('peak_cuda_gib'), ops.get('latency_measured_queries')
    if not ops.get('source_accepted') or not _number(latency) or not _number(measured) or \
            measured < criteria['latency_min_measured_queries']:
        checks['latency_ms_max_inclusive'] = 'NOT_ESTABLISHED'
        reasons.append('LATENCY_GATE_NOT_ESTABLISHED')
    else:
        gate('latency_ms_max_inclusive', latency <= criteria['latency_ms_max_inclusive'], 'LATENCY_ABOVE_MAX')
    if not ops.get('source_accepted') or not _number(cuda):
        checks['cuda_gib_max_exclusive'] = 'NOT_ESTABLISHED'
        reasons.append('CUDA_GATE_NOT_ESTABLISHED')
    else:
        gate('cuda_gib_max_exclusive', cuda < criteria['cuda_gib_max_exclusive'], 'CUDA_AT_OR_ABOVE_MAX')
    gate('reload_abs_tolerance', ops['reload_max_abs_diff'] <= criteria['reload_abs_tolerance'],
         'RELOAD_ABOVE_TOLERANCE')
    gate('finite_outputs', ops['finite_outputs'], 'NONFINITE_OUTPUTS')
    return {'decision': 'LIMITED-CLAIM' if reasons else 'GO', 'checks': checks, 'reasons': reasons}


def acceptance_state(confirmation, root, task_id, accepted, report_field):
    """An acceptance counts only for its task, an accepted decision and the exact report bytes it names."""
    if confirmation is None:
        return 'MISSING'
    if confirmation.get('task_id') != task_id:
        return 'WRONG_TASK'
    if confirmation.get('decision') not in accepted:
        return f"NOT_ACCEPTED:{confirmation.get('decision')}"
    if report_field is not None:
        report = root / confirmation.get(f'{report_field}_ref', '')
        if not report.is_file() or sha(report) != confirmation.get(f'{report_field}_sha256'):
            return 'REPORT_MISMATCH'
    return 'ACCEPTED'


def _finite_post_run(record):
    finite = [c for c in record.get('checks', []) if 'finite' in c.get('check', '')]
    return record.get('verdict') == 'ALL CHECKS PASS' and bool(finite) and all(c['status'] == 'PASS' for c in finite)


def collect_evidence(root, inputs, criteria):
    pins = inputs['files']
    for rel, expected in pins.items():
        if not (root / rel).is_file() or sha(root / rel) != expected:
            raise ValueError('pin drift: ' + rel)
    needed = [path for path, _, _ in ACCEPTANCES.values()] + list(FILES.values()) + list(POST_RUN)
    for rel in needed:
        if (root / rel).is_file() and rel not in pins:
            raise ValueError('unpinned evidence: ' + rel)
    load = lambda rel: read(root / rel) if (root / rel).is_file() else None  # noqa: E731
    loaded = {name: load(rel) or {} for name, rel in FILES.items()}
    prerequisites = {name: acceptance_state(load(path), root, task, criteria['accepted_decisions'][name], field)
                     for name, (path, task, field) in ACCEPTANCES.items()}
    summary, r7, g2a, prereg = loaded['summary'], loaded['r7_review'], loaded['g2a'], loaded['preregistration']
    contrasts = summary.get('contrasts', {})
    ndcg = lambda name: contrasts.get(name, {}).get('metrics', {}).get('ndcg_at_10', {})  # noqa: E731
    qarf = ndcg('QPAF_minus_matched_QARF')
    co_strongest = g2a.get('baselines', {}).get('co_strongest', [])
    baseline_delta = {name: ndcg(f'QPAF_minus_{name}').get('mean_delta') for name in co_strongest}
    test_plan = prereg.get('test_plan', {})
    wtl_totals = [sum(ndcg(name)['wtl'].values()) for name in contrasts if 'wtl' in ndcg(name)]
    reloads = [v['max_abs_difference'] for k, v in r7.get('parity', {}).items() if k.startswith(('qarf_', 'qpaf_'))]
    for name in ('reload_m53_qarf', 'reload_m54_qarf'):
        reloads.append(loaded[name].get('fresh_checkpoint_reload', {}).get('score_max_abs_difference'))
    for name in ('reload_m53_qpaf', 'reload_m54_qpaf'):
        reloads.append(loaded[name].get('checkpoint_reload', {}).get('score_max_abs_difference'))
    reloads.append(loaded['reload_seed1_qpaf'].get('runs', {}).get('QPAF', {})
                   .get('fresh_checkpoint_reload', {}).get('score_max_abs_difference'))
    gpu = loaded['m55_review'].get('gpu', {})
    post_runs = [load(rel) for rel in POST_RUN]
    return {
        'prerequisites': prerequisites,
        'coverage': {
            'query_count': summary.get('query_count'),
            'r7_query_count': r7.get('query_count'),
            'seeds_match_preregistration': (summary.get('seeds') == test_plan.get('qpaf_seeds') ==
                                            test_plan.get('qarf_seeds') and len(summary.get('seeds', [])) == 3),
            'wtl_totals_match': bool(wtl_totals) and all(t == summary.get('query_count') for t in wtl_totals),
            'summary_pins_r7_review': (summary.get('r7_independent_audit_sha256') ==
                                       (sha(root / FILES['r7_review']) if r7 else None) and
                                       summary.get('r7_manifest_sha256') == r7.get('manifest_sha256')),
            'r7_review_pass': str(r7.get('status', '')).startswith('PASS'),
            'r7_per_query_metric_max_abs_difference': r7.get('per_query_metric_max_abs_difference'),
            'baselines_present': bool(co_strongest) and all(f'QPAF_minus_{n}' in contrasts for n in co_strongest),
        },
        'quality': {'mean_delta': qarf.get('mean_delta'),
                    'ci95_lower': qarf['ci95'][0] if 'ci95' in qarf else None,
                    'top5_share': qarf.get('top_5pct_positive_gain_share'),
                    'baseline_mean_delta': baseline_delta},
        'operational': {'source_accepted': prerequisites['M5.5'] == 'ACCEPTED',
                        'median_latency_ms': gpu.get('qpaf_online_median_ms_per_query'),
                        'latency_measured_queries': gpu.get('distinct_validation_queries'),
                        'peak_cuda_gib': gpu.get('qpaf_peak_cuda_allocated_gib'),
                        'reload_max_abs_diff': max(reloads) if reloads and all(map(_number, reloads)) else None,
                        'finite_outputs': all(r is not None and _finite_post_run(r) for r in post_runs)},
    }


def claim_limits(result, criteria):
    return [criteria['claim_limits'][reason] for reason in result['reasons'] if reason in criteria['claim_limits']]


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
    evidence = collect_evidence(ROOT, inputs, criteria)
    result = g3_outcome(evidence, criteria)
    record = {'schema_version': 1, 'task_id': 'M5.9', 'gate': 'G3_ROBUSTNESS',
              'question': 'Is the result stable across seeds and checks?', **result,
              'claim_limits': claim_limits(result, criteria), 'evidence': evidence,
              'run_ids': inputs.get('run_ids'), 'criteria_sha256': args.expected_criteria_sha256,
              'inputs_sha256': args.expected_inputs_sha256, 'owner_confirmation': 'PENDING_RESEARCH_LEAD',
              'seeds': [20260820, 20260821, 20260822], 'held_out': 'ViDoSeek TEST-172',
              'external_generalization_claimed': False, 'test_labels_read_by_this_record': False,
              'authorizes_execution': False}
    if args.output is None:
        import json
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        write_new(args.output, record)
        print(f"G3 {result['decision']}: {args.output}")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, FileNotFoundError) as exc:
        print(f'G3 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
