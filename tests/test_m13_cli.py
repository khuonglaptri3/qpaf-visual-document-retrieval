"""Tests for primary corpus audit CLI script in M1.3."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from qpaf.m13.corpus import generate_synthetic_vidoseek_fixture


class TestM13CLI(unittest.TestCase):
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

            res = subprocess.run(cmd, capture_output=True, text=True, env={"PYTHONPATH": "src"})
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
