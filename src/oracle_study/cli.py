from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .budget import run_budget_oracle
from .cache import CoverageError, build_cache
from .decision import final_decision
from .feasibility import assess_short_pilot, feasibility_markdown
from .io import read_table, write_json, write_jsonl, write_parquet
from .manifest import capture_manifest
from .preflight import run_preflight
from .qpaf import run_qpaf_oracle
from .report import decision_markdown, plot_budget, plot_budget_cost, plot_qpaf
from .sampling import stratified_query_sample


def _json(path: str | None) -> dict | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def command_build_cache(args: argparse.Namespace) -> None:
    official_metrics = read_table(args.query_metrics) if args.query_metrics else None
    output = Path(args.output_dir)
    try:
        result = build_cache(read_table(args.raw), args.min_coverage, official_metrics)
    except CoverageError as error:
        write_json(error.report, output / "coverage_report.json")
        write_parquet(error.query_audit, output / "candidate_audit.parquet")
        raise
    write_parquet(result.retrieval_scores, output / "retrieval_scores.parquet")
    write_parquet(result.query_metrics, output / "query_metrics.parquet")
    write_parquet(result.query_audit, output / "candidate_audit.parquet")
    write_json(result.coverage_report, output / "coverage_report.json")


def command_preflight(args: argparse.Namespace) -> None:
    report = run_preflight(
        read_table(args.scores),
        read_table(args.metrics),
        _json(args.reference_means),
        args.reproduction_tolerance,
    )
    write_json(report, args.output)
    if not report["passed"]:
        raise SystemExit(2)


def command_qpaf(args: argparse.Namespace) -> None:
    rows, summary, subgroup = run_qpaf_oracle(
        read_table(args.scores),
        tuple(args.grids.split(",")),
        args.bootstrap,
    )
    output = Path(args.output_dir)
    write_jsonl(rows, output / "qpaf_oracle_results.jsonl")
    write_json(summary, output / "qpaf_summary.json")
    result_frame = pd.DataFrame(
        [
            {
                "dataset": row["dataset"],
                "query_id": row["query_id"],
                "source": row["source"],
                "grid": row["grid"],
                "global_ndcg10": row["global_metrics"]["ndcg10"],
                "qarf_ndcg10": row["qarf_metrics"]["ndcg10"],
                "qpaf_ndcg10": row["qpaf_metrics"]["ndcg10"],
                "delta_qarf_vs_global": row["delta_qarf_vs_global"],
                "delta_qpaf_vs_qarf": row["delta_qpaf_vs_qarf"],
                "delta_qpaf_vs_global": row["delta_qpaf_vs_global"],
                "delta_ndcg10": row["delta_ndcg10"],
            }
            for row in rows
        ]
    )
    write_parquet(result_frame, output / "qpaf_query_summary.parquet")
    subgroup.to_csv(output / "qpaf_subgroups.csv", index=False)
    plot_qpaf(result_frame, output / "qpaf_oracle_gain.png")


def command_pilot_report(args: argparse.Namespace) -> None:
    report = assess_short_pilot(_json(args.summary), _json(args.coverage), args.grid)
    output = Path(args.output_dir)
    write_json(report, output / "pilot_feasibility.json")
    output.mkdir(parents=True, exist_ok=True)
    (output / "pilot_feasibility.md").write_text(feasibility_markdown(report), encoding="utf-8")


def command_budget(args: argparse.Namespace) -> None:
    rows, curve, summary = run_budget_oracle(
        read_table(args.metrics),
        args.random_repeats,
        args.bootstrap,
    )
    output = Path(args.output_dir)
    write_jsonl(rows, output / "budget_oracle_results.jsonl")
    curve.to_csv(output / "budget_curve.csv", index=False)
    write_json(summary, output / "budget_summary.json")
    plot_budget(curve, output / "budget_oracle_curve.png")
    plot_budget_cost(curve, output / "budget_cost_curves.png")


def command_manifest(args: argparse.Namespace) -> None:
    revisions = dict(item.split("=", 1) for item in args.checkpoint_revision)
    capture_manifest(args.heaven_root, args.dataset_file, args.output, revisions)


