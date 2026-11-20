"""CLI and no-download runtime tests for the actual rerankers and Kev trainer."""
import contextlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

if __package__:
    from .test_jev_training import ROOT, EXPORT, cli, dataset
else:
    from test_jev_training import ROOT, EXPORT, cli, dataset

from qpaf.jev.cli import main
from qpaf.jev.contracts import load_scores, write_json


class ScoringTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        dataset(self.root)

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
            dataset(root)
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
            causal = Qwen2ForCausalLM(Qwen2Config(**common, vocab_size=len(qt), num_key_value_heads=1)).eval()
            causal.save_pretrained(qwen_dir)
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
            result = cli(root, *EXPORT)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = cli(root, "train", "--data", "train.jsonl", "--init", "base", "--base", qwen_dir,
                         "--out", "trained", "--device", "cpu", "--max-steps", 1, "--accum", 1,
                         "--batch-size", 1, "--lora", 2, "--head-dim", 8, "--execute", isolated=False)
            print(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ("adapter_model.safetensors", "adapter_config.json", "head.pt", "jev-run.json"):
                self.assertTrue((root / "trained" / name).is_file(), name)
            metrics = json.loads((root / "trained/training_metrics.json").read_bytes())
            self.assertEqual(metrics["optimizer_steps"], 1)
            print(f"Optimizer steps={metrics['optimizer_steps']}, forward tokens={metrics['forward_tokens']}")
            result = cli(root, "score", "--backend", "kev", "--checkpoint", "trained", "--pairs", "pairs",
                         "--out", "kev", "--device", "cpu", "--batch-size", 2, "--input-cap", 128, isolated=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            cache = load_scores(root / "kev", root / "pairs")
            self.assertTrue(all(0 <= p <= 1 for p in cache["scores"]))
            self.assertTrue(any(p != round(p, 4) for p in cache["scores"]))
            print(f"Kev reloaded scores: {cache['scores']}, tokens={cache['manifest']['input_tokens']}")
