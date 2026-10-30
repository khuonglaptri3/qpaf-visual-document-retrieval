"""F3: listwise loss on the anchor's top-k units, extra weight on queries the anchor gets wrong at top-1."""
import math

import torch

from . import Variant

TOP_K, HARD_WEIGHT = 50, 3.


def topk_hard_loss(unit_scores, unit_mask, positive, log_tau, anchor_scores, k=TOP_K, hard=HARD_WEIGHT):
    ranked = torch.argsort(torch.where(unit_mask, anchor_scores, -math.inf), dim=1, descending=True, stable=True)
    keep = torch.zeros_like(unit_mask).scatter_(1, ranked[:, :k], True) & unit_mask
    positive = positive & keep
    valid = positive.any(1) & (keep & ~positive).any(1)
    if not valid.any():
        return unit_scores.new_zeros(()), 0
    logits = torch.where(keep, unit_scores, 0.)[valid]/torch.exp(log_tau)
    log_z = torch.logsumexp(logits.masked_fill(~keep[valid], -math.inf), 1)
    log_pos = torch.logsumexp(logits.masked_fill(~positive[valid], -math.inf), 1)
    wrong_top1 = ~positive[valid].gather(1, ranked[valid][:, :1]).squeeze(1)
    weight = torch.where(wrong_top1, hard, 1.).to(logits.dtype)
    return ((log_z-log_pos)*weight).sum()/weight.sum(), int(valid.sum())


def build(assets):
    if assets:
        raise ValueError('f3_topk_hard takes no assets')
    return Variant('f3_topk_hard', loss=topk_hard_loss)
