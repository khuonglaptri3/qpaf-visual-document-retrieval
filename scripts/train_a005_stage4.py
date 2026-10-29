"""Run one authorized A005 Stage 4 training run, or evaluate the no-deviation stop rule."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005.stage4 import GRANULARITIES, create, no_deviation_rule  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, help='dir with the Stage 1 cache files')
    parser.add_argument('--granularity', choices=GRANULARITIES)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--stop-rule', action='store_true', help='evaluate A005 §4.4 over the QPAF-SA runs')
    args = parser.parse_args(argv)
    if args.stop_rule:
        print(json.dumps(no_deviation_rule(ROOT), indent=2))
        return 0
    if not (args.cache and args.granularity and args.seed):
        parser.error('--cache, --granularity and --seed are required for a run')
    record = create(ROOT, args.cache, args.granularity, args.seed)
    print(f"{record['method']} seed {record['seed']}: best epoch {record['best_epoch']}, validation nDCG@10 "
          f"{record['validation_ndcg_at_10']:.6f} (static {record['train_fitted_static_validation_ndcg_at_10']:.6f}, "
          f"gain {record['gain_over_train_fitted_static']:+.6f}); reload {record['reload_max_abs_difference']:.2e}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f'A005 Stage 4 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
