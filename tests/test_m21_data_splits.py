"""Tests for the M2.1 data-role and split freeze."""

import hashlib
import importlib
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from qpaf.m13.splits import write_split_bundle


class M21Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.raw_dir = root / "data/raw/vidoseek-fixture"
        self.splits_dir = root / "evidence/revisions/m1.3-fixture/splits"
        self.source_manifest = root / "data/manifests/vidoseek-fixture.json"
        self.query_ids = [f"q-{index:02d}" for index in range(20)]

        self.raw_dir.mkdir(parents=True)
        annotation = {
            "examples": [
                {
                    "uid": query_id,
                    "query": f"Question {query_id}",
                    "meta_info": {"file_name": "doc.pdf", "reference_page": [1]},
                }
                for query_id in self.query_ids
            ]
        }
        payloads = {
            "README.md": b"fixture dataset card\n",
            "vidoseek.json": (json.dumps(annotation) + "\n").encode("utf-8"),
            "vidoseek_pdf_document.zip": b"fixture archive bytes",
        }
        for name, data in payloads.items():
            (self.raw_dir / name).write_bytes(data)

        manifest = {
            "schema_version": 1,
            "dataset": "Qiuchen-Wang/ViDoSeek",
            "revision": "e91a92ba5f38690696c7e66be5c5474b54c6e791",
            "files": [
                {
                    "filename": name,
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                for name, data in payloads.items()
            ],
        }
        self.source_manifest.parent.mkdir(parents=True)
        self.source_manifest.write_text(json.dumps(manifest), encoding="utf-8")
        write_split_bundle(self.splits_dir, self.query_ids)


class TestM21DataSplits(unittest.TestCase):
    def test_freeze_rejects_wrong_dataset_identity(self):
        module = importlib.import_module("qpaf.m21.data_splits")
        cases = {
            "dataset": "unexpected/dataset",
            "revision": "wrong-revision",
        }
        for field, value in cases.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                fixture = M21Fixture(Path(tmp))
                source = json.loads(fixture.source_manifest.read_text(encoding="utf-8"))
                source[field] = value
                fixture.source_manifest.write_text(json.dumps(source), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "dataset identity mismatch"):
                    module.build_data_split_freeze(
                        repo_root=fixture.root,
                        source_manifest_path=fixture.source_manifest,
                        raw_dir=fixture.raw_dir,
                        splits_dir=fixture.splits_dir,
                    )

    def test_freeze_requires_exact_payload_inventory(self):
        module = importlib.import_module("qpaf.m21.data_splits")
        for mutation in ("missing", "duplicate"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                fixture = M21Fixture(Path(tmp))
                source = json.loads(fixture.source_manifest.read_text(encoding="utf-8"))
                if mutation == "missing":
                    source["files"] = source["files"][:-1]
                else:
                    source["files"].append(dict(source["files"][0]))
                fixture.source_manifest.write_text(json.dumps(source), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "payload inventory mismatch"):
                    module.build_data_split_freeze(
                        repo_root=fixture.root,
                        source_manifest_path=fixture.source_manifest,
                        raw_dir=fixture.raw_dir,
                        splits_dir=fixture.splits_dir,
                    )

    def test_freeze_records_active_split_roles(self):
        try:
            module = importlib.import_module("qpaf.m21.data_splits")
        except ModuleNotFoundError:
            self.fail("M2.1 data split freezer is not implemented")

        with tempfile.TemporaryDirectory() as tmp:
            fixture = M21Fixture(Path(tmp))
            manifest, _ = module.build_data_split_freeze(
                repo_root=fixture.root,
                source_manifest_path=fixture.source_manifest,
                raw_dir=fixture.raw_dir,
                splits_dir=fixture.splits_dir,
            )

        roles = manifest["roles"]
        self.assertEqual(manifest["task_id"], "M2.1")
        self.assertEqual(manifest["status"], "VERIFIED_ACTIVE_PRIMARY_SPLITS")
        self.assertEqual(roles["train"]["count"], 14)
        self.assertEqual(roles["validation"]["count"], 3)
        self.assertEqual(roles["test"]["count"], 3)
        self.assertEqual(roles["confirmation"]["status"], "NOT_ACTIVATED_FUTURE_SCOPE")
        self.assertIsNone(roles["confirmation"]["id_manifest"])
        self.assertEqual(roles["external"]["status"], "NOT_ADOPTED")
        self.assertIsNone(roles["external"]["id_manifest"])

    def test_freeze_rejects_tampered_reproduced_payload(self):
        module = importlib.import_module("qpaf.m21.data_splits")
        with tempfile.TemporaryDirectory() as tmp:
            fixture = M21Fixture(Path(tmp))
            archive = fixture.raw_dir / "vidoseek_pdf_document.zip"
            archive.write_bytes(archive.read_bytes() + b"tampered")

            with self.assertRaisesRegex(ValueError, "payload hash mismatch"):
                module.build_data_split_freeze(
                    repo_root=fixture.root,
                    source_manifest_path=fixture.source_manifest,
                    raw_dir=fixture.raw_dir,
                    splits_dir=fixture.splits_dir,
                )

    def test_freeze_reports_split_hashes_and_zero_overlap(self):
        module = importlib.import_module("qpaf.m21.data_splits")
        with tempfile.TemporaryDirectory() as tmp:
            fixture = M21Fixture(Path(tmp))
            source_split_manifest = json.loads(
                (fixture.splits_dir / "split_manifest.json").read_text(encoding="utf-8")
            )
            manifest, report = module.build_data_split_freeze(
                repo_root=fixture.root,
                source_manifest_path=fixture.source_manifest,
                raw_dir=fixture.raw_dir,
                splits_dir=fixture.splits_dir,
            )

        self.assertEqual(
            manifest["roles"]["train"].get("sha256"),
            source_split_manifest["files"]["train_ids.txt"]["sha256"],
        )
        self.assertEqual(
            report["integrity"]["pairwise_overlap"],
            {"train_validation": 0, "train_test": 0, "validation_test": 0},
        )
        self.assertEqual(report["integrity"]["union_count"], 20)
        self.assertEqual(report["integrity"]["annotation_query_count"], 20)
        self.assertEqual(report["checks"]["split_disjointness"], "PASS")
        self.assertEqual(report["checks"]["split_union_matches_annotations"], "PASS")

    def test_freeze_binds_source_and_split_manifests(self):
        module = importlib.import_module("qpaf.m21.data_splits")
        with tempfile.TemporaryDirectory() as tmp:
            fixture = M21Fixture(Path(tmp))
            manifest, _ = module.build_data_split_freeze(
                repo_root=fixture.root,
                source_manifest_path=fixture.source_manifest,
                raw_dir=fixture.raw_dir,
                splits_dir=fixture.splits_dir,
            )
            expected_source_hash = hashlib.sha256(fixture.source_manifest.read_bytes()).hexdigest()
            split_manifest_path = fixture.splits_dir / "split_manifest.json"
            expected_split_hash = hashlib.sha256(split_manifest_path.read_bytes()).hexdigest()

        self.assertEqual(manifest["dataset"].get("source_manifest_sha256"), expected_source_hash)
        self.assertEqual(
            manifest.get("split_bundle"),
            {
                "source_task": "M1.3",
                "manifest_path": "evidence/revisions/m1.3-fixture/splits/split_manifest.json",
                "manifest_sha256": expected_split_hash,
            },
        )

    def test_cli_exports_create_once_verified_evidence(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts/freeze_m21_data_splits.py"
        with tempfile.TemporaryDirectory() as tmp:
            fixture = M21Fixture(Path(tmp) / "fixture-repo")
            output_dir = Path(tmp) / "m2.1-001"
            command = [
                sys.executable,
                str(script),
                "--repo-root",
                str(fixture.root),
                "--source-manifest",
                str(fixture.source_manifest),
                "--raw-dir",
                str(fixture.raw_dir),
                "--splits-dir",
                str(fixture.splits_dir),
                "--output-dir",
                str(output_dir),
            ]

            first = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            expected_files = {
                "README.md",
                "data_split_manifest.json",
                "verification_report.json",
                "hash_manifest.csv",
            }
            self.assertEqual({path.name for path in output_dir.iterdir()}, expected_files)

            verification = json.loads(
                (output_dir / "verification_report.json").read_text(encoding="utf-8")
            )
            provenance = verification.get("provenance")
            self.assertIsNotNone(provenance)
            self.assertEqual(len(provenance["source_commit"]), 40)
            self.assertIsInstance(provenance["tracked_tree_dirty"], bool)
            self.assertEqual(
                set(provenance["source_hashes"]),
                {"scripts/freeze_m21_data_splits.py", "src/qpaf/m21/data_splits.py"},
            )

            with (output_dir / "hash_manifest.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(
                {row["path"] for row in rows},
                {"README.md", "data_split_manifest.json", "verification_report.json"},
            )
            for row in rows:
                payload = (output_dir / row["path"]).read_bytes()
                self.assertEqual(int(row["size_bytes"]), len(payload))
                self.assertEqual(row["sha256"], hashlib.sha256(payload).hexdigest())

            before = {path.name: path.read_bytes() for path in output_dir.iterdir()}
            second = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("already exists", second.stderr)
            self.assertEqual(before, {path.name: path.read_bytes() for path in output_dir.iterdir()})


if __name__ == "__main__":
    unittest.main()
