from dataclasses import asdict

import numpy as np
import pytest

from oracle_study.metrics import evaluate_scores
from oracle_study.profiles import get_profiles
from oracle_study.qpaf import _candidate_oracle, _query_oracle
from scripts.qpaf_candidate_oracle_optimized import candidate_oracle_exact_fast


def compare_exact(
    score_matrix: np.ndarray,
    relevance: np.ndarray,
    page_ids: np.ndarray,
    grid: str,
) -> None:
    profiles = get_profiles(grid)
    query_profile, query_scores, query_metrics = _query_oracle(
        score_matrix, relevance, page_ids, profiles
    )
    expected = _candidate_oracle(
        score_matrix,
        relevance,
        page_ids,
        profiles,
        query_profile,
        query_scores,
        query_metrics,
    )
    observed = candidate_oracle_exact_fast(
        score_matrix,
        relevance,
        page_ids,
        profiles,
        query_profile,
        query_scores,
        query_metrics,
    )
    assert np.array_equal(observed[0], expected[0])
    assert np.array_equal(observed[1], expected[1])
    assert asdict(observed[2]) == asdict(expected[2])
    assert observed[3] == expected[3]
    assert asdict(evaluate_scores(observed[1], relevance, page_ids)) == asdict(
        observed[2]
    )


@pytest.mark.parametrize("grid", ["w7", "w66"])
@pytest.mark.parametrize("size", [1, 2, 5, 11, 32])
@pytest.mark.parametrize("seed", [0, 1, 17, 20260820])
def test_random_inputs_match_frozen_oracle_exactly(grid, size, seed):
    rng = np.random.default_rng(seed)
    score_matrix = rng.random((size, 3))
    relevance = rng.integers(0, 4, size=size).astype(float)
    page_ids = np.asarray([f"p{index:04d}" for index in rng.permutation(size)])
    compare_exact(score_matrix, relevance, page_ids, grid)


@pytest.mark.parametrize("grid", ["w7", "w66"])
def test_score_and_page_id_ties_match_frozen_oracle_exactly(grid):
    score_matrix = np.asarray(
        [
            [0.5, 0.5, 0.5],
            [0.5, 0.5, 0.5],
            [0.2, 0.8, 0.5],
            [0.8, 0.2, 0.5],
            [0.0, 1.0, 0.5],
            [1.0, 0.0, 0.5],
        ]
    )
    relevance = np.asarray([0.0, 3.0, 1.0, 2.0, 0.0, 1.0])
    page_ids = np.asarray(["p5", "p1", "p4", "p2", "p3", "p0"])
    compare_exact(score_matrix, relevance, page_ids, grid)


@pytest.mark.parametrize("grid", ["w7", "w66"])
def test_zero_relevance_matches_frozen_oracle_exactly(grid):
    rng = np.random.default_rng(9)
    score_matrix = rng.random((20, 3))
    relevance = np.zeros(20, dtype=float)
    page_ids = np.asarray([f"p{index}" for index in range(20)])
    compare_exact(score_matrix, relevance, page_ids, grid)


def test_bounded_larger_w66_fixture_matches_frozen_oracle_exactly():
    rng = np.random.default_rng(20260909)
    size = 128
    score_matrix = rng.random((size, 3))
    relevance = rng.integers(0, 4, size=size).astype(float)
    page_ids = np.asarray([f"page-{index:04d}" for index in rng.permutation(size)])
    compare_exact(score_matrix, relevance, page_ids, "w66")
