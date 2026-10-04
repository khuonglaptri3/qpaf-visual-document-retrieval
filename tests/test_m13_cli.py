"""Tests for primary corpus audit CLI script in M1.3."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
import os

from qpaf.m13.corpus import generate_synthetic_vidoseek_fixture


class TestM13CLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "scripts/audit_primary_corpus.py", *map(str, args)],
                              capture_output=True, text=True, env={**os.environ, "PYTHONUTF8": "1"})

    def test_missing_inputs_cannot_report_verified(self):
        for args in [[], ["--annotations", "missing.json"], ["--config", "missing.toml"]]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("VERIFIED_CPU_AUDIT", result.stdout)

    def test_verify_detects_tampering_and_does_not_rewrite_any_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = generate_synthetic_vidoseek_fixture(root / "fixture")
            report = root / "report.json"
            split_dir = root / "splits"
            base = ["--annotations", fixture["json_path"], "--corpus-zip", fixture["zip_path"],
                    "--splits-dir", split_dir]
            self.assertEqual(self.run_cli(*base, "--generate-splits", "--output", report).returncode, 0)
            parsed = json.loads(report.read_bytes())
            self.assertEqual(len(parsed["queries"]), 10)
            self.assertEqual(len(parsed["qrels"]), 10)
            self.assertIn("source_hashes", parsed["provenance"])
            self.assertEqual(parsed["corpus"]["total_pages"], 6)
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}
            self.assertEqual(self.run_cli(*base, "--verify-splits").returncode, 0)
            self.assertNotEqual(self.run_cli(*base, "--generate-splits", "--output", report).returncode, 0)
            self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()})
            content = (split_dir / "train_ids.txt").read_bytes()
            (split_dir / "train_ids.txt").write_bytes(content + b"bogus\n")
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}
            result = self.run_cli(*base, "--verify-splits", "--output", report)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()})

    def test_cli_rejects_empty_annotations_and_corrupt_pdfs_without_creating_report(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = generate_synthetic_vidoseek_fixture(root / "fixture")
            report = root / "report.json"
            arguments = ["--annotations", fixture["json_path"], "--corpus-zip", fixture["zip_path"], "--output", report]
            raw = fixture["json_path"].read_bytes()
            fixture["json_path"].write_text('{"examples": []}', encoding="utf-8")
            self.assertNotEqual(self.run_cli(*arguments).returncode, 0)
            self.assertFalse(report.exists())
            fixture["json_path"].write_bytes(raw)
            with zipfile.ZipFile(fixture["zip_path"], "w") as archive:
                archive.writestr("doc_1.pdf", b"%PDF-1.4 fake")
            self.assertNotEqual(self.run_cli(*arguments).returncode, 0)
            self.assertFalse(report.exists())

    def test_cli_rejects_unknown_documents_and_actual_page_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = generate_synthetic_vidoseek_fixture(tmp)
            raw = json.loads(fixture["json_path"].read_bytes())
            for filename, page in [("missing.pdf", 1), ("doc_1.pdf", 3)]:
                raw["examples"][0]["meta_info"] = {"file_name": filename, "reference_page": [page]}
                fixture["json_path"].write_text(json.dumps(raw), encoding="utf-8")
                result = self.run_cli("--annotations", fixture["json_path"], "--corpus-zip", fixture["zip_path"])
                self.assertNotEqual(result.returncode, 0)

    def test_cli_execution_with_synthetic_fixture(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir) / "fixture"
            paths = generate_synthetic_vidoseek_fixture(fixture_dir)
            out_report = Path(tmpdir) / "report.json"
            splits_dir = Path(tmpdir) / "splits"

            cmd = [
                sys.executable,
                "scripts/audit_primary_corpus.py",
                "--annotations",
                str(paths["json_path"]),
                "--corpus-zip",
                str(paths["zip_path"]),
                "--output",
                str(out_report),
                "--splits-dir",
                str(splits_dir),
                "--generate-splits",
            ]

            res = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "PYTHONUTF8": "1"})
            self.assertEqual(res.returncode, 0, f"CLI failed: {res.stderr}\n{res.stdout}")
            self.assertTrue(out_report.exists())

            with open(out_report, "r") as f:
                report = json.load(f)

            self.assertEqual(report["status"], "VERIFIED_CPU_AUDIT")
            self.assertEqual(report["boundary"]["execution_authorized"], False)
            self.assertEqual(report["boundary"]["boundary_state"], "CLOSED")
            self.assertEqual(report["annotations"]["total_queries"], 10)
            self.assertIn("train", report["splits"])

            # Verify generated split manifest files
            self.assertTrue((splits_dir / "train_ids.txt").exists())
            self.assertTrue((splits_dir / "val_ids.txt").exists())
            self.assertTrue((splits_dir / "test_ids.txt").exists())


if __name__ == "__main__":
    unittest.main()
