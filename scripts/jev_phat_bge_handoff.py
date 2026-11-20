"""Select missing ViDoSeek BGE pairs or integrate a compatible historical-format score cache."""
import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from qpaf.jev.contracts import decode_scores, read_pairs_snapshot, write_json, write_scores


def read_cache(pairs_path, scores_path):
    bundle, pairs_raw = read_pairs_snapshot(pairs_path)
    digest = hashlib.sha256(pairs_raw).hexdigest()
    raw = scores_path.read_bytes()
    cache = decode_scores(raw, scores_path, bundle, digest)
    manifest = cache["manifest"]
    required = ("model", "revision", "max_length", "dtype", "torch", "packages")
    if any(not manifest.get(key) for key in required):
        raise ValueError("expected a complete historical BGE inference manifest")
    if manifest["model"] != "BAAI/bge-reranker-v2-m3" or manifest.get("limit", 0):
        raise ValueError("expected complete BGE inference on the source pairs")
    policy = {key: manifest.get(key) for key in (*required, "instruction")}
    provenance = {"pairs_sha256": digest, "scores_sha256": hashlib.sha256(raw).hexdigest(),
                  "manifest": manifest}
    return bundle, cache["scores"], policy, provenance


def align(full, source, scores, wanted):
    if (source["dataset"] != full["dataset"] or source.get("synthetic", False) != full.get("synthetic", False)
            or source.get("partition") not in (None, full.get("partition"))):
        raise ValueError("incompatible source dataset or partition")
    found = {}
    for (q, p), score in zip(source["pairs"], scores, strict=True):
        if (q, p) in wanted:
            if source["queries"][q] != full["queries"][q] or source["pages"][p] != full["pages"][p]:
                raise ValueError("query text or OCR differs for a reused pair")
            found[q, p] = score
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("missing", "merge"):
        sub = commands.add_parser(command)
        names = ["full", "static", "static-scores", "out"]
        if command == "merge":
            names.extend(["extra", "extra-scores"])
        for name in names:
            sub.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("choose a fresh output path")
    full, raw = read_pairs_snapshot(args.full)
    if full["dataset"] != "vidoseek" or full.get("partition") != "validation":
        parser.error("expected ViDoSeek validation pairs")
    order = list(map(tuple, full["pairs"]))
    wanted = set(order)
    source, scores, policy, original = read_cache(args.static, args.static_scores)
    matched = align(full, source, scores, wanted)
    missing = [pair for pair in order if pair not in matched]
    if args.command == "missing":
        if not missing:
            parser.error("no missing scores")
        queries = dict.fromkeys(q for q, p in missing)
        pages = dict.fromkeys(p for q, p in missing)
        write_json(args.out, {key: full[key] for key in ("dataset", "partition", "top_k")} |
                   {"synthetic": full.get("synthetic", False), "pairs": missing,
                    "queries": {q: full["queries"][q] for q in queries},
                    "pages": {p: full["pages"][p] for p in pages}})
        return
    extra, values, new_policy, supplement = read_cache(args.extra, args.extra_scores)
    if policy != new_policy or set(map(tuple, extra["pairs"])) != set(missing):
        parser.error("supplement must match the historical policy and exactly cover the missing pairs")
    matched.update(align(full, extra, values, set(missing)))
    write_scores(args.out, args.full, [matched[pair] for pair in order],
                 {**policy, "source": "historical cache join by query and page",
                  "synthetic": full.get("synthetic", False), "parents": [original, supplement]},
                 expected_pairs_sha256=hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
