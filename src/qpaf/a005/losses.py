"""A005 §2.2 multi-positive listwise softmax cross-entropy and its temperature profile."""
import math

import torch

from qpaf.m24.trainer import learnable

LOG_TAU_BOUNDS = (math.log(1e-3), 0.)
GOLDEN_ITERATIONS = 60


def listwise_loss(scores, labels, mask, log_tau):
    """Query-mean −log(Σ_relevant e^{s/τ} / Σ_active e^{s/τ}) over learnable queries.

    Returns (loss, valid_queries). Units are pages here; ViMDoc document
    aggregation is applied by the caller before this function.
    """
    valid = learnable(labels, mask)
    if not valid.any():
        return scores.new_zeros(()), 0
    logits = scores[valid]/torch.exp(torch.as_tensor(log_tau, dtype=scores.dtype))
    active, positive = mask[valid], (labels[valid] == 1) & mask[valid]
    log_z = torch.logsumexp(logits.masked_fill(~active, -math.inf), dim=1)
    log_pos = torch.logsumexp(logits.masked_fill(~positive, -math.inf), dim=1)
    return (log_z-log_pos).mean(), int(valid.sum())


def golden_minimum(f, low, high, iterations=GOLDEN_ITERATIONS):
    """Deterministic golden-section search; the bounds compete so a boundary minimum is kept.

    The loss is convex in 1/τ, hence unimodal in log τ, so the search is valid.
    """
    ratio = (math.sqrt(5)-1)/2
    a, b = low, high
    c, d = b-ratio*(b-a), a+ratio*(b-a)
    fc, fd = f(c), f(d)
    for _ in range(iterations):
        if fc <= fd:
            b, d, fd = d, c, fc
            c = b-ratio*(b-a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a+ratio*(b-a)
            fd = f(d)
    candidates = [(fc, c), (fd, d), (f(low), low), (f(high), high)]
    return min(candidates, key=lambda item: (item[0], item[1]))
