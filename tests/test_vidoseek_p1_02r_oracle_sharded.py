import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oracle_study.qpaf import run_qpaf_oracle
from oracle_study.vidoseek_p1_02r_sharded import (
    _write_immutable_oracle_outputs,
    build_run_identity,
    iter_parquet_queries,
    query_order_from_audit,
    run_query_sharded_w7,
)


def _fixture_scores() -> pd.DataFrame:
    rng = np.random.default_rng(20260820)
    rows = []
    for query_index in range(5):
        for page_index in range(7):
            rows.append(
                {
                    "dataset": "fixture",
                    "query_id": f"q{query_index}",
                    "page_id": f"p{page_index:02d}",
                    "source": "multi" if query_index % 2 else "single",
                    "relevance": float(
                        page_index in {query_index % 7, (query_index + 3) % 7}
                    ),
                    "bm25_score": float(rng.random()),
                    "dense_score": float(rng.random()),
                    "stage1_score": float(rng.random()),
                    "visual_score": float(rng.random()),
                    "branch_ranks": "{}",
                }
            )
    return pd.DataFrame(rows)


def _fixture_paths(tmp_path: Path) -> tuple[pd.DataFrame, Path, Path]:
    scores = _fixture_scores()
    scores_path = tmp_path / "retrieval_scores.parquet"
    audit_path = tmp_path / "candidate_audit.parquet"
    scores.to_parquet(scores_path, index=False, row_group_size=14)
    pd.DataFrame(
        {
            "dataset": ["fixture"] * 5,
            "query_id": [f"q{index}" for index in range(5)],
        }
    ).to_parquet(audit_path, index=False)
    return scores, scores_path, audit_path


def _run_fixture(
    tmp_path: Path,
    checkpoint_root: Path,
    *,
    bootstrap_resamples: int = 100,
):
    scores, scores_path, audit_path = _fixture_paths(tmp_path)
    query_order = query_order_from_audit(audit_path)
    identity = build_run_identity(
        protocol_id="fixture_protocol",
        protocol_sha256="a" * 64,
        source_commit="b" * 40,
        retrieval_score_sha256="c" * 64,
        retrieval_score_content_sha256="d" * 64,
        query_order=query_order,
        pages_per_query=7,
        bootstrap_resamples=bootstrap_resamples,
    )
    result = run_query_sharded_w7(
        query_order=query_order,
        query_frames=lambda: iter_parquet_queries(scores_path, query_order, 7),
        expected_pages_per_query=7,
        checkpoint_root=checkpoint_root,
        run_identity=identity,
        n_bootstrap=bootstrap_resamples,
    )
    return scores, result


def test_sharded_wrapper_exactly_matches_frozen_monolithic_w7(tmp_path: Path) -> None:
    scores, (rows, summary, subgroup, stats) = _run_fixture(
        tmp_path,
        tmp_path / "checkpoints",
    )
    expected_rows, expected_summary, expected_subgroup = run_qpaf_oracle(
        scores,
        grids=("w7",),
        n_bootstrap=100,
    )

    assert rows == expected_rows
    assert summary == expected_summary
    pd.testing.assert_frame_equal(subgroup, expected_subgroup, check_exact=True)
    assert stats == {
        "plan_reused": 0,
        "global_created": 5,
        "global_reused": 0,
        "selection_reused": 0,
        "query_created": 5,
        "query_reused": 0,
    }
    run_plan = json.loads(
        (tmp_path / "checkpoints" / "run_plan.json").read_text(encoding="utf-8")
    )["payload"]
    assert run_plan["profile_selection_tie_break"] == [
        "ndcg10",
        "recall3",
        "mrr10",
    ]
    assert run_plan["ranking_tie_break"] == "ascending_page_id"
    assert run_plan["qpaf_max_sweeps"] == 2
    assert run_plan["strict_improvement_tolerance"] == 1e-12
    assert run_plan["bootstrap_unit"] == "query"
    assert run_plan["bootstrap_seed"] == 20260820
    assert run_plan["bootstrap_resamples"] == 100
    assert run_plan["bootstrap_confidence"] == 0.95
    assert run_plan["bootstrap_interval"] == "percentile"


def test_sharded_wrapper_resumes_without_overwriting_checkpoints(
    tmp_path: Path,
) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    _, first = _run_fixture(tmp_path, checkpoint_root)
    before = {
        path.relative_to(checkpoint_root).as_posix(): path.read_bytes()
        for path in checkpoint_root.rglob("*.json")
    }

    _, second = _run_fixture(tmp_path, checkpoint_root)
    after = {
        path.relative_to(checkpoint_root).as_posix(): path.read_bytes()
        for path in checkpoint_root.rglob("*.json")
    }

    assert second[:3][0] == first[:3][0]
    assert second[:3][1] == first[:3][1]
    pd.testing.assert_frame_equal(second[2], first[2], check_exact=True)
    assert second[3] == {
        "plan_reused": 1,
        "global_created": 0,
        "global_reused": 5,
        "selection_reused": 1,
        "query_created": 0,
        "query_reused": 5,
    }
    assert after == before


