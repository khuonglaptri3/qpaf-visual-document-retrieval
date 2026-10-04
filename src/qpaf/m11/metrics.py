"""Binary relevance metrics; denominator never depends on the candidate pool."""
import math
import random


def validate_qrels(qrels):
    if not qrels or not any(value == 1 for value in qrels.values()):
        raise ValueError('Each query must have at least one relevant page')
    if any(type(value) not in (int, float) or value not in (0, 1) for value in qrels.values()):
        raise ValueError('The exact QPAF solver supports binary qrels only')


def ndcg(ranking, qrels, k):
    validate_qrels(qrels)
    if type(k) is not int or k < 1 or len(set(ranking)) != len(ranking):
        raise ValueError('Invalid cutoff or duplicate ranked page IDs')
    ideal = sum(1/math.log2(i+2) for i in range(min(k, sum(v == 1 for v in qrels.values()))))
    actual = sum(qrels.get(page, 0)/math.log2(i+2) for i, page in enumerate(ranking[:k]))
    return actual/ideal


def paired_summary(deltas, samples, seed, tolerance):
    if not deltas or samples < 1 or tolerance < 0 or any(not math.isfinite(d) for d in deltas):
        raise ValueError('Invalid paired bootstrap input')
    rng = random.Random(seed)
    count = len(deltas)
    means = sorted(sum(deltas[rng.randrange(count)] for _ in range(count))/count
                   for _ in range(samples))

    def percentile(p):
        position = (samples-1)*p
        low = math.floor(position)
        high = math.ceil(position)
        return means[low]+(means[high]-means[low])*(position-low)

    return {'mean_delta': sum(deltas)/count, 'ci95': [percentile(.025), percentile(.975)],
            'wins': sum(d > tolerance for d in deltas),
            'ties': sum(abs(d) <= tolerance for d in deltas),
            'losses': sum(d < -tolerance for d in deltas),
            'resampling_unit': 'query', 'samples': samples, 'seed': seed,
            'tie_tolerance': tolerance, 'interval': 'percentile_linear_interpolation',
            'single_query': count == 1}
