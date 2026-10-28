"""A005 §2.1 static-anchored residual gate and the ViMDoc document aggregation.

w = softmax((log(w̄ + ε) + Δθ(x)) / T), with Δθ a zero-initialized 13→3 linear map, so
epoch 0 returns the anchor for every page. QARF-SA reads query-mean features;
QPAF-SA reads page features. That is the only difference between them.
"""
import math

import torch
from torch import nn

from qpaf.m12.features import FEATURE_NAMES, FeatureBatch, validate_mask
from qpaf.m12.model import FusionOutput, fuse_scores
from qpaf.m24.evaluator import query_metrics

from .losses import LOG_TAU_BOUNDS

EPSILON = 1e-3


class AnchoredFusionGate(nn.Module):
    def __init__(self, anchor, granularity='page', *, epsilon=EPSILON, temperature=1.):
        super().__init__()
        anchor = torch.as_tensor(anchor, dtype=torch.float64)
        if (granularity not in ('query', 'page') or anchor.shape != (3,) or (anchor < 0).any()
                or not math.isclose(anchor.sum().item(), 1., abs_tol=1e-12)):
            raise ValueError('Anchor must be three non-negative weights summing to 1; granularity query/page')
        if not (math.isfinite(epsilon) and epsilon > 0 and math.isfinite(temperature) and temperature > 0):
            raise ValueError('epsilon and temperature must be finite and positive')
        self.granularity, self.temperature = granularity, float(temperature)
        self.register_buffer('log_anchor', torch.log(anchor+epsilon))
        self.delta = nn.Linear(len(FEATURE_NAMES), 3, dtype=torch.float64)
        nn.init.zeros_(self.delta.weight)
        nn.init.zeros_(self.delta.bias)
        # Listwise-loss temperature (A005 §2.2), learned on train labels only.
        self.log_tau = nn.Parameter(torch.zeros((), dtype=torch.float64))

    def loss_log_tau(self):
        return self.log_tau.clamp(*LOG_TAU_BOUNDS)

    def forward(self, batch):
        if not isinstance(batch, FeatureBatch):
            raise ValueError('AnchoredFusionGate requires a FeatureBatch')
        values, scores, mask = batch.values, batch.scores, batch.mask
        validate_mask(mask, values.shape[:2], values.device)
        if not mask.any(dim=1).all() or not torch.isfinite(values[mask]).all():
            raise ValueError('Each query needs finite features for at least one candidate')
        frozen = torch.where(mask[..., None], values.detach(), 0.)
        if self.granularity == 'query':
            residual = self.delta(frozen.sum(dim=1)/mask.sum(dim=1, keepdim=True))[:, None, :]
            residual = residual.expand(-1, values.shape[1], -1)
        else:
            residual = self.delta(frozen)
        weights = torch.softmax((self.log_anchor+residual)/self.temperature, dim=-1)
        weights = torch.where(mask[..., None], weights, 0.)
        return FusionOutput(weights, fuse_scores(scores, weights, mask))


def document_of(page_id):
    """M4.1 frozen mapping: drop the final underscore segment."""
    head, sep, _ = page_id.rpartition('_')
    if not sep or not head:
        raise ValueError(f'page ID has no document prefix: {page_id!r}')
    return head


def document_scores(page_scores, page_ids):
    """Max fused page score per document; a tie goes to the smallest page ID, so one page gets the gradient.

    Returns (document_ids ascending, scores tensor) for one query's active pages.
    """
    best = {}
    for index in sorted(range(len(page_ids)), key=lambda i: (-page_scores[i].item(), page_ids[i])):
        best.setdefault(document_of(page_ids[index]), index)
    documents = sorted(best)
    return documents, torch.stack([page_scores[best[document]] for document in documents])


def document_metrics(page_ids, page_scores, relevant_documents):
    """Document-unit metrics: rank by (score desc, document ID asc); IDCG over every relevant document."""
    documents, scores = document_scores(torch.as_tensor(page_scores, dtype=torch.float64), page_ids)
    order = sorted(range(len(documents)), key=lambda i: (-scores[i].item(), documents[i]))
    relevant = set(relevant_documents)
    return query_metrics([int(documents[i] in relevant) for i in order], len(relevant))
