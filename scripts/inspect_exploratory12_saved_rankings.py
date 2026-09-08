"""Reconstruct saved rankings for a case study; never run oracle search."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-index", type=int, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    run = (root / args.run).resolve()
    output = (root / args.output).resolve()
    if output.exists() or not output.is_relative_to(root):
        raise ValueError("Output must be a new directory within the repository")
    manifest = read_json(run / "run_manifest.json")
    assert manifest["status"] == "COMPLETE"
    assert manifest["phase1_decision"] == "NOT_APPLICABLE_EXPLORATORY_SUBSET"
    for name, expected in manifest["artifact_sha256"].items():
        path = (run / name).resolve()
        assert path.is_relative_to(run) and sha256(path) == expected, name
    proposal = read_json(
        run
        / "parent_snapshot/source_snapshot/docs/vidoseek_w7_exploratory12_proposal.json"
    )
    score_path = root / proposal["input"]["retrieval_scores_path"]
    assert sha256(score_path) == proposal["input"]["retrieval_scores_byte_sha256"]
    selected = proposal["selection"]["queries"]
    assert args.audit_index in [q["audit_index"] for q in selected]
    frame = pd.read_parquet(
        score_path,
        filters=[
            [("dataset", "=", q["dataset"]), ("query_id", "=", q["query_id"])]
            for q in selected
        ],
    )
    results = read_json(run / "per_query.json")["rows"]
    assert len(selected) == len(results) == manifest["queries"]
    summaries = []
    case = None
    case_table = None
    for query, saved in zip(selected, results):
        assert (saved["dataset"], saved["query_id"]) == (
            query["dataset"],
            query["query_id"],
        )
        part = frame.loc[
            (frame.dataset == query["dataset"]) & (frame.query_id == query["query_id"])
        ].copy()
        part = part.sort_values("page_id").reset_index(drop=True)
        assert len(part) == manifest["pages_per_query"] and part.page_id.is_unique
        matrix = part[["bm25_score", "dense_score", "visual_score"]].to_numpy(float)
        labels = part.relevance.to_numpy(float)
        ids = part.page_id.astype(str).to_numpy()
        assert np.isfinite(matrix).all() and np.isfinite(labels).all()
        # This diagnostic is deliberately restricted to the observed one-positive queries.
        assert np.count_nonzero(labels > 0) == saved["relevant_count"] == 1
        assert (labels >= 0).all()
        positive = int(np.flatnonzero(labels > 0)[0])
        assert set(saved["changed_pages"]).issubset(set(ids))
        assert len(saved["changed_pages"]) == saved["changed_candidates"]
        weights = np.tile(saved["qarf_profile"], (len(part), 1))
        for i, page_id in enumerate(ids):
            if page_id in saved["changed_pages"]:
                weights[i] = saved["changed_pages"][page_id]
        values = {
            "global": matrix @ np.asarray(saved["global_profile"]),
            "qarf": matrix @ np.asarray(saved["qarf_profile"]),
            "qpaf": np.sum(matrix * weights, axis=1),
        }
        summary = {"audit_index": query["audit_index"], "query_id": query["query_id"]}
        for name, scores in {
            **dict(zip(("bm25", "dense", "visual"), matrix.T)),
            **values,
        }.items():
            order = np.lexsort((ids, -scores))
            ranks = np.empty(len(order), dtype=int)
            ranks[order] = np.arange(1, len(order) + 1)
            part[f"{name}_rank"] = ranks
            if name in values:
                part[f"{name}_fused_score"] = scores
                rank = int(ranks[positive])
                # Independent closed form for exactly one positive, including graded relevance.
                metrics = {
                    "ndcg10": 1 / np.log2(rank + 1) if rank <= 10 else 0.0,
                    "mrr10": 1 / rank if rank <= 10 else 0.0,
                    "recall1": float(rank == 1),
                    "recall3": float(rank <= 3),
                }
                for metric, value in metrics.items():
                    assert abs(value - saved[f"{name}_metrics"][metric]) <= 1e-12
                summary[f"{name}_relevant_rank"] = rank
                summary[f"{name}_ndcg10"] = float(metrics["ndcg10"])
        summaries.append(summary)
        if query["audit_index"] == args.audit_index:
            part["qpaf_weights_bm25_dense_visual"] = [
                json.dumps(w.tolist()) for w in weights
            ]
            part["weight_changed"] = [p in saved["changed_pages"] for p in ids]
            case_table = part
            case = {
                **summary,
                "relevant_page_id": ids[positive],
                "global_profile": saved["global_profile"],
                "qarf_profile": saved["qarf_profile"],
                "changed_pages": saved["changed_pages"],
                "source": saved["source"],
                "accepted_updates": saved["accepted_updates"],
            }
    summary_table = pd.DataFrame(summaries)
    ceiling = int((summary_table.global_ndcg10 == 1.0).sum())
    assert case is not None and case_table is not None
    selected_pages = case_table.loc[
        (case_table.relevance > 0) | case_table.weight_changed
    ]
    report = {
        "status": "PASS_SAVED_RANKING_RECONSTRUCTION",
        "classification": "post_hoc_case_study_not_new_oracle_run",
        "oracle_search_executed": False,
        "seed": proposal["selection"]["seed"],
        "verified_queries": len(summaries),
        "metrics_checked": len(summaries) * 3 * 4,
        "global_ceiling_queries": ceiling,
        "case": case,
        "relevant_and_changed_pages": selected_pages.to_dict(orient="records"),
        "input_sha256": {
            "run_manifest": sha256(run / "run_manifest.json"),
            "retrieval_scores": sha256(score_path),
            "script": sha256(Path(__file__)),
        },
    }
    output.mkdir(parents=True, exist_ok=False)
    case_table.to_csv(output / "query_page_rankings.csv", index=False, encoding="utf-8")
    summary_table.to_csv(
        output / "all_query_relevant_ranks.csv", index=False, encoding="utf-8"
    )
    report["output_sha256"] = {p.name: sha256(p) for p in sorted(output.glob("*.csv"))}
    (output / "case_review.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "metrics_checked": report["metrics_checked"],
                "global_ceiling_queries": ceiling,
                "case": case,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
