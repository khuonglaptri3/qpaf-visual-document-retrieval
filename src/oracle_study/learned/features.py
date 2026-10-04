from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import torch
from torch import nn


FEATURE_DIM = 13
CHANNELS = 3


def _page_id_rows(
    page_ids: Sequence[Sequence[str]], batch_size: int, candidates: int
) -> list[list[str]]:
    if len(page_ids) != batch_size:
        raise ValueError("Page IDs must have shape [B,C]")
    rows = [list(row) for row in page_ids]
    if any(len(row) != candidates for row in rows):
        raise ValueError("Page IDs must have shape [B,C]")
    if any(not isinstance(page_id, str) for row in rows for page_id in row):
        raise TypeError("Page IDs must be strings")
    return rows


def build_fusion_features(
    scores: torch.Tensor,
    page_ids: Sequence[Sequence[str]],
    valid_mask: torch.Tensor,
) -> torch.Tensor:
    """Build Eq. 3 features with gradients intentionally stopped at the output.

    Normalized rank is one for the best candidate and zero for the worst. Score
    ties use ascending page ID. A single valid candidate receives rank one and a
    zero top-1/top-2 gap.
    """
    if not isinstance(scores, torch.Tensor) or scores.ndim != 3:
        raise ValueError("Scores must have shape [B,C,3]")
    if scores.shape[-1] != CHANNELS:
        raise ValueError("Scores must have shape [B,C,3]")
    if scores.dtype != torch.float32:
        raise TypeError("Scores must be float32")
    if not isinstance(valid_mask, torch.Tensor) or valid_mask.dtype != torch.bool:
        raise TypeError("Valid mask must be a bool tensor")
    if valid_mask.shape != scores.shape[:2]:
        raise ValueError("Valid mask must have shape [B,C]")
    if not torch.isfinite(scores).all():
        raise ValueError("Scores must be finite")
    if torch.any((scores < 0) | (scores > 1)):
        raise ValueError("Scores must be in [0,1]")

    batch_size, candidates, _ = scores.shape
    id_rows = _page_id_rows(page_ids, batch_size, candidates)
    score_rows = scores.detach().cpu().numpy()
    mask_rows = valid_mask.detach().cpu().numpy()
    output = np.zeros((batch_size, candidates, FEATURE_DIM), dtype=np.float32)

    for batch in range(batch_size):
        valid_indices = np.flatnonzero(mask_rows[batch])
        if valid_indices.size == 0:
            raise ValueError("Every query requires at least one valid candidate")
        valid_ids = np.asarray(
            [id_rows[batch][index] for index in valid_indices], dtype=str
        )
        if len(np.unique(valid_ids)) != len(valid_ids):
            raise ValueError("Page IDs must be unique at valid positions")
        values = score_rows[batch, valid_indices]
        ranks = np.empty_like(values, dtype=np.float32)
        gaps = np.empty(CHANNELS, dtype=np.float32)
        for channel in range(CHANNELS):
            order = np.lexsort((valid_ids, -values[:, channel]))
            if len(order) == 1:
                ranks[:, channel] = 1.0
                gaps[channel] = 0.0
            else:
                normalized = 1.0 - np.arange(len(order), dtype=np.float32) / (
                    len(order) - 1
                )
                ranks[order, channel] = normalized
                gaps[channel] = values[order[0], channel] - values[order[1], channel]

        medians = np.median(values, axis=0)
        margins = values - medians
        disagreement = np.std(ranks, axis=1, dtype=np.float32)[:, None]
        output[batch, valid_indices] = np.concatenate(
            [
                values.astype(np.float32, copy=False),
                ranks,
                margins.astype(np.float32, copy=False),
                np.broadcast_to(gaps, values.shape),
                disagreement,
            ],
            axis=1,
        )

    return torch.from_numpy(output).to(device=scores.device)


class FusionFeatureBuilder(nn.Module):
    def forward(
        self,
        scores: torch.Tensor,
        page_ids: Sequence[Sequence[str]],
        valid_mask: torch.Tensor,
    ) -> torch.Tensor:
        return build_fusion_features(scores, page_ids, valid_mask)
