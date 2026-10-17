import unittest

import pandas as pd

from oracle_study.cache import CoverageError, build_cache


class CacheTest(unittest.TestCase):
    def raw(self):
        rows = []
        for index in range(6):
            rows.append(
                {
                    "dataset": "d",
                    "query_id": "q",
                    "page_id": f"p{index}",
                    "source": "s",
                    "relevance": 1 if index == 0 else 0,
                    "bm25_score": 6 - index,
                    "dense_score": 5 - abs(index - 1),
                    "stage1_score": 4 - abs(index - 2),
                    "visual_score": 3 - abs(index - 3),
                    "full_score": 6 - index,
                    "stage2_ms": 5.0,
                    "stage2_flops": 10.0,
                }
            )
        return pd.DataFrame(rows)

    def test_cache_builds_required_artifacts(self):
        result = build_cache(self.raw())
        self.assertEqual(result.coverage_report["final_coverage"], 1.0)
        self.assertEqual(len(result.query_metrics), 1)
        self.assertIn("branch_ranks", result.retrieval_scores.columns)

    def test_relevance_does_not_change_candidate_pool(self):
        first = build_cache(self.raw()).retrieval_scores["page_id"].tolist()
        altered = self.raw()
        altered["relevance"] = altered["relevance"].iloc[::-1].to_numpy()
        second = build_cache(altered).retrieval_scores["page_id"].tolist()
        self.assertEqual(first, second)

    def test_official_metrics_are_preserved_and_marked(self):
        computed = build_cache(self.raw()).query_metrics
        official = computed.copy()
        official.loc[:, "ndcg_full"] = 0.123
        result = build_cache(self.raw(), official_query_metrics=official)
        self.assertAlmostEqual(result.query_metrics.iloc[0]["ndcg_full"], 0.123)
        self.assertEqual(
            result.coverage_report["query_metrics_source"],
            "official_full_corpus_export",
        )

    def test_negative_relevance_is_rejected(self):
        raw = self.raw()
        raw.loc[0, "relevance"] = -1
        with self.assertRaisesRegex(ValueError, "non-negative"):
            build_cache(raw)

    def test_failed_coverage_reports_the_affected_query(self):
        rows = []
        for index in range(400):
            rows.append(
                {
                    "dataset": "d",
                    "query_id": "q-low-coverage",
                    "page_id": f"p{index:03d}",
                    "source": "s",
                    "relevance": int(index == 399),
                    "bm25_score": 400 - index,
                    "dense_score": 400 - index,
                    "stage1_score": 400 - index,
                    "visual_score": 400 - index,
                    "full_score": 400 - index,
                }
            )
        with self.assertRaises(CoverageError) as caught:
            build_cache(pd.DataFrame(rows))
        self.assertEqual(caught.exception.report["queries_below_candidate_gate"], 1)
        self.assertEqual(
            caught.exception.query_audit.iloc[0]["status"],
            "candidate_coverage_below_gate",
        )


if __name__ == "__main__":
    unittest.main()
