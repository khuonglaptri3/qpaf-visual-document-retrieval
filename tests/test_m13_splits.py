"""Tests for deterministic split derivation and verification in M1.3."""
import unittest
import tempfile
import json
import hashlib
from pathlib import Path
from qpaf.m13 import splits as split_module

from qpaf.m13.splits import (
    create_deterministic_splits,
    verify_split_disjointness,
    serialize_split_manifest,
)


class TestM13Splits(unittest.TestCase):
    def test_duplicate_ids_are_rejected_within_one_split_and_input(self):
        valid, _ = verify_split_disjointness({"train": ["a", "a"], "val": [], "test": []}, 1)
        self.assertFalse(valid)
        with self.assertRaises(ValueError):
            create_deterministic_splits(["a", "a"])

    def test_bundle_roundtrip_is_create_once_and_verification_is_read_only(self):
        self.assertTrue(hasattr(split_module, "write_split_bundle"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            written = split_module.write_split_bundle(path, self.query_ids)
            before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in path.iterdir()}
            self.assertEqual(split_module.read_split_bundle(path, self.query_ids), written)
            self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in path.iterdir()})
            with self.assertRaises(FileExistsError):
                split_module.write_split_bundle(path, self.query_ids)
            target = path / "train_ids.txt"
            target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
            with self.assertRaises(ValueError):
                split_module.read_split_bundle(path, self.query_ids)

    def test_bundle_rejects_policy_changes_and_ids_even_with_updated_hash(self):
        self.assertTrue(hasattr(split_module, "write_split_bundle"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            split_module.write_split_bundle(path, self.query_ids)
            manifest_path = path / "split_manifest.json"
            original = manifest_path.read_bytes()
            manifest = json.loads(original)
            manifest["policy"]["seed"] = 99
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                split_module.read_split_bundle(path, self.query_ids)
            manifest = json.loads(original)
            target = path / "train_ids.txt"
            content = target.read_bytes().replace(b"q_", b"x_", 1)
            target.write_bytes(content)
            manifest["files"]["train_ids.txt"]["sha256"] = hashlib.sha256(content).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                split_module.read_split_bundle(path, self.query_ids)
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
