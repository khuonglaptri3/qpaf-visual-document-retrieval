"""Pinned rerankers and byte-bound, restartable scoring. Model imports stay inside loaders."""
from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import sys
from tempfile import TemporaryDirectory
import time

from .contracts import (
    baseline_scores, encode_json, number, positive_int, read_json, read_pairs_snapshot,
    score_vector, sha256_file, write_json, write_scores,
)
from .data import lexical_scores


MODELS = Path(__file__).resolve().parents[3] / "configs/jev/models.json"
INSTRUCTION = "Given a question, retrieve the document page that contains the answer"
PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the '
          'Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
DTYPES = {"fp32": "float32", "bf16": "bfloat16", "fp16": "float16"}


def kev_request(query, page):
    return {"state": page, "questions": {"relevant": {
        "type": "noul", "instructions": f"Does this document page contain the answer to this question?\n{query}"}}}


def model_spec(backend):
    return read_json(MODELS)[backend]


def require_kev_source():
    expected = model_spec("kev")["source_commit"]
    try:
        source = metadata.distribution("kev").read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        source = None
    if not source or json.loads(source).get("vcs_info", {}).get("commit_id") != expected:
        raise ValueError(f"install requirements/jev-kev.txt to use the official Kev source at {expected}")


def _explicit_weight_name(path):
    config_path = path / "config.json"
    if not config_path.is_file():
        return None
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise ValueError(f"{config_path}: expected a model configuration object")
    if "configuration_files" in config:
        try:
            from transformers import PreTrainedConfig
        except ImportError as exc:
            raise ValueError("versioned local model configuration requires Transformers") from exc
        config, _ = PreTrainedConfig.get_config_dict(path, local_files_only=True)
    return config.get("transformers_weights")


def _weight_archive(path):
    name = _explicit_weight_name(path)
    if name is not None:
        if not isinstance(name, str) or not (
            name.endswith((".safetensors", ".safetensors.index.json")) or name == "adapter_model.bin"
        ):
            raise ValueError("transformers_weights must name a safetensors archive, safetensors index or adapter_model.bin")
        archive = path / name
        # The loader checks lexical containment. Linked targets inside the directory are supported.
        if not Path(os.path.abspath(archive)).is_relative_to(Path(os.path.abspath(path))):
            raise ValueError(f"transformers_weights must reference a file inside the model directory: {name}")
        if not archive.is_file():
            raise ValueError(f"transformers_weights references a missing archive: {name}")
        return name, archive

    # Match the Transformers local loader's default checkpoint selection order.
    for name in ("model.safetensors", "model.safetensors.index.json", "pytorch_model.bin", "pytorch_model.bin.index.json"):
        archive = path / name
        if archive.is_file():
            return name, archive
    return None, None


def _weight_files(path):
    name, archive = _weight_archive(path)
    if archive is None:
        return {}
    files = {Path(name).as_posix(): archive}
    if not name.endswith(".index.json"):
        return files

    data = read_json(archive)
    weights = data.get("weight_map") if isinstance(data, dict) else None
    if not isinstance(weights, dict) or not weights or not all(isinstance(shard, str) and shard for shard in weights.values()):
        raise ValueError(f"{archive}: expected a nonempty weight_map with shard paths")
    # An indexed shard can be under hidden metadata directories or behind directory symlinks.
    for name in set(weights.values()):
        shard = path / name
        if not shard.is_file():
            raise ValueError(f"{archive}: referenced shard is missing: {name}")
        files[Path(name).as_posix()] = shard
    return files


def tree_hash(path):
    """A local checkpoint can change without its directory name changing."""
    if not path.is_dir():
        raise ValueError(f"local checkpoint directory does not exist: {path}")
    files = {f.relative_to(path).as_posix(): f for f in path.rglob("*")
             if f.is_file() and not {".git", ".cache"}.intersection(f.relative_to(path).parts)}
    files.update(_weight_files(path))
    if not files:
        raise ValueError(f"empty checkpoint directory: {path}")
    digests, resolved_digests = {}, {}
    for name, file in sorted(files.items()):
        target = file.resolve()
        if target not in resolved_digests:
            resolved_digests[target] = sha256_file(target)
        digests[name] = resolved_digests[target]
    return sha256(encode_json(digests)).hexdigest()


