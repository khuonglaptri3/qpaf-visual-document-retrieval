"""Create or verify the A005 Stage 3 ViMDoc validation baseline record; never trains."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005.stage3 import OUTPUT, create, verify  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True,
                        help='dir with candidate_scores.parquet, queries.jsonl and dev_qrels.json from Stage 1')
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--create', action='store_true', help=f'create {OUTPUT}; needs an APPROVED authorization')
    actions.add_argument('--verify', action='store_true', help='read-only recomputation of the stored record')
    args = parser.parse_args(argv)
    if args.verify:
        print(json.dumps(verify(ROOT, args.cache), ensure_ascii=True, indent=2))
    else:
        record = create(ROOT, args.cache)
        for name, entry in sorted(record['roster'].items(), key=lambda kv: -kv[1]['ndcg_at_10']):
            print(f"{name:22s} {entry['ndcg_at_10']:.6f}")
        print(f"train_fitted_static weights {record['train_fitted_static_weights']}; "
              f"co-strongest {record['co_strongest']}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f'A005 Stage 3 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
