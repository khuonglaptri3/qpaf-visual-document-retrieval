"""Exercise owner scripts and native development evaluation without site packages."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class OwnerWorkflowsTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cwd = Path(folder.name)

    def run_script(self, owner, *args):
        script = "run_jev.py" if owner is None else f"run_jev_{owner}.py"
        return subprocess.run(
            [sys.executable, "-I", "-S", str(SCRIPTS / script), *args],
            cwd=self.cwd, capture_output=True, text=True, check=False,
        )

    def read(self, name):
        return json.loads((self.cwd / name).read_text(encoding="utf-8"))

    def save(self, name, data):
        (self.cwd / name).write_text(json.dumps(data), encoding="utf-8")

    def digest(self, name):
        return hashlib.sha256((self.cwd / name).read_bytes()).hexdigest()

    def test_phat_prepares_partition_and_byte_bound_baseline(self):
        result = self.run_script("phat", "--out", "demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        splits = self.read("demo/splits.json")
        self.assertEqual(splits["splits"], {"q1": "train", "q2": "validation"})
        self.assertNotEqual(splits["groups"]["q1"], splits["groups"]["q2"])
        pairs = self.read("demo/prepared/pairs.json")
        self.assertIs(pairs["synthetic"], True)
        self.assertEqual(pairs["pairs"], [["q1", "p1"], ["q1", "p3"]])
        self.assertEqual(pairs["base_scores"], [1, 2])
        manifest = self.read("demo/prepared/manifest.json")
        self.assertEqual(manifest["partition"], "train")
        self.assertEqual(manifest["empty_ocr_pages"], 1)
        self.assertEqual(manifest["inputs_sha256"]["splits"], self.digest("demo/splits.json"))
        cache = self.read("demo/prepared/base_scores.json")
        self.assertIs(cache["manifest"]["synthetic"], True)
        self.assertEqual(cache["pairs_sha256"], self.digest("demo/prepared/pairs.json"))
        self.assertEqual(cache["scores"], [1, 2])
        self.assertIn("Score length, values and input hash verified.", result.stdout)

    def test_thanh_evaluates_supplied_baseline_and_toy_scores_with_csv(self):
        result = self.run_script("thanh", "--out", "demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name, mrr in (("baseline", 0.5), ("evaluation", 1.0)):
            report = self.read(f"demo/{name}.json")
            self.assertIs(report["synthetic"], True)
            self.assertEqual(report["ranking_scope"], "provided_candidate_pool")
            self.assertEqual(report["mean"]["mrr@10"], mrr)
            self.assertEqual(report["mean"]["recall@10"], 0.75)
        cache = self.read("demo/scores.json")
        self.assertEqual(cache["scores"], [2, 0, 2, 0])
        self.assertEqual(cache["pairs_sha256"], self.digest("demo/prepared/pairs.json"))
        comparison = self.read("demo/comparison.json")
        self.assertIs(comparison["synthetic"], True)
        self.assertEqual(comparison["metrics"]["mrr@10"]["delta"], 0.5)
        with (self.cwd / "demo/comparison.csv").open(encoding="utf-8", newline="") as stream:
            row = next(row for row in csv.DictReader(stream) if row["metric"] == "mrr@10")
        self.assertEqual((row["synthetic"], row["delta"], row["win"]), ("True", "0.5", "2"))

    def test_khuong_exports_train_labels_and_writes_matched_dry_run_plans(self):
        result = self.run_script("khuong", "--out", "demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in (self.cwd / "demo/train.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(row["_meta"]["split"], row["_meta"]["query_id"], row["_meta"]["page_id"],
                           row["questions"]["relevant"]["label"]) for row in rows],
                         [("train", "q1", "p1", True), ("train", "q1", "p3", False)])
        manifest = self.read("demo/train.jsonl.manifest.json")
        self.assertIs(manifest["synthetic"], True)
        self.assertEqual((manifest["split"], manifest["label_unit"], manifest["records"]), ("train", "page", 2))
        self.assertEqual(manifest["data_sha256"], self.digest("demo/train.jsonl"))
        plans = {init: self.read(f"demo/{init}-plan.json") for init in ("kev", "base")}
        for init, plan in plans.items():
            self.assertEqual(plan["init"], init)
            self.assertEqual(plan["export"], manifest)
            self.assertFalse((self.cwd / f"demo/{init}-checkpoint").exists())
        kev, base = (plans[init]["argv"] for init in ("kev", "base"))
        self.assertEqual(kev[-2], "--init_from")
        self.assertTrue(kev[-1].startswith("jaredpalmer/kev-4b@"))
        for argv in (kev, base):
            self.assertEqual(argv[argv.index("--max_steps") + 1], "1")
            for flag in ("--data", "--out"):
                argv[argv.index(flag) + 1] = "arm-specific path"
        self.assertEqual(kev[:-2], base)

    def test_demo_rejects_existing_output_directory(self):
        self.save("untouched.json", {"sentinel": True})
        for owner in ("phat", "thanh", "khuong"):
            with self.subTest(owner=owner):
                result = self.run_script(owner, "--out", ".")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("output directory", result.stderr)
                self.assertEqual(list(self.cwd.iterdir()), [self.cwd / "untouched.json"])

    def test_owner_commands_report_missing_explicit_input(self):
        cases = {
            "phat": ("prepare", "--f9-pairs", "absent.json", "--out", "prepared"),
            "thanh": ("score", "--backend", "baseline", "--pairs", "absent.json", "--out", "score.json"),
            "khuong": ("export-train", "--pairs", "absent.json", "--splits", "split.json",
                       "--qrels", "qrels.json", "--out", "train.jsonl"),
        }
        for owner, args in cases.items():
            with self.subTest(owner=owner):
                result = self.run_script(owner, *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("Jev:", result.stderr)
                self.assertIn("absent.json", result.stderr)
        self.assertEqual(list(self.cwd.iterdir()), [])

    def doc_inputs(self):
        self.save("pairs.json", {
            "dataset": "vimdoc", "synthetic": True, "partition": "validation", "top_k": 3,
            "queries": {"q2": "query"}, "pages": {"p1": "a", "p2": "b", "p3": "c"},
            "pairs": [["q2", "p1"], ["q2", "p2"], ["q2", "p3"]], "base_scores": [0, 3, 2],
        })
        self.save("units.json", {"p1": "d1", "p2": "d1", "p3": "d2"})
        self.save("qrels.json", {"train": {"q1": ["d1"]}, "validation": {"q2": ["d1", "outside"]}})
        return ("evaluate", "--pairs", "pairs.json", "--baseline", "--qrels", "qrels.json")

    def test_native_vimdoc_qrels_preserve_out_of_pool_documents_and_max_pool(self):
        common = self.doc_inputs()
        result = self.run_script(None, *common, "--units", "units.json", "--k", "1")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        result = self.run_script(None, *common, "--units", "units.json", "--k", "1", "--qrels-format", "vimdoc-dev")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["qrels_format"], "vimdoc-dev")
        self.assertEqual(report["qrels_sha256"], self.digest("qrels.json"))
        self.assertEqual(report["units_sha256"], self.digest("units.json"))
        self.assertEqual(report["mean"], {"ndcg@1": 1.0, "mrr@1": 1.0, "recall@1": 0.5, "recall@20": 0.5})

    def test_native_vimdoc_requires_the_document_map(self):
        common = self.doc_inputs()
        result = self.run_script(None, *common, "--qrels-format", "vimdoc-dev")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("page-to-document mapping", result.stderr)
        self.save("units.json", {"p1": "d1", "p2": "d1"})
        result = self.run_script(None, *common, "--units", "units.json", "--qrels-format", "vimdoc-dev")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("page-to-document mapping", result.stderr)

    def test_native_vimdoc_uses_embedded_units(self):
        common = self.doc_inputs()
        pairs = self.read("pairs.json")
        pairs["units"] = self.read("units.json")
        self.save("pairs.json", pairs)
        result = self.run_script(None, *common, "--qrels-format", "vimdoc-dev")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["mean"]["recall@20"], 0.5)
        self.assertNotIn("units_sha256", report)

    def test_native_vimdoc_rejects_ambiguous_roles_and_judgments(self):
        common = (*self.doc_inputs(), "--units", "units.json", "--qrels-format", "vimdoc-dev")
        cases = (
            ({"train": {"q2": ["d1"]}, "validation": {"q2": ["d1"]}}, "duplicate query"),
            ({"train": {}, "validation": {"q2": ["d1", "d1"]}}, "duplicate document"),
            ({"train": {"q2": ["d1"]}, "validation": {}}, "validation partition"),
            ({"train": {}, "validation": {"q2": ["d1"]}, "test": {}}, "train and validation"),
            ({"train": {}, "validation": {"q2": {"d1": 1}}}, "document IDs"),
        )
        for qrels, message in cases:
            with self.subTest(qrels=qrels):
                self.save("qrels.json", qrels)
                result = self.run_script(None, *common)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(message, result.stderr)

    def test_compare_rejects_changed_known_unit_map_and_allows_legacy_unknown(self):
        common = (*self.doc_inputs(), "--units", "units.json")
        self.save("qrels.json", {"q2": {"d1": 1}})
        result = self.run_script(None, *common, "--out", "left.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.save("units.json", {"p1": "d1", "p2": "d2", "p3": "d2"})
        result = self.run_script(None, *common, "--out", "right.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        compare = ("compare", "--left", "left.json", "--right", "right.json", "--resamples", "5")
        result = self.run_script(None, *compare)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("units_sha256", result.stderr)
        right = self.read("right.json")
        del right["units_sha256"]
        self.save("right.json", right)
        result = self.run_script(None, *compare)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
