"""Tests for ViDoSeek annotations and qrels parser in M1.3."""
import unittest

from qpaf.m13.vidoseek import (
    format_page_id,
    page_to_document_id,
    parse_vidoseek_annotations,
)


class TestM13ViDoSeek(unittest.TestCase):
    def setUp(self):
        self.sample_raw = {
            "examples": [
                {
                    "uid": "q001",
                    "query": "What is the revenue in 2023?",
                    "meta_info": {
                        "file_name": "annual_report.pdf",
                        "reference_page": [1, 3],
                    },
                },
                {
                    "uid": "q002",
                    "query": "Show me the market share chart.",
                    "meta_info": {
                        "file_name": "market_analysis.pdf",
                        "reference_page": [5],
                    },
                },
            ]
        }
        self.doc_page_counts = {
            "annual_report.pdf": 10,
            "market_analysis.pdf": 12,
        }

    def test_page_id_formatting_and_parsing(self):
        page_id = format_page_id("report.pdf", 5)
        self.assertEqual(page_id, "report_page_0005")
        doc_id = page_to_document_id(page_id)
        self.assertEqual(doc_id, "report")

    def test_parse_valid_annotations(self):
        parsed = parse_vidoseek_annotations(self.sample_raw, self.doc_page_counts)
        self.assertEqual(len(parsed.queries), 2)
        self.assertEqual(parsed.queries[0]["query_id"], "q001")
        self.assertEqual(parsed.queries[0]["text"], "What is the revenue in 2023?")
        
        # Check qrels
        self.assertIn("q001", parsed.qrels)
        self.assertEqual(parsed.qrels["q001"]["annual_report_page_0001"], 1)
        self.assertEqual(parsed.qrels["q001"]["annual_report_page_0003"], 1)
        self.assertIn("q002", parsed.qrels)
        self.assertEqual(parsed.qrels["q002"]["market_analysis_page_0005"], 1)

    def test_duplicate_query_id_rejected(self):
        bad_raw = {
            "examples": [
                {
                    "uid": "dup_01",
                    "query": "Query 1",
                    "meta_info": {"file_name": "doc.pdf", "reference_page": [1]},
                },
                {
                    "uid": "dup_01",
                    "query": "Query 2",
                    "meta_info": {"file_name": "doc.pdf", "reference_page": [2]},
                },
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            parse_vidoseek_annotations(bad_raw)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_empty_query_rejected(self):
        bad_raw = {
            "examples": [
                {
                    "uid": "q_empty",
                    "query": "   ",
                    "meta_info": {"file_name": "doc.pdf", "reference_page": [1]},
                }
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            parse_vidoseek_annotations(bad_raw)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_out_of_bounds_page_rejected(self):
        bad_raw = {
            "examples": [
                {
                    "uid": "q_oob",
                    "query": "Query",
                    "meta_info": {"file_name": "doc.pdf", "reference_page": [15]},
                }
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            parse_vidoseek_annotations(bad_raw, doc_page_counts={"doc.pdf": 10})
        self.assertIn("page", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
