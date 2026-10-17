import unittest

import numpy as np

from oracle_study.metrics import evaluate_scores, minmax, ndcg_at_k


class MetricsTest(unittest.TestCase):
    def test_hand_computed_binary_ndcg(self):
        expected = (1 / np.log2(3)) / (1 / np.log2(2))
        self.assertAlmostEqual(ndcg_at_k(np.array([0, 1]), 10), expected)

    def test_stable_tie_break_uses_page_id(self):
        metrics = evaluate_scores(
            np.array([0.5, 0.5]),
            np.array([0, 1]),
            np.array(["b", "a"]),
        )
        self.assertEqual(metrics.recall1, 1.0)

    def test_minmax_constant_becomes_zero(self):
        np.testing.assert_array_equal(minmax(np.array([3.0, 3.0])), np.zeros(2))


if __name__ == "__main__":
    unittest.main()

