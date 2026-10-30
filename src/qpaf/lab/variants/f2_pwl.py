"""F2: monotone piecewise-linear score calibration per channel (docs/feature_lab/F2)."""
import torch
from torch import nn

from . import Variant

BINS = 8


class MonotonePWL(nn.Module):
    """g(s) = Σ_k p_k · clamp(K·s − k, 0, 1), p = softmax(logits): monotone, g(0)=0, g(1)=1, identity at init."""
    def __init__(self, bins=BINS):
        super().__init__()
        self.logits = nn.Parameter(torch.zeros(3, bins, dtype=torch.float64))
        self.register_buffer('offsets', torch.arange(bins, dtype=torch.float64))

    def forward(self, scores, mask):
        ramps = (scores[..., None]*len(self.offsets)-self.offsets).clamp(0, 1)
        return (ramps*torch.softmax(self.logits, dim=-1)).sum(-1)


def build(assets):
    if assets:
        raise ValueError('f2_pwl takes no assets')
    return Variant('f2_pwl', calibrator=MonotonePWL)
