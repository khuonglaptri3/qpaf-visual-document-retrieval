"""G3 applies the frozen three-seed thresholds in a fixed precedence and fails closed on bad evidence."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.decide_g3 import CORE, acceptance_state, collect_evidence, g3_outcome  # noqa: E402
from scripts.m36_gpu_worker import read, sha  # noqa: E402

RECORD = ROOT / 'evidence/revisions/m5.9-001'
CRITERIA = read(RECORD / 'criteria.json')


def evidence(**over):
    base = {'prerequisites': {name: 'ACCEPTED' for name in (*CORE, 'M5.5')},
            'coverage': {'query_count': 172, 'r7_query_count': 172, 'seeds_match_preregistration': True,
                         'wtl_totals_match': True, 'summary_pins_r7_review': True, 'r7_review_pass': True,
                         'r7_per_query_metric_max_abs_difference': 0.0, 'baselines_present': True},
            'quality': {'mean_delta': 0.076175, 'ci95_lower': 0.042928, 'top5_share': 0.3104,
                        'baseline_mean_delta': {'train_fitted_static': 0.004}},
            'operational': {'source_accepted': True, 'median_latency_ms': 2.426, 'latency_measured_queries': 1000,
                            'peak_cuda_gib': 0.0324, 'reload_max_abs_diff': 4.44e-16, 'finite_outputs': True}}
    for path, value in over.items():
        section, key = path.split('__')
        base[section] = {**base[section], key: value}
    return base


def decision(**over):
    return g3_outcome(evidence(**over), CRITERIA)['decision']


class G3OutcomeTests(unittest.TestCase):
    def test_go_only_when_every_item_passes(self):
        self.assertEqual(g3_outcome(evidence(), CRITERIA), {'decision': 'GO', 'checks': mock.ANY, 'reasons': []})

    def test_threshold_boundaries(self):
        self.assertEqual(decision(quality__mean_delta=0.01), 'GO')
        self.assertEqual(decision(quality__ci95_lower=0.0), 'NO-GO')
        self.assertEqual(decision(quality__baseline_mean_delta={'train_fitted_static': 0.0}), 'LIMITED-CLAIM')
        self.assertEqual(decision(quality__top5_share=0.90), 'LIMITED-CLAIM')
        self.assertEqual(decision(operational__median_latency_ms=10.0), 'GO')
        self.assertEqual(decision(operational__peak_cuda_gib=1.5), 'LIMITED-CLAIM')
        self.assertEqual(decision(operational__reload_max_abs_diff=2e-7), 'LIMITED-CLAIM')

    def test_every_co_strongest_baseline_must_be_beaten(self):
        result = g3_outcome(evidence(quality__baseline_mean_delta={'a': 0.01, 'b': -0.001}), CRITERIA)
        self.assertEqual((result['decision'], result['reasons']), ('LIMITED-CLAIM', ['BASELINE_NOT_BEATEN']))

    def test_short_latency_measurement_is_not_established_even_when_fast(self):
        result = g3_outcome(evidence(operational__latency_measured_queries=171), CRITERIA)
        self.assertEqual(result['checks']['latency_ms_max_inclusive'], 'NOT_ESTABLISHED')
        self.assertEqual((result['decision'], result['reasons']), ('LIMITED-CLAIM', ['LATENCY_GATE_NOT_ESTABLISHED']))
        self.assertEqual(decision(operational__source_accepted=False), 'LIMITED-CLAIM')

    def test_negative_quality_is_no_go_before_any_limit(self):
        result = g3_outcome(evidence(quality__mean_delta=0.005, operational__peak_cuda_gib=9.0), CRITERIA)
        self.assertEqual((result['decision'], result['reasons']), ('NO-GO', ['MEAN_DELTA_BELOW_MIN']))

    def test_unaccepted_core_review_blocks_strong_quality(self):
        for name in CORE:
            self.assertEqual(decision(**{f'prerequisites__{name}': 'REPORT_MISMATCH'}), 'BLOCKED')
        self.assertEqual(decision(**{'prerequisites__M5.5': 'MISSING'}), 'GO')

    def test_coverage_problems_block(self):
        for over in ({'coverage__query_count': 171}, {'coverage__seeds_match_preregistration': False},
                     {'coverage__wtl_totals_match': False}, {'coverage__summary_pins_r7_review': False},
                     {'coverage__r7_per_query_metric_max_abs_difference': 1e-9}, {'coverage__baselines_present': False}):
            self.assertEqual(decision(**over), 'BLOCKED')

    def test_missing_or_nonfinite_evidence_blocks(self):
        self.assertEqual(decision(quality__mean_delta=float('nan')), 'BLOCKED')
        self.assertEqual(decision(quality__baseline_mean_delta={}), 'BLOCKED')
        broken = evidence()
        del broken['operational']['reload_max_abs_diff']
        self.assertEqual(g3_outcome(broken, CRITERIA)['decision'], 'BLOCKED')


class CommittedEvidenceTests(unittest.TestCase):
    def test_pinned_record_reproduces(self):
        result = g3_outcome(collect_evidence(ROOT, read(RECORD / 'inputs.json'), CRITERIA), CRITERIA)
        stored = read(RECORD / 'decision.json')
        self.assertEqual((stored['decision'], stored['checks'], stored['reasons']),
                         (result['decision'], result['checks'], result['reasons']))
        self.assertEqual(stored['criteria_sha256'], sha(RECORD / 'criteria.json'))
        self.assertEqual(stored['inputs_sha256'], sha(RECORD / 'inputs.json'))

    def test_pin_drift_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'a.json').write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'pin drift: a.json'):
                collect_evidence(root, {'files': {'a.json': '0' * 64}}, CRITERIA)


class AcceptanceStateTests(unittest.TestCase):
    def test_acceptance_counts_only_for_the_pinned_report_task_and_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'summary.json').write_text('{}', encoding='utf-8')
            good = {'task_id': 'M5.7', 'decision': 'ACCEPTED_WITH_NEGATIVE_BASELINE_RESULT',
                    'summary_ref': 'summary.json', 'summary_sha256': sha(root / 'summary.json')}
            check = lambda c: acceptance_state(c, root, 'M5.7', CRITERIA['accepted_decisions']['M5.7'],  # noqa: E731
                                               'summary')
            self.assertEqual(check(good), 'ACCEPTED')
            self.assertEqual(check({**good, 'summary_sha256': '0' * 64}), 'REPORT_MISMATCH')
            self.assertEqual(check({**good, 'task_id': 'M5.8'}), 'WRONG_TASK')
            self.assertEqual(check({**good, 'decision': 'ACCEPTED'}), 'NOT_ACCEPTED:ACCEPTED')
            self.assertEqual(check(None), 'MISSING')


if __name__ == '__main__':
    unittest.main()
