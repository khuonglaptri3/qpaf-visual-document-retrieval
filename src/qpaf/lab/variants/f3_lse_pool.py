"""F3: smooth-max (log-sum-exp) page→document pooling; ViMDoc only, since ViDoSeek units are pages."""
import torch

from . import Variant
from ..model import max_pool

TAU = 0.02


def lse_pool(page_scores, units, unit_count, tau=TAU):
    peak = max_pool(page_scores, units, unit_count)
    spread = torch.exp((page_scores-peak.gather(1, units))/tau)
    total = page_scores.new_zeros(peak.shape).scatter_add(1, units, spread)
    return peak+tau*torch.log(total.clamp_min(1.))  # clamp: empty padding units; exact for real units (total ≥ 1)


def build(assets):
    if assets:
        raise ValueError('f3_lse_pool takes no assets')
    return Variant('f3_lse_pool', aggregate=lse_pool)
