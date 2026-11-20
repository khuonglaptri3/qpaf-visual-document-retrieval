"""Regression tests for published run boundaries and consumed-input provenance."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import importlib.util
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qpaf.jev import cli, owners

FINALIZER = ROOT / "docs/reports/tasks/jev-runnable-team-kit-20261120/evidence/finalize_artifacts.py"


class PublicationTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def save(self, name, value):
        path = self.root / name
        path.write_bytes(json.dumps(value).encode())
        return path

    def run_cli(self, *args):
        errors = StringIO()
        with redirect_stdout(StringIO()), redirect_stderr(errors):
            code = cli.main(list(map(str, args)))
        return code, errors.getvalue()

    def pool(self):
        return self.save("pool.json", {
            "dataset": "vidoseek", "top_k": 1, "queries": {"q": "question", "r": "second"},
            "pages": {"p": "page"}, "pairs": [["q", "p"], ["r", "p"]],
        })

    def splits(self, q, r):
        return self.save("splits.json", {"splits": {"q": q, "r": r}, "groups": {"q": "g", "r": "h"}})

    def test_partitioned_source_keeps_its_role_on_reimport(self):
        pool, splits = self.pool(), self.splits("test", "test")
        source = self.root / "held-out"
        prepare = ["prepare", "--splits", splits, "--f9-pairs"]
        self.assertEqual(self.run_cli(*prepare, pool, "--partition", "test", "--out", source), (0, ""))
        ids = self.root / "ids.txt"
        ids.write_bytes(b"q\n")
        allowed = self.root / "subset"
        self.assertEqual(self.run_cli(*prepare, source / "pairs.json", "--partition", "test",
                                      "--query-ids", ids, "--out", allowed), (0, ""))
        subset = json.loads((allowed / "pairs.json").read_bytes())
        self.assertEqual((subset["partition"], subset["pairs"]), ("test", [["q", "p"]]))
        exact_copy = self.root / "copy"
        self.assertEqual(self.run_cli("prepare", "--f9-pairs", allowed / "pairs.json", "--out", exact_copy),
                         (0, ""))
        self.assertEqual((allowed / "pairs.json").read_bytes(), (exact_copy / "pairs.json").read_bytes())
        self.assertEqual(json.loads((exact_copy / "manifest.json").read_bytes())["partition"], "test")
        self.splits("train", "test")
        dest = self.root / "relabelled"
        code, error = self.run_cli(*prepare, source / "pairs.json", "--partition", "train", "--out", dest)
        self.assertEqual(code, 2, error)
        self.assertIn("partition", error)
        self.assertFalse(dest.exists())

    def test_export_rejects_mixed_assignments_in_explicit_train_bundle(self):
        pool = self.pool()
        source = self.root / "trained"
        splits = self.splits("train", "train")
        self.assertEqual(self.run_cli("prepare", "--f9-pairs", pool, "--splits", splits,
                                      "--partition", "train", "--out", source), (0, ""))
        self.splits("train", "test")
        qrels = self.save("qrels.json", {"q": {"p": 1}, "r": {"p": 1}})
        dest = self.root / "rows.jsonl"
        code, error = self.run_cli("export-train", "--pairs", source / "pairs.json", "--splits", splits,
                                   "--qrels", qrels, "--out", dest)
        self.assertEqual(code, 2, error)
        self.assertIn("partition", error)
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_suffix(".jsonl.manifest.json").exists())

    def test_shared_demo_preserves_an_occupied_directory(self):
        dest = self.root / "demo"
        dest.mkdir()
        sentinel = dest / "qrels.json"
        sentinel.write_bytes(b"original external judgments")
        code, error = self.run_cli("demo", "--out", dest)
        self.assertEqual(code, 2, error)
        self.assertIn("demo output directory", error)
        self.assertEqual(list(dest.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"original external judgments")

    def test_prepare_preserves_previous_imported_run(self):
        pool, dest = self.pool(), self.root / "prepared"
        cache = self.save("cache.json", {"pairs_sha256": sha256(pool.read_bytes()).hexdigest(),
                                        "scores": [1, 2], "manifest": {"model": "legacy"}})
        prepare = ("prepare", "--f9-pairs", pool, "--out", dest)
        self.assertEqual(self.run_cli(*prepare, "--import-scores", cache), (0, ""))
        previous = {p.name: p.read_bytes() for p in dest.iterdir()}
        self.assertIn("score_cache", json.loads(previous["manifest.json"])["inputs_sha256"])
        code, error = self.run_cli(*prepare)
        self.assertEqual(code, 2, error)
        self.assertIn("prepare output directory", error)
        self.assertEqual({p.name: p.read_bytes() for p in dest.iterdir()}, previous)

    def test_prepare_late_failure_does_not_publish_a_partial_run(self):
        pool, out = self.pool(), self.root / "prepared"
        with patch.object(cli, "write_json", side_effect=OSError("manifest write failed")):
            code, error = self.run_cli("prepare", "--f9-pairs", pool, "--out", out)
        self.assertEqual(code, 2, error)
        self.assertIn("manifest write failed", error)
        self.assertFalse(out.exists())
        self.assertEqual(self.run_cli("prepare", "--f9-pairs", pool, "--out", out), (0, ""))

    def test_khuong_rejects_editable_trainer_flags_before_running_workflow(self):
        config_path = self.root / "configs/jev/khuong.json"
        config_path.parent.mkdir(parents=True)
        config = json.loads((ROOT / "configs/jev/khuong.json").read_bytes())
        config["training_args"] = ["--execute", "--data", str(self.root / "private.jsonl"),
                                   "--out", str(self.root / "external")]
        config_path.write_bytes(json.dumps(config).encode())

        def guarded_train(args):
            # Prevent any trainer or model hub call even on the broken implementation.
            raise ValueError(f"unexpected trainer dispatch with execute={args.execute}, data={args.data}")
        errors = StringIO()
        with (patch.object(owners, "ROOT", self.root), patch.object(cli, "train", guarded_train),
              redirect_stdout(StringIO()), redirect_stderr(errors)):
            code = owners.main("khuong", ["--out", str(self.root / "demo")])
        self.assertEqual(code, 2)
        self.assertIn("training_args", errors.getvalue())
        self.assertFalse((self.root / "demo").exists())
        self.assertFalse((self.root / "external").exists())

    def test_configured_max_steps_is_a_positive_integer(self):
        config_path = self.root / "configs/jev/khuong.json"
        config_path.parent.mkdir(parents=True)
        config = json.loads((ROOT / "configs/jev/khuong.json").read_bytes())
        for invalid in (True, 0, "--execute", ["--out", "outside"]):
            with self.subTest(invalid=invalid):
                config_path.write_bytes(json.dumps({**config, "max_steps": invalid}).encode())
                with (patch.object(owners, "ROOT", self.root), redirect_stdout(StringIO()),
                      redirect_stderr(StringIO()) as errors):
                    self.assertEqual(owners.main("khuong", ["--out", str(self.root / "demo")]), 2)
                self.assertIn("max_steps", errors.getvalue())
                self.assertFalse((self.root / "demo").exists())

    def test_concurrent_claim_of_prepare_destination_preserves_new_owner(self):
        pool, dest = self.pool(), self.root / "prepared"
        sentinel = dest / "sentinel.txt"
        original_write = cli.write_json

        def claim_while_staging(path, value):
            original_write(path, value)
            self.assertFalse(dest.exists())
            dest.mkdir()
            sentinel.write_bytes(b"other owner")

        with patch.object(cli, "write_json", claim_while_staging):
            code, error = self.run_cli("prepare", "--f9-pairs", pool, "--out", dest)
        self.assertEqual(code, 2, error)
        self.assertIn("prepare output directory", error)
        self.assertEqual(list(dest.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"other owner")

    def test_prepare_hashes_inputs_consumed_before_source_replacement(self):
        paths = {"queries": self.save("queries.json", {"q": "original query"}),
                 "page_text": self.save("pages.json", {"a": "original page", "b": "other"}),
                 "units": self.save("units.json", {"a": "doc-a", "b": "doc-b"}),
                 "query_ids": self.root / "ids.txt"}
        paths["query_ids"].write_bytes(b"q\r\n")
        rows = [{"query_id": "q", "page_id": "a", "base_score": 2},
                {"query_id": "q", "page_id": "b", "base_score": 1}]
        paths["raw_scores"] = self.save("rows.json", rows)
        digests = {key: sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}
        original_prepare = cli.prepare_candidates

        def replace_sources(*args, **kwargs):
            bundle = original_prepare(*args, **kwargs)
            self.save("queries.json", {"q": "new question"})
            self.save("pages.json", {"a": "new page", "b": "other"})
            self.save("units.json", {"a": "different", "b": "doc-b"})
            paths["query_ids"].write_bytes(b"r\n")
            self.save("rows.json", [{**rows[0], "base_score": 0}, rows[1]])
            return bundle

        dest = self.root / "prepared"
        with patch.object(cli, "prepare_candidates", replace_sources):
            code, error = self.run_cli("prepare", "--dataset", "test", "--top-k", "1", "--out", dest,
                                       "--queries", paths["queries"], "--page-text", paths["page_text"],
                                       "--raw-scores", paths["raw_scores"], "--units", paths["units"],
                                       "--query-ids", paths["query_ids"])
        self.assertEqual(code, 0, error)
        bundle = json.loads((dest / "pairs.json").read_bytes())
        self.assertEqual((bundle["pairs"], bundle["queries"]["q"], bundle["pages"]["a"], bundle["units"]["a"]),
                         ([["q", "a"]], "original query", "original page", "doc-a"))
        self.assertEqual(json.loads((dest / "manifest.json").read_bytes())["inputs_sha256"], digests)

    def test_compare_hashes_reports_and_groups_consumed_before_replacement(self):
        report = {"synthetic": True, "per_query": {"q": {"mrr@10": 0}}}
        left = self.save("left.json", report)
        right = self.save("right.json", {**report, "per_query": {"q": {"mrr@10": 1}}})
        groups = self.save("groups.json", {"q": "g"})
        paths = {"left": left, "right": right, "groups": groups}
        expected = {k: sha256(p.read_bytes()).hexdigest() for k, p in paths.items()}
        original_compare = cli.compare

        def replace_sources(*args):
            result = original_compare(*args)
            for path in paths.values():
                path.write_bytes(b"{}")
            return result

        dest = self.root / "result.json"
        with patch.object(cli, "compare", replace_sources):
            code, error = self.run_cli("compare", "--left", left, "--right", right, "--groups", groups,
                                       "--resamples", "2", "--out", dest)
        self.assertEqual(code, 0, error)
        result = json.loads(dest.read_bytes())
        self.assertEqual(result["metrics"]["mrr@10"]["delta"], 1)
        self.assertEqual(result["inputs_sha256"], expected)

    def test_parquet_hash_identifies_the_consumed_ranking_after_replacement(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("Parquet preparation requires optional pyarrow")
        queries = self.save("queries.json", {"q": "question"})
        pages = self.save("pages.json", {"a": "one", "b": "two"})
        data = self.root / "rows.parquet"

        def parquet(scores):
            pq.write_table(pa.table({"query_id": ["q", "q"], "page_id": ["a", "b"], "base_score": scores}), data)

        parquet([2, 1])
        digest = sha256(data.read_bytes()).hexdigest()
        original = cli.prepare_candidates

        def replace(*args, **kwargs):
            bundle = original(*args, **kwargs)
            parquet([0, 1])
            return bundle

        dest = self.root / "prepared"
        with patch.object(cli, "prepare_candidates", replace):
            code, error = self.run_cli("prepare", "--dataset", "test", "--queries", queries,
                                       "--page-text", pages, "--raw-scores", data, "--top-k", "1", "--out", dest)
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads((dest / "pairs.json").read_bytes())["pairs"], [["q", "a"]])
        self.assertNotEqual(sha256(data.read_bytes()).hexdigest(), digest)
        self.assertEqual(json.loads((dest / "manifest.json").read_bytes())["inputs_sha256"]["raw_scores"], digest)


class InventoryTest(unittest.TestCase):
    def test_verifier_requires_each_expected_file_once_and_checks_size_and_digest(self):
        spec = importlib.util.spec_from_file_location("jev_finalizer", FINALIZER)
        finalizer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(finalizer)
        with TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence"
            evidence.mkdir()
            files = [root / "a", root / "b"]
            for path in files:
                path.write_bytes(path.name.encode())
            entries = [{"path": p.name, "bytes": 1, "sha256": sha256(p.read_bytes()).hexdigest()} for p in files]
            cases = {"missing": None, "empty": [], "omitted": entries[:1], "duplicate": [*entries, entries[0]],
                     "unexpected": [*entries, {**entries[0], "path": "../outside"}],
                     "wrong_size": [{**entries[0], "bytes": 2}, entries[1]],
                     "wrong_digest": [{**entries[0], "sha256": "0" * 64}, entries[1]],
                     "valid": list(reversed(entries))}
            manifest = evidence / "hashes.json"
            with patch.multiple(finalizer, ROOT=root, TASK=root, delivered_files=lambda: files,
                                validate=lambda: {"passed": True}), patch.object(sys, "argv", ["verify"]):
                for name, rows in cases.items():
                    with self.subTest(name=name), redirect_stdout(StringIO()) as log:
                        if rows is not None:
                            manifest.write_bytes(json.dumps({"files": rows}).encode())
                        code = finalizer.main()
                        self.assertEqual(code, 0 if name == "valid" else 1, log.getvalue())
                        self.assertEqual(json.loads(log.getvalue())["passed"], name == "valid")
