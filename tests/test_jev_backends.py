"""CLI and no-download runtime tests for the actual rerankers and Kev trainer."""
import contextlib
from concurrent.futures import ThreadPoolExecutor
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
from types import SimpleNamespace
import unittest
from unittest.mock import patch

if __package__:
    from .test_jev_training import ROOT, EXPORT, cli, dataset
else:
    from test_jev_training import ROOT, EXPORT, cli, dataset

from qpaf.jev.cli import main
from qpaf.jev.contracts import load_scores, write_json
from qpaf.jev.backends import tree_hash


class LocalWeightIdentityTest(unittest.TestCase):
    def assert_shard_mutation_changes_identity(self, model, shard_name, index_name="model.safetensors.index.json"):
        shard = model / shard_name
        shard.write_bytes(b"old weights")
        write_json(model / index_name, {"metadata": {}, "weight_map": {
            "first.weight": shard_name, "second.weight": shard_name,
        }})
        old_identity = tree_hash(model)
        shard.write_bytes(b"new weights")
        self.assertNotEqual(tree_hash(model), old_identity)

    def test_shard_index_binds_a_file_under_the_local_cache(self):
        with TemporaryDirectory() as tmp:
            model = Path(tmp)
            (model / ".cache").mkdir()
            self.assert_shard_mutation_changes_identity(model, ".cache/weights.safetensors")

    def test_explicit_weights_archive_binds_a_file_under_the_local_cache(self):
        with TemporaryDirectory() as tmp:
            model = Path(tmp)
            (model / ".cache").mkdir()
            (model / "model.safetensors").write_bytes(b"default archive")
            archive_name = ".cache/selected.safetensors"
            write_json(model / "config.json", {"transformers_weights": archive_name})
            archive = model / archive_name
            archive.write_bytes(b"old selected weights")
            before = tree_hash(model)
            archive.write_bytes(b"new selected weights")
            self.assertNotEqual(tree_hash(model), before)

    def test_explicit_weights_index_binds_a_file_under_the_local_cache(self):
        with TemporaryDirectory() as tmp:
            model = Path(tmp)
            (model / ".cache").mkdir()
            (model / "model.safetensors").write_bytes(b"default archive")
            index_name = ".cache/selected.safetensors.index.json"
            write_json(model / "config.json", {"transformers_weights": index_name})
            self.assert_shard_mutation_changes_identity(model, ".cache/weights.safetensors", index_name)

    def test_explicit_weights_cannot_be_missing_or_escape_the_model_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "model"
            model.mkdir()
            (root / "outside.safetensors").write_bytes(b"external archive")
            (model / "model.safetensors").write_bytes(b"default archive")
            for name in ("missing.safetensors", "../outside.safetensors"):
                with self.subTest(name=name):
                    write_json(model / "config.json", {"transformers_weights": name})
                    with self.assertRaisesRegex(ValueError, "transformers_weights"):
                        tree_hash(model)

    def test_shard_index_binds_a_file_through_a_nested_symlinked_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model, target = root / "model", root / "actual-shards"
            (model / "shards").mkdir(parents=True)
            target.mkdir()
            try:
                (model / "shards/link").symlink_to(target, target_is_directory=True)
            except OSError as exc:
                if sys.platform == "win32" and exc.winerror in (5, 1314):
                    self.skipTest("creating Windows directory symlinks is not permitted")
                raise
            self.assert_shard_mutation_changes_identity(model, "shards/link/weights.safetensors")


class ScoringTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        dataset(self.root)
        runtime = patch("qpaf.jev.backends._runtime_identity", create=True, return_value={"hardware": "test"})
        self.runtime = runtime.start()
        self.addCleanup(runtime.stop)

    def model_args(self, backend="bge"):
        return ["score", "--backend", backend, "--pairs", str(self.root / "pairs"),
                "--out", str(self.root / "scores"), "--chunks", str(self.root / "chunks"), "--device", "cpu"]

    @staticmethod
    def adapter():
        return SimpleNamespace(score=lambda batch: ([1] * len(batch), 12), peak_bytes=lambda: None)

    def test_cached_scores_reject_a_changed_runtime(self):
        with patch("qpaf.jev.backends.load_adapter", return_value=self.adapter()):
            self.assertEqual(main(self.model_args()), 0)
        self.runtime.return_value = {"hardware": "different"}
        self.assertNotEqual(main(self.model_args()), 0)

    def test_cached_kev_scores_validate_source_pin(self):
        with patch("qpaf.jev.backends.require_kev_source"), patch("qpaf.jev.backends.load_adapter", return_value=self.adapter()):
            self.assertEqual(main(self.model_args("kev")), 0)
        with patch("qpaf.jev.backends.require_kev_source", side_effect=ValueError("wrong official Kev commit")):
            self.assertNotEqual(main(self.model_args("kev")), 0)

    def test_local_kev_scores_bind_the_base_declared_by_the_head(self):
        checkpoint = self.root / "checkpoint"
        checkpoint.mkdir()
        actual, decoy = self.root / "actual", self.root / "decoy"
        for base in (actual, decoy):
            base.mkdir()
            (base / "tokenizer.json").write_text("initial")
        write_json(checkpoint / "adapter_config.json", {"base_model_name_or_path": str(decoy)})
        official = SimpleNamespace(meta=SimpleNamespace(base=str(actual), base_revision=None))
        args = self.model_args("kev") + ["--checkpoint", str(checkpoint)]
        with patch("qpaf.jev.backends.require_kev_source"), \
             patch("qpaf.jev.backends._open_kev_checkpoint", create=True, return_value=official), \
             patch("qpaf.jev.backends.load_adapter", return_value=self.adapter()):
            self.assertEqual(main(args), 0)
            (actual / "tokenizer.json").write_text("changed")
            self.assertNotEqual(main(args), 0)

    def test_local_kev_rejects_an_unpinned_hub_backbone_before_scoring(self):
        checkpoint = self.root / "checkpoint"
        checkpoint.mkdir()
        write_json(checkpoint / "adapter_config.json", {"base_model_name_or_path": "org/base"})
        official = SimpleNamespace(meta=SimpleNamespace(base="org/base", base_revision="main"))
        with patch("qpaf.jev.backends.require_kev_source"), \
             patch("qpaf.jev.backends._open_kev_checkpoint", create=True, return_value=official), \
             patch("qpaf.jev.backends.load_adapter", return_value=self.adapter()):
            self.assertNotEqual(main(self.model_args("kev") + ["--checkpoint", str(checkpoint)]), 0)
        self.assertFalse((self.root / "scores").exists())

    def test_local_kev_rejects_changes_during_model_load_before_caching(self):
        checkpoint, base = self.root / "checkpoint", self.root / "base"
        checkpoint.mkdir()
        base.mkdir()
        write_json(checkpoint / "adapter_config.json", {"base_model_name_or_path": str(base)})
        tokenizer = base / "tokenizer.json"
        tokenizer.write_text("initial")
        official = SimpleNamespace(meta=SimpleNamespace(base=str(base), base_revision=None))

        def load(_):
            tokenizer.write_text("changed during load")
            return self.adapter()

        with patch("qpaf.jev.backends.require_kev_source"), \
             patch("qpaf.jev.backends._open_kev_checkpoint", create=True, return_value=official), \
             patch("qpaf.jev.backends.load_adapter", side_effect=load):
            self.assertNotEqual(main(self.model_args("kev") + ["--checkpoint", str(checkpoint)]), 0)
        self.assertFalse(list((self.root / "chunks").glob("chunk-*.json")))

    def test_different_configurations_cannot_both_claim_a_shared_chunk_directory(self):
        publication = Barrier(2)
        rename_path = Path.rename

        def write(path, row):
            if path == self.root / "chunks/config.json":
                publication.wait(timeout=10)
            return write_json(path, row)

        def rename(path, target):
            if target == self.root / "chunks/.jev-config":
                publication.wait(timeout=10)
            return rename_path(path, target)

        with patch("qpaf.jev.backends.write_json", side_effect=write), \
             patch.object(Path, "rename", rename), patch("qpaf.jev.backends.load_adapter", return_value=self.adapter()), \
             ThreadPoolExecutor(2) as pool:
            jobs = [pool.submit(main, self.model_args() + ["--input-cap", str(cap), "--out", str(self.root / f"scores-{cap}")])
                    for cap in (64, 128)]
            results = [job.result() for job in jobs]
        self.assertEqual(results.count(0), 1, results)
        self.assertEqual(len(list(self.root.glob("scores-*"))), 1)

    def test_modal_plans_reject_invalid_numeric_settings_before_loading_the_sdk(self):
        script = ROOT / "scripts/modal_jev_rerank.py"
        for argv, diagnostic in (
            (["score", "--backend", "kev", "--pairs", "pairs", "--out", "scores", "--batch-size", "0"], "batch size"),
            (["train", "--data", "data", "--out", "run", "--lr", "nan"], "lr"),
        ):
            for outer in ([], ["--execute"]):
                with self.subTest(argv=argv, outer=outer):
                    result = subprocess.run([sys.executable, "-I", "-S", str(script), "--volume", "test-volume", *outer, *argv],
                                            cwd=self.root, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stdout)
                    self.assertIn(diagnostic, result.stderr)

    def test_cpu_score_from_arbitrary_cwd(self):
        result = cli(self.root, "score", "--backend", "baseline", "--pairs", "pairs", "--out", "scores")
        self.assertEqual(result.returncode, 0, result.stderr)
        cache = load_scores(self.root / "scores", self.root / "pairs")
        self.assertEqual(cache["scores"], [-1, 3, 6, 2])
        self.assertTrue(cache["manifest"]["synthetic"])

    def test_modal_plan_without_sdk_uses_volume_paths_and_matching_environment(self):
        script = ROOT / "scripts/modal_jev_rerank.py"
        result = subprocess.run([sys.executable, "-I", "-S", str(script), "--volume", "test-volume", "score",
                                 "--backend", "kev", "--pairs", "pools/pairs.json", "--out", "scores/kev.json"],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["requirements"], "jev-kev.txt")
        self.assertEqual(plan["volume"], "test-volume")
        self.assertEqual(plan["worker_cwd"], "/data")
        self.assertIn("pools/pairs.json", plan["argv"])
        self.assertFalse((self.root / "scores").exists())
        result = subprocess.run([sys.executable, "-I", "-S", str(script), "--volume", "test-volume", "train",
                                 "--data", "input/train.jsonl", "--out", "trained", "--base", "models/base",
                                 "--init-checkpoint", "models/init"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["requirements"], "jev-kev.txt")
        self.assertIn("models/base", plan["argv"])
        self.assertIn("models/init", plan["argv"])
        self.assertEqual(plan["argv"][-1], "--execute")

    def test_model_failure_then_resume_preserves_order_and_rejects_stale_chunks(self):
        args = ["score", "--backend", "bge", "--pairs", str(self.root / "pairs"),
                "--out", str(self.root / "scores"), "--chunks", str(self.root / "chunks"),
                "--device", "cpu", "--batch-size", "2", "--chunk-size", "2"]
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertIn("score", __import__("qpaf.jev.cli", fromlist=["build_parser"]).build_parser()[1].choices)
            class Adapter:
                def __init__(self, fail):
                    self.fail = fail

                def score(self, batch):
                    if self.fail and ("fruit", "") in batch:
                        raise ValueError("failed second chunk")
                    return [len(q) - len(p) for q, p in batch], sum(len(q.split()) + len(p.split()) for q, p in batch)

                def peak_bytes(self):
                    return None

            with patch("qpaf.jev.backends.load_adapter", return_value=Adapter(True)):
                self.assertNotEqual(main(args), 0)
            self.assertFalse((self.root / "scores").exists())
            with patch("qpaf.jev.backends.load_adapter", return_value=Adapter(False)):
                self.assertEqual(main(args), 0)
            cache = load_scores(self.root / "scores", self.root / "pairs")
            self.assertEqual(cache["scores"], [0, 3, 5, 2])
            self.assertEqual(cache["manifest"]["chunks_reused"], 1)
            self.assertNotEqual(main(args + ["--input-cap", "128"]), 0)
            chunk = sorted((self.root / "chunks").glob("chunk-*.json"))[0]
            original = json.loads(chunk.read_bytes())
            write_json(chunk, {**original, "scores": [False, 0]})
            self.assertNotEqual(main(args), 0)


@unittest.skipUnless(os.environ.get("JEV_MODEL_TESTS") == "1", "set JEV_MODEL_TESTS=1 in the pinned Kev environment")
class ActualRuntimeTest(unittest.TestCase):
    def test_real_baseline_forwards_and_trained_checkpoint_reload(self):
        import torch
        from kev.model import SPECIAL
        from tokenizers import Tokenizer, models, pre_tokenizers
        from transformers import (BertConfig, BertForSequenceClassification, PreTrainedTokenizerFast,
                                  Qwen2Config, Qwen2ForCausalLM, Qwen2Tokenizer)

        torch.manual_seed(17)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = dataset(root)
            words = ["[UNK]", "[PAD]", "yes", "no", "fruit", "car", "apple", "held", "out", *SPECIAL,
                     "<|im_start|>", "<|im_end|>"]
            tokenizer = Tokenizer(models.WordLevel({w: i for i, w in enumerate(words)}, unk_token="[UNK]"))
            tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
            tok = PreTrainedTokenizerFast(tokenizer_object=tokenizer, unk_token="[UNK]", pad_token="[PAD]",
                                          additional_special_tokens=words[9:])
            qwen_dir, bert_dir = root / "tiny-qwen", root / "tiny-bert"
            tok.save_pretrained(bert_dir)
            alphabet = list(dict.fromkeys([*words, *sorted(pre_tokenizers.ByteLevel.alphabet()), "ye"]))
            qt = Qwen2Tokenizer(vocab={w: i for i, w in enumerate(alphabet)}, merges=[("y", "e"), ("ye", "s"), ("n", "o")],
                                unk_token="[UNK]", pad_token="[PAD]", eos_token="[PAD]",
                                additional_special_tokens=words[9:])
            qt.save_pretrained(qwen_dir)
            common = dict(hidden_size=16, num_hidden_layers=1, num_attention_heads=2,
                          intermediate_size=32, pad_token_id=1, max_position_embeddings=512)
            bert = BertForSequenceClassification(BertConfig(**common, vocab_size=len(tok), num_labels=1)).eval()
            bert.save_pretrained(bert_dir)
            (bert_dir / ".cache").mkdir()
            bert_archive = bert_dir / ".cache/selected.safetensors"
            (bert_dir / "model.safetensors").rename(bert_archive)
            bert_config = json.loads((bert_dir / "config.json").read_bytes())
            write_json(bert_dir / "config.json", {**bert_config, "transformers_weights": ".cache/selected.safetensors"})
            (bert_dir / "model.safetensors").write_bytes(b"unused default archive")

            causal = Qwen2ForCausalLM(Qwen2Config(**common, vocab_size=len(qt), num_key_value_heads=1)).eval()
            causal.save_pretrained(qwen_dir, max_shard_size="4KB")
            index_file = qwen_dir / "model.safetensors.index.json"
            index = json.loads(index_file.read_bytes())
            shard = next(iter(index["weight_map"].values()))
            hidden_shard = f".cache/{shard}"
            (qwen_dir / ".cache").mkdir()
            (qwen_dir / shard).rename(qwen_dir / hidden_shard)
            index["weight_map"] = {parameter: hidden_shard if name == shard else name
                                   for parameter, name in index["weight_map"].items()}
            selected_index = ".cache/selected.safetensors.index.json"
            write_json(qwen_dir / selected_index, index)
            qwen_config = json.loads((qwen_dir / "config.json").read_bytes())
            versioned = "config.5.17.0.json"
            write_json(qwen_dir / versioned, {**qwen_config, "transformers_weights": selected_index})
            write_json(qwen_dir / "config.json", {**qwen_config, "configuration_files": [versioned]})
            (qwen_dir / "model.safetensors").write_bytes(b"unused default archive")
            pairs = [("fruit", "apple"), ("held out", "apple"), ("fruit", ""), ("fruit", "car")]
            ids = tok([q for q, _ in pairs], [p for _, p in pairs], padding=True, return_tensors="pt")
            expected = bert(**ids).logits[:, 0].detach().tolist()
            for name, folder in (("bge", bert_dir), ("qwen", qwen_dir)):
                result = cli(root, "score", "--backend", name, "--checkpoint", folder, "--pairs", "pairs",
                             "--out", name, "--input-cap", 384, "--batch-size", 2, "--device", "cpu", isolated=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                cache = load_scores(root / name, root / "pairs")
                self.assertEqual(len(cache["scores"]), 4)
                self.assertTrue(all(map(math.isfinite, cache["scores"])))
                self.assertGreater(cache["manifest"]["input_tokens"], 0)
                if name == "bge":
                    for got, want in zip(cache["scores"], expected, strict=True):
                        self.assertAlmostEqual(got, want, places=5)
                    with bert_archive.open("ab") as stream:
                        stream.write(b"changed")
                    self.assertNotEqual(tree_hash(bert_dir), cache["manifest"]["revision"])
                else:
                    prompt = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the Query '
                              'and the Instruct provided. Note that the answer can only be "yes" or "no".'
                              '<|im_end|>\n<|im_start|>user\n<Instruct>: Given a question, retrieve the document page '
                              'that contains the answer\n<Query>: fruit\n<Document>: apple'
                              '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n')
                    inputs = qt(prompt, return_tensors="pt", return_token_type_ids=False)
                    logits = causal(**inputs).logits[0, -1].detach()
                    self.assertAlmostEqual(cache["scores"][0], float(logits[2] - logits[3]), places=5)
                print(f"{name} real scores: {cache['scores']}, tokens={cache['manifest']['input_tokens']}")
            bundle["pages"]["c"] = "apple " * 512
            write_json(root / "pairs", bundle)
            result = cli(root, *EXPORT, "--unjudged-as-negative")
            self.assertEqual(result.returncode, 0, result.stderr)
            result = cli(root, "train", "--data", "train.jsonl", "--init", "base", "--base", qwen_dir,
                         "--out", "trained", "--device", "cpu", "--max-steps", 1, "--accum", 1,
                         "--batch-size", 1, "--max-state", 384, "--lora", 2, "--head-dim", 8, "--execute", isolated=False)
            print(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ("adapter_model.safetensors", "adapter_config.json", "head.pt", "jev-run.json"):
                self.assertTrue((root / "trained" / name).is_file(), name)
            metrics = json.loads((root / "trained/training_metrics.json").read_bytes())
            self.assertEqual(metrics["optimizer_steps"], 1)
            run = json.loads((root / "trained/jev-run.json").read_bytes())
            self.assertEqual(run.get("training_records"), {"exported": 3, "admitted": 2, "dropped_for_context": 1,
                             "scheduled_visits": 2, "actual_visits": 1, "unvisited": 1, "optimizer_steps": 1})
            print(f"Training record provenance: {run['training_records']}")
            print(f"Optimizer steps={metrics['optimizer_steps']}, forward tokens={metrics['forward_tokens']}")
            result = cli(root, "score", "--backend", "kev", "--checkpoint", "trained", "--pairs", "pairs",
                         "--out", "kev", "--device", "cpu", "--batch-size", 2, "--input-cap", 128, isolated=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            cache = load_scores(root / "kev", root / "pairs")
            self.assertTrue(all(0 <= p <= 1 for p in cache["scores"]))
            self.assertTrue(any(p != round(p, 4) for p in cache["scores"]))
            self.assertEqual(Path(cache["manifest"]["local_kev_base"]["path"]), qwen_dir)
            with (qwen_dir / hidden_shard).open("ab") as stream:
                stream.write(b"changed")
            self.assertNotEqual(tree_hash(qwen_dir), cache["manifest"]["local_kev_base"]["sha256"])
            print(f"Kev reloaded scores: {cache['scores']}, tokens={cache['manifest']['input_tokens']}")
