from __future__ import annotations

import numpy as np
import pytest

from oracle_study.metrics import evaluate_scores, normalize_three_channel_scores, stable_order


def test_three_channel_minmax_matches_equation_2() -> None:
    scores = np.asarray(
        [
            [5.0, 2.0, 7.0],
            [3.0, 2.0, 9.0],
            [1.0, 2.0, 8.0],
        ]
    )
    expected = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.5, 0.0, 1.0],
            [0.0, 0.0, 0.5],
        ]
    )
    actual = normalize_three_channel_scores(scores)
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)
    assert np.isfinite(actual).all()
    assert ((0.0 <= actual) & (actual <= 1.0)).all()
    np.testing.assert_array_equal(actual[:, 1], np.zeros(3))


def test_constant_range_at_threshold_becomes_exact_zero() -> None:
    scores = np.asarray([[0.0, 2.0, 4.0], [1e-15, 2.0, 5.0]])
    actual = normalize_three_channel_scores(scores)
    np.testing.assert_array_equal(actual[:, :2], np.zeros((2, 2)))
    np.testing.assert_array_equal(actual[:, 2], np.asarray([0.0, 1.0]))


@pytest.mark.parametrize("missing", [np.nan, np.inf, -np.inf])
def test_missing_score_policy_rejects_non_finite_values(missing: float) -> None:
    scores = np.asarray([[0.0, 1.0, 2.0], [missing, 2.0, 3.0]])
    with pytest.raises(ValueError, match="finite"):
        normalize_three_channel_scores(scores)


def test_three_channel_shape_is_exact_and_empty_matrix_is_supported() -> None:
    assert normalize_three_channel_scores(np.empty((0, 3))).shape == (0, 3)
    with pytest.raises(ValueError, match=r"\[C,3\]"):
        normalize_three_channel_scores(np.zeros((3, 4)))
    with pytest.raises(ValueError, match=r"\[C,3\]"):
        normalize_three_channel_scores(np.zeros(3))


def test_tied_scores_have_identical_order_in_100_repetitions() -> None:
    scores = np.asarray([0.5, 0.5, 0.1])
    page_ids = np.asarray(["b", "a", "c"])
    expected = np.asarray([1, 0, 2])
    for _ in range(100):
        np.testing.assert_array_equal(stable_order(scores, page_ids), expected)


def test_metric_input_contract_rejects_duplicate_ids_and_invalid_relevance() -> None:
    with pytest.raises(ValueError, match="unique"):
        evaluate_scores(np.asarray([1.0, 0.0]), np.asarray([1.0, 0.0]), np.asarray(["p", "p"]))
    with pytest.raises(ValueError, match="non-negative"):
        evaluate_scores(np.asarray([1.0]), np.asarray([-1.0]), np.asarray(["p"]))
    with pytest.raises(ValueError, match="same length"):
        evaluate_scores(np.asarray([1.0]), np.asarray([1.0, 0.0]), np.asarray(["p"]))
