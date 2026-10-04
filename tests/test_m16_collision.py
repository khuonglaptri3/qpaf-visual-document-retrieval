"""Unit tests for M1.6 Primary-Corpus Collision Audit Subsystem."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from qpaf.m16.manifest import (
    AliasRecord,
    PageRecord,
    build_page_manifest,
    resolve_aliases,
)
from qpaf.m16.detector import (
    DuplicateRecord,
    detect_content_duplicates,
    detect_split_leakage,
    verify_qrel_consistency,
)
from qpaf.m16.report import (
    export_alias_csv,
    export_duplicate_csv,
    export_manifest_csv,
    generate_collision_markdown_report,
)


class TestM16CollisionAudit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_page_record_and_manifest_construction(self):
        """Verify building canonical page records from raw inputs."""
        raw_pages = [
            {
                "document_id": "doc_001",
                "page_number": 1,
                "source_path": "corpus/doc_001.pdf",
                "file_sha256": "aaaa" * 16,
                "content": b"Page 1 unique text content",
            },
            {
                "document_id": "doc_001",
                "page_number": 2,
                "source_path": "corpus/doc_001.pdf",
                "file_sha256": "aaaa" * 16,
                "content": b"Page 2 unique text content",
            },
        ]
        split_assignment = {"doc_001": "train"}

        manifest = build_page_manifest(raw_pages, split_assignment=split_assignment)
        self.assertEqual(len(manifest), 2)

        p1 = manifest[0]
        self.assertEqual(p1.document_id, "doc_001")
        self.assertEqual(p1.page_id, "doc_001_page_0001")
        self.assertEqual(p1.page_number, 1)
        self.assertEqual(p1.split, "train")
        self.assertEqual(p1.extraction_method, "direct_bytes")
        self.assertEqual(p1.review_status, "pending_review")

        expected_hash = hashlib.sha256(b"Page 1 unique text content").hexdigest()
        self.assertEqual(p1.content_sha256, expected_hash)

    def test_alias_resolution_and_normalization(self):
        """Verify normalization of arbitrary alias strings to canonical page IDs."""
        canonical_page_ids = {"doc_001_page_0001", "doc_001_page_0002"}
        raw_aliases = [
            ("doc_001_p1", "doc_001.pdf_page_1"),
            ("doc_001_1", "query_rel_ref"),
            ("doc_001_page_0001", "exact_match"),
            ("unknown_doc_p99", "bad_ref"),
        ]

        mapping, records = resolve_aliases(raw_aliases, canonical_page_ids)
        self.assertEqual(mapping.get("doc_001_p1"), "doc_001_page_0001")
        self.assertEqual(mapping.get("doc_001_1"), "doc_001_page_0001")
        self.assertEqual(mapping.get("doc_001_page_0001"), "doc_001_page_0001")
        self.assertNotIn("unknown_doc_p99", mapping)

        self.assertGreaterEqual(len(records), 2)
        r0 = records[0]
        self.assertEqual(r0.canonical_page_id, "doc_001_page_0001")
        self.assertEqual(r0.review_status, "pending_review")

    def test_detect_content_duplicates(self):
        """Verify grouping of identical content hashes."""
        shared_content = b"Exact identical boiler plate notice across multiple pages"
        shared_hash = hashlib.sha256(shared_content).hexdigest()

        records = [
            PageRecord(
                document_id="doc_a",
                page_id="doc_a_page_0001",
                page_number=1,
                source_path="a.pdf",
                file_sha256="1111" * 16,
                content_sha256=shared_hash,
                split="train",
                extraction_method="direct_bytes",
                review_status="verified",
            ),
            PageRecord(
                document_id="doc_b",
                page_id="doc_b_page_0001",
                page_number=1,
                source_path="b.pdf",
                file_sha256="2222" * 16,
                content_sha256=shared_hash,
                split="train",
                extraction_method="direct_bytes",
                review_status="verified",
            ),
            PageRecord(
                document_id="doc_c",
                page_id="doc_c_page_0001",
                page_number=1,
                source_path="c.pdf",
                file_sha256="3333" * 16,
                content_sha256=hashlib.sha256(b"Unique content").hexdigest(),
                split="test",
                extraction_method="direct_bytes",
                review_status="verified",
            ),
        ]

        duplicates = detect_content_duplicates(records)
        self.assertEqual(len(duplicates), 1)
        dup = duplicates[0]
        self.assertEqual(dup.collision_type, "EXACT_CONTENT_DUPLICATE")
        self.assertEqual(dup.left_page_id, "doc_a_page_0001")
        self.assertEqual(dup.right_page_id, "doc_b_page_0001")
        self.assertEqual(dup.content_sha256, shared_hash)
        self.assertFalse(dup.split_leakage)

    def test_detect_split_leakage(self):
        """Verify flag when identical content spans across train/val/test splits."""
        shared_hash = hashlib.sha256(b"Confidential leaked page").hexdigest()

        manifest = [
            PageRecord(
                document_id="doc_train",
                page_id="doc_train_page_0001",
                page_number=1,
                source_path="train.pdf",
                file_sha256="1111" * 16,
                content_sha256=shared_hash,
                split="train",
                extraction_method="direct_bytes",
                review_status="verified",
            ),
            PageRecord(
                document_id="doc_test",
                page_id="doc_test_page_0001",
                page_number=1,
                source_path="test.pdf",
                file_sha256="2222" * 16,
                content_sha256=shared_hash,
                split="test",
                extraction_method="direct_bytes",
                review_status="verified",
            ),
        ]

        duplicates = detect_content_duplicates(manifest)
        leakage_records = detect_split_leakage(duplicates, manifest)

        self.assertEqual(len(leakage_records), 1)
        self.assertTrue(leakage_records[0].split_leakage)
        self.assertEqual(leakage_records[0].resolution, "split_leakage_blocker")

    def test_verify_qrel_consistency_and_orphans(self):
        """Verify query-document relevance mappings against canonical pages."""
        canonical_ids = {"doc_01_page_0001", "doc_01_page_0002", "doc_02_page_0001"}
        qrels = {
            "q1": {"doc_01_page_0001": 1},
            "q2": {"doc_01_page_0002": 1},
            "q3": {"missing_page_0001": 1},  # dangling reference
        }

        res = verify_qrel_consistency(qrels, canonical_ids)
        self.assertEqual(res["total_queries"], 3)
        self.assertEqual(res["valid_queries"], 2)
        self.assertIn("q3", res["orphan_queries"])
        self.assertIn("doc_02_page_0001", res["unreferenced_pages"])

    def test_export_manifests_and_duplicate_csvs(self):
        """Verify that exported CSVs strictly conform to the expected schema."""
        page_csv = self.work_dir / "page_manifest.csv"
        alias_csv = self.work_dir / "alias_manifest.csv"
        dup_csv = self.work_dir / "duplicate_report.csv"
        rep_md = self.work_dir / "collision_report.md"

        page_records = [
            PageRecord(
                document_id="doc_01",
                page_id="doc_01_page_0001",
                page_number=1,
                source_path="doc_01.pdf",
                file_sha256="1" * 64,
                content_sha256="2" * 64,
                split="train",
                extraction_method="native_pdf",
                review_status="reviewed",
            )
        ]
        alias_records = [
            AliasRecord(
                alias_id="doc_01_p1",
                canonical_page_id="doc_01_page_0001",
                source_reference="vidoseek.json",
                reason="zero_padded_page_index",
                review_status="reviewed",
            )
        ]
        dup_records = [
            DuplicateRecord(
                group_id="DUP-0001",
                collision_type="EXACT_CONTENT_DUPLICATE",
                left_page_id="doc_01_page_0001",
                right_page_id="doc_02_page_0001",
                content_sha256="2" * 64,
                split_leakage=False,
                resolution="canonical_alias_assigned",
                review_status="reviewed",
            )
        ]

        export_manifest_csv(page_records, page_csv)
        export_alias_csv(alias_records, alias_csv)
        export_duplicate_csv(dup_records, dup_csv)

        # Verify page manifest schema
        with open(page_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(
                header,
                [
                    "document_id",
                    "page_id",
                    "page_number",
                    "source_path",
                    "file_sha256",
                    "content_sha256",
                    "split",
                    "extraction_method",
                    "review_status",
                ],
            )
            row = next(reader)
            self.assertEqual(row[1], "doc_01_page_0001")

        # Verify alias manifest schema
        with open(alias_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(
                header,
                ["alias_id", "canonical_page_id", "source_reference", "reason", "review_status"],
            )

        # Verify duplicate report schema
        with open(dup_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(
                header,
                [
                    "group_id",
                    "collision_type",
                    "left_page_id",
                    "right_page_id",
                    "content_sha256",
                    "split_leakage",
                    "resolution",
                    "review_status",
                ],
            )

        # Test markdown report generation
        summary = {
            "status": "PASS_AUDIT",
            "total_documents": 10,
            "total_pages": 50,
            "unique_content_hashes": 49,
            "duplicate_groups_count": 1,
            "split_leakage_count": 0,
            "total_queries": 100,
            "orphan_query_count": 0,
            "orphan_page_count": 5,
        }
        md_text = generate_collision_markdown_report(summary)
        self.assertIn("# M1.6 — Primary-Corpus Collision Audit", md_text)
        self.assertIn("PASS_AUDIT", md_text)
        self.assertIn("Zero cross-split leakage confirmed", md_text)

    def test_cli_execution_with_fixture(self):
        """Verify standalone execution of scripts/audit_collisions.py."""
        import subprocess

        cli_script = ROOT / "scripts" / "audit_collisions.py"
        out_dir = self.work_dir / "audit_output"

        cmd = [
            sys.executable,
            str(cli_script),
            "--fixture",
            "--output-dir",
            str(out_dir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"CLI stderr: {result.stderr}")

        self.assertTrue((out_dir / "page_manifest.csv").is_file())
        self.assertTrue((out_dir / "alias_manifest.csv").is_file())
        self.assertTrue((out_dir / "duplicate_report.csv").is_file())
        self.assertTrue((out_dir / "collision_report.md").is_file())
        self.assertTrue((out_dir / "collision_summary.json").is_file())

        with open(out_dir / "collision_summary.json", "r", encoding="utf-8") as f:
            summary = json.load(f)
        self.assertEqual(summary["status"], "PASS_AUDIT")
        self.assertEqual(summary["split_leakage_count"], 0)


if __name__ == "__main__":
    unittest.main()