def _open_kev_checkpoint(model):
    from kev.checkpoint import Checkpoint

    return Checkpoint(model)


def _kev_base_reference(meta):
    base, revision = meta.base, meta.base_revision
    if not isinstance(base, str) or not base.strip():
        raise ValueError("Kev head.pt must declare a backbone")
    local = Path(base)
    if local.is_dir():
        return {"model": base, "revision": revision, "path": str(local.resolve())}
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", base) or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Kev head.pt must declare an existing local backbone or a Hub backbone pinned to a full commit SHA")
    return {"model": base, "revision": revision, "path": None}


def _local_identity(backend, path):
    revision = tree_hash(path)
    base = None
    if backend == "kev":
        base = _kev_base_reference(_open_kev_checkpoint(str(path)).meta)
        if base["path"] is not None:
            base["sha256"] = tree_hash(Path(base["path"]))
    return revision, base


class TransformerAdapter:
    def __init__(self, config, torch, dtype):
        from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification, AutoTokenizer
        self.torch, self.device, self.cap = torch, config["device"], config["input_cap"]
        self.qwen = config["backend"] == "qwen"
        model, revision = config["model"], config["hub_revision"]
        self.tokenizer = AutoTokenizer.from_pretrained(model, revision=revision)
        if self.qwen:
            self.tokenizer.padding_side = "left"
            self.prefix = self.tokenizer.encode(PREFIX, add_special_tokens=False)
            self.suffix = self.tokenizer.encode(SUFFIX, add_special_tokens=False)
            if self.cap <= len(self.prefix) + len(self.suffix):
                raise ValueError("Qwen input cap must leave room for the query and document after the prompt")
            self.yes, self.no = (self.tokenizer.convert_tokens_to_ids(t) for t in ("yes", "no"))
            if self.yes == self.no or {None, self.tokenizer.unk_token_id}.intersection((self.yes, self.no)):
                raise ValueError("Qwen tokenizer must have distinct yes and no tokens")
        cls = AutoModelForCausalLM if self.qwen else AutoModelForSequenceClassification
        self.model = cls.from_pretrained(model, revision=revision, dtype=dtype).to(self.device).eval()

    def score(self, batch):
        if self.qwen:
            bodies = [f"<Instruct>: {INSTRUCTION}\n<Query>: {q}\n<Document>: {p}" for q, p in batch]
            ids = self.tokenizer(bodies, truncation=True, max_length=self.cap-len(self.prefix)-len(self.suffix),
                                 add_special_tokens=False, return_attention_mask=False)["input_ids"]
            inputs = self.tokenizer.pad({"input_ids": [self.prefix + x + self.suffix for x in ids]},
                                        padding=True, return_tensors="pt")
        else:
            queries, pages = zip(*batch, strict=True)
            inputs = self.tokenizer(list(queries), list(pages), padding=True, truncation=True,
                                    max_length=self.cap, return_tensors="pt")
        inputs = inputs.to(self.device)
        with self.torch.inference_mode():
            if self.qwen:
                logits = self.model(**inputs, logits_to_keep=1, use_cache=False).logits[:, -1, :].float()
                scores = logits[:, self.yes] - logits[:, self.no]
            else:
                logits = self.model(**inputs).logits
                if tuple(logits.shape) != (len(batch), 1):
                    raise ValueError(f"BGE requires one classifier logit per pair, received {tuple(logits.shape)}")
                scores = logits[:, 0].float()
        return scores.cpu().tolist(), int(inputs["attention_mask"].sum().item())

    def peak_bytes(self):
        return self.torch.cuda.max_memory_allocated(self.device) if self.device == "cuda" else None


