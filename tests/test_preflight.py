import unittest

import pandas as pd

from oracle_study.cache import build_cache
from oracle_study.preflight import run_preflight


class PreflightTest(unittest.TestCase):
    def test_content_hash_is_order_independent(self):
        rows = []
        for index in range(6):
            rows.append(
                {
                    "dataset": "d",
                    "query_id": "q",
                    "page_id": f"p{index}",
                    "source": "s",
                    "relevance": int(index == 0),
                    "bm25_score": 6 - index,
                    "dense_score": 5 - abs(index - 1),
                    "stage1_score": 4 - abs(index - 2),
                    "visual_score": 3 - abs(index - 3),
                    "full_score": 6 - index,
                    "stage2_ms": 5.0,
                    "stage2_flops": 10.0,
                }
            )
        result = build_cache(pd.DataFrame(rows))
        first = run_preflight(result.retrieval_scores, result.query_metrics)
        second = run_preflight(
            result.retrieval_scores.sample(frac=1.0, random_state=7),
            result.query_metrics.sample(frac=1.0, random_state=8),
        )
        self.assertEqual(
            first["retrieval_score_content_sha256"],
            second["retrieval_score_content_sha256"],
        )
        self.assertEqual(
            first["query_metric_content_sha256"],
            second["query_metric_content_sha256"],
        )

    def test_reference_metric_outside_tolerance_fails(self):
        result = build_cache(pd.DataFrame([
            {
                "dataset": "d", "query_id": "q", "page_id": "p", "source": "s",
                "relevance": 1, "bm25_score": 1.0, "dense_score": 1.0,
                "stage1_score": 1.0, "visual_score": 1.0, "full_score": 1.0,
            }
        ]))
        report = run_preflight(
            result.retrieval_scores,
            result.query_metrics,
            {"ndcg_full": 0.5},
            0.01,
        )
        self.assertFalse(report["passed"])
        self.assertFalse(report["reproduction_passed"])


if __name__ == "__main__":
    unittest.main()
