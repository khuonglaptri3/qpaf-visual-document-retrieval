"""F2: PWL calibration blended with a normalized RRF-k60 channel (docs/feature_lab/F2)."""
import torch
from torch import nn

from . import Variant
from .f2_pwl import MonotonePWL


def rrf_channel(scores, mask, k=60):
    """(k+1)/(k+rank) per channel among the active pages; ties go to the smaller page index, padding is 0."""
    masked = torch.where(mask[..., None], scores, -torch.inf)
    order = torch.argsort(masked, dim=1, descending=True, stable=True)
    rank = torch.empty_like(order)
    rank.scatter_(1, order, torch.arange(1, scores.shape[1]+1).view(1, -1, 1).expand_as(order))
    return torch.where(mask[..., None], (k+1)/(k+rank.to(scores.dtype)), 0.)


class PWLRankBlend(MonotonePWL):
    """g + c·(u − g) per channel, c zero-initialized, so epoch 0 is still the identity."""
    def __init__(self):
        super().__init__()
        self.blend = nn.Parameter(torch.zeros(3, dtype=torch.float64))

    def forward(self, scores, mask):
        g = super().forward(scores, mask)
        return g+self.blend*(rrf_channel(scores, mask)-g)


def build(assets):
    if assets:
        raise ValueError('f2_pwl_rrf takes no assets')
    return Variant('f2_pwl_rrf', calibrator=PWLRankBlend)
