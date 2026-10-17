import unittest

import numpy as np
import pandas as pd

from oracle_study.metrics import evaluate_scores
from oracle_study.qpaf import _single_item_ndcg, run_qpaf_oracle


class QpafOracleTest(unittest.TestCase):
    def test_fast_single_item_update_matches_full_reranking(self):
        rng = np.random.default_rng(20260820)
        for length in [3, 10, 17]:
            for _ in range(30):
                scores = rng.normal(size=length)
                relevance = rng.integers(0, 3, size=length).astype(float)
                page_ids = np.asarray([f"p{index:02d}" for index in range(length)])
                current = evaluate_scores(scores, relevance, page_ids)
                candidate = int(rng.integers(0, length))
                new_score = float(rng.normal())
                expected_scores = scores.copy()
                expected_scores[candidate] = new_score
                expected = evaluate_scores(expected_scores, relevance, page_ids).ndcg10
                actual = _single_item_ndcg(
                    scores,
                    relevance,
                    page_ids,
                    candidate,
                    new_score,
                    current.ndcg10,
                )
                self.assertAlmostEqual(actual, expected, places=12)
    def test_candidate_oracle_never_worse_than_query_oracle(self):
        frame = pd.DataFrame(
            [
                {"dataset": "d", "query_id": "q", "page_id": "a", "relevance": 1, "bm25_score": 1.0, "dense_score": 0.0, "stage1_score": 0.2, "visual_score": 0.0, "branch_ranks": "{}", "source": "s"},
                {"dataset": "d", "query_id": "q", "page_id": "b", "relevance": 1, "bm25_score": 0.0, "dense_score": 0.0, "stage1_score": 0.2, "visual_score": 1.0, "branch_ranks": "{}", "source": "s"},
                {"dataset": "d", "query_id": "q", "page_id": "c", "relevance": 0, "bm25_score": 0.9, "dense_score": 0.9, "stage1_score": 0.8, "visual_score": 0.9, "branch_ranks": "{}", "source": "s"},
            ]
        )
        rows, summary, _ = run_qpaf_oracle(frame, grids=("w7",), n_bootstrap=100)
        self.assertGreaterEqual(rows[0]["qarf_metrics"]["ndcg10"], rows[0]["global_metrics"]["ndcg10"])
        self.assertGreaterEqual(rows[0]["qpaf_metrics"]["ndcg10"], rows[0]["qarf_metrics"]["ndcg10"])
        self.assertGreaterEqual(summary["grids"]["w7"]["mean_delta_ndcg10"], 0.0)

    def test_global_profile_is_shared_and_all_three_levels_are_monotonic(self):
        rows = []
        for query_id, preferred in [("q1", "bm25_score"), ("q2", "visual_score")]:
            for page_id, relevance in [("relevant", 1), ("distractor", 0)]:
                row = {
                    "dataset": "d",
                    "query_id": query_id,
                    "page_id": page_id,
                    "relevance": relevance,
                    "bm25_score": 0.0,
                    "dense_score": 0.5,
                    "stage1_score": 0.5,
                    "visual_score": 0.0,
                    "branch_ranks": "{}",
                    "source": "s",
                }
                row[preferred] = 1.0 if relevance else 0.0
                other = "visual_score" if preferred == "bm25_score" else "bm25_score"
                row[other] = 0.0 if relevance else 1.0
                rows.append(row)
        output, summary, _ = run_qpaf_oracle(pd.DataFrame(rows), grids=("w7",), n_bootstrap=100)
        self.assertEqual(output[0]["global_profile"], output[1]["global_profile"])
        for row in output:
            self.assertGreaterEqual(row["delta_qarf_vs_global"], -1e-12)
            self.assertGreaterEqual(row["delta_qpaf_vs_qarf"], -1e-12)
        self.assertIn("qarf_vs_global", summary["grids"]["w7"])
        self.assertIn("qpaf_vs_qarf", summary["grids"]["w7"])


if __name__ == "__main__":
    unittest.main()
