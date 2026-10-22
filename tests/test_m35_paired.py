"""M3.5's paired query calculations and failure diagnostics."""
import unittest

from scripts.audit_m35_paired import METRICS, paired_statistics, rank_diagnostics


class PairedStatisticsTests(unittest.TestCase):
    def setUp(self):
        deltas = [0.5, 0.5, -0.5, 0.0]
        self.rows = [{'query_id': f'q{i}', **{f'delta_{m}': delta for m in METRICS}}
                     for i, delta in enumerate(deltas)]

    def test_query_bootstrap_wtl_and_concentration(self):
        first = paired_statistics(self.rows, resamples=10000, seed=20260820)
        second = paired_statistics(self.rows, resamples=10000, seed=20260820)
        self.assertEqual(first, second)
        for metric in METRICS:
            result = first[metric]
            self.assertEqual(result['mean_delta'], 0.125)
            self.assertEqual(result['wtl'], {'wins': 2, 'ties': 1, 'losses': 1})
            self.assertEqual(result['top_5pct_positive_gain_query_count'], 1)
            self.assertEqual(result['top_5pct_positive_gain_share'], 0.5)
            self.assertLessEqual(result['ci95'][0], 0.125)
            self.assertGreaterEqual(result['ci95'][1], 0.125)

    def test_duplicate_or_nonfinite_rows_fail_closed(self):
        for rows in (self.rows + [self.rows[0]],
                     [{**self.rows[0], 'delta_ndcg_at_10': float('nan')}] + self.rows[1:]):
            with self.assertRaises(ValueError):
                paired_statistics(rows)

    def test_rank_diagnostics_use_page_id_tie_break(self):
        prediction = {'scores': [0.5, 0.5, 0.1], 'page_ids': ['b', 'a', 'c']}
        result = rank_diagnostics(prediction, {'b': 1})
        self.assertEqual(result, {'top1_page_id': 'a', 'top1_relevant': False,
                                  'first_relevant_rank_at_10': 2})


if __name__ == '__main__':
    unittest.main()
