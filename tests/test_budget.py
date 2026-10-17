import unittest

import pandas as pd

from oracle_study.budget import run_budget_oracle


class BudgetOracleTest(unittest.TestCase):
    def test_endpoints_match_stage1_and_full(self):
        rows = []
        for index, (cheap, full) in enumerate([(0.2, 0.8), (0.3, 0.7), (0.6, 0.6), (0.8, 0.7)]):
            rows.append(
                {
                    "dataset": "d",
                    "query_id": f"q{index}",
                    "source": "s",
                    "relevant_count": 1,
                    "ndcg_stage1": cheap,
                    "ndcg_full": full,
                    "recall_stage1": cheap,
                    "recall_full": full,
                    "stage1_margin": 0.1 * index,
                    "stage2_ms": 10.0,
                    "stage2_flops": 100.0,
                }
            )
        _, curve, _ = run_budget_oracle(pd.DataFrame(rows), random_repeats=5, n_bootstrap=100)
        at_zero = curve.loc[curve["budget_percent"] == 0].iloc[0]
        at_full = curve.loc[curve["budget_percent"] == 100].iloc[0]
        self.assertAlmostEqual(at_zero["oracle_ndcg10"], at_zero["cheap_ndcg10"])
        self.assertAlmostEqual(at_full["oracle_ndcg10"], at_full["full_ndcg10"])


if __name__ == "__main__":
    unittest.main()

