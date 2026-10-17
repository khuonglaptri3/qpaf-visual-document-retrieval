from __future__ import annotations

import json

import pandas as pd

from scripts.finalize_p0_03 import (
    _rank_contract,
    _read_text_preserving_legacy_encoding,
    summarize_baselines,
)


def _scores() -> pd.DataFrame:
    rows = []
    values = [
        ("p1", 1.0, 1.0, 0.0, 0.5, 1, 2, 3, 2),
        ("p2", 0.0, 0.5, 1.0, 1.0, 2, 1, 1, 1),
        ("p3", 0.0, 0.0, 0.5, 0.0, 3, 3, 2, 3),
    ]
    for page_id, relevance, bm25, dense, visual, bm25_rank, dense_rank, stage1_rank, visual_rank in values:
        rows.append(
            {
                "dataset": "d",
                "query_id": "q",
                "page_id": page_id,
                "source": "s",
                "relevance": relevance,
                "bm25_score": bm25,
                "dense_score": dense,
                "stage1_score": dense,
                "visual_score": visual,
                "branch_ranks": json.dumps(
                    {
                        "bm25": bm25_rank,
                        "dense": dense_rank,
                        "stage1": stage1_rank,
                        "visual": visual_rank,
                    }
                ),
            }
        )
    return pd.DataFrame(rows)


def test_rank_contract_requires_each_query_branch_to_be_a_permutation() -> None:
    scores = _scores()
    assert _rank_contract(scores)
    invalid = scores.copy()
    ranks = json.loads(invalid.loc[1, "branch_ranks"])
    ranks["bm25"] = 1
    invalid.loc[1, "branch_ranks"] = json.dumps(ranks)
    assert not _rank_contract(invalid)


def test_candidate_baseline_summary_is_explicitly_non_official() -> None:
    summary = summarize_baselines(_scores())
    assert summary["status"] == "PASS"
    assert summary["scope"] == "candidate_pool_metrics_not_official_full_corpus_metrics"
    assert set(summary["methods"]) == {"bm25", "dense", "visual", "rrf", "fixed_equal"}
    for metrics in summary["methods"].values():
        assert set(metrics) == {"ndcg_at_10", "recall_at_1", "recall_at_3", "mrr_at_10"}
        assert all(0.0 <= value <= 1.0 for value in metrics.values())


def test_legacy_utf16_baseline_log_is_read_without_changing_bytes(tmp_path) -> None:
    path = tmp_path / "baseline.txt"
    path.write_bytes("29 passed in 4.66s\r\n".encode("utf-16"))
    assert _read_text_preserving_legacy_encoding(path).splitlines() == ["29 passed in 4.66s"]
