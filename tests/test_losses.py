from __future__ import annotations

import math

import pytest
import torch

from oracle_study.learned.losses import (
    ListwiseRankLoss,
    aggregate_evaluation_unit_scores,
)


def test_page_level_loss_matches_hand_computed_cross_entropy() -> None:
    scores = torch.tensor([[2.0, 1.0, 0.0]], dtype=torch.float32)
    relevance = torch.tensor([[2.0, 1.0, 0.0]], dtype=torch.float32)
    groups = torch.tensor([[0, 1, 2]])
    mask = torch.ones(1, 3, dtype=torch.bool)

    actual = ListwiseRankLoss()(scores, relevance, groups, mask, mask)
    targets = torch.tensor([3.0 / 4.0, 1.0 / 4.0, 0.0])
    expected = -(targets * torch.log_softmax(scores[0], dim=0)).sum()
    torch.testing.assert_close(actual, expected)
    assert actual.item() >= 0


def test_padding_is_excluded_from_scores_targets_and_gradients() -> None:
    loss_fn = ListwiseRankLoss()
    relevance = torch.tensor([[1.0, 0.0, 99.0]])
    groups = torch.tensor([[0, 1, -1]])
    candidate_mask = torch.tensor([[True, True, False]])
    unit_mask = torch.tensor([[True, True, False]])

    baseline_scores = torch.tensor([[0.4, 0.2, -10.0]], requires_grad=True)
    changed_scores = torch.tensor([[0.4, 0.2, 10_000.0]], requires_grad=True)
    baseline = loss_fn(
        baseline_scores, relevance, groups, candidate_mask, unit_mask
    )
    changed = loss_fn(changed_scores, relevance, groups, candidate_mask, unit_mask)
    torch.testing.assert_close(changed, baseline, atol=1e-7, rtol=0)
    changed.backward()
    assert changed_scores.grad is not None
    assert changed_scores.grad[0, 2].item() == 0.0


def test_group_aggregation_uses_first_candidate_for_equal_score_tie() -> None:
    scores = torch.tensor([[0.8, 0.8, 0.1]], requires_grad=True)
    groups = torch.tensor([[0, 0, 1]])
    candidate_mask = torch.ones(1, 3, dtype=torch.bool)
    unit_mask = torch.ones(1, 2, dtype=torch.bool)
    units = aggregate_evaluation_unit_scores(
        scores, groups, candidate_mask, unit_mask
    )
    units[0, 0].backward()
    torch.testing.assert_close(units, torch.tensor([[0.8, 0.1]]))
    torch.testing.assert_close(scores.grad, torch.tensor([[1.0, 0.0, 0.0]]))


def test_loss_rejects_missing_positive_and_too_few_candidates() -> None:
    loss_fn = ListwiseRankLoss()
    with pytest.raises(ValueError, match="positive"):
        loss_fn(
            torch.tensor([[0.2, 0.1]]),
            torch.zeros(1, 2),
            torch.tensor([[0, 1]]),
            torch.ones(1, 2, dtype=torch.bool),
            torch.ones(1, 2, dtype=torch.bool),
        )
    with pytest.raises(ValueError, match="two valid candidates"):
        loss_fn(
            torch.tensor([[0.2, 0.1]]),
            torch.tensor([[1.0, 0.0]]),
            torch.tensor([[0, -1]]),
            torch.tensor([[True, False]]),
            torch.tensor([[True, False]]),
        )


def test_uniform_predictions_start_at_log_valid_unit_count() -> None:
    scores = torch.zeros(2, 4)
    relevance = torch.tensor([[1.0, 0.0, 0.0, 0.0], [0.0, 2.0, 1.0, 0.0]])
    groups = torch.arange(4).repeat(2, 1)
    mask = torch.ones(2, 4, dtype=torch.bool)
    actual = ListwiseRankLoss()(scores, relevance, groups, mask, mask)
    assert actual.item() == pytest.approx(math.log(4.0))