class KevAdapter:
    def __init__(self, config, torch, dtype):
        from kev.checkpoint import LoadOptions
        require_kev_source()
        self.torch, self.device, self.cap = torch, config["device"], config["input_cap"]
        name, revision = config["model"], config["hub_revision"]
        checkpoint = _open_kev_checkpoint(f"{name}@{revision}" if revision else name)
        if config["local_kev_base"] is not None:
            expected = {k: v for k, v in config["local_kev_base"].items() if k != "sha256"}
            if _kev_base_reference(checkpoint.meta) != expected:
                raise ValueError("Kev backbone reference changed before model load")
        self.tokenizer, self.model = checkpoint.load(self.device, LoadOptions(dtype=dtype))
        if self.model.dtype != DTYPES[config["precision"]]:
            raise ValueError(f"checkpoint loads at {self.model.dtype}; request its actual precision")

    def score(self, batch):
        from kev.api import SystemOneRequest, to_answers, to_record
        from kev.model import admit, SERVE_MAX_BRANCH, SERVE_MAX_STATE

        encodings, metas = [], []
        for query, page in batch:
            rec, meta = to_record(SystemOneRequest(**kev_request(query, page)))
            # Measure the question branch independently, then spend the remaining cap on OCR.
            empty = admit(self.model, self.tokenizer, {**rec, "state": ""})
            remaining = min(self.cap, SERVE_MAX_BRANCH) - len(empty["ids"]) + 1
            if remaining < 1:
                raise ValueError("Kev input cap is too small for the question and Noul options")
            encodings.append(self.model.encode(self.tokenizer, rec, max_state=min(remaining, SERVE_MAX_STATE),
                                               max_branch=min(self.cap, SERVE_MAX_BRANCH), strict=False))
            metas.append(meta)
        with self.torch.inference_mode():
            probabilities, _ = self.model.probs_batch(encodings, [None] * len(batch), [False] * len(batch))
        scores = []
        for questions, meta in zip(probabilities, metas, strict=True):
            row, = questions
            values = row.tolist()
            if len(values) != 2 or meta[0]["keys"] != ["false", "true"]:
                raise ValueError("unexpected official Kev Noul readout")
            raw = number(values[1], "Noul p(true)")
            answer = to_answers([values], meta)["relevant"]
            if not 0 <= raw <= 1 or answer["noul"] != round(raw, 4):
                raise ValueError("inconsistent official Kev Noul probability")
            scores.append(raw)
        return scores, sum(len(enc["ids"]) for enc in encodings)

    def peak_bytes(self):
        return self.torch.cuda.max_memory_allocated(self.device) if self.device == "cuda" else None


def load_adapter(config):
    try:
        import torch
        if config["device"] == "cuda":
            if not torch.cuda.is_available():
                raise ValueError("CUDA is unavailable; select --device cpu or install a CUDA Torch runtime")
            torch.cuda.reset_peak_memory_stats()
        cls = KevAdapter if config["backend"] == "kev" else TransformerAdapter
        return cls(config, torch, getattr(torch, DTYPES[config["precision"]]))
    except ImportError as exc:
        req = "kev" if config["backend"] == "kev" else "baselines"
        raise ValueError(f"install requirements/jev-{req}.txt: {exc}") from exc


