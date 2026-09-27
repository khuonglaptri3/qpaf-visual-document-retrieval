"""Matched query/page gates with frozen feature and retriever boundaries."""
from dataclasses import dataclass
import math

import torch
from torch import nn

from .config import validate
from .features import FEATURE_NAMES, FeatureBatch, validate_mask


@dataclass(frozen=True)
class FusionOutput:
    weights: torch.Tensor
    scores: torch.Tensor


def fuse_scores(scores, weights, mask):
    if (not isinstance(scores, torch.Tensor) or not isinstance(weights, torch.Tensor)
            or scores.ndim != 3 or scores.shape[-1] != 3 or weights.shape != scores.shape
            or scores.dtype not in (torch.float32, torch.float64)
            or weights.dtype != scores.dtype or weights.device != scores.device):
        raise ValueError('Scores and weights must share float shape [batch, candidates, 3]')
    validate_mask(mask, scores.shape[:2], scores.device)
    active_scores, active_weights = scores[mask], weights[mask]
    if (not torch.isfinite(active_scores).all() or not torch.isfinite(active_weights).all()
            or (active_scores < 0).any() or (active_scores > 1).any()
            or (active_weights < 0).any()
            or not torch.allclose(active_weights.sum(-1), torch.ones_like(active_weights[:, 0]),
                                  rtol=1e-6, atol=1e-7)):
        raise ValueError('Normalized scores must be in [0,1] and weights must be finite simplex vectors')
    frozen = torch.where(mask[..., None], scores.detach(), 0.)
    active = torch.where(mask[..., None], weights, 0.)
    return (frozen*active).sum(-1)


class FusionGate(nn.Module):
    def __init__(self, granularity='page', *, kind='linear', hidden_dim=16, temperature=1.):
        super().__init__()
        if granularity not in ('query', 'page') or kind not in ('linear', 'mlp'):
            raise ValueError('Choose query/page granularity and linear/mlp gate')
        if type(hidden_dim) is not int or hidden_dim < 1:
            raise ValueError('hidden_dim must be a positive integer')
        if type(temperature) not in (int, float) or not math.isfinite(temperature) or temperature <= 0:
            raise ValueError('temperature must be finite and positive')
        self.granularity = granularity
        self.temperature = float(temperature)
        self.gate = (nn.Linear(len(FEATURE_NAMES), 3) if kind == 'linear' else
                     nn.Sequential(nn.Linear(len(FEATURE_NAMES), hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, 3)))

    def forward(self, batch):
        if not isinstance(batch, FeatureBatch):
            raise ValueError('FusionGate requires a FeatureBatch')
        values, scores, mask = batch.values, batch.scores, batch.mask
        parameter = next(self.parameters())
        if (values.ndim != 3 or values.shape[-1] != len(FEATURE_NAMES)
                or scores.shape != (*values.shape[:2], 3)
                or values.dtype != parameter.dtype or values.device != parameter.device
                or scores.dtype != values.dtype or scores.device != values.device):
            raise ValueError('Feature/score dimensions, dtype and device must match the gate')
        validate_mask(mask, values.shape[:2], values.device)
        if not mask.any(dim=1).all() or not torch.isfinite(values[mask]).all():
            raise ValueError('Each query needs finite features for at least one candidate')
        frozen = torch.where(mask[..., None], values.detach(), 0.)
        if self.granularity == 'query':
            inputs = frozen.sum(dim=1)/mask.sum(dim=1, keepdim=True)
            logits = self.gate(inputs)[:, None, :].expand(-1, values.shape[1], -1)
        else:
            logits = self.gate(frozen)
        weights = torch.softmax(logits/self.temperature, dim=-1)
        weights = torch.where(mask[..., None], weights, 0.)
        return FusionOutput(weights, fuse_scores(scores, weights, mask))


def make_model(config, granularity):
    """Same seed and architecture for both variants, without advancing CPU RNG."""
    validate(config)
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(config['verification']['seed'])
        return FusionGate(granularity, **config['gate'])
