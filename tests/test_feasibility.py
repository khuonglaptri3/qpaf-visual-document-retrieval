import unittest

from oracle_study.feasibility import assess_short_pilot, feasibility_markdown


class FeasibilityTest(unittest.TestCase):
    def test_strong_and_weak_directions_are_reported_separately(self):
        strong = {
            "mean_delta_ndcg10": 0.031,
            "delta_ci95": [0.01, 0.05],
            "fraction_gain_ge_001": 0.4,
            "fraction_gain_ge_003": 0.2,
            "fraction_gain_ge_005": 0.1,
            "top_5pct_gain_share": 0.5,
        }
        weak = {
            "mean_delta_ndcg10": 0.004,
            "delta_ci95": [-0.001, 0.01],
            "fraction_gain_ge_001": 0.04,
            "fraction_gain_ge_003": 0.01,
            "fraction_gain_ge_005": 0.0,
            "top_5pct_gain_share": 0.95,
        }
        report = assess_short_pilot(
            {"grids": {"w7": {"queries": 309, "qarf_vs_global": strong, "qpaf_vs_qarf": weak}}},
            {"final_coverage": 0.97},
        )
        self.assertEqual(report["qarf_vs_global"]["status"], "strong_signal_for_full_discovery")
        self.assertEqual(report["qpaf_vs_qarf"]["status"], "no_clear_signal_on_finance_en_pilot")
        self.assertIn("Global -> QARF", feasibility_markdown(report))

    def test_low_coverage_invalidates_both_directions(self):
        gain = {
            "mean_delta_ndcg10": 0.04,
            "delta_ci95": [0.02, 0.06],
            "fraction_gain_ge_001": 0.5,
            "fraction_gain_ge_003": 0.2,
            "fraction_gain_ge_005": 0.1,
            "top_5pct_gain_share": 0.4,
        }
        report = assess_short_pilot(
            {"grids": {"w7": {"queries": 10, "qarf_vs_global": gain, "qpaf_vs_qarf": gain}}},
            {"final_coverage": 0.90},
        )
        self.assertEqual(report["qarf_vs_global"]["status"], "invalid_candidate_coverage")
        self.assertEqual(report["qpaf_vs_qarf"]["status"], "invalid_candidate_coverage")


if __name__ == "__main__":
    unittest.main()