def _environment(backend):
    environment = {"python": sys.version.split()[0], "platform": sys.platform}
    packages = ["torch", "transformers", "tokenizers", "huggingface-hub", "numpy"]
    if backend == "kev":
        packages += ["kev", "peft", "accelerate"]
    for package in packages:
        try:
            environment[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            environment[package] = None
    return environment


def _cuda_driver_version():
    import ctypes

    lib = ctypes.WinDLL("nvcuda.dll") if sys.platform == "win32" else ctypes.CDLL("libcuda.so.1")
    version = ctypes.c_int()
    status = lib.cuDriverGetVersion(ctypes.byref(version))
    if status != 0 or version.value <= 0:
        raise ValueError(f"could not read the active NVIDIA driver API version (status {status})")
    return version.value


def _runtime_identity(device, backend):
    try:
        import torch
    except ImportError as exc:
        req = "kev" if backend == "kev" else "baselines"
        raise ValueError(f"install requirements/jev-{req}.txt: {exc}") from exc

    runtime = {"torch": str(torch.__version__), "build_sha256": sha256(torch.__config__.show().encode()).hexdigest(),
               "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
               "float32_matmul_precision": torch.get_float32_matmul_precision()}
    if device == "cpu":
        return {**runtime, "hardware": platform.machine(), "processor": platform.processor(),
                "capability": torch.backends.cpu.get_cpu_capability(), "threads": torch.get_num_threads()}
    if not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable; select --device cpu or install a CUDA Torch runtime")
    try:
        props = torch.cuda.get_device_properties(torch.cuda.current_device())
        return {**runtime, "hardware": props.name, "compute_capability": [props.major, props.minor],
                "memory_bytes": props.total_memory, "multiprocessors": props.multi_processor_count,
                "cuda": torch.version.cuda, "driver_api": _cuda_driver_version(), "cudnn": torch.backends.cudnn.version(),
                "cudnn_deterministic": torch.backends.cudnn.deterministic,
                "cudnn_benchmark": torch.backends.cudnn.benchmark, "cudnn_tf32": torch.backends.cudnn.allow_tf32,
                "cublas_workspace": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
                "nvidia_tf32_override": os.environ.get("NVIDIA_TF32_OVERRIDE")}
    except RuntimeError as exc:
        raise ValueError(f"could not identify the selected CUDA runtime: {exc}") from exc


def validate_score_options(args):
    positive_int(args.input_cap, "input cap")
    positive_int(args.batch_size, "batch size")
    positive_int(args.chunk_size, "chunk size")


def _config(args, digest):
    validate_score_options(args)
    spec = model_spec(args.backend)
    if args.backend == "kev":
        require_kev_source()
    runtime = _runtime_identity(args.device, args.backend)
    revision, hub_revision, model = spec["revision"], spec["revision"], spec["model"]
    base = None
    if args.checkpoint is not None:
        path = args.checkpoint.resolve()
        revision, base = _local_identity(args.backend, path)
        hub_revision, model = None, str(path)
    return {"backend": args.backend, "model": model, "revision": revision, "hub_revision": hub_revision,
            "readout": spec["readout"], "source_commit": spec.get("source_commit"), "local_kev_base": base,
            "pairs_sha256": digest, "device": args.device, "runtime": runtime,
            "precision": args.precision or (spec["cuda_precision"] if args.device == "cuda" else "fp32"),
            "input_cap": args.input_cap, "batch_size": args.batch_size, "chunk_size": args.chunk_size,
            "environment": _environment(args.backend),
            "code": sha256_file(__file__)}


def _claim_chunks(chunks, config):
    chunks.mkdir(parents=True, exist_ok=True)
    claim = chunks / ".jev-config"
    run_path = claim / "config.json"
    if not run_path.is_file():
        leftovers = any(p != claim and not p.name.startswith(".jev-claim-") for p in chunks.iterdir())
        if leftovers and not run_path.is_file():
            raise ValueError(f"chunk directory {chunks} contains files from another run; use a fresh --chunks directory")
        with TemporaryDirectory(dir=chunks, prefix=".jev-claim-") as temp:
            staged = Path(temp) / "config"
            write_json(staged / "config.json", config)
            # A same-filesystem rename publishes a complete, nonempty directory. It cannot replace the winner.
            try:
                staged.rename(claim)
            except OSError:
                if not run_path.is_file():
                    raise
    if read_json(run_path) != config:
        raise ValueError(f"stale scoring configuration in {chunks}; use a fresh --chunks directory")


def _check_chunk(row, fingerprint, start, stop):
    if not isinstance(row, dict) or (row.get("fingerprint"), row.get("start"), row.get("stop")) != (fingerprint, start, stop):
        raise ValueError(f"stale or incorrect score chunk at pair {start}")
    payload = {k: v for k, v in row.items() if k != "sha256"}
    if row.get("sha256") != sha256(encode_json(payload)).hexdigest():
        raise ValueError(f"score chunk checksum mismatch at pair {start}")
    score_vector(row.get("scores"), stop - start)
    return row


def score_file(args):
    bundle, raw = read_pairs_snapshot(args.pairs)
    digest = sha256(raw).hexdigest()
    if args.backend in ("baseline", "lexical"):
        scores = baseline_scores(bundle) if args.backend == "baseline" else lexical_scores(bundle)
        manifest = {"model": args.backend, "revision": "v1", "input_cap": None, "precision": "float64",
                    "environment": {"python": sys.version.split()[0]}, "code": "qpaf.jev",
                    "synthetic": bundle.get("synthetic", False)}
    else:
        chunks = args.chunks or Path(str(args.out) + ".chunks")
        inputs_outputs = [args.out.resolve(), args.pairs.resolve()]
        if any(chunks.resolve() == p or chunks.resolve() in p.parents for p in inputs_outputs):
            raise ValueError("chunk directory must be separate from the pairs file and final output")
        if args.checkpoint and any(p.is_relative_to(args.checkpoint.resolve()) for p in [*inputs_outputs, chunks.resolve()]):
            raise ValueError("keep scoring files outside the model checkpoint directory")
        config = _config(args, digest)
        base = config["local_kev_base"]
        if base and base["path"] is not None and any(p.is_relative_to(Path(base["path"])) for p in [*inputs_outputs, chunks.resolve()]):
            raise ValueError("keep scoring files outside the model backbone directory")
        fingerprint = sha256(encode_json(config)).hexdigest()
        _claim_chunks(chunks, config)
        adapter, scores, reused, tokens, seconds, peaks = None, [], 0, 0, 0.0, []
        pairs = bundle["pairs"]
        for start in range(0, len(pairs), args.chunk_size):
            stop = min(start + args.chunk_size, len(pairs))
            path = chunks / f"chunk-{start:09d}.json"
            if path.exists():
                row = _check_chunk(read_json(path), fingerprint, start, stop)
                reused += 1
            else:
                values, token_count = [], 0
                try:
                    if adapter is None:
                        adapter = load_adapter(config)
                        if args.checkpoint is not None and _local_identity(args.backend, Path(config["model"])) != (config["revision"], base):
                            raise ValueError("local checkpoint or backbone changed during model load")
                    started = time.perf_counter()
                    for offset in range(start, stop, args.batch_size):
                        batch = [(bundle["queries"][q], bundle["pages"][p])
                                 for q, p in pairs[offset:min(offset + args.batch_size, stop)]]
                        result, measured = adapter.score(batch)
                        values.extend(score_vector(result, len(batch)))
                        token_count += measured
                    row = {"fingerprint": fingerprint, "start": start, "stop": stop, "scores": values,
                           "input_tokens": token_count, "score_seconds": time.perf_counter() - started,
                           "peak_cuda_allocated_bytes": adapter.peak_bytes()}
                    row["sha256"] = sha256(encode_json(row)).hexdigest()
                    write_json(path, row)
                except (ValueError, OSError, RuntimeError, ImportError) as exc:
                    raise ValueError(f"{args.backend} scoring failed at chunk [{start},{stop}); "
                                     f"{len(scores)}/{len(pairs)} validated scores before error: {exc}") from exc
            scores.extend(row["scores"])
            tokens += row["input_tokens"]
            seconds += row["score_seconds"]
            if row["peak_cuda_allocated_bytes"] is not None:
                peaks.append(row["peak_cuda_allocated_bytes"])
        manifest = {**config, "fingerprint": fingerprint, "chunks_reused": reused, "input_tokens": tokens,
                    "sum_chunk_score_seconds": seconds, "peak_cuda_allocated_bytes": max(peaks, default=None),
                    "synthetic": bundle.get("synthetic", False)}
    write_scores(args.out, args.pairs, scores, manifest, expected_pairs_sha256=digest)
    print(f"Wrote {len(scores)} scores to {args.out}")
    return 0
