import unittest

from oracle_study.decision import final_decision, qpaf_confirmation_gate


def qpaf_summary(mean, fraction=0.25, ci=(0.01, 0.04), concentration=0.4):
    grid = {
        "mean_delta_ndcg10": mean,
        "delta_ci95": list(ci),
        "fraction_gain_ge_005": fraction,
        "fraction_gain_ge_001": fraction,
        "top_5pct_gain_share": concentration,
    }
    return {"grids": {"w7": dict(grid), "w66": dict(grid)}}


class DecisionTest(unittest.TestCase):
    def test_qpaf_requires_both_grids(self):
        discovery = qpaf_summary(0.04)
        confirmation = qpaf_summary(0.03)
        confirmation["grids"]["w66"]["mean_delta_ndcg10"] = 0.005
        self.assertNotEqual(qpaf_confirmation_gate(discovery, confirmation), "pass")

    def test_budget_wins_when_both_pass(self):
        qpaf_discovery = qpaf_summary(0.04)
        qpaf_confirmation = qpaf_summary(0.03)
        budget = {
            "full_minus_stage1": 0.03,
            "beneficial_fraction": 0.5,
            "non_beneficial_fraction": 0.5,
            "b_star_percent": 40,
            "control_gap_at_b_star": 0.02,
            "retention_ci95": [0.99, 1.0],
        }
        result = final_decision(
            qpaf_discovery,
            qpaf_confirmation,
            budget,
            budget,
        )
        self.assertEqual(result["recommended_direction"], "budget_aware_adaptive_heaven")


if __name__ == "__main__":
    unittest.main()
