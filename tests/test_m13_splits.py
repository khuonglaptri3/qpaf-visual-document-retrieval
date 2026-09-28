"""Tests for deterministic split derivation and verification in M1.3."""
import unittest

from qpaf.m13.splits import (
    create_deterministic_splits,
    verify_split_disjointness,
    serialize_split_manifest,
)


class TestM13Splits(unittest.TestCase):
    def setUp(self):
        # 100 mock query IDs
        self.query_ids = [f"q_{i:04d}" for i in range(100)]

    def test_split_counts_and_reproducibility(self):
        splits1 = create_deterministic_splits(
            self.query_ids,
            train_ratio=0.7,
            val_ratio=0.15,
            test_ratio=0.15,
            seed=2026,
        )
        self.assertEqual(len(splits1["train"]), 70)
        self.assertEqual(len(splits1["val"]), 15)
        self.assertEqual(len(splits1["test"]), 15)

        # Same seed and IDs must produce identical splits
        splits2 = create_deterministic_splits(
            self.query_ids,
            train_ratio=0.7,
            val_ratio=0.15,
            test_ratio=0.15,
            seed=2026,
        )
        self.assertEqual(splits1["train"], splits2["train"])
        self.assertEqual(splits1["val"], splits2["val"])
        self.assertEqual(splits1["test"], splits2["test"])

    def test_zero_leakage_and_invariants(self):
        splits = create_deterministic_splits(self.query_ids, seed=2026)
        valid, msg = verify_split_disjointness(splits, total_expected=100)
        self.assertTrue(valid, msg)

    def test_detects_overlap(self):
        corrupted_splits = {
            "train": ["q_01", "q_02"],
            "val": ["q_02", "q_03"],
            "test": ["q_04"],
        }
        valid, msg = verify_split_disjointness(corrupted_splits, total_expected=4)
        self.assertFalse(valid)
        self.assertIn("overlap", msg.lower())

    def test_manifest_serialization_and_hash(self):
        sample_ids = ["q_0001", "q_0002", "q_0003"]
        text, digest = serialize_split_manifest(sample_ids)
        self.assertEqual(text, "q_0001\nq_0002\nq_0003\n")
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