def command_sample(args: argparse.Namespace) -> None:
    frame = read_table(args.queries)
    if "doc_ids" in frame and frame["doc_ids"].map(type).eq(str).any():
        frame["doc_ids"] = frame["doc_ids"].map(
            lambda value: json.loads(value) if isinstance(value, str) else value
        )
    sampled = stratified_query_sample(frame, args.n)
    write_parquet(sampled, args.output)


def command_decide(args: argparse.Namespace) -> None:
    decision = final_decision(
        _json(args.qpaf_discovery),
        _json(args.qpaf_confirmation),
        _json(args.budget_discovery),
        _json(args.budget_confirmation),
    )
    output = Path(args.output_dir)
    write_json(decision, output / "final_decision.json")
    output.mkdir(parents=True, exist_ok=True)
    (output / "decision_memo.md").write_text(decision_markdown(decision), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="oracle-study")
    commands = root.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build-cache", help="Build validated Parquet artifacts from raw scores")
    build.add_argument("--raw", required=True)
    build.add_argument("--output-dir", required=True)
    build.add_argument("--min-coverage", type=float, default=0.95)
    build.add_argument(
        "--query-metrics",
        help="Optional full-corpus HEAVEN metric export; recommended for real runs",
    )
    build.set_defaults(func=command_build_cache)

    preflight = commands.add_parser("preflight", help="Validate score and metric artifacts")
    preflight.add_argument("--scores", required=True)
    preflight.add_argument("--metrics", required=True)
    preflight.add_argument("--output", required=True)
    preflight.add_argument(
        "--reference-means",
        help='JSON map such as {"ndcg_stage1": 0.42, "ndcg_full": 0.51}',
    )
    preflight.add_argument("--reproduction-tolerance", type=float, default=0.01)
    preflight.set_defaults(func=command_preflight)

    qpaf = commands.add_parser("qpaf", help="Run QARF and constrained QPAF oracles")
    qpaf.add_argument("--scores", required=True)
    qpaf.add_argument("--output-dir", required=True)
    qpaf.add_argument("--grids", default="w7,w66")
    qpaf.add_argument("--bootstrap", type=int, default=10_000)
    qpaf.set_defaults(func=command_qpaf)

    pilot = commands.add_parser("pilot-report", help="Assess the short ViDoRe V3 fusion pilot")
    pilot.add_argument("--summary", required=True)
    pilot.add_argument("--coverage", required=True)
    pilot.add_argument("--output-dir", required=True)
    pilot.add_argument("--grid", default="w7")
    pilot.set_defaults(func=command_pilot_report)

    budget = commands.add_parser("budget", help="Run Budget-Aware HEAVEN oracle")
    budget.add_argument("--metrics", required=True)
    budget.add_argument("--output-dir", required=True)
    budget.add_argument("--random-repeats", type=int, default=100)
    budget.add_argument("--bootstrap", type=int, default=10_000)
    budget.set_defaults(func=command_budget)

    manifest = commands.add_parser("manifest", help="Capture the frozen run environment")
    manifest.add_argument("--heaven-root")
    manifest.add_argument("--dataset-file", action="append", default=[])
    manifest.add_argument(
        "--checkpoint-revision",
        action="append",
        default=[],
        metavar="MODEL=REVISION",
    )
    manifest.add_argument("--output", required=True)
    manifest.set_defaults(func=command_manifest)

    sample = commands.add_parser("sample-vimdoc", help="Create the fixed 2,000-query confirmation sample")
    sample.add_argument("--queries", required=True)
    sample.add_argument("--output", required=True)
    sample.add_argument("-n", type=int, default=2_000)
    sample.set_defaults(func=command_sample)

    decide = commands.add_parser("decide", help="Apply preregistered confirmation gates")
    decide.add_argument("--qpaf-discovery")
    decide.add_argument("--qpaf-confirmation")
    decide.add_argument("--budget-discovery")
    decide.add_argument("--budget-confirmation")
    decide.add_argument("--output-dir", required=True)
    decide.set_defaults(func=command_decide)
    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
