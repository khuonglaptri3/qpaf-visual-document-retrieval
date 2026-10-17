from __future__ import annotations

import torch
from torch import nn


FEATURE_DIM = 13
CHANNELS = 3


def _validate_features(features: torch.Tensor, valid_mask: torch.Tensor) -> None:
    if features.ndim != 3 or features.shape[-1] != FEATURE_DIM:
        raise ValueError("Features must have shape [B,C,13]")
    if not features.is_floating_point() or not torch.isfinite(features).all():
        raise ValueError("Features must be finite floating-point values")
    if valid_mask.dtype != torch.bool or valid_mask.shape != features.shape[:2]:
        raise ValueError("Valid mask must be bool with shape [B,C]")
    if valid_mask.device != features.device:
        raise ValueError("Features and valid mask must use the same device")


def _zero_linear(linear: nn.Linear) -> None:
    nn.init.zeros_(linear.weight)
    nn.init.zeros_(linear.bias)


class LinearQPAFGate(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = nn.Linear(FEATURE_DIM, CHANNELS)
        _zero_linear(self.linear)

    def forward(
        self, features: torch.Tensor, valid_mask: torch.Tensor
    ) -> torch.Tensor:
        _validate_features(features, valid_mask)
        return torch.softmax(self.linear(features), dim=-1)


class LinearQARFGate(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = nn.Linear(FEATURE_DIM, CHANNELS)
        _zero_linear(self.linear)

    def forward(
        self, features: torch.Tensor, valid_mask: torch.Tensor
    ) -> torch.Tensor:
        _validate_features(features, valid_mask)
        counts = valid_mask.sum(dim=1, keepdim=True)
        if torch.any(counts == 0):
            raise ValueError("Every query requires at least one valid candidate")
        pooled = (features * valid_mask.unsqueeze(-1)).sum(dim=1) / counts
        query_weights = torch.softmax(self.linear(pooled), dim=-1)
        return query_weights.unsqueeze(1).expand(-1, features.shape[1], -1)


class FusionScorer(nn.Module):
    def forward(
        self,
        scores: torch.Tensor,
        weights: torch.Tensor,
        valid_mask: torch.Tensor,
    ) -> torch.Tensor:
        if scores.ndim != 3 or scores.shape[-1] != CHANNELS:
            raise ValueError("Scores must have shape [B,C,3]")
        if weights.shape != scores.shape:
            raise ValueError("Weights must have the same shape as scores")
        if valid_mask.dtype != torch.bool or valid_mask.shape != scores.shape[:2]:
            raise ValueError("Valid mask must be bool with shape [B,C]")
        if scores.device != weights.device or scores.device != valid_mask.device:
            raise ValueError("Scores, weights, and mask must use the same device")
        if not scores.is_floating_point() or not weights.is_floating_point():
            raise TypeError("Scores and weights must be floating-point tensors")
        if not torch.isfinite(scores).all() or not torch.isfinite(weights).all():
            raise ValueError("Scores and weights must be finite")
        fused = (scores * weights).sum(dim=-1)
        return fused.masked_fill(~valid_mask, 0.0)
