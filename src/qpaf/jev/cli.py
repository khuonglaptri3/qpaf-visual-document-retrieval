"""Command-line workflows for the Jev CPU toolkit."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from io import StringIO
from pathlib import Path
import sys

from .contracts import (
    atomic_write, baseline_scores, decode_json, decode_scores, encode_json, load_pairs, load_scores,
    read_json, read_pairs_snapshot, sha256_file, write_json, write_scores,
)
from .data import (
    f9_bundle_paths, f9_pairs_path, lexical_scores, load_query_ids, load_raw_rows, load_texts,
    prepare_candidates, require_inputs, subset_partition,
)
from .evaluation import blend_scores, compare, evaluate


def _prep_inputs(args):
    if args.f9_bundle is not None:
        if args.queries is not None:
            raise ValueError("--f9-bundle uses the native query file in the bundle")
        return f9_bundle_paths(args.dataset, args.f9_bundle, args.page_text, args.query_ids)
    paths = {"queries": args.queries, "page_text": args.page_text, "raw_scores": args.raw_scores}
    if args.query_ids is not None:
        paths["query_ids"] = args.query_ids
    return paths


def _prep_hint(args):
    if args.f9_bundle is not None:
        return ("prepare --dataset vidoseek|vimdoc --f9-bundle DIR --page-text FILE.jsonl "
                "--weights BM25 DENSE VISUAL --out DIR")
    return "prepare --dataset NAME --queries FILE --page-text FILE --raw-scores FILE --out DIR"


def _outputs_differ(outputs, inputs):
    destinations = [Path(path).resolve() for path in outputs if path is not None]
    sources = {Path(path).resolve() for path in inputs if path is not None}
    if len(destinations) != len(set(destinations)) or sources.intersection(destinations):
        raise ValueError("output paths must be distinct and must differ from the inputs")


def _validate_import_input(args):
    path = args.f9_pairs or f9_pairs_path(args.f9_cache)
    require_inputs({"f9_pairs": path}, "prepare --f9-pairs FILE --out DIR")
    return path


def _doctor(args):
    pairs = args.pairs
    if args.f9_pairs is not None or args.f9_cache is not None:
        if pairs is not None:
            raise ValueError("provide only one of --pairs, --f9-pairs and --f9-cache")
        pairs = _validate_import_input(args)
    if pairs is not None:
        require_inputs({"pairs": pairs}, "doctor --pairs FILE [--scores FILE]")
        bundle = load_pairs(pairs)
        empty = sum(not text.strip() for text in bundle["pages"].values())
        print(f"Pairs verified: {len(bundle['queries'])} queries, {len(bundle['pairs'])} pairs, {empty} empty OCR pages")
        if "base_scores" not in bundle:
            print("Baseline and blend require aligned base_scores. Use prepare with explicit raw scores to add them.")
    if args.scores is not None:
        require_inputs({"pairs": pairs, "scores": args.scores}, "doctor --pairs FILE --scores FILE")
        load_scores(args.scores, pairs)
        print("Score length, values and input hash verified.")
    raw_args = (args.f9_bundle, args.raw_scores, args.queries, args.page_text, args.query_ids)
    if any(path is not None for path in raw_args):
        require_inputs(_prep_inputs(args), _prep_hint(args))
        print(f"Input files found. Next command: {_prep_hint(args)}")
    print(f"Jev CPU toolkit ready (Python {sys.version.split()[0]}). Try demo --out DIR.")
    return 0


def _cpu_manifest(model, synthetic, input_cap=None):
    return {
        "model": model,
        "revision": "v1",
        "input_cap": input_cap,
        "precision": "float64",
        "code": "qpaf.jev",
        "environment": {"python": sys.version.split()[0], "platform": sys.platform},
        "synthetic": synthetic,
    }


def _prepare(args):
    out = args.out
    pairs_path = out / "pairs.json"
    manifest_path = out / "manifest.json"
    base_path = out / "base_scores.json"
    score_path = out / "scores.json"
    if (args.splits is None) != (args.partition is None):
        raise ValueError("prepare requires --splits and --partition together")
    sidecars = (args.splits, args.import_scores)
    outputs = (pairs_path, manifest_path, base_path, score_path)
    raw = None
    imported = None
    if args.f9_pairs is not None or args.f9_cache is not None:
        if any(option is not None for option in (
            args.dataset, args.queries, args.page_text, args.query_ids, args.weights, args.units, args.top_k,
        )) or args.synthetic:
            raise ValueError("F9 pairs import only accepts --out, --import-scores and optional partition selection")
        source = _validate_import_input(args)
        bundle, raw = read_pairs_snapshot(source)
        digest = hashlib.sha256(raw).hexdigest()
        if args.import_scores is not None:
            score_raw = args.import_scores.read_bytes()
            imported = decode_scores(score_raw, args.import_scores, bundle, digest)
        _outputs_differ(outputs, (source, *sidecars))
        provenance = {"source": "f9-pairs", "inputs_sha256": {"f9_pairs": digest}}
        if imported is not None:
            provenance["inputs_sha256"]["score_cache"] = hashlib.sha256(score_raw).hexdigest()
    else:
        if args.import_scores is not None:
            raise ValueError("--import-scores requires --f9-pairs or --f9-cache")
        if not args.dataset:
            raise ValueError("prepare requires --dataset in raw-score and F9 bundle modes")
        paths = _prep_inputs(args)
        if args.units is not None:
            paths["units"] = args.units
        require_inputs(paths, _prep_hint(args))
        if args.f9_bundle is not None and args.weights is None:
            raise ValueError("native F9 channel scores require explicit --weights BM25 DENSE VISUAL")
        _outputs_differ(outputs, (*paths.values(), *sidecars))
        selected = load_query_ids(paths["query_ids"]) if "query_ids" in paths else None
        queries = load_texts(paths["queries"], "query_id", selected)
        pages = load_texts(paths["page_text"], "page_id")
        units = read_json(args.units) if args.units is not None else None
        rows = load_raw_rows(
            paths["raw_scores"], args.weights, selected, args.dataset if args.f9_bundle is not None else None
        )
        bundle = prepare_candidates(
            args.dataset, queries, pages, rows, 20 if args.top_k is None else args.top_k,
            weights=args.weights, units=units, synthetic=args.synthetic,
        )
        provenance = {
            "source": "f9-raw-bundle" if args.f9_bundle is not None else "raw-scores",
            "selection": "per-query channel min-max and supplied weights" if args.weights is not None else "base_score",
            "weights_bm25_dense_visual": args.weights,
            "inputs_sha256": {name: sha256_file(path) for name, path in paths.items()},
        }
    selected_indices = range(len(bundle["pairs"]))
    if args.splits is not None:
        split_raw = args.splits.read_bytes()
        bundle, selected_indices = subset_partition(
            bundle, decode_json(split_raw, args.splits), args.partition,
        )
        provenance["inputs_sha256"]["splits"] = hashlib.sha256(split_raw).hexdigest()
        provenance["partition"] = args.partition
        raw = None
    if raw is None:
        raw = encode_json(bundle)
    pairs_digest = hashlib.sha256(raw).hexdigest()
    atomic_write(pairs_path, raw)
    if imported is not None:
        write_scores(
            score_path, pairs_path, [imported["scores"][index] for index in selected_indices],
            {**imported["manifest"], "source_cache_sha256": provenance["inputs_sha256"]["score_cache"],
             "source_pairs_sha256": imported["pairs_sha256"],
             "synthetic": bundle.get("synthetic", False) or imported["manifest"].get("synthetic", False)},
            expected_pairs_sha256=pairs_digest,
        )
    if "base_scores" in bundle:
        write_scores(
            base_path, pairs_path, baseline_scores(bundle),
            {**_cpu_manifest("supplied base scores", bundle.get("synthetic", False)), **provenance},
            expected_pairs_sha256=pairs_digest,
        )
    manifest = {
        **provenance,
        "dataset": bundle["dataset"],
        "synthetic": bundle.get("synthetic", False),
        "top_k": bundle["top_k"],
        "queries": len(bundle["queries"]),
        "pairs": len(bundle["pairs"]),
        "pages": len(bundle["pages"]),
        "empty_ocr_pages": sum(not text.strip() for text in bundle["pages"].values()),
        "pairs_sha256": pairs_digest,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    write_json(manifest_path, manifest)
    print(f"Prepared {manifest['pairs']} pairs for {manifest['queries']} queries in {out}. "
          f"Empty OCR pages: {manifest['empty_ocr_pages']}.")
    return 0


def _write_csv(path, fields, rows):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(path, stream.getvalue().encode("utf-8"))


def _evaluation_csv(path, report):
    _write_csv(path, ["query_id", "synthetic", *report["mean"]], [
        {"query_id": query, "synthetic": report["synthetic"], **row}
        for query, row in report["per_query"].items()
    ])


def _comparison_csv(path, report):
    _write_csv(path, ["metric", "synthetic", "delta", "ci95_low", "ci95_high", "win", "tie", "loss"], [
        {
            "metric": name, "synthetic": report["synthetic"], "delta": row["delta"],
            "ci95_low": row["ci95"][0], "ci95_high": row["ci95"][1], **row["win_tie_loss"],
        }
        for name, row in report["metrics"].items()
    ])


def _publish(report, path):
    if path is None:
        # Keep stdout valid JSON for piping into other local tools.
        print(json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False))
    else:
        write_json(path, report)
        print(f"Wrote {path}")


def _evaluate(args):
    _outputs_differ((args.out, args.csv), (args.pairs, args.scores, args.qrels, args.units))
    bundle, raw = read_pairs_snapshot(args.pairs)
    digest = hashlib.sha256(raw).hexdigest()
    manifest = _cpu_manifest("supplied base scores", bundle.get("synthetic", False))
    if args.baseline:
        scores = baseline_scores(bundle)
    else:
        cache = decode_scores(args.scores.read_bytes(), args.scores, bundle, digest)
        manifest, scores = cache["manifest"], cache["scores"]
        if args.lam is not None:
            scores = blend_scores(bundle, scores, args.lam)
    units_raw = None
    if args.units is not None:
        units_raw = args.units.read_bytes()
        units = decode_json(units_raw, args.units)
        if "units" in bundle and bundle["units"] != units:
            raise ValueError("--units disagrees with the mapping already embedded in pairs JSON")
        bundle = {**bundle, "units": units}
    qrels_raw = args.qrels.read_bytes()
    report = evaluate(bundle, scores, decode_json(qrels_raw, args.qrels), args.k)
    report.update({
        "synthetic": report["synthetic"] or manifest.get("synthetic", False),
        "pairs_sha256": digest,
        "qrels_sha256": hashlib.sha256(qrels_raw).hexdigest(),
        "score_manifest": manifest,
        "score_mode": "baseline" if args.baseline else ("blend" if args.lam is not None else "pure"),
        "lambda": args.lam,
    })
    if units_raw is not None:
        report["units_sha256"] = hashlib.sha256(units_raw).hexdigest()
    if "partition" in bundle:
        report["partition"] = bundle["partition"]
    if args.csv is not None:
        _evaluation_csv(args.csv, report)
    _publish(report, args.out)
    return 0


def _compare(args):
    _outputs_differ((args.out, args.csv), (args.left, args.right, args.groups))
    groups = read_json(args.groups) if args.groups is not None else None
    if isinstance(groups, dict) and isinstance(groups.get("groups"), dict):
        groups = groups["groups"]  # Accept the groups map in a split manifest.
    report = compare(read_json(args.left), read_json(args.right), args.seed, args.resamples, groups)
    report["inputs_sha256"] = {"left": sha256_file(args.left), "right": sha256_file(args.right)}
    if args.groups is not None:
        report["inputs_sha256"]["groups"] = sha256_file(args.groups)
    if args.csv is not None:
        _comparison_csv(args.csv, report)
    _publish(report, args.out)
    return 0


def _demo(args):
    bundle = prepare_candidates(
        "synthetic-toy-jev-demo",
        {"q1": "red apple", "q2": "blue bicycle"},
        {"p1": "a red apple", "p2": "a blue bicycle", "p3": ""},
        [
            {"query_id": "q1", "page_id": "p1", "base_score": 1},
            {"query_id": "q1", "page_id": "p2", "base_score": 2},
            {"query_id": "q2", "page_id": "p2", "base_score": 1},
            {"query_id": "q2", "page_id": "p3", "base_score": 2},
        ],
        2,
        synthetic=True,
    )
    qrels = {"q1": {"p1": 1, "outside-demo-pool": 1}, "q2": {"p2": 1}}
    dest = args.out
    pairs_path, qrels_path = dest / "pairs.json", dest / "qrels.json"
    base_path, scores_path = dest / "base_scores.json", dest / "scores.json"
    write_json(pairs_path, bundle)
    write_json(qrels_path, qrels)
    write_scores(base_path, pairs_path, baseline_scores(bundle), _cpu_manifest("toy supplied base scores", True))
    write_scores(scores_path, pairs_path, lexical_scores(bundle), _cpu_manifest("toy lexical overlap", True))
    common = {"pairs": pairs_path, "qrels": qrels_path, "units": None, "k": 10, "lam": None}
    left, right = dest / "baseline.json", dest / "evaluation.json"
    _evaluate(argparse.Namespace(
        **common, baseline=True, scores=None, out=left, csv=dest / "baseline.csv",
    ))
    _evaluate(argparse.Namespace(
        **common, baseline=False, scores=scores_path, out=right, csv=dest / "evaluation.csv",
    ))
    _compare(argparse.Namespace(
        left=left, right=right, groups=None, seed=20260820, resamples=1000,
        out=dest / "comparison.json", csv=dest / "comparison.csv",
    ))
    print(f"Synthetic demo artifacts: {dest}")
    return 0


def _add_prepare_inputs(parser, required):
    source = parser.add_mutually_exclusive_group(required=required)
    source.add_argument("--f9-pairs", type=Path, help="Existing F9 pairs JSON, imported byte-for-byte")
    source.add_argument("--f9-cache", type=Path, help="Folder containing f9_pairs.json or test_pairs.json")
    source.add_argument("--f9-bundle", type=Path, help="Native ViDoSeek or ViMDoc retriever cache folder")
    source.add_argument("--raw-scores", type=Path, help="Score rows in JSON, JSONL, CSV or Parquet")
    parser.add_argument("--dataset", help="Dataset name; native F9 layout accepts vidoseek or vimdoc")
    parser.add_argument("--queries", type=Path, help="ID-to-text JSON or {query_id,text} JSONL")
    parser.add_argument("--page-text", type=Path, help="ID-to-OCR JSON or {page_id,text} JSONL")
    parser.add_argument("--query-ids", type=Path, help="Selected query IDs, one per line")


def _add_report_outputs(parser):
    parser.add_argument("--out", type=Path, help="JSON result path; default is stdout")
    parser.add_argument("--csv", type=Path, help="Optional CSV result path")


def build_parser():
    parser = argparse.ArgumentParser(description="Prepare and evaluate Jev reranker candidate pools.")
    commands = parser.add_subparsers(title="commands", required=True)

    doctor = commands.add_parser("doctor", help="Check CPU setup and inspect local input paths")
    _add_prepare_inputs(doctor, required=False)
    doctor.add_argument("--pairs", type=Path, help="Validate a prepared pairs file")
    doctor.add_argument("--scores", type=Path, help="Validate an existing score cache against --pairs")
    doctor.set_defaults(handler=_doctor)

    prep = commands.add_parser(
        "prepare", help="Prepare candidates without labels or import existing F9 pairs",
        description=(
            "Raw rows require query_id, page_id and either a base_score or the three numeric "
            "bm25, dense and visual channels with explicit --weights. A document_id column or "
            "--units supplies document pooling. Native F9 Parquet preparation also requires pyarrow."
        ),
    )
    _add_prepare_inputs(prep, required=True)
    prep.add_argument("--top-k", type=int, help="Candidate pages per query (default: 20)")
    prep.add_argument("--weights", type=float, nargs=3, metavar=("BM25", "DENSE", "VISUAL"))
    prep.add_argument("--units", type=Path, help="Optional page-ID to label-unit mapping in JSON")
    prep.add_argument("--splits", type=Path, help="Query split/group manifest")
    prep.add_argument("--partition", choices=("train", "validation", "test"), help="Select a split from --splits")
    prep.add_argument("--import-scores", type=Path, help="Validate an F9 cache and rebind to the output pairs")
    prep.add_argument("--synthetic", action="store_true", help="Mark these inputs as synthetic")
    prep.add_argument("--out", type=Path, required=True, help="Output directory")
    prep.set_defaults(handler=_prepare)

    ev = commands.add_parser("evaluate", help="Compute unit-level metrics and per-query results")
    ev.add_argument("--pairs", type=Path, required=True)
    ev.add_argument("--qrels", type=Path, required=True, help="Full query-to-unit judgments in JSON")
    ev.add_argument("--units", type=Path, help="Page-to-unit map for byte-exact imported pairs without units")
    score = ev.add_mutually_exclusive_group(required=True)
    score.add_argument("--scores", type=Path, help="Existing byte-bound score cache")
    score.add_argument("--baseline", action="store_true", help="Use explicit aligned base_scores")
    ev.add_argument("--lambda", "--lam", dest="lam", type=float, help="Explicit reranker blend weight in [0,1]")
    ev.add_argument("--k", type=int, default=10)
    _add_report_outputs(ev)
    ev.set_defaults(handler=_evaluate)

    comp = commands.add_parser("compare", help="Compute paired right-minus-left changes")
    comp.add_argument("--left", type=Path, required=True)
    comp.add_argument("--right", type=Path, required=True)
    comp.add_argument("--groups", type=Path, help="Optional query-to-group JSON or split manifest")
    comp.add_argument("--seed", type=int, default=20260820)
    comp.add_argument("--resamples", type=int, default=10000)
    _add_report_outputs(comp)
    comp.set_defaults(handler=_compare)

    demo = commands.add_parser("demo", help="Run a complete synthetic workflow offline")
    demo.add_argument("--out", type=Path, required=True, help="Output directory")
    demo.set_defaults(handler=_demo)
    return parser, commands


def main(argv=None):
    parser, _ = build_parser()
    try:
        args = parser.parse_args(argv)
        if getattr(args, "baseline", False) and getattr(args, "lam", None) is not None:
            parser.error("--lambda requires --scores")
        return args.handler(args)
    except SystemExit as exc:
        return int(exc.code)
    except (ValueError, OSError) as exc:
        print(f"Jev: {exc}", file=sys.stderr)
        return 2
