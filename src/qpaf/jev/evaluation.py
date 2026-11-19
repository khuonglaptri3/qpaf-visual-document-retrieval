"""Unit-level ranking metrics and paired resampling."""
from collections import defaultdict
import math
import random
from statistics import mean

from .contracts import baseline_scores, number, positive_int, score_vector, text_id, validate_pairs


def minmax(values):
    low, high = min(values), max(values)
    if low == high:
        return [0.0] * len(values)
    span = high - low
    if math.isinf(span):
        # Scaling by a power of two avoids overflow for large finite scores.
        return [(value / 2 - low / 2) / (high / 2 - low / 2) for value in values]
    return [(value - low) / span for value in values]


def blend_scores(bundle, scores, lam):
    """Interpolate per-query min-max normalized scores within the given pool."""
    validate_pairs(bundle)
    lam = number(lam, "lambda")
    if not 0 <= lam <= 1:
        raise ValueError("lambda must lie in [0, 1]")
    base = baseline_scores(bundle)
    scores = score_vector(scores, len(base))
    by_query = defaultdict(list)
    for index, (query, _) in enumerate(bundle["pairs"]):
        by_query[query].append(index)
    blended = [0.0] * len(base)
    for indices in by_query.values():
        left = minmax([base[i] for i in indices])
        right = minmax([scores[i] for i in indices])
        for index, a, b in zip(indices, left, right, strict=True):
            blended[index] = (1 - lam) * a + lam * b
    return blended


def validate_qrels(qrels, queries):
    if not isinstance(qrels, dict):
        raise ValueError("qrels: expected a mapping of query IDs to unit judgments")
    if missing := sorted(queries.keys() - qrels.keys()):
        raise ValueError(f"qrels: missing judgments for queries {missing}")
    for query_id, judgments in qrels.items():
        if not text_id(query_id) or not isinstance(judgments, dict):
            raise ValueError(f"qrels: invalid judgments for query {query_id!r}")
        for unit, relevance in judgments.items():
            if not text_id(unit) or number(relevance, f"relevance for {query_id}/{unit}") < 0:
                raise ValueError(f"qrels: invalid unit ID or negative relevance for {query_id}/{unit}")
    return qrels


def _metrics(ranking, judgments, k):
    positive = sum(rel > 0 for rel in judgments.values())
    if positive == 0:
        return {f"ndcg@{k}": 0.0, f"mrr@{k}": 0.0, f"recall@{k}": 0.0, "recall@20": 0.0}
    # Dividing all gains by 2**max_relevance leaves nDCG unchanged.
    ideal = sorted(judgments.values(), reverse=True)[:k]
    scale = ideal[0]

    def dcg(relevances):
        return sum(
            2.0 ** (rel - scale) * -math.expm1(-rel * math.log(2)) / math.log2(rank + 2)
            for rank, rel in enumerate(relevances)
        )

    labels = [judgments.get(unit, 0) for unit in ranking]
    hits = [i for i, rel in enumerate(labels[:k], 1) if rel > 0]
    return {
        f"ndcg@{k}": dcg(labels[:k]) / dcg(ideal),
        f"mrr@{k}": 1 / hits[0] if hits else 0.0,
        f"recall@{k}": len(hits) / positive,
        "recall@20": sum(rel > 0 for rel in labels[:20]) / positive,
    }


def evaluate(bundle, scores, qrels, k=10):
    validate_pairs(bundle)
    positive_int(k, "k")
    scores = score_vector(scores, len(bundle["pairs"]))
    judgments = validate_qrels(qrels, bundle["queries"])
    units = bundle.get("units")
    pooled = {query: {} for query in bundle["queries"]}
    for (query, page), score in zip(bundle["pairs"], scores, strict=True):
        unit = page if units is None else units[page]
        by_unit = pooled[query]
        by_unit[unit] = max(score, by_unit.get(unit, -math.inf))
    per_query = {}
    for query, by_unit in pooled.items():
        # Match the historical F9 tie rule at the label-unit level.
        ranking = sorted(by_unit, key=lambda unit: (-by_unit[unit], unit))
        per_query[query] = _metrics(ranking, judgments[query], k)
    names = next(iter(per_query.values()))
    return {
        "dataset": bundle["dataset"],
        "synthetic": bundle.get("synthetic", False),
        "k": k,
        "ranking_scope": "provided_candidate_pool",
        "label_unit": "mapped" if units is not None else "page",
        "queries": len(per_query),
        "mean": {metric: mean(row[metric] for row in per_query.values()) for metric in names},
        "per_query": per_query,
    }


def _percentile(ordered, fraction):
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def compare(left, right, seed=20260820, resamples=10000, groups=None):
    """Report right minus left, with a query-paired or group-paired percentile CI."""
    positive_int(resamples, "resamples")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if not all(isinstance(side, dict) and isinstance(side.get("per_query"), dict) for side in (left, right)):
        raise ValueError("comparison requires two evaluation reports with per_query mappings")
    a, b = left["per_query"], right["per_query"]
    if not a or a.keys() != b.keys() or not all(map(text_id, a)):
        raise ValueError("comparison requires the same nonempty query cohort on both sides")
    for key in ("dataset", "k", "qrels_sha256", "ranking_scope", "label_unit"):
        if key in left and key in right and left[key] != right[key]:
            raise ValueError(f"comparison requires matching {key} across both reports")
    if groups is not None and not isinstance(groups, dict):
        raise ValueError("groups: expected a mapping from query ID to group ID")
    first = next(iter(a.values()))
    if not isinstance(first, dict) or not first:
        raise ValueError("comparison requires a nonempty set of per-query metrics")
    names = list(first)
    if not all(map(text_id, names)):
        raise ValueError("metric names must be nonempty strings")

    clustered = defaultdict(list)
    deltas = {}
    for query in sorted(a):
        lrow, rrow = a[query], b[query]
        if not all(isinstance(row, dict) and row.keys() == first.keys() for row in (lrow, rrow)):
            raise ValueError(f"mismatched metrics for query {query!r}")
        group = query if groups is None else groups.get(query)
        if not text_id(group):
            raise ValueError(f"groups: missing or invalid group for query {query!r}")
        delta = {}
        for name in names:
            x = number(lrow[name], f"{query}/{name} left")
            y = number(rrow[name], f"{query}/{name} right")
            delta[name] = number(y - x, f"{query}/{name} delta")
        deltas[query] = delta
        clustered[group].append(delta)

    summary = {}
    for metric in names:
        differences = [row[metric] for row in deltas.values()]
        # Sample clusters uniformly and average over all sampled queries.
        # Each metric uses the same draws, regardless of metric ordering.
        clusters = [(sum(row[metric] for row in rows), len(rows)) for rows in clustered.values()]
        rng = random.Random(seed)
        sampled = []
        for _ in range(resamples):
            total, count = 0.0, 0
            for _ in clusters:
                score, size = rng.choice(clusters)
                total += score
                count += size
            sampled.append(total / count)
        sampled.sort()
        summary[metric] = {
            "delta": mean(differences),
            "ci95": [_percentile(sampled, 0.025), _percentile(sampled, 0.975)],
            "win_tie_loss": {
                "win": sum(value > 0 for value in differences),
                "tie": sum(value == 0 for value in differences),
                "loss": sum(value < 0 for value in differences),
            },
        }
    return {
        "synthetic": bool(left.get("synthetic") or right.get("synthetic")),
        "queries": len(a),
        "resampling": "group" if groups is not None else "query",
        "groups": len(clustered),
        "seed": seed,
        "resamples": resamples,
        "metrics": summary,
        "per_query": deltas,
    }
