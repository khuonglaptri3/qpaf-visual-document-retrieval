from __future__ import annotations

from itertools import product

import numpy as np


W7 = np.asarray(
    [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.5, 0.5, 0.0),
        (0.5, 0.0, 0.5),
        (0.0, 0.5, 0.5),
        (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
    ],
    dtype=float,
)


def w66() -> np.ndarray:
    values = []
    for a, b, c in product(range(11), repeat=3):
        if a + b + c == 10:
            values.append((a / 10.0, b / 10.0, c / 10.0))
    return np.asarray(values, dtype=float)


def get_profiles(name: str) -> np.ndarray:
    lowered = name.lower()
    if lowered == "w7":
        return W7.copy()
    if lowered == "w66":
        return w66()
    raise ValueError(f"Unknown profile grid: {name}")

