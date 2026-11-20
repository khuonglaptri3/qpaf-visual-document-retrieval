"""Export train-partition page judgments and run the pinned official Kev trainer."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time

from .backends import kev_request, model_spec, require_kev_source, tree_hash
from .contracts import (
    atomic_write, decode_json, number, positive_int, read_json, read_pairs_snapshot,
    sha256_file, validate_splits, write_json,
)
from .evaluation import validate_qrels


def build_training_records(bundle, splits, qrels, *, unjudged_as_negative=False):
    validate_splits(bundle, splits)
    if bundle["dataset"].strip().casefold() == "vimdoc" or "units" in bundle:
        raise ValueError("document-level judgments cannot be used for page relevance training")
    if bundle.get("partition", "train") != "train":
        raise ValueError("only a train partition can supply training records")
    train = {q: text for q, text in bundle["queries"].items() if splits["splits"][q] == "train"}
    if not isinstance(qrels, dict):
        raise ValueError("qrels must map train query IDs to page judgments")
    judged = validate_qrels({q: qrels[q] for q in train if q in qrels}, train)
    records = []
    for query, page in bundle["pairs"]:
        if query not in train:
            continue
        assigned = page in judged[query]
        if not assigned and not unjudged_as_negative:
            continue
        request = kev_request(train[query], bundle["pages"][page])
        request["questions"]["relevant"]["label"] = assigned and judged[query][page] > 0
        request["_meta"] = {"query_id": query, "page_id": page, "group_id": splits["groups"][query],
                            "split": "train", "judgment": "judged" if assigned else "unjudged-as-negative"}
        records.append(request)
    if not records:
        raise ValueError("no assigned train page judgments available for export")
    return records


def manifest_path(data):
    return Path(str(data) + ".manifest.json")


def export_training(args):
    sidecar = manifest_path(args.out)
    destinations = {args.out.resolve(), sidecar.resolve()}
    if destinations.intersection(path.resolve() for path in (args.pairs, args.qrels, args.splits)):
        raise ValueError("training export destinations must differ from source paths")
    bundle, pairs_raw = read_pairs_snapshot(args.pairs)
    splits_raw, qrels_raw = args.splits.read_bytes(), args.qrels.read_bytes()
    rows = build_training_records(bundle, decode_json(splits_raw, args.splits), decode_json(qrels_raw, args.qrels),
                                  unjudged_as_negative=args.unjudged_as_negative)
    data = "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows).encode()
    manifest = {"format": "jev-page-noul-v1", "dataset": bundle["dataset"], "synthetic": bundle.get("synthetic", False),
                "split": "train", "label_unit": "page", "records": len(rows),
                "positives": sum(row["questions"]["relevant"]["label"] for row in rows),
                "unjudged_as_negative": args.unjudged_as_negative, "data_sha256": sha256(data).hexdigest(),
                "inputs_sha256": {"pairs": sha256(pairs_raw).hexdigest(), "qrels": sha256(qrels_raw).hexdigest(),
                                  "splits": sha256(splits_raw).hexdigest()}}
    atomic_write(args.out, data)
    write_json(sidecar, manifest)
    print(f"Exported {len(rows)} train records ({manifest['positives']} positive) to {args.out}")
    return 0


def validate_train_options(args):
    for field in ("epochs", "batch_size", "accum", "head_dim", "lora"):
        positive_int(getattr(args, field), field)
    if args.max_steps < 0 or not 384 <= args.max_state <= 65536:
        raise ValueError("max-steps must be nonnegative and max-state must be in [384,65536]")
    if not -(2**63) <= args.seed < 2**64:
        raise ValueError("seed: expected an integer from -9223372036854775808 through 18446744073709551615")
    if number(args.lr, "lr") <= 0 or number(args.head_lr, "head-lr") < 0:
        raise ValueError("lr must be positive and head-lr nonnegative")
    if args.init_checkpoint is not None and args.init != "kev":
        raise ValueError("--init-checkpoint requires --init kev")
    dtype = args.dtype or ("bf16" if args.device == "cuda" else "fp32")
    if dtype == "bf16" and args.device != "cuda":
        raise ValueError("training with bf16 autocast requires --device cuda")
    return dtype


def build_train_command(args, data_path):
    dtype = validate_train_options(args)
    spec = model_spec("kev")
    if args.base is not None and not args.base.is_dir():
        raise ValueError("--base requires an existing local backbone directory")
    if args.init_checkpoint is not None and not args.init_checkpoint.is_dir():
        raise ValueError("--init-checkpoint requires an existing local checkpoint directory")
    launcher = [sys.executable, "-m", "kev.train"]
    if sys.platform == "win32":
        script = Path(__file__).resolve().parents[3] / "scripts/train_jev_reranker.py"
        launcher = [sys.executable, str(script), "--windows-trainer", "kev.train"]
    argv = [*launcher, "--base", str(args.base.resolve()) if args.base else spec["base"]]
    if not args.base:
        argv += ["--base_revision", spec["base_revision"]]
    options = {
        "data": data_path, "out": args.out.resolve(), "device": args.device, "seed": args.seed, "lr": args.lr,
        "head_lr": args.head_lr, "lora": args.lora, "lora_targets": args.lora_targets, "head_dim": args.head_dim,
        "option_isolation": 0, "special_embeddings": 0, "max_steps": args.max_steps, "epochs": args.epochs,
        "max_state": args.max_state, "batch": args.batch_size, "accum": args.accum, "checkpointing": args.checkpointing,
        "dtype": dtype, "weights_dtype": args.weights_dtype, "p_none": 0, "p_none_distract": 0, "p_distract": 0,
        "p_none_pair": 0, "perm_frac": 0, "perm_kl": 0, "replay": 0,
    }
    for flag, value in options.items():
        argv += ["--" + flag, str(value)]
    if args.init == "kev":
        init = str(args.init_checkpoint.resolve()) if args.init_checkpoint else f"{spec['model']}@{spec['revision']}"
        argv += ["--init_from", init]
    return argv


def _training_record_counts(path, exported, epochs):
    metrics = read_json(path)
    scheduled = positive_int(metrics.get("requested_records"), "trainer requested_records")
    visited = positive_int(metrics.get("records_seen"), "trainer records_seen")
    steps = positive_int(metrics.get("optimizer_steps"), "trainer optimizer_steps")
    # The pinned trainer writes epochs * len(reqs) after context filtering. Its rejected_records
    # counter excludes this filter. Our command disables replay and custom record augmentation.
    admitted, remainder = divmod(scheduled, epochs)
    if remainder or not 0 < admitted <= exported or visited > scheduled:
        raise ValueError("trainer visit counts disagree with the export or epoch settings")
    return {"exported": exported, "admitted": admitted, "dropped_for_context": exported - admitted,
            "scheduled_visits": scheduled, "actual_visits": visited, "unvisited": scheduled - visited,
            "optimizer_steps": steps}


def train(args):
    raw = args.data.read_bytes()
    manifest = read_json(manifest_path(args.data))
    digest = sha256(raw).hexdigest()
    if manifest.get("data_sha256") != digest:
        raise ValueError("training data sha256 differs from its export manifest")
    if (manifest.get("format"), manifest.get("split"), manifest.get("label_unit")) != ("jev-page-noul-v1", "train", "page"):
        raise ValueError("train requires a train-only page export from export-train")
    rows = raw.splitlines()
    if not rows or len(rows) != manifest.get("records"):
        raise ValueError("training record count disagrees with its export manifest")
    for line in rows:
        row = decode_json(line, args.data)
        if row.get("_meta", {}).get("split") != "train" or type(row.get("questions", {}).get("relevant", {}).get("label")) is not bool:
            raise ValueError("export contains a non-train record or invalid Noul label")
    if args.out.exists():
        raise ValueError("trainer output must be a new directory")
    # Give the subprocess immutable bytes. The upstream trainer creates its own output directory.
    snapshot = args.out.resolve().with_name(f".{args.out.name}-{digest}.input.jsonl")
    if snapshot == args.data.resolve():
        raise ValueError("trainer snapshot must differ from source data")
    command = build_train_command(args, snapshot)
    info = {"argv": command, "source_commit": model_spec("kev")["source_commit"], "export": manifest, "init": args.init}
    if not args.execute:
        print(json.dumps(info, indent=2, ensure_ascii=True))
        return 0
    require_kev_source()
    if args.base:
        info["local_base_sha256"] = tree_hash(args.base)
    if args.init_checkpoint:
        info["local_init_sha256"] = tree_hash(args.init_checkpoint)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    stream = snapshot.open("xb")
    try:
        with stream as owned_snapshot:
            owned_snapshot.write(raw)
        started = time.perf_counter()
        result = subprocess.run(command, check=False)
        info.update(returncode=result.returncode, trainer_seconds=time.perf_counter() - started)
        if result.returncode != 0:
            raise ValueError(f"official kev.train exited {result.returncode}; inspect its stderr and output directory")
        info["checkpoint_sha256"] = {name: sha256_file(args.out / name) for name in
                                     ("adapter_config.json", "adapter_model.safetensors", "head.pt", "training_config.json")}
        info["training_records"] = _training_record_counts(args.out / "training_metrics.json", len(rows), args.epochs)
        write_json(args.out / "jev-run.json", info)
    finally:
        snapshot.unlink(missing_ok=True)
    print(f"Saved adapter, pointer head and run provenance to {args.out}")
    return 0
