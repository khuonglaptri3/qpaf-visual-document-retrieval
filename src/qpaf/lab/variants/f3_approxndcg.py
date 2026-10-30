"""F3: ApproxNDCG@10 loss (Qin, Liu & Li 2010) on units (docs/feature_lab/F3)."""
import torch

from . import Variant

ALPHA, CUTOFF = 0.01, 10


def approx_ndcg_loss(unit_scores, unit_mask, positive, log_tau, anchor_scores, alpha=ALPHA, width=0.5):
    """1 − smooth nDCG@10: sigmoid ranks with temperature alpha, soft cut at rank 10 with the given width."""
    positive = positive & unit_mask
    valid = positive.any(1) & (unit_mask & ~positive).any(1)
    if not valid.any():
        return unit_scores.new_zeros(()), 0
    s, m, p = unit_scores[valid], unit_mask[valid], positive[valid].to(unit_scores.dtype)
    s = torch.where(m, s, s.detach().min()-1)  # padding far below every real unit
    beats = torch.sigmoid((s[:, None, :]-s[:, :, None])/alpha)*m[:, None, :]  # [b, i, j]: j above i
    rank = 0.5+beats.sum(-1)  # 1 + Σ_{j≠i}; the self term contributes 0.5
    gain = p*torch.sigmoid((CUTOFF+0.5-rank)/width)/torch.log2(1+rank)
    ideal = (1/torch.log2(torch.arange(2, CUTOFF+2, dtype=s.dtype))).cumsum(0)
    count = p.sum(1).clamp(max=CUTOFF).long()
    return (1-gain.sum(1)/ideal[count-1]).mean(), int(valid.sum())


def build(assets):
    if assets:
        raise ValueError('f3_approxndcg takes no assets')
    return Variant('f3_approxndcg', loss=approx_ndcg_loss)
