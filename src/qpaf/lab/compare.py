"""Feature-lab comparisons: paired query bootstrap, W/T/L, and the summary tables of docs/feature_lab/."""
import json
from pathlib import Path

import numpy as np

RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260820
TIE = 1e-12
METHODS = ('static', 'qarf', 'qpaf')


def paired(a, b, resamples=RESAMPLES, seed=BOOTSTRAP_SEED):
    """Mean of a−b over the shared queries, percentile CI95 from a query bootstrap, and W/T/L."""
    if set(a) != set(b) or not a:
        raise ValueError('paired comparison needs the same non-empty query set on both sides')
    ids = sorted(a)
    diff = np.array([a[i]-b[i] for i in ids])
    rng = np.random.default_rng(seed)
    means = np.concatenate([diff[rng.integers(0, len(diff), (min(1000, resamples-done), len(diff)))].mean(axis=1)
                            for done in range(0, resamples, 1000)])
    low, high = np.percentile(means, [2.5, 97.5])
    return {'delta': float(diff.mean()), 'ci95': [float(low), float(high)], 'wins': int((diff > TIE).sum()),
            'ties': int((np.abs(diff) <= TIE).sum()), 'losses': int((diff < -TIE).sum()), 'queries': len(ids)}


def verdict(comparison):
    """KEEP / DROP / UNCLEAR for a variant row compared with the baseline row of the same method.

    `comparison` is the dict returned by paired(variant, baseline): delta, ci95 [low, high],
    wins, ties, losses, queries.
    """
    # TODO(Tấn Phát): chốt luật giữ/bỏ một feature trước khi các thành viên chạy (5-10 dòng).
    raise NotImplementedError


def load_results(directory):
    """Every non-smoke result JSON under results/lab/<dataset>/, keyed by (dataset, variant)."""
    out = {}
    for path in sorted(Path(directory).glob('*/*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('schema') != 'qpaf-lab-v1' or record.get('smoke'):
            continue
        if (record['dataset'], record['variant']) in out:
            raise ValueError(f"two results for {record['dataset']}/{record['variant']}")
        out[(record['dataset'], record['variant'])] = record
    return out


def cell(c):
    return f"{c['delta']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}] {c['wins']}/{c['ties']}/{c['losses']}"


def summary(results, reference='baseline'):
    """Markdown: absolute means, then each variant against `reference` for QARF and QPAF."""
    lines = ['| Dataset | Variant | Queries | static | QARF | QPAF | QPAF − QARF |', '|---|---|---:|---:|---:|---:|---|']
    for (dataset, variant), r in sorted(results.items()):
        means = [f"{r['mean'][m]:.4f}" if m in r['mean'] else '—' for m in METHODS]
        gap = cell(paired(r['per_query']['qpaf'], r['per_query']['qarf'])) if {'qarf', 'qpaf'} <= set(r['mean']) else '—'
        lines.append(f"| {dataset} | {variant} | {r['queries']} | {' | '.join(means)} | {gap} |")
    lines += ['', f'Delta so với `{reference}` cùng method: mean [CI95] W/T/L, rồi verdict.', '',
              '| Dataset | Variant | Method | Delta vs reference | Verdict |', '|---|---|---|---|---|']
    for (dataset, variant), r in sorted(results.items()):
        base = results.get((dataset, reference))
        if variant == reference or base is None:
            continue
        for method in ('qarf', 'qpaf'):
            if method in r['per_query'] and method in base['per_query']:
                c = paired(r['per_query'][method], base['per_query'][method])
                try:
                    decision = verdict(c)
                except NotImplementedError:
                    decision = 'n/a'
                lines.append(f'| {dataset} | {variant} | {method.upper()} | {cell(c)} | {decision} |')
    return '\n'.join(lines)+'\n'
