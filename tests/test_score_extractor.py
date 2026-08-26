from __future__ import annotations

import numpy as np

from scripts.extract_vidore_baseline import make_candidate_indices, stable_top_indices


def test_stable_top_indices_breaks_score_ties_by_page_id() -> None:
    scores = np.array([1.0, 1.0, 0.0])
    page_ids = np.array(["b", "a", "c"])
    assert stable_top_indices(scores, page_ids, 2).tolist() == [1, 0]


def test_candidate_union_uses_only_score_branches() -> None:
    page_ids = np.array(["0", "1", "2", "3"])
    stage1 = np.array([[4.0, 3.0, 2.0, 1.0]])
    bm25 = np.array([[1.0, 4.0, 3.0, 2.0]])
    dense = np.array([[1.0, 2.0, 4.0, 3.0]])
    candidates = make_candidate_indices(
        stage1,
        bm25,
        dense,
        page_ids,
        {"stage1": 1, "bm25": 1, "dense": 1},
    )
    assert candidates[0].tolist() == [0, 1, 2]


def test_full_score_is_explicitly_outside_extractor_source() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "scripts" / "extract_vidore_baseline.py").read_text(
        encoding="utf-8"
    )
    assert '"full_score": "intentionally_unavailable"' in source
    assert '"full_score_produced": False' in source
    assert "full_score =" not in source
