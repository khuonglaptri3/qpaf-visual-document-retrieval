"""Labels enter here, after the label-free feature and scoring boundary."""
from dataclasses import dataclass

import torch
from torch.nn import functional as F

from .features import validate_mask


@dataclass(frozen=True)
class PairwiseLoss:
    loss: torch.Tensor
    valid_queries: int
    skipped_queries: int
    pairs: int


def pairwise_logistic_loss(scores, labels, mask):
    if (not isinstance(scores, torch.Tensor) or not isinstance(labels, torch.Tensor)
            or scores.ndim != 2 or scores.dtype not in (torch.float32, torch.float64)
            or labels.shape != scores.shape or labels.device != scores.device or labels.is_complex()):
        raise ValueError('Scores and binary labels must align as [batch, candidates]')
    validate_mask(mask, scores.shape, scores.device)
    if (not torch.isfinite(scores[mask]).all()
            or not ((labels[mask] == 0) | (labels[mask] == 1)).all()):
        raise ValueError('Active scores must be finite and labels binary 0/1')
    losses, pairs = [], 0
    for qi in range(scores.shape[0]):
        positive = scores[qi, mask[qi] & (labels[qi] == 1)]
        negative = scores[qi, mask[qi] & (labels[qi] == 0)]
        if not positive.numel() or not negative.numel():
            continue
        losses.append(F.softplus(negative[None, :]-positive[:, None]).mean())
        pairs += positive.numel()*negative.numel()
    if not losses:
        raise ValueError('No query has both a positive and a negative candidate')
    return PairwiseLoss(torch.stack(losses).mean(), len(losses), scores.shape[0]-len(losses), pairs)
