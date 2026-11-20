"""Run small synthetic demonstrations using the production Jev commands."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import mkdtemp

from . import cli
from .contracts import read_json, write_json


ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "docs/reports/tasks/jev-runnable-team-kit-20261120/evidence/runs"


def _command(*args):
    code = cli.main([str(arg) for arg in args])
    if code:
        raise ValueError(f"demo command {args[0]!r} exited {code}")


def _prepare(out, partition=None):
    source, splits = out / "f9_pairs.json", out / "splits.json"
    write_json(source, {
        "dataset": "synthetic-toy-jev-demo", "synthetic": True, "top_k": 2,
        "queries": {"q1": "red apple", "q2": "blue bicycle"},
        "pages": {"p1": "a red apple", "p2": "a blue bicycle", "p3": ""},
        "pairs": [["q1", "p1"], ["q1", "p3"], ["q2", "p2"], ["q2", "p3"]],
        "base_scores": [1, 2, 1, 2],
    })
    write_json(splits, {
        "splits": {"q1": "train", "q2": "validation"},
        "groups": {"q1": "toy-group-1", "q2": "toy-group-2"},
        "synthetic": True,
    })
    prepared = out / "prepared"
    selection = [] if partition is None else ["--splits", splits, "--partition", partition]
    _command("prepare", "--f9-pairs", source, "--out", prepared, *selection)
    return prepared / "pairs.json", splits


def _phat(out, config):
    pairs, _ = _prepare(out, config["partition"])
    _command("doctor", "--pairs", pairs, "--scores", pairs.with_name("base_scores.json"))


def _thanh(out, config):
    pairs, splits = _prepare(out)
    qrels, scores = out / "qrels.json", out / "scores.json"
    write_json(qrels, {"q1": {"p1": 1, "outside-demo-pool": 1}, "q2": {"p2": 1}})
    _command("score", "--backend", "lexical", "--pairs", pairs, "--out", scores)
    common = ["--pairs", pairs, "--qrels", qrels, "--k", config["k"]]
    for name, selected in (("baseline", ["--baseline"]), ("evaluation", ["--scores", scores])):
        _command("evaluate", *common, *selected, "--out", out / f"{name}.json", "--csv", out / f"{name}.csv")
    _command("compare", "--left", out / "baseline.json", "--right", out / "evaluation.json",
             "--groups", splits, "--resamples", config["resamples"],
             "--out", out / "comparison.json", "--csv", out / "comparison.csv")


def _khuong(out, config):
    pairs, splits = _prepare(out, config["partition"])
    qrels, data = out / "page-qrels.json", out / "train.jsonl"
    write_json(qrels, {"q1": {"p1": 1, "p3": 0}})
    _command("export-train", "--pairs", pairs, "--splits", splits, "--qrels", qrels, "--out", data)
    for init in ("kev", "base"):
        stream = StringIO()
        with redirect_stdout(stream):
            _command("train", "--init", init, "--data", data, "--out", out / f"{init}-checkpoint",
                     *config["training_args"])
        write_json(out / f"{init}-plan.json", json.loads(stream.getvalue()))


def main(owner, argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    if args and args[0] not in ("demo", "--out", "-h", "--help") and not args[0].startswith("--out="):
        return cli.main(args)
    try:
        config = read_json(ROOT / "configs/jev" / f"{owner}.json")
        parser = argparse.ArgumentParser(
            description=f"Offline synthetic {owner} demo: {config['workflow']}.",
            epilog="Pass any shared Jev command (e.g. doctor --help or prepare --help) for real inputs.",
        )
        parser.add_argument("--out", type=Path, help="New output directory (default: unique synthetic run in evidence)")
        options = parser.parse_args(args[1:] if args[:1] == ["demo"] else args)
        out = options.out
        if out is None:
            parent = RUNS / owner
            parent.mkdir(parents=True, exist_ok=True)
            out = Path(mkdtemp(prefix="synthetic-", dir=parent))
        else:
            try:
                out.mkdir(parents=True, exist_ok=False)
            except FileExistsError as exc:
                raise ValueError(f"demo output directory must be new: {out}") from exc
        workflows = {"phat": _phat, "thanh": _thanh, "khuong": _khuong}
        workflows[owner](out, config)
        print(f"Synthetic {owner} demo artifacts: {out}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Jev: {exc}", file=sys.stderr)
        return 2
