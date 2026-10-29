"""Feature-lab gate, unit pooling, default loss and the unit nDCG@10 used for every row.

LabGate generalizes the A005 anchored gate: w = softmax(log(w̄ + ε) + Δθ(x)), Δθ zero-initialized,
with optional extra inputs, an optional score calibrator and an optional hidden layer. At
initialization every variant scores exactly like the static anchor.
"""
import math

import numpy as np
import torch
from torch import nn

from qpaf.a005.losses import LOG_TAU_BOUNDS

DISCOUNT = 1/np.log2(np.arange(2, 12))


class LabGate(nn.Module):
    def __init__(self, anchor, granularity, feature_dim, *, hidden=0, calibrator=None, epsilon=1e-6):
        super().__init__()
        anchor = torch.as_tensor(anchor, dtype=torch.float64)
        if (granularity not in ('query', 'page') or anchor.shape != (3,) or (anchor < 0).any()
                or not math.isclose(anchor.sum().item(), 1., abs_tol=1e-9)):
            raise ValueError('Anchor must be three non-negative weights summing to 1; granularity query/page')
        self.granularity = granularity
        self.register_buffer('anchor', anchor)
        self.register_buffer('log_anchor', torch.log(anchor+epsilon))
        out = nn.Linear(hidden or feature_dim, 3, dtype=torch.float64)
        nn.init.zeros_(out.weight)
        nn.init.zeros_(out.bias)
        self.delta = nn.Sequential(nn.Linear(feature_dim, hidden, dtype=torch.float64), nn.Tanh(), out) if hidden else out
        self.calibrator = calibrator
        self.log_tau = nn.Parameter(torch.zeros((), dtype=torch.float64))

    def loss_log_tau(self):
        return self.log_tau.clamp(*LOG_TAU_BOUNDS)

    def forward(self, features, scores, mask):
        """Fused page scores [B, N] (0 on padding) and gate weights [B, N, 3]."""
        if self.calibrator is not None:
            scores = self.calibrator(scores, mask)
        x = torch.where(mask[..., None], features, 0.)
        if self.granularity == 'query':
            residual = self.delta(x.sum(dim=1)/mask.sum(dim=1, keepdim=True))[:, None, :].expand(-1, x.shape[1], -1)
        else:
            residual = self.delta(x)
        weights = torch.softmax(self.log_anchor+residual, dim=-1)
        return torch.where(mask, (weights*scores).sum(-1), 0.), weights


def max_pool(page_scores, units, unit_count):
    """Unit score = best page score in the unit (the frozen ViMDoc rule; identity when units are pages)."""
    return page_scores.new_zeros((page_scores.shape[0], unit_count)).scatter_reduce(
        1, units, page_scores, reduce='amax', include_self=False)


def listwise_loss(unit_scores, unit_mask, positive, log_tau, anchor_scores=None):
    """A005 multi-positive listwise loss on units; queries without both a positive and a negative are skipped."""
    positive = positive & unit_mask
    valid = positive.any(1) & (unit_mask & ~positive).any(1)
    if not valid.any():
        return unit_scores.new_zeros(()), 0
    logits = torch.where(unit_mask, unit_scores, 0.)[valid]/torch.exp(log_tau)
    log_z = torch.logsumexp(logits.masked_fill(~unit_mask[valid], -math.inf), dim=1)
    log_pos = torch.logsumexp(logits.masked_fill(~positive[valid], -math.inf), dim=1)
    return (log_z-log_pos).mean(), int(valid.sum())


def unit_max(page_scores, units, count):
    """NumPy max pooling for [pages] or [pages, K] scores."""
    page_scores = np.asarray(page_scores, dtype=np.float64)
    out = np.full((count, *page_scores.shape[1:]), -np.inf)
    np.maximum.at(out, units, page_scores)
    return out


def unit_ndcg(unit_scores, positive, relevant_total):
    """nDCG@10 with units ranked by (score desc, index asc); [U] gives a float, [U, K] gives K values."""
    scores = np.asarray(unit_scores, dtype=np.float64)
    single = scores.ndim == 1
    scores = scores[:, None] if single else scores
    order = np.argsort(-scores, axis=0, kind='stable')[:10]
    dcg = (np.asarray(positive)[order]*DISCOUNT[:len(order), None]).sum(axis=0)
    values = dcg/DISCOUNT[:min(10, relevant_total)].sum()
    return float(values[0]) if single else values
