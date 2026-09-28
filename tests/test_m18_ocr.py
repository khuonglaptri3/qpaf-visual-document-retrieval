"""Unit tests for M1.8 OCR Quality Policy & Artifact Namespace."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from qpaf.m18.ocr_policy import (
    ExtractionDecision,
    QualityMetrics,
    evaluate_page_text,
)
from qpaf.m18.namespace import (
    create_run_namespace,
    format_canonical_run_id,
    parse_canonical_run_id,
)


class TestM18OCRPolicy(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_native_text_qualification(self):
        """Clean academic text with > 50 chars passes native text check."""
        clean_text = (
            "Deep learning models for visual document retrieval achieve state of the "
            "art performance by leveraging multi-vector late interaction architectures."
        )
        decision = evaluate_page_text(clean_text)
        self.assertEqual(decision.route, "NATIVE_TEXT_QUALIFIED")
        self.assertGreaterEqual(decision.metrics.char_count, 50)
        self.assertGreaterEqual(decision.metrics.printable_ratio, 0.85)

    def test_short_text_triggers_ocr_fallback(self):
        """Short text (< 50 chars) triggers OCR fallback."""
        short_text = "Page 1 - Title"
        decision = evaluate_page_text(short_text)
        self.assertEqual(decision.route, "OCR_FALLBACK_TRIGGERED")
        self.assertIn("insufficient_character_count", decision.reason)

    def test_corrupted_mojibake_triggers_ocr_fallback(self):
        """Text with high ratio of unprintable control characters triggers OCR fallback."""
        corrupted_text = "ValidText" + ("\x00\x01\x02\x03\x04\x05\x06\x07\x08" * 15)
        decision = evaluate_page_text(corrupted_text)
        self.assertEqual(decision.route, "OCR_FALLBACK_TRIGGERED")
        self.assertIn("low_printable_ratio", decision.reason)

    def test_empty_text_and_low_confidence_fails(self):
        """Zero text and OCR failure leads to EXTRACTION_FAILED."""
        empty_text = ""
        decision = evaluate_page_text(empty_text, confidence=45.0)
        self.assertEqual(decision.route, "EXTRACTION_FAILED")

    def test_format_and_parse_canonical_run_id(self):
        """Verify format and parsing of Thanh's M1.7 canonical Run ID."""
        ts = datetime(2026, 9, 28, 16, 45, 0, tzinfo=timezone.utc)
        run_id = format_canonical_run_id("QPAF-M1_8-OCR-001", ts, attempt_num=1)
        self.assertEqual(run_id, "RUN-QPAF-M1_8-OCR-001-20260928T164500Z-A01")

        parsed = parse_canonical_run_id(run_id)
        self.assertEqual(parsed["experiment_id"], "QPAF-M1_8-OCR-001")
        self.assertEqual(parsed["attempt_num"], 1)
        self.assertEqual(parsed["timestamp_utc"], "20260928T164500Z")

    def test_create_run_namespace_create_once(self):
        """Creating an existing namespace must fail-closed with FileExistsError."""
        exp_id = "QPAF-M1_8-OCR-001"
        run_id = "RUN-QPAF-M1_8-OCR-001-20260928T164500Z-A01"

        run_path = create_run_namespace(self.work_dir, exp_id, run_id)
        self.assertTrue(run_path.is_dir())
        self.assertTrue((run_path / "logs").is_dir())
        self.assertTrue((run_path / "outputs").is_dir())

        # Second creation must fail
        with self.assertRaises(FileExistsError):
            create_run_namespace(self.work_dir, exp_id, run_id)

    def test_cli_execution_and_generation(self):
        """Verify standalone execution of scripts/audit_ocr_policy.py."""
        import subprocess

        cli_script = ROOT / "scripts" / "audit_ocr_policy.py"
        out_dir = self.work_dir / "m1.8_out"

        cmd = [
            sys.executable,
            str(cli_script),
            "--probe",
            "--output-dir",
            str(out_dir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"CLI stderr: {result.stderr}")

        self.assertTrue((out_dir / "ocr_checklist.md").is_file())
        self.assertTrue((out_dir / "ocr_failure_threshold.md").is_file())
        self.assertTrue((out_dir / "artifact_namespace.md").is_file())
        self.assertTrue((out_dir / "calibration_methodology.md").is_file())
        self.assertTrue((out_dir / "hash_manifest.csv").is_file())

        threshold_content = (out_dir / "ocr_failure_threshold.md").read_text(encoding="utf-8")
        self.assertIn("PROVISIONAL", threshold_content)
        self.assertIn("M2.3", threshold_content)


if __name__ == "__main__":
    unittest.main()
