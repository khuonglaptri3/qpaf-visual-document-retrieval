"""Run one feature-lab variant on one dataset: 5-fold CV over the development queries (docs/feature_lab/)."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.lab.data import DATASETS, load  # noqa: E402
from qpaf.lab.train import SEEDS, run_experiment  # noqa: E402
from qpaf.lab.variants import load_variant  # noqa: E402
from qpaf.m43.freeze import git, sha  # noqa: E402

DATA_FILES = {'vimdoc': ('candidate_scores.parquet', 'queries.jsonl', 'dev_qrels.json'),
              'vidoseek': ('raw_scores.parquet', 'queries.json', 'qrels_development.json')}
GRANULARITY = {'both': ('query', 'page'), 'query': ('query',), 'page': ('page',)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, choices=DATASETS)
    parser.add_argument('--data', required=True, type=Path, help='input directory, layout in docs/feature_lab/README.md')
    parser.add_argument('--variant', default='baseline', help='module name under src/qpaf/lab/variants/')
    parser.add_argument('--asset', action='append', default=[], metavar='NAME=PATH', help='file a variant needs')
    parser.add_argument('--granularity', default='both', choices=sorted(GRANULARITY))
    parser.add_argument('--seeds', type=int, default=1, choices=(1, 3), help='1 to screen, 3 for the final rows')
    parser.add_argument('--folds', type=int, default=5)
    parser.add_argument('--epochs', type=int, help='smoke tests only; averages over the second half')
    parser.add_argument('--limit', type=int, help='smoke tests only: first N queries')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    assets = dict(item.split('=', 1) for item in args.asset)
    for name, path in assets.items():
        if not Path(path).is_file():
            parser.error(f'asset {name}: no file at {path}')
    smoke = bool(args.limit or args.epochs)
    output = args.output or ROOT/'results/lab'/('_smoke' if smoke else args.dataset)/f'{args.dataset}-{args.variant}.json'
    variant = load_variant(args.variant, assets)
    queries = load(args.dataset, ROOT, args.data)[:args.limit]
    recipe = {'epochs': args.epochs, 'average_from': max(1, args.epochs//2)} if args.epochs else {}
    result = run_experiment(queries, variant, granularities=GRANULARITY[args.granularity], seeds=SEEDS[:args.seeds],
                            folds=args.folds, recipe=recipe)
    record = {'schema': 'qpaf-lab-v1', 'dataset': args.dataset, 'smoke': smoke, **result,
              'assets_sha256': {name: sha(path) for name, path in assets.items()},
              'inputs_sha256': {name: sha(args.data/name) for name in DATA_FILES[args.dataset]},
              'source_commit': git(ROOT, 'rev-parse', 'HEAD'),
              'tracked_changes': bool(git(ROOT, 'status', '--porcelain', '--untracked-files=no'))}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'mean': record['mean'], 'seconds': round(record['seconds'], 1)}, indent=2))


if __name__ == '__main__':
    main()
