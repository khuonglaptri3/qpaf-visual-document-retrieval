"""Frozen three-seed, query-paired uncertainty calculations."""
import math

import numpy as np

SEEDS = (20260820, 20260821, 20260822)


def paired_report(qpaf, comparator, *, seeds=SEEDS, resamples=10000, bootstrap_seed=20260820):
    """Inputs are {seed: {query_id: per-query nDCG@10}} for both methods."""
    if (tuple(seeds) != SEEDS or set(qpaf) != set(SEEDS) or set(comparator) != set(SEEDS)
            or type(resamples) is not int or resamples < 1 or type(bootstrap_seed) is not int):
        raise ValueError('Exact three-seed inputs and a positive bootstrap budget are required')
    query_ids = None
    by_seed = {}
    for seed in SEEDS:
        left, right = qpaf[seed], comparator[seed]
        if not isinstance(left, dict) or not isinstance(right, dict) or not left or set(left) != set(right):
            raise ValueError(f'Seed {seed}: methods must cover identical nonempty query IDs')
        if query_ids is None:
            query_ids = tuple(sorted(left))
        if set(left) != set(query_ids) or any(not isinstance(q, str) or not q for q in left):
            raise ValueError(f'Seed {seed}: query IDs differ across seeds')
        if any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1
               for v in (*left.values(), *right.values())):
            raise ValueError(f'Seed {seed}: nDCG values must be finite and in [0,1]')
        by_seed[seed] = np.array([left[q]-right[q] for q in query_ids], dtype=np.float64)
    deltas = np.mean(np.stack([by_seed[s] for s in SEEDS]), axis=0)
    means = [float(np.mean(by_seed[s])) for s in SEEDS]
    rng = np.random.default_rng(bootstrap_seed)
    bootstrap = np.empty(resamples, dtype=np.float64)
    # Chunking keeps confirmation-size runs bounded in memory.
    for start in range(0, resamples, 256):
        count = min(256, resamples-start)
        indices = rng.integers(0, len(deltas), size=(count, len(deltas)))
        bootstrap[start:start+count] = deltas[indices].mean(axis=1)
    lower, upper = np.percentile(bootstrap, [2.5, 97.5])
    wins = int(np.count_nonzero(deltas > 1e-12))
    ties = int(np.count_nonzero(np.abs(deltas) <= 1e-12))
    losses = int(np.count_nonzero(deltas < -1e-12))
    positive = np.maximum(deltas, 0.)
    top_count = max(1, math.ceil(.05*len(deltas)))
    share = float(np.sort(positive)[-top_count:].sum()/positive.sum()) if positive.sum() else 0.
    return {
        'query_count': len(query_ids), 'seeds': list(SEEDS),
        'per_seed_mean_delta': dict(zip(map(str, SEEDS), means)),
        'mean_of_seed_means': float(np.mean(means)),
        'sample_std_of_seed_means': float(np.std(means, ddof=1)),
        'mean_delta': float(np.mean(deltas)),
        'ci95': [float(lower), float(upper)],
        'bootstrap': {'unit': 'query', 'resamples': resamples, 'seed': bootstrap_seed,
                      'method': 'percentile_linear'},
        'wtl': {'wins': wins, 'ties': ties, 'losses': losses,
                'fractions': {'wins': wins/len(deltas), 'ties': ties/len(deltas),
                              'losses': losses/len(deltas)}, 'tolerance': 1e-12},
        'top_5pct_positive_gain_share': share,
        'per_query': [{'query_id': q, 'seed_averaged_delta': float(delta)}
                      for q, delta in zip(query_ids, deltas)],
    }
