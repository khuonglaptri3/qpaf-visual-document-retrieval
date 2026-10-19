"""Read-only M2.1 audit plus M2.5 software fixture; no real inference or test labels."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m24.dataset import build_records
from qpaf.m24.evaluator import evaluate
from qpaf.m24.synthetic import make_fixture
from qpaf.m25.baselines import ROSTER, fit_static_on_train, predictions
from qpaf.m25.leakage import audit_score_rows, verify_frozen_splits
from qpaf.m25.statistics import SEEDS, paired_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Create a fixture verification JSON at this path')
    args = parser.parse_args(argv)
    config_path = ROOT/'configs/m2.5/freeze.json'
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if (config['required_deployable_baselines'] != list(ROSTER) or
            config['statistics']['seeds'] != list(SEEDS) or
            config['statistics']['resamples'] != 10000 or
            config['statistics']['bootstrap_seed'] != 20260820 or
            config['static_fit']['grid_denominator'] != 10 or
            config['rrf_k'] != 60):
        raise ValueError('M2.5 freeze config differs from implemented contract')
    split_audit = verify_frozen_splits(ROOT, config)
    rows, queries, qrels, fixture_splits = make_fixture()
    cache_audit = audit_score_rows(rows, fixture_splits)
    records = build_records(rows, queries, qrels, fixture_splits, ('train', 'validation'))
    fitted = fit_static_on_train(records['train'], fixture_splits['train'],
                                 config['static_fit']['grid_denominator'])
    validation = {}
    for method in ROSTER:
        if method == 'learned_qarf':
            validation[method] = 'NOT_RUN: M2.4 synthetic QARF is not a matched real-data baseline'
            continue
        weights = fitted['weights'] if method == 'train_fitted_static' else None
        validation[method] = evaluate(predictions(records['validation'], method, weights=weights),
                                      records['validation'])[0]['ndcg_at_10']
    # Signed, tied and seed-varying deltas expose the exact paired-statistics path.
    query_ids = ('a', 'b', 'c', 'd')
    right = {seed: {q: .5 for q in query_ids} for seed in SEEDS}
    left = {seed: {q: .5+delta for q, delta in zip(query_ids, (.2, 0., -.1, .1))}
            for seed in SEEDS}
    stats = paired_report(left, right, resamples=config['statistics']['resamples'],
                          bootstrap_seed=config['statistics']['bootstrap_seed'])
    report = {
        'task_id': 'M2.5', 'status': 'FROZEN_METHOD_AND_SOFTWARE_FIXTURE_ONLY',
        'config_sha256': hashlib.sha256(config_bytes).hexdigest(),
        'source_sha256': {
            path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
            for path in ('src/qpaf/m25/baselines.py', 'src/qpaf/m25/statistics.py',
                         'src/qpaf/m25/leakage.py', 'scripts/verify_m25_freeze.py')
        },
        'real_split_audit': {key: value for key, value in split_audit.items() if key != 'roles'},
        'synthetic_cache_audit': cache_audit,
        'synthetic_train_fitted_static': fitted,
        'synthetic_validation_ndcg_at_10': validation,
        'synthetic_paired_statistics': stats,
        'real_baseline_scores': 'NOT_RUN: frozen full score cache unavailable',
        'real_paired_statistics': 'NOT_RUN: matched three-seed predictions unavailable',
        'independent_review': 'PENDING',
    }
    output = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)+'\n'
    if args.output:
        target = args.output if args.output.is_absolute() else ROOT/args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f'Create-once verification exists: {target}')
        target.write_text(output, encoding='utf-8', newline='\n')
    else:
        print(output, end='')


if __name__ == '__main__':
    main()
