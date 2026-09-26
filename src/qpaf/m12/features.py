"""Thirteen inference-time features from frozen scores; no label inputs."""
from dataclasses import dataclass
import re

import torch

FEATURE_NAMES = (
    'score_bm25', 'score_dense', 'score_visual',
    'rr_bm25', 'rr_dense', 'rr_visual',
    'gap_bm25', 'gap_dense', 'gap_visual',
    'disagreement_bm25_dense', 'disagreement_bm25_visual',
    'disagreement_dense_visual', 'query_length',
)


@dataclass(frozen=True)
class FeatureBatch:
    values: torch.Tensor
    scores: torch.Tensor
    mask: torch.Tensor


def validate_mask(mask, shape, device):
    if (not isinstance(mask, torch.Tensor) or mask.dtype != torch.bool
            or tuple(mask.shape) != tuple(shape) or mask.device != device):
        raise ValueError('Mask must be bool [batch, candidates] on the same device')


def build_features(raw_scores, query_texts, page_ids, mask=None, *, query_length_cap=64):
    if (not isinstance(raw_scores, torch.Tensor) or raw_scores.ndim != 3
            or raw_scores.shape[-1] != 3 or min(raw_scores.shape[:2]) < 1
            or raw_scores.dtype not in (torch.float32, torch.float64)):
        raise ValueError('Raw scores must be nonempty float32/float64 [batch, candidates, 3]')
    if type(query_length_cap) is not int or query_length_cap < 1:
        raise ValueError('query_length_cap must be a positive integer')
    batch_size, count, _ = raw_scores.shape
    if (not isinstance(query_texts, (list, tuple)) or len(query_texts) != batch_size
            or any(not isinstance(text, str) for text in query_texts)):
        raise ValueError('One query string is required per batch row')
    if (not isinstance(page_ids, (list, tuple)) or len(page_ids) != batch_size
            or any(not isinstance(ids, (list, tuple)) or len(ids) != count for ids in page_ids)):
        raise ValueError('Page IDs must align with [batch, candidates]')
    if mask is None:
        mask = torch.ones(raw_scores.shape[:2], dtype=torch.bool, device=raw_scores.device)
    validate_mask(mask, raw_scores.shape[:2], raw_scores.device)
    mask = mask.clone()
    if not mask.any(dim=1).all():
        raise ValueError('Every query needs at least one candidate')
    raw = raw_scores.detach()
    if not torch.isfinite(raw[mask]).all():
        raise ValueError('Every active candidate needs three finite scores')
    normalized = torch.zeros_like(raw)
    features = raw.new_zeros((batch_size, count, len(FEATURE_NAMES)))
    for qi in range(batch_size):
        valid = mask[qi].nonzero(as_tuple=False).flatten()
        ids = [page_ids[qi][i] for i in valid.tolist()]
        if any(not isinstance(value, str) or not value.strip() for value in ids) or len(set(ids)) != len(ids):
            raise ValueError('Active page IDs must be nonempty and unique within a query')
        values = raw[qi, valid]
        low, high = values.amin(dim=0), values.amax(dim=0)
        span = high-low
        norm = (values-low)/torch.where(span == 0, torch.ones_like(span), span)
        if not torch.isfinite(norm).all():
            raise ValueError('Score range overflows normalization; rescale the input cache')
        normalized[qi, valid] = norm
        canonical = sorted(range(len(ids)), key=lambda i: ids[i])
        canonical = torch.tensor(canonical, dtype=torch.long, device=raw.device)
        reciprocal = torch.empty_like(norm)
        for channel in range(3):
            order = canonical[torch.argsort(values[canonical, channel], descending=True, stable=True)]
            reciprocal[order, channel] = 1/torch.arange(1, len(ids)+1, dtype=raw.dtype, device=raw.device)
        gaps = raw.new_zeros(3)
        if len(ids) > 1:
            top = norm.topk(2, dim=0).values
            gaps = top[0]-top[1]
        disagreements = torch.stack(((norm[:, 0]-norm[:, 1]).abs(),
                                      (norm[:, 0]-norm[:, 2]).abs(),
                                      (norm[:, 1]-norm[:, 2]).abs()), dim=-1)
        length = min(len(re.findall(r'\w+', query_texts[qi])), query_length_cap)/query_length_cap
        features[qi, valid] = torch.cat((norm, reciprocal, gaps.expand(len(ids), 3),
                                        disagreements, raw.new_full((len(ids), 1), length)), dim=-1)
    return FeatureBatch(features, normalized, mask)
