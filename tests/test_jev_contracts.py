"""Contract tests for the Jev CPU toolkit."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qpaf.jev.contracts import (
    baseline_scores, load_pairs, load_scores, sha256_file, validate_splits, write_scores,
)
from qpaf.jev.data import prepare_candidates


def example_pairs():
    return {
        "dataset": "synthetic",
        "synthetic": True,
        "top_k": 2,
        "queries": {"q": "question"},
        "pages": {"a": "", "b": "ocr text"},
        "pairs": [["q", "a"], ["q", "b"]],
    }


class ContractsTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.pairs = Path(folder.name) / "pairs.json"
        self.cache = Path(folder.name) / "score.json"

    def save_pairs(self, body=None):
        self.pairs.write_text(
            json.dumps(example_pairs() if body is None else body) + "\n",
            encoding="utf-8",
        )

    def test_empty_ocr_remains_a_valid_page(self):
        self.save_pairs()
        self.assertEqual(load_pairs(self.pairs)["pages"]["a"], "")

    def test_duplicate_pair_and_missing_text_rejected(self):
        for change, error in (
            ({"pairs": [["q", "a"], ["q", "a"]]}, "duplicate"),
            ({"pages": {"a": ""}}, "b"),
            ({"queries": {"q": " "}}, "query"),
        ):
            with self.subTest(change=change):
                self.save_pairs({**example_pairs(), **change})
                with self.assertRaisesRegex(ValueError, error):
                    load_pairs(self.pairs)

    def test_cache_is_bound_to_raw_bytes_and_preserves_details(self):
        self.save_pairs()
        digest = hashlib.sha256(self.pairs.read_bytes()).hexdigest()
        self.assertEqual(sha256_file(self.pairs), digest)
        info = {"model": "toy", "revision": "v1", "synthetic": True}
        written = write_scores(self.cache, self.pairs, [4, -2], info, {"batches": 1})
        self.assertEqual(
            written,
            {"pairs_sha256": digest, "scores": [4, -2], "manifest": info, "details": {"batches": 1}},
        )
        self.assertEqual(load_scores(self.cache, self.pairs), written)
        self.pairs.write_bytes(self.pairs.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "pairs_sha256"):
            load_scores(self.cache, self.pairs)

    def test_invalid_write_leaves_previous_cache_intact(self):
        self.save_pairs()
        write_scores(self.cache, self.pairs, [5, 2], {"model": "toy"})
        old = self.cache.read_bytes()
        for scores in ([5], [5, 2, -1], [5, float("nan")], [5, True], [5, float("inf")]):
            with self.subTest(scores=scores):
                with self.assertRaises(ValueError):
                    write_scores(self.cache, self.pairs, scores, {"model": "toy"})
                self.assertEqual(self.cache.read_bytes(), old)

    def test_writer_rejects_pair_changes_since_scoring(self):
        self.save_pairs()
        original = sha256_file(self.pairs)
        self.pairs.write_bytes(self.pairs.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "changed"):
            write_scores(self.cache, self.pairs, [4, 2], {}, expected_pairs_sha256=original)
        self.assertFalse(self.cache.exists())

    def test_invalid_existing_cache_fails_even_with_matching_hash(self):
        self.save_pairs()
        for scores in ([], [2, True], [2, float("nan")]):
            self.cache.write_text(json.dumps({
                "scores": scores, "pairs_sha256": sha256_file(self.pairs), "manifest": {},
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_scores(self.cache, self.pairs)

    def test_baseline_never_uses_pair_order(self):
        with self.assertRaisesRegex(ValueError, "base_scores"):
            baseline_scores(example_pairs())
        self.assertEqual(baseline_scores({**example_pairs(), "base_scores": [0, 2]}), [0, 2])

    def test_split_validation_checks_group_leakage_even_outside_pool(self):
        bundle = example_pairs()
        manifest = {"splits": {"q": "train", "other": "test"}, "groups": {"q": "g", "other": "g"}}
        with self.assertRaisesRegex(ValueError, "group"):
            validate_splits(bundle, manifest)
        manifest["groups"]["other"] = "h"
        self.assertEqual(validate_splits(bundle, manifest)["splits"]["q"], "train")
        del manifest["groups"]["q"]
        with self.assertRaisesRegex(ValueError, "q"):
            validate_splits(bundle, manifest)

    def test_explicit_base_selection_keeps_scores_aligned_with_page_order(self):
        bundle = prepare_candidates(
            "synthetic", {"q": "query"}, {"a": "", "b": "", "c": ""},
            [
                {"query_id": "q", "page_id": "c", "base_score": 10, "relevance": 0},
                {"query_id": "q", "page_id": "b", "base_score": -1, "relevance": 99},
                {"query_id": "q", "page_id": "a", "base_score": 4},
            ],
            2,
        )
        self.assertEqual(bundle["pairs"], [["q", "a"], ["q", "c"]])
        self.assertEqual(bundle["base_scores"], [4, 10])
        self.assertEqual(set(bundle["pages"]), {"a", "c"})

    def test_explicit_channel_weights_use_query_local_normalization(self):
        bundle = prepare_candidates(
            "synthetic", {"q": "query"}, {"a": "", "b": "", "c": ""},
            [
                {"query_id": "q", "page_id": "a", "bm25": 20, "dense": 2, "visual": 10},
                {"query_id": "q", "page_id": "b", "bm25": 10, "dense": 5, "visual": 10},
                {"query_id": "q", "page_id": "c", "bm25": 15, "dense": 4, "visual": 10},
            ],
            2,
            weights=(0.1, 0.7, 0.2),
        )
        self.assertEqual(bundle["pairs"], [["q", "b"], ["q", "c"]])
        self.assertAlmostEqual(bundle["base_scores"][0], 0.7)
        self.assertAlmostEqual(bundle["base_scores"][1], 0.05 + 0.7 * (2 / 3))
