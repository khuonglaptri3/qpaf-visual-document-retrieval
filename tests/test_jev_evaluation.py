"""Hand-computed examples for Jev evaluation and comparisons."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qpaf.jev.evaluation import blend_scores, compare, evaluate


def document_pool():
    return {
        "dataset": "synthetic",
        "top_k": 3,
        "queries": {"q": "query"},
        "pages": {"a1": "", "a2": "", "b": ""},
        "pairs": [["q", "a1"], ["q", "a2"], ["q", "b"]],
        "units": {"a1": "a", "a2": "a", "b": "b"},
        "base_scores": [6, 12, 0],
    }


class EvaluationTest(unittest.TestCase):
    def test_document_pooling_uses_max_and_retains_out_of_pool_gold(self):
        report = evaluate(document_pool(), [0, 3, 2], {"q": {"b": 1, "outside": 1}}, k=2)
        query = report["per_query"]["q"]
        self.assertAlmostEqual(query["ndcg@2"], 1 / (1 + math.log2(3)))
        self.assertEqual(query["mrr@2"], 0.5)
        self.assertEqual(query["recall@2"], 0.5)
        self.assertEqual(query["recall@20"], 0.5)
        self.assertEqual(report["mean"]["mrr@2"], 0.5)

    def test_tied_units_follow_unit_id_even_when_page_order_differs(self):
        bundle = document_pool()
        bundle["units"] = {"a1": "z", "a2": "z", "b": "a"}
        report = evaluate(bundle, [0, 0, 0], {"q": {"a": 1}})
        self.assertEqual(report["mean"]["mrr@10"], 1)

    def test_graded_relevance_uses_exponential_gain(self):
        report = evaluate(document_pool(), [0, 3, 2], {"q": {"a": 1, "b": 2}})
        self.assertAlmostEqual(report["mean"]["ndcg@10"], (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3)))

    def test_queries_without_hits_stay_in_mean(self):
        bundle = document_pool()
        bundle["queries"]["miss"] = "second query"
        bundle["pairs"].append(["miss", "a1"])
        bundle["base_scores"].append(1)
        report = evaluate(bundle, [3, 0, 1, 0], {"q": {"a": 1}, "miss": {"outside": 1}})
        self.assertEqual(report["per_query"]["miss"]["mrr@10"], 0)
        self.assertEqual(report["mean"]["mrr@10"], 0.5)

    def test_incomplete_coverage_fails_explicitly(self):
        bundle = document_pool()
        with self.assertRaisesRegex(ValueError, "q"):
            evaluate(bundle, [3, 2, 1], {})
        with self.assertRaisesRegex(ValueError, "scores"):
            evaluate(bundle, [3, 2], {"q": {}})
        del bundle["units"]["a1"]
        with self.assertRaisesRegex(ValueError, "a1"):
            evaluate(bundle, [3, 2, 1], {"q": {}})

    def test_explicit_blend_minmaxes_each_score_vector(self):
        bundle = document_pool()
        scores = [1, 0, 4]
        self.assertEqual(blend_scores(bundle, scores, 0.5), [0.375, 0.5, 0.5])
        self.assertEqual(evaluate(bundle, scores, {"q": {"b": 1}})["mean"]["mrr@10"], 1)
        del bundle["base_scores"]
        with self.assertRaisesRegex(ValueError, "base_scores"):
            blend_scores(bundle, scores, 1)

    def test_group_bootstrap_samples_whole_groups(self):
        left = {"per_query": {"a": {"m": 0}, "b": {"m": 1}, "c": {"m": 0}}}
        right = {"per_query": {"c": {"m": 0}, "a": {"m": 1}, "b": {"m": 0}}}
        paired = compare(left, right, seed=7, resamples=200)
        grouped = compare(left, right, seed=7, resamples=200, groups={"a": "x", "b": "x", "c": "y"})
        self.assertEqual(grouped["metrics"]["m"]["ci95"], [0, 0])
        self.assertEqual(grouped["metrics"]["m"]["delta"], 0)
        self.assertEqual(grouped["metrics"]["m"]["win_tie_loss"], {"win": 1, "tie": 1, "loss": 1})
        self.assertLess(paired["metrics"]["m"]["ci95"][0], 0)
        self.assertGreater(paired["metrics"]["m"]["ci95"][1], 0)
        self.assertEqual(paired, compare(left, right, seed=7, resamples=200))

    def test_comparison_rejects_mismatched_cohorts(self):
        left = {"per_query": {"a": {"m": 0}}}
        right = {"per_query": {"b": {"m": 0}}}
        with self.assertRaisesRegex(ValueError, "cohort"):
            compare(left, right)
        with self.assertRaisesRegex(ValueError, "a"):
            compare(left, left, groups={})

    def test_known_vimdoc_requires_page_to_document_mapping(self):
        bundle = {**document_pool(), "dataset": "ViMDoc"}
        del bundle["units"]
        with self.assertRaisesRegex(ValueError, "--units"):
            evaluate(bundle, [0, 0, 1], {"q": {"document": 1}})

    def test_comparison_preserves_matching_protocol_fields(self):
        report = evaluate(document_pool(), [0, 3, 2], {"q": {"a": 1}})
        comparison = compare(report, report, resamples=10)
        self.assertEqual(comparison["ranking_scope"], "provided_candidate_pool")
        self.assertEqual(comparison["label_unit"], "mapped")
        self.assertFalse(comparison["synthetic"])

    def test_comparison_rejects_explicit_protocol_mismatches(self):
        report = evaluate(document_pool(), [0, 3, 2], {"q": {"a": 1}})
        for key, incompatible in (("ranking_scope", "full"), ("label_unit", "page"), ("synthetic", True)):
            with self.subTest(field=key):
                with self.assertRaisesRegex(ValueError, key):
                    compare(report, {**report, key: incompatible}, resamples=10)

    def test_missing_legacy_protocol_fields_remain_unknown(self):
        report = {"per_query": {"q": {"m": 1}}}
        comparison = compare(report, report, resamples=10)
        self.assertEqual(comparison["ranking_scope"], "unknown")
        self.assertEqual(comparison["label_unit"], "unknown")
        self.assertIsNone(comparison["synthetic"])
