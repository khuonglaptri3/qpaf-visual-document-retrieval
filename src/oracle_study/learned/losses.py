from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


def _validate_inputs(
    candidate_scores: torch.Tensor,
    relevance: torch.Tensor,
    page_to_unit_groups: torch.Tensor,
    candidate_mask: torch.Tensor,
    unit_mask: torch.Tensor,
) -> None:
    if candidate_scores.ndim != 2:
        raise ValueError("Candidate scores must have shape [B,C]")
    if relevance.ndim != 2 or relevance.shape[0] != candidate_scores.shape[0]:
        raise ValueError("Relevance must have shape [B,U]")
    if page_to_unit_groups.shape != candidate_scores.shape:
        raise ValueError("Page-to-unit groups must have shape [B,C]")
    if candidate_mask.dtype != torch.bool or candidate_mask.shape != candidate_scores.shape:
        raise ValueError("Candidate mask must be bool with shape [B,C]")
    if unit_mask.dtype != torch.bool or unit_mask.shape != relevance.shape:
        raise ValueError("Unit mask must be bool with shape [B,U]")
    tensors = [relevance, page_to_unit_groups, candidate_mask, unit_mask]
    if any(tensor.device != candidate_scores.device for tensor in tensors):
        raise ValueError("All loss inputs must use the same device")
    if not candidate_scores.is_floating_point() or not relevance.is_floating_point():
        raise TypeError("Scores and relevance must be floating-point tensors")
    if not torch.isfinite(candidate_scores[candidate_mask]).all():
        raise ValueError("Valid candidate scores must be finite")
    if not torch.isfinite(relevance[unit_mask]).all():
        raise ValueError("Valid relevance values must be finite")
    if torch.any(relevance[unit_mask] < 0):
        raise ValueError("Relevance must be non-negative")
    if torch.any(candidate_mask.sum(dim=1) < 2):
        raise ValueError("Every training query requires at least two valid candidates")
    if torch.any(unit_mask.sum(dim=1) == 0):
        raise ValueError("Every query requires at least one valid evaluation unit")
    if torch.any((relevance * unit_mask).sum(dim=1) <= 0):
        raise ValueError("Every query requires at least one positive valid candidate")

    unit_count = relevance.shape[1]
    valid_groups = page_to_unit_groups[candidate_mask]
    if torch.any((valid_groups < 0) | (valid_groups >= unit_count)):
        raise ValueError("Valid page-to-unit group indices are out of range")
    for batch in range(candidate_scores.shape[0]):
        groups = page_to_unit_groups[batch, candidate_mask[batch]]
        if torch.any(~unit_mask[batch, groups]):
            raise ValueError("A valid candidate maps to an invalid evaluation unit")
        present = torch.zeros(unit_count, dtype=torch.bool, device=groups.device)
        present[groups] = True
        if torch.any(unit_mask[batch] & ~present):
            raise ValueError("Every valid evaluation unit must have a candidate")


def aggregate_evaluation_unit_scores(
    candidate_scores: torch.Tensor,
    page_to_unit_groups: torch.Tensor,
    candidate_mask: torch.Tensor,
    unit_mask: torch.Tensor,
) -> torch.Tensor:
    """Take a deterministic max per unit.

    Candidate input order must already use ascending page ID. Equal maxima retain
    the first candidate, giving Eq. 6b a single deterministic gradient recipient.
    """
    batch_size, candidates = candidate_scores.shape
    units = unit_mask.shape[1]
    flat_scores = candidate_scores.flatten()
    flat_mask = candidate_mask.flatten()
    batch_offsets = (
        torch.arange(batch_size, device=candidate_scores.device)
        .repeat_interleave(candidates)
        .mul(units)
    )
    flat_groups = page_to_unit_groups.flatten() + batch_offsets
    valid_groups = flat_groups[flat_mask]
    valid_scores = flat_scores.detach()[flat_mask]

    maxima = torch.full(
        (batch_size * units,),
        -torch.inf,
        dtype=candidate_scores.dtype,
        device=candidate_scores.device,
    )
    maxima.scatter_reduce_(
        0, valid_groups, valid_scores, reduce="amax", include_self=True
    )
    positions = torch.arange(
        batch_size * candidates, device=candidate_scores.device
    )[flat_mask]
    sentinel = batch_size * candidates
    tied_positions = torch.where(
        valid_scores == maxima[valid_groups],
        positions,
        torch.full_like(positions, sentinel),
    )
    winners = torch.full(
        (batch_size * units,),
        sentinel,
        dtype=torch.long,
        device=candidate_scores.device,
    )
    winners.scatter_reduce_(
        0, valid_groups, tied_positions, reduce="amin", include_self=True
    )
    required = unit_mask.flatten()
    if torch.any(winners[required] == sentinel):
        raise ValueError("Every valid evaluation unit must have a candidate")
    safe_winners = winners.clamp_max(sentinel - 1)
    unit_scores = flat_scores[safe_winners].reshape(batch_size, units)
    return unit_scores.masked_fill(~unit_mask, 0.0)


class ListwiseRankLoss(nn.Module):
    def __init__(self, temperature: float = 1.0) -> None:
        super().__init__()
        if not isinstance(temperature, (float, int)) or temperature <= 0:
            raise ValueError("Temperature must be positive")
        self.temperature = float(temperature)

    def forward(
        self,
        candidate_scores: torch.Tensor,
        relevance: torch.Tensor,
        page_to_unit_groups: torch.Tensor,
        candidate_mask: torch.Tensor,
        unit_mask: torch.Tensor,
    ) -> torch.Tensor:
        _validate_inputs(
            candidate_scores,
            relevance,
            page_to_unit_groups,
            candidate_mask,
            unit_mask,
        )
        unit_scores = aggregate_evaluation_unit_scores(
            candidate_scores, page_to_unit_groups, candidate_mask, unit_mask
        )
        gains = torch.pow(2.0, relevance) - 1.0
        gains = torch.where(unit_mask, gains, torch.zeros_like(gains))
        if not torch.isfinite(gains).all():
            raise ValueError("Relevance gains must be finite")
        targets = gains / gains.sum(dim=1, keepdim=True)
        logits = (unit_scores / self.temperature).masked_fill(~unit_mask, -torch.inf)
        log_probabilities = F.log_softmax(logits, dim=1)
        log_probabilities = torch.where(
            unit_mask, log_probabilities, torch.zeros_like(log_probabilities)
        )
        return -(targets * log_probabilities).sum(dim=1).mean()