@pytest.mark.parametrize(
    ("missing_relative", "expected_stats"),
    [
        (
            Path("global/000002.json"),
            {
                "plan_reused": 1,
                "global_created": 1,
                "global_reused": 4,
                "selection_reused": 1,
                "query_created": 0,
                "query_reused": 5,
            },
        ),
        (
            Path("queries/000002.json"),
            {
                "plan_reused": 1,
                "global_created": 0,
                "global_reused": 5,
                "selection_reused": 1,
                "query_created": 1,
                "query_reused": 4,
            },
        ),
    ],
)
def test_sharded_wrapper_recomputes_only_an_absent_expected_checkpoint(
    tmp_path: Path,
    missing_relative: Path,
    expected_stats: dict[str, int],
) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    _, first = _run_fixture(tmp_path, checkpoint_root)
    before = {
        path.relative_to(checkpoint_root).as_posix(): path.read_bytes()
        for path in checkpoint_root.rglob("*.json")
    }
    missing = checkpoint_root / missing_relative
    missing.unlink()

    _, second = _run_fixture(tmp_path, checkpoint_root)
    after = {
        path.relative_to(checkpoint_root).as_posix(): path.read_bytes()
        for path in checkpoint_root.rglob("*.json")
    }

    assert second[:2] == first[:2]
    pd.testing.assert_frame_equal(second[2], first[2], check_exact=True)
    assert second[3] == expected_stats
    assert after == before


def test_sharded_wrapper_writes_standard_outputs_once(tmp_path: Path) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    _, (rows, summary, subgroup, stats) = _run_fixture(tmp_path, checkpoint_root)
    output_dir = tmp_path / "oracle_output"
    run_identity = {"classification": "synthetic_fixture_only"}

    _write_immutable_oracle_outputs(
        output_dir,
        rows=rows,
        summary=summary,
        subgroup=subgroup,
        run_identity=run_identity,
        checkpoint_root=checkpoint_root,
        checkpoint_stats=stats,
    )

    expected_files = {
        "qpaf_oracle_gain.png",
        "qpaf_oracle_results.jsonl",
        "qpaf_query_summary.parquet",
        "qpaf_subgroups.csv",
        "qpaf_summary.json",
        "run_manifest.json",
    }
    assert {path.name for path in output_dir.iterdir()} == expected_files
    observed_rows = [
        json.loads(line)
        for line in (output_dir / "qpaf_oracle_results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert observed_rows == rows
    assert (
        json.loads((output_dir / "qpaf_summary.json").read_text(encoding="utf-8"))
        == summary
    )
    expected_query_summary = pd.DataFrame(
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
    pd.testing.assert_frame_equal(
        pd.read_parquet(output_dir / "qpaf_query_summary.parquet"),
        expected_query_summary,
        check_exact=True,
    )
    manifest = json.loads(
        (output_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "PASS"
    assert manifest["run_identity"] == run_identity
    before = {
        path.name: path.read_bytes() for path in output_dir.iterdir() if path.is_file()
    }

    with pytest.raises(FileExistsError, match="already exists"):
        _write_immutable_oracle_outputs(
            output_dir,
            rows=rows,
            summary=summary,
            subgroup=subgroup,
            run_identity=run_identity,
            checkpoint_root=checkpoint_root,
            checkpoint_stats=stats,
        )

    after = {
        path.name: path.read_bytes() for path in output_dir.iterdir() if path.is_file()
    }
    assert after == before


def test_sharded_wrapper_rejects_corrupt_checkpoint(tmp_path: Path) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    _run_fixture(tmp_path, checkpoint_root)
    checkpoint = checkpoint_root / "queries" / "000002.json"
    envelope = json.loads(checkpoint.read_text(encoding="utf-8"))
    envelope["payload"]["row"]["qpaf_metrics"]["ndcg10"] = 0.123
    checkpoint.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(ValueError, match="content hash mismatch"):
        _run_fixture(tmp_path, checkpoint_root)


def test_sharded_wrapper_rejects_run_identity_drift(tmp_path: Path) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    _run_fixture(tmp_path, checkpoint_root)

    with pytest.raises(ValueError, match="run identity mismatch"):
        _run_fixture(
            tmp_path,
            checkpoint_root,
            bootstrap_resamples=101,
        )


def test_sharded_wrapper_rejects_unexpected_checkpoint(tmp_path: Path) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    _run_fixture(tmp_path, checkpoint_root)
    unexpected = checkpoint_root / "queries" / "duplicate.json"
    unexpected.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="checkpoint inventory mismatch"):
        _run_fixture(tmp_path, checkpoint_root)
