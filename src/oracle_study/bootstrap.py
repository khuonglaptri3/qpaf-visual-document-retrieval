from __future__ import annotations

import numpy as np

from .constants import SEED


def bootstrap_mean_ci(
    values: np.ndarray,
    n_resamples: int = 10_000,
    seed: int = SEED,
    confidence: float = 0.95,
) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        raise ValueError("Cannot bootstrap an empty sample")
    rng = np.random.default_rng(seed)
    estimates = np.empty(n_resamples, dtype=float)
    batch = 256
    for start in range(0, n_resamples, batch):
        size = min(batch, n_resamples - start)
        indices = rng.integers(0, values.size, size=(size, values.size))
        estimates[start : start + size] = values[indices].mean(axis=1)
    tail = (1.0 - confidence) / 2.0
    return tuple(float(x) for x in np.quantile(estimates, [tail, 1.0 - tail]))


def bootstrap_ratio_ci(
    numerator: np.ndarray,
    denominator: np.ndarray,
    n_resamples: int = 10_000,
    seed: int = SEED,
    confidence: float = 0.95,
) -> tuple[float, float]:
    numerator = np.asarray(numerator, dtype=float)
    denominator = np.asarray(denominator, dtype=float)
    if numerator.shape != denominator.shape or numerator.size == 0:
        raise ValueError("Ratio bootstrap arrays must be non-empty and have equal shape")
    rng = np.random.default_rng(seed)
    estimates = np.empty(n_resamples, dtype=float)
    batch = 256
    for start in range(0, n_resamples, batch):
        size = min(batch, n_resamples - start)
        indices = rng.integers(0, numerator.size, size=(size, numerator.size))
        num = numerator[indices].mean(axis=1)
        den = denominator[indices].mean(axis=1)
        estimates[start : start + size] = np.divide(
            num,
            den,
            out=np.ones_like(num),
            where=np.abs(den) > 1e-15,
        )
    tail = (1.0 - confidence) / 2.0
    return tuple(float(x) for x in np.quantile(estimates, [tail, 1.0 - tail]))

