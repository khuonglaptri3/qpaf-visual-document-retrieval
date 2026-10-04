"""Tests for corpus scanner and synthetic fixture generator in M1.3."""
import tempfile
from pathlib import Path
import unittest
import zipfile
import hashlib
import io
import pypdfium2 as pdfium
from qpaf.m13 import corpus


def pdf_bytes(pages=2):
    output = io.BytesIO()
    document = pdfium.PdfDocument.new()
    try:
        for _ in range(pages):
            document.new_page(100, 100).close()
        document.save(output)
    finally:
        document.close()
    return output.getvalue()

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
                zf.writestr("doc1.pdf", pdf_bytes(2))
                zf.writestr("doc2.pdf", pdf_bytes(3))
                zf.writestr("notes.txt", b"ignore me")

            info = inspect_pdf_archive(zip_path)
            self.assertEqual(info["total_files"], 3)
            self.assertEqual(info["pdf_count"], 2)
            self.assertIn("doc1.pdf", info["pdf_documents"])
            self.assertIn("doc2.pdf", info["pdf_documents"])
            self.assertEqual(len(info["sha256"]), 64)
            self.assertEqual(info["doc_page_counts"], {"doc1.pdf": 2, "doc2.pdf": 3})
            self.assertEqual(info["total_pages"], 5)

    def test_rejects_empty_corrupt_unsafe_and_ambiguous_archives(self):
        valid = pdf_bytes()
        cases = [[], [("a.pdf", b"%PDF-1.4 fake")], [("../a.pdf", valid)],
                 [("C:/a.pdf", valid)], [("a\\b.pdf", valid)],
                 [("a.pdf", valid), ("nested/A.PDF", valid)],
                 [("../notes.txt", b"unsafe"), ("a.pdf", valid)]]
        for members in cases:
            with self.subTest(members=[name for name, _ in members]), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "corpus.zip"
                with zipfile.ZipFile(path, "w") as archive:
                    for name, data in members:
                        info = zipfile.ZipInfo("placeholder")
                        info.filename = name  # Preserve unsafe backslashes on Windows.
                        archive.writestr(info, data)
                with self.assertRaises(ValueError):
                    inspect_pdf_archive(path)

    def test_rejects_zip_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corpus.zip"
            info = zipfile.ZipInfo("a.pdf")
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(info, "target.pdf")
            with self.assertRaises(ValueError):
                inspect_pdf_archive(path)

    def test_directory_inspection_reads_pages_and_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested"
            path.mkdir()
            data = pdf_bytes(3)
            (path / "a.pdf").write_bytes(data)
            self.assertTrue(hasattr(corpus, "inspect_pdf_directory"))
            info = corpus.inspect_pdf_directory(tmp)
            self.assertEqual(info["doc_page_counts"], {"a.pdf": 3})
            self.assertEqual(info["documents"][0]["file_sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(info["documents"][0]["document_id"], "a")

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
