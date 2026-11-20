"""Exercise the train-only export and the two controlled training commands."""
import json
import contextlib
import io
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qpaf.jev.contracts import write_json
from qpaf.jev.cli import main


def dataset(root):
    bundle = {
        "dataset": "synthetic", "synthetic": True, "top_k": 3,
        "queries": {"q": "fruit", "hold": "held out"},
        "pages": {"a": "apple", "b": "car", "c": ""},
        "pairs": [["q", "a"], ["hold", "a"], ["q", "c"], ["q", "b"]],
        "base_scores": [-1, 3, 6, 2],
    }
    write_json(root / "pairs", bundle)
    write_json(root / "qrels", {"q": {"a": 2, "b": 0}, "hold": {"a": 1}})
    write_json(root / "splits", {"splits": {"q": "train", "hold": "test"}, "groups": {"q": "g", "hold": "h"}})
    return bundle


def cli(root, *args, isolated=True):
    return subprocess.run([sys.executable, *(["-I", "-S"] if isolated else []),
                           str(ROOT / "scripts/run_jev.py"), *map(str, args)],
                          cwd=root, capture_output=True, encoding="utf-8", errors="replace")


EXPORT = ["export-train", "--pairs", "pairs", "--qrels", "qrels", "--splits", "splits", "--out", "train.jsonl"]


class TrainingTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bundle = dataset(self.root)

    def export(self, *extra):
        result = cli(self.root, *EXPORT, *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in (self.root / "train.jsonl").read_bytes().splitlines()]

    def test_only_assigned_judged_pages_become_labelled_requests(self):
        records = self.export()
        self.assertEqual([r["state"] for r in records], ["apple", "car"])
        self.assertEqual([r["questions"]["relevant"]["label"] for r in records], [True, False])
        for row in records:
            self.assertIs(type(row["questions"]["relevant"]["label"]), bool)
            self.assertEqual(row["questions"]["relevant"]["type"], "noul")
            self.assertIn("fruit", row["questions"]["relevant"]["instructions"])
            self.assertEqual(row["_meta"]["group_id"], "g")
        with_unknown = self.export("--unjudged-as-negative")
        self.assertEqual([(r["_meta"]["page_id"], r["questions"]["relevant"]["label"]) for r in with_unknown],
                         [("a", True), ("c", False), ("b", False)])
        self.assertEqual(with_unknown[1]["_meta"]["judgment"], "unjudged-as-negative")

    def test_document_level_and_leaky_groups_rejected(self):
        for changes in [{"dataset": "ViMDoc"}, {"units": {"a": "doc", "b": "doc", "c": "doc"}}]:
            write_json(self.root / "pairs", {**self.bundle, **changes})
            result = cli(self.root, *EXPORT, "--unjudged-as-negative")
            self.assertIn("document", result.stderr.lower())
            self.assertFalse((self.root / "train.jsonl").exists())
        dataset(self.root)
        write_json(self.root / "splits", {"splits": {"q": "train", "hold": "test"}, "groups": {"q": "g", "hold": "g"}})
        self.assertIn("spans partitions", cli(self.root, *EXPORT).stderr)

    def test_dry_run_controls_only_differ_in_initial_checkpoint(self):
        self.export()
        commands = []
        for init in ("base", "kev"):
            result = cli(self.root, "train", "--init", init, "--data", "train.jsonl", "--out", "new")
            self.assertEqual(result.returncode, 0, result.stderr)
            commands.append(json.loads(result.stdout)["argv"])
        base, warm = commands
        offset = warm.index("--init_from")
        self.assertEqual(base, warm[:offset] + warm[offset + 2:])
        self.assertIn("@6cfce5c2fa4b4bd64026336ab649c5ca78857d52", warm[offset + 1])
        for option in ("--p_none", "--p_distract", "--p_none_distract", "--p_none_pair"):
            self.assertEqual(base[base.index(option) + 1], "0")
        self.assertIn("kev.train", base)
        self.assertFalse((self.root / "new").exists())

    def test_train_refuses_mutated_export_before_starting_trainer(self):
        self.export()
        with (self.root / "train.jsonl").open("ab") as stream:
            stream.write(b"\n")
        result = cli(self.root, "train", "--init", "base", "--data", "train.jsonl", "--out", "new", "--execute")
        self.assertIn("sha256", result.stderr)
        self.assertFalse((self.root / "new").exists())

    def execute_args(self, out):
        return ["train", "--init", "base", "--data", str(self.root / "train.jsonl"), "--out", str(out),
                "--epochs", "2", "--max-steps", "1", "--execute"]

    def test_run_provenance_separates_context_drops_from_budgeted_visits(self):
        self.export("--unjudged-as-negative")
        out = self.root / "new"

        def run(*_, **__):
            out.mkdir()
            for name in ("adapter_config.json", "adapter_model.safetensors", "head.pt", "training_config.json"):
                (out / name).write_bytes(b"checkpoint")
            write_json(out / "training_metrics.json", {"requested_records": 4, "records_seen": 1, "optimizer_steps": 1})
            return subprocess.CompletedProcess([], 0)

        with patch("qpaf.jev.training.require_kev_source"), patch("qpaf.jev.training.subprocess.run", side_effect=run):
            self.assertEqual(main(self.execute_args(out)), 0)
        manifest = json.loads((out / "jev-run.json").read_bytes())
        self.assertEqual(manifest.get("training_records"), {"exported": 3, "admitted": 2, "dropped_for_context": 1,
                         "scheduled_visits": 4, "actual_visits": 1, "unvisited": 3, "optimizer_steps": 1})

    def test_failed_snapshot_write_leaves_no_partial_snapshot(self):
        self.export()
        open_path = Path.open

        @contextlib.contextmanager
        def broken_stream(stream):
            with stream:
                class FailedWrite:
                    def write(self, data):
                        stream.write(data[:1])
                        raise OSError("snapshot write failed")

                yield FailedWrite()

        def open_file(path, mode="r", *args, **kwargs):
            stream = open_path(path, mode, *args, **kwargs)
            return broken_stream(stream) if mode == "xb" else stream

        with patch("qpaf.jev.training.require_kev_source"), patch.object(Path, "open", open_file), \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertNotEqual(main(self.execute_args(self.root / "new")), 0)
        self.assertIn("snapshot write failed", stderr.getvalue())
        self.assertFalse(list(self.root.glob(".*.input.jsonl")))
