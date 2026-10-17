from __future__ import annotations

import inspect

import pytest
import torch

from oracle_study.learned.features import FusionFeatureBuilder, build_fusion_features


def reference_batch() -> tuple[torch.Tensor, list[list[str]], torch.Tensor]:
    scores = torch.tensor(
        [
            [
                [1.0, 0.0, 0.50],
                [1.0, 1.0, 0.25],
                [0.0, 0.5, 0.75],
                [0.2, 0.2, 0.20],
                [0.3, 0.3, 0.30],
            ],
            [
                [0.1, 0.9, 0.40],
                [0.7, 0.3, 0.20],
                [0.2, 0.5, 0.80],
                [0.6, 0.1, 0.60],
                [0.4, 0.7, 0.10],
            ],
        ],
        dtype=torch.float32,
    )
    page_ids = [
        ["b", "a", "c", "pad", "pad"],
        ["p1", "p2", "p3", "p4", "p5"],
    ]
    valid_mask = torch.tensor(
        [[True, True, True, False, False], [True, True, True, True, True]]
    )
    return scores, page_ids, valid_mask


def test_reference_shape_values_padding_and_rank_convention() -> None:
    scores, page_ids, valid_mask = reference_batch()
    actual = build_fusion_features(scores, page_ids, valid_mask)

    assert actual.shape == (2, 5, 13)
    assert actual.dtype == torch.float32
    assert actual.device == scores.device
    assert torch.isfinite(actual).all()
    assert torch.equal(actual[0, 3:], torch.zeros(2, 13))

    # Feature order: score, normalized rank, median margin, query gap, disagreement.
    torch.testing.assert_close(actual[0, 0, :3], scores[0, 0])
    torch.testing.assert_close(
        actual[0, :, 3:6],
        torch.tensor(
            [
                [0.5, 0.0, 0.5],
                [1.0, 1.0, 0.0],
                [0.0, 0.5, 1.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ]
        ),
    )
    torch.testing.assert_close(actual[0, 0, 6:9], torch.tensor([0.0, -0.5, 0.0]))
    torch.testing.assert_close(actual[0, 0, 9:12], torch.tensor([0.0, 0.5, 0.25]))
    torch.testing.assert_close(actual[0, 0, 12], torch.tensor(0.23570226))


def test_page_associated_features_are_permutation_stable_and_deterministic() -> None:
    scores, page_ids, valid_mask = reference_batch()
    baseline = build_fusion_features(scores, page_ids, valid_mask)
    permutation = torch.tensor([2, 0, 1, 4, 3])
    permuted_ids = [[row[index] for index in permutation] for row in page_ids]
    permuted = build_fusion_features(
        scores[:, permutation], permuted_ids, valid_mask[:, permutation]
    )

    for batch in range(2):
        expected_by_id = {
            page_ids[batch][index]: baseline[batch, index]
            for index in torch.nonzero(valid_mask[batch], as_tuple=False).flatten()
        }
        for index in torch.nonzero(
            valid_mask[batch, permutation], as_tuple=False
        ).flatten():
            page_id = permuted_ids[batch][index]
            torch.testing.assert_close(permuted[batch, index], expected_by_id[page_id])

    for _ in range(100):
        assert torch.equal(
            baseline, FusionFeatureBuilder()(scores, page_ids, valid_mask)
        )


def test_single_candidate_has_one_rank_and_zero_gap() -> None:
    scores = torch.tensor([[[0.2, 0.4, 0.6], [0.9, 0.9, 0.9]]])
    mask = torch.tensor([[True, False]])
    actual = build_fusion_features(scores, [["only", "pad"]], mask)
    torch.testing.assert_close(actual[0, 0, 3:6], torch.ones(3))
    torch.testing.assert_close(actual[0, 0, 9:12], torch.zeros(3))


def test_contract_rejects_invalid_inputs_and_has_no_label_argument() -> None:
    scores, page_ids, valid_mask = reference_batch()
    assert "relevance" not in inspect.signature(build_fusion_features).parameters

    with pytest.raises(ValueError, match="unique"):
        duplicate_ids = [["a", "a", "c", "pad", "pad"], page_ids[1]]
        build_fusion_features(scores, duplicate_ids, valid_mask)
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        invalid = scores.clone()
        invalid[0, 0, 0] = 1.1
        build_fusion_features(invalid, page_ids, valid_mask)
    with pytest.raises(TypeError, match="float32"):
        build_fusion_features(scores.double(), page_ids, valid_mask)
