"""A004 loss: pairwise logistic with |ΔnDCG@10| pair weights (LambdaRank-style).

Pair weights come from the model's own detached ranking, ordered by the metric
tie rule (`qpaf.m24.evaluator.rank`). For binary gains, swapping positive i and
negative j changes DCG@k by |d(p_i) - d(p_j)|; the query's IDCG is a constant
factor that cancels in sum(w * softplus) / sum(w), so `relevant_total` is not
an input.
"""
import math

import torch
from torch.nn import functional as F

from qpaf.m12.features import validate_mask
from qpaf.m12.losses import PairwiseLoss
from qpaf.m24.evaluator import rank


def discounts(page_ids, scores, cutoff=10):
    """Per-candidate DCG discount in input order; zero at or past `cutoff`."""
    values = [0.]*len(page_ids)
    for position, index in enumerate(rank(page_ids, scores)):
        if position < cutoff:
            values[index] = 1/math.log2(position+2)
    return values


def lambda_pairwise_logistic_loss(scores, labels, mask, page_ids, cutoff=10):
    if (not isinstance(scores, torch.Tensor) or not isinstance(labels, torch.Tensor)
            or scores.ndim != 2 or scores.dtype not in (torch.float32, torch.float64)
            or labels.shape != scores.shape or labels.device != scores.device or labels.is_complex()):
        raise ValueError('Scores and binary labels must align as [batch, candidates]')
    validate_mask(mask, scores.shape, scores.device)
    if (not torch.isfinite(scores[mask]).all()
            or not ((labels[mask] == 0) | (labels[mask] == 1)).all()):
        raise ValueError('Active scores must be finite and labels binary 0/1')
    if (not isinstance(page_ids, (list, tuple)) or len(page_ids) != scores.shape[0]
            or any(not isinstance(ids, (list, tuple)) or len(ids) != scores.shape[1] for ids in page_ids)):
        raise ValueError('Page IDs must align with [batch, candidates]')
    if type(cutoff) is not int or cutoff < 1:
        raise ValueError('cutoff must be a positive integer')
    losses, pairs = [], 0
    for qi in range(scores.shape[0]):
        active = mask[qi].nonzero(as_tuple=False).flatten()
        positive, negative = active[labels[qi, active] == 1], active[labels[qi, active] == 0]
        if not positive.numel() or not negative.numel():
            continue
        ids = [page_ids[qi][i] for i in active.tolist()]
        local = discounts(ids, scores[qi, active].detach().tolist(), cutoff)
        d = scores.new_zeros(scores.shape[1])
        d[active] = torch.tensor(local, dtype=scores.dtype, device=scores.device)
        weights = (d[positive][:, None]-d[negative][None, :]).abs()
        total = weights.sum()
        if total <= 0:
            raise ValueError(f'Query {qi}: no pair touches the top {cutoff}')
        margins = scores[qi, negative][None, :]-scores[qi, positive][:, None]
        losses.append((weights*F.softplus(margins)).sum()/total)
        pairs += positive.numel()*negative.numel()
    if not losses:
        raise ValueError('No query has both a positive and a negative candidate')
    return PairwiseLoss(torch.stack(losses).mean(), len(losses), scores.shape[0]-len(losses), pairs)
