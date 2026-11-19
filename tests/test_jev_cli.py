"""Run the real Jev CLI with site packages disabled and from another cwd."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_jev.py"


class CliTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cwd = Path(folder.name)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-S", str(SCRIPT), *args],
            cwd=self.cwd, capture_output=True, text=True, check=False,
        )

    def read(self, path):
        return json.loads((self.cwd / path).read_text(encoding="utf-8"))

    def save(self, filename, value):
        (self.cwd / filename).write_text(json.dumps(value), encoding="utf-8")

    def test_demo_writes_cache_and_evaluation_marked_as_synthetic(self):
        result = self.cli("demo", "--out", "demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.read("demo/pairs.json")["synthetic"])
        self.assertTrue(self.read("demo/scores.json")["manifest"]["synthetic"])
        self.assertTrue(self.read("demo/evaluation.json")["synthetic"])
        with (self.cwd / "demo/evaluation.csv").open(encoding="utf-8", newline="") as file:
            self.assertEqual(len(list(csv.DictReader(file))), 2)
        self.assertTrue(self.read("demo/comparison.json")["synthetic"])

    def test_doctor_diagnoses_missing_private_inputs(self):
        result = self.cli("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli("--help").returncode, 0)
        result = self.cli("doctor", "--dataset", "vidoseek", "--f9-bundle", "private", "--page-text", "pages.jsonl")
        self.assertNotEqual(result.returncode, 0)
        for name in ("raw_scores.parquet", "queries.json", "test_ids.txt", "pages.jsonl", "prepare"):
            self.assertIn(name, result.stderr)

    def test_imported_f9_bytes_allow_existing_cache_evaluation(self):
        raw = (b'{"dataset":"vimdoc","top_k":2,"queries":{"q":"text"},'
               b'"pages":{"a":"A","b":"B"},"pairs":[["q","a"],["q","b"]]}\r\n')
        (self.cwd / "f9_pairs.json").write_bytes(raw)
        self.save("f9_scores.json", {
            "pairs_sha256": hashlib.sha256(raw).hexdigest(),
            "manifest": {"model": "legacy F9"},
            "scores": [0.1, 0.9],
        })
        result = self.cli("prepare", "--f9-pairs", "f9_pairs.json", "--out", "prep")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.cwd / "prep/pairs.json").read_bytes(), raw)
        self.save("qrels.json", {"q": {"b": 1, "outside": 1}})
        common = ("evaluate", "--pairs", "prep/pairs.json", "--qrels", "qrels.json")
        result = self.cli(*common, "--scores", "f9_scores.json", "--out", "metrics.json", "--csv", "metrics.csv")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read("metrics.json")["mean"]["recall@10"], 0.5)
        result = self.cli(*common, "--baseline")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("base_scores", result.stderr)

        self.save("units.json", {"a": "document", "b": "document"})
        self.save("doc-qrels.json", {"q": {"document": 1}})
        result = self.cli(
            "evaluate", "--pairs", "prep/pairs.json", "--scores", "f9_scores.json",
            "--qrels", "doc-qrels.json", "--units", "units.json", "--out", "doc-metrics.json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read("doc-metrics.json")["mean"]["recall@10"], 1)
        self.assertEqual(self.read("doc-metrics.json")["ranking_scope"], "provided_candidate_pool")

    def test_native_vimdoc_bundle_reads_only_label_free_inputs(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("native Parquet preparation requires optional pyarrow")
        folder = self.cwd / "private"
        folder.mkdir()
        pq.write_table(pa.table({
            "query_id": ["q", "q", "excluded"],
            "page_id": ["a1", "a2", "b"],
            "document_id": ["a", "a", "b"],
            "bm25": [1.0, 2.0, 3.0],
            "dense": [0.0, 0.0, 0.0],
            "visual": [0.0, 0.0, 0.0],
            "relevance": [9, 0, 9],
        }), folder / "candidate_scores.parquet")
        (folder / "queries.jsonl").write_text(
            '{"query_id":"q","text":"question"}\n{"query_id":"excluded","text":"other"}\n', encoding="utf-8"
        )
        (folder / "confirmation_qrels.sealed.json").write_text("invalid JSON", encoding="utf-8")
        (self.cwd / "query_ids.txt").write_text("q\n", encoding="utf-8")
        self.save("pages.json", {"a1": "a", "a2": ""})
        result = subprocess.run(
            [
                sys.executable, str(SCRIPT), "prepare", "--dataset", "vimdoc", "--f9-bundle", "private",
                "--query-ids", "query_ids.txt", "--page-text", "pages.json", "--weights", "1", "0", "0",
                "--top-k", "1", "--out", "prep",
            ],
            cwd=self.cwd, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        prepared = self.read("prep/pairs.json")
        self.assertEqual(prepared["pairs"], [["q", "a2"]])
        self.assertEqual(prepared["units"], {"a2": "a"})
        self.assertEqual(prepared["pages"], {"a2": ""})
        self.assertEqual(self.read("prep/manifest.json")["empty_ocr_pages"], 1)

    def test_raw_csv_preparation_and_explicit_baseline_comparison(self):
        self.save("queries.json", {"q": "query"})
        (self.cwd / "pages.jsonl").write_text(
            '{"page_id":"a","text":""}\n{"page_id":"b","text":"text"}\n', encoding="utf-8"
        )
        (self.cwd / "raw.csv").write_text(
            "query_id,page_id,base_score,relevance\nq,a,1,1\nq,b,2,0\n", encoding="utf-8"
        )
        result = self.cli(
            "prepare", "--dataset", "synthetic", "--queries", "queries.json", "--page-text", "pages.jsonl",
            "--raw-scores", "raw.csv", "--top-k", "1", "--synthetic", "--out", "prep",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read("prep/pairs.json")["pairs"], [["q", "b"]])
        self.assertEqual(self.read("prep/base_scores.json")["scores"], [2])
        self.save("qrels.json", {"q": {"b": 1}})
        result = self.cli(
            "evaluate", "--pairs", "prep/pairs.json", "--baseline", "--qrels", "qrels.json", "--out", "left.json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read("left.json")["mean"]["mrr@10"], 1)
        result = self.cli(
            "compare", "--left", "left.json", "--right", "left.json", "--out", "cmp.json", "--csv", "cmp.csv",
            "--resamples", "10",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read("cmp.json")["metrics"]["mrr@10"]["delta"], 0)

    def test_partition_rewrites_paired_scores_and_keeps_only_its_queries(self):
        self.save("old-pairs.json", {
            "dataset": "example", "top_k": 2, "queries": {"train": "training", "test": "testing"},
            "pages": {"a": "", "b": "B", "c": "C"}, "units": {"a": "X", "b": "Y", "c": "Z"},
            "pairs": [["test", "c"], ["train", "a"], ["test", "b"]], "base_scores": [3, 4, 2],
        })
        old_digest = hashlib.sha256((self.cwd / "old-pairs.json").read_bytes()).hexdigest()
        self.save("old-scores.json", {
            "pairs_sha256": old_digest, "manifest": {"model": "example scores"}, "scores": [7, 8, 6],
        })
        manifest = {"splits": {"test": "test", "train": "train"}, "groups": {"test": "g", "train": "h"}}
        self.save("splits.json", manifest)
        args = (
            "prepare", "--f9-pairs", "old-pairs.json", "--import-scores", "old-scores.json",
            "--splits", "splits.json", "--partition", "test", "--out", "prep",
        )
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        bundle = self.read("prep/pairs.json")
        self.assertEqual(bundle["queries"], {"test": "testing"})
        self.assertEqual(bundle["pages"], {"c": "C", "b": "B"})
        self.assertEqual(bundle["units"], {"c": "Z", "b": "Y"})
        self.assertEqual(bundle["pairs"], [["test", "c"], ["test", "b"]])
        self.assertEqual(bundle["base_scores"], [3, 2])
        rebound = self.read("prep/scores.json")
        self.assertEqual(rebound["scores"], [7, 6])
        digest = hashlib.sha256((self.cwd / "prep/pairs.json").read_bytes()).hexdigest()
        self.assertNotEqual(digest, old_digest)
        self.assertEqual(rebound["pairs_sha256"], digest)
        self.assertEqual(self.read("prep/manifest.json")["partition"], "test")

        manifest["groups"]["train"] = "g"
        self.save("splits.json", manifest)
        result = self.cli(*args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("group", result.stderr)
        self.assertEqual(hashlib.sha256((self.cwd / "prep/pairs.json").read_bytes()).hexdigest(), digest)
