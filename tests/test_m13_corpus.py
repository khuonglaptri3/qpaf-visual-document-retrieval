"""Tests for corpus scanner and synthetic fixture generator in M1.3."""
import tempfile
from pathlib import Path
import unittest
import zipfile

from qpaf.m13.corpus import (
    inspect_pdf_archive,
    scan_pdf_directory,
    generate_synthetic_vidoseek_fixture,
)


class TestM13Corpus(unittest.TestCase):
    def test_inspect_pdf_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "test_corpus.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("doc1.pdf", b"%PDF-1.4 mock")
                zf.writestr("doc2.pdf", b"%PDF-1.4 mock 2")
                zf.writestr("notes.txt", b"ignore me")

            info = inspect_pdf_archive(zip_path)
            self.assertEqual(info["total_files"], 3)
            self.assertEqual(info["pdf_count"], 2)
            self.assertIn("doc1.pdf", info["pdf_documents"])
            self.assertIn("doc2.pdf", info["pdf_documents"])
            self.assertEqual(len(info["sha256"]), 64)

    def test_scan_pdf_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / "a.pdf").write_bytes(b"content")
            (dir_path / "b.pdf").write_bytes(b"")
            (dir_path / "c.txt").write_bytes(b"txt")

            info = scan_pdf_directory(dir_path)
            self.assertEqual(info["total_pdfs"], 2)
            self.assertIn("a.pdf", info["pdf_names"])
            self.assertIn("b.pdf", info["empty_files"])

    def test_generate_synthetic_vidoseek_fixture(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            paths = generate_synthetic_vidoseek_fixture(target)
            self.assertTrue(paths["json_path"].exists())
            self.assertTrue(paths["zip_path"].exists())

            archive_info = inspect_pdf_archive(paths["zip_path"])
            self.assertGreater(archive_info["pdf_count"], 0)


if __name__ == "__main__":
    unittest.main()
