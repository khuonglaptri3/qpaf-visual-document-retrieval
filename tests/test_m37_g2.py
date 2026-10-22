"""G2 applies the frozen thresholds in a fixed precedence and fails closed on bad evidence."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.decide_g2 import collect_evidence, g2_outcome  # noqa: E402

CRITERIA = {'mean_delta_min_inclusive': 0.01, 'ci95_lower_min_exclusive': 0.0,
            'top5_share_max_exclusive': 0.90, 'latency_ms_max_inclusive': 10.0,
            'cuda_gib_max_exclusive': 1.5, 'reload_abs_tolerance': 1e-7}


def evidence(**over):
    base = {'prerequisites': {'M3.3': 'ACCEPTED', 'M3.5': 'ACCEPTED', 'M3.6_technical': 'PASS',
                              'M3.6_owner': 'ACCEPTED', 'M3.6_qa': 'ACCEPTED'},
            'pairing': {'query_count': 171, 'wtl_total': 171, 'test_labels_opened': False,
                        'metric_replay_max_abs_difference': 0.0, 'm35_replay_equal': True},
            'quality': {'mean_delta': 0.114132, 'ci95_lower': 0.077501, 'top5_share': 0.2809},
            'operational': {'median_latency_ms': 2.447, 'peak_cuda_gib': 0.0325,
                            'reload_max_abs_diff': 0.0, 'finite_outputs': True}}
    for path, value in over.items():
        section, key = path.split('__')
        base[section] = {**base[section], key: value}
    return base


class G2OutcomeTests(unittest.TestCase):
    def test_go_with_current_evidence_shape(self):
        result = g2_outcome(evidence(), CRITERIA)
        self.assertEqual((result['decision'], result['m4_branch']), ('GO', 'continue_qpaf'))

    def test_threshold_boundaries(self):
        self.assertEqual(g2_outcome(evidence(quality__mean_delta=0.01), CRITERIA)['decision'], 'GO')
        self.assertEqual(g2_outcome(evidence(quality__ci95_lower=0.0), CRITERIA)['decision'], 'NO-GO-PIVOT')
        self.assertEqual(g2_outcome(evidence(quality__top5_share=0.90), CRITERIA)['decision'],
                         'PARTIAL-INVESTIGATE')
        self.assertEqual(g2_outcome(evidence(operational__median_latency_ms=10.0), CRITERIA)['decision'], 'GO')
        self.assertEqual(g2_outcome(evidence(operational__peak_cuda_gib=1.5), CRITERIA)['decision'],
                         'PARTIAL-INVESTIGATE')
        self.assertEqual(g2_outcome(evidence(operational__reload_max_abs_diff=2e-7), CRITERIA)['decision'],
                         'PARTIAL-INVESTIGATE')

    def test_negative_quality_is_no_go_even_if_operational_fails(self):
        result = g2_outcome(evidence(quality__mean_delta=0.005, operational__peak_cuda_gib=9.0), CRITERIA)
        self.assertEqual((result['decision'], result['m4_branch']), ('NO-GO-PIVOT', 'negative_qpaf_result'))

    def test_unaccepted_prerequisite_blocks_strong_quality(self):
        for key, value in (('M3.6_qa', 'MISSING'), ('M3.6_technical', 'BLOCKED'), ('M3.5', 'PENDING')):
            result = g2_outcome(evidence(**{f'prerequisites__{key}': value}), CRITERIA)
            self.assertEqual((result['decision'], result['m4_branch']), ('BLOCKED', None))

    def test_pairing_problems_block(self):
        for over in ({'pairing__wtl_total': 170}, {'pairing__test_labels_opened': True},
                     {'pairing__metric_replay_max_abs_difference': 1e-9}, {'pairing__m35_replay_equal': False}):
            self.assertEqual(g2_outcome(evidence(**over), CRITERIA)['decision'], 'BLOCKED')

    def test_missing_or_nonfinite_evidence_blocks(self):
        self.assertEqual(g2_outcome(evidence(quality__mean_delta=float('nan')), CRITERIA)['decision'], 'BLOCKED')
        broken = evidence()
        del broken['operational']['peak_cuda_gib']
        self.assertEqual(g2_outcome(broken, CRITERIA)['decision'], 'BLOCKED')


class CollectEvidenceTests(unittest.TestCase):
    def test_pin_drift_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'a.json').write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'pin drift: a.json'):
                collect_evidence(root, {'files': {'a.json': '0' * 64}})


if __name__ == '__main__':
    unittest.main()
