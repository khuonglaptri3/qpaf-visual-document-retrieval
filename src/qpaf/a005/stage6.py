"""A005 Stage 6: seed-averaged, query-paired comparison of QPAF-SA-v2 on the ViMDoc confirmation (A005 §6).

Reads only the Stage 5 record and the Stage 3 co-strongest set; no qrels, no model. Baselines have
no seeds, so each baseline's per-query values are passed under all three seed keys. The verdict
rests on the co-strongest baselines alone; QARF-SA-v2 is reported as the matched learned comparator.
"""
from pathlib import Path

from qpaf.m25.statistics import SEEDS, paired_report
from qpaf.m43.freeze import git, read, sha, write_json

from .stage4 import METHOD, STAGE3
from .stage5 import OUTPUT as CONFIRMATION

OUTPUT = 'evidence/revisions/a005-s6-001/aggregate.json'
VERDICT_RULE = ('QPAF_SA_BEATS_BASELINE when, for every co-strongest baseline, mean_of_seed_means > 0 and the '
                'lower end of ci95 > 0; otherwise NOT_ESTABLISHED')


class Stage6Error(ValueError):
    """An input or stored record violates the A005 Stage 6 contract."""


def require(ok, message):
    if not ok:
        raise Stage6Error(message)


def verdict(reports):
    """A005 §6: every co-strongest comparison must be positive on the mean and on the CI lower bound."""
    wins = bool(reports) and all(r['mean_of_seed_means'] > 0 and r['ci95'][0] > 0 for r in reports)
    return 'QPAF_SA_BEATS_BASELINE' if wins else 'NOT_ESTABLISHED'


def by_seed(runs):
    """{seed: {query_id: nDCG}} from the Stage 5 record's string-keyed runs."""
    require({int(seed) for seed in runs} == set(SEEDS), 'a method does not hold exactly the three seeds')
    return {int(seed): entry['per_query'] for seed, entry in runs.items()}


def build(root):
    root = Path(root)
    confirmation, stage3 = read(root/CONFIRMATION), read(root/STAGE3)
    qpaf, qarf = by_seed(confirmation['methods'][METHOD['page']]), by_seed(confirmation['methods'][METHOD['query']])
    names = stage3['co_strongest']
    for name in names:
        require(name in confirmation['baselines'], f'co-strongest baseline absent from the confirmation: {name}')
    # A baseline has no seeds: one per-query dict under every seed key leaves only the QPAF-SA seed variation.
    vs_baseline = {name: paired_report(qpaf, {seed: confirmation['baselines'][name]['per_query'] for seed in SEEDS})
                   for name in names}
    vs_qarf = paired_report(qpaf, qarf)
    seed_means = lambda runs: {s: e['ndcg_at_10'] for s, e in runs.items()}  # noqa: E731
    return {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': 6,
            'experiment_id': 'QPAF-A005-AGG-001', 'dataset': 'ViMDoc', 'split': 'confirmation', 'unit': 'document',
            'confirmation_query_count': len(next(iter(qpaf.values()))), 'co_strongest': names,
            'ndcg_at_10': {'baselines': {n: e['ndcg_at_10'] for n, e in confirmation['baselines'].items()},
                           'methods': {m: {'per_seed': seed_means(runs),
                                           'mean_of_seeds': sum(seed_means(runs).values())/len(runs)}
                                       for m, runs in confirmation['methods'].items()}},
            'vs_co_strongest': vs_baseline, 'vs_qarf_sa': vs_qarf,
            'verdict': verdict(list(vs_baseline.values())), 'verdict_rule': VERDICT_RULE,
            'confirmation_sha256': sha(root/CONFIRMATION), 'stage3_sha256': sha(root/STAGE3),
            'independent_review': 'WAIVED_BY_A006'}


def aggregate(root):
    """Create-once: statistics over the Stage 5 record, written next to the evidence."""
    root = Path(root).resolve()
    require(not (root/OUTPUT).exists(), f'output already exists: {OUTPUT}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'), 'aggregation requires a clean tracked tree')
    record = {**build(root), 'source_commit': git(root, 'rev-parse', 'HEAD')}
    (root/OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    write_json(root/OUTPUT, record)
    return record
