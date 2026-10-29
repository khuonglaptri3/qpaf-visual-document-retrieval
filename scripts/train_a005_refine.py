"""Run one A005-R1 refined-training run (create-once): weight-averaged and best-epoch checkpoints on ViMDoc."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005.refine import VARIANTS, create_run  # noqa: E402
from qpaf.a005.stage4 import GRANULARITIES  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True, help='dir with the Stage 1 cache files')
    parser.add_argument('--variant', choices=VARIANTS, required=True)
    parser.add_argument('--granularity', choices=GRANULARITIES, required=True)
    parser.add_argument('--seed', type=int, required=True)
    args = parser.parse_args(argv)
    record = create_run(ROOT, args.cache, args.variant, args.granularity, args.seed)
    averaged, best = record['validation']['averaged'], record['validation']['best_epoch_model']
    print(f"{record['variant']} {record['granularity']} seed {record['seed']}: averaged validation nDCG@10 "
          f"{averaged['ndcg_at_10']:.6f}; best epoch {record['best_epoch']} {best['ndcg_at_10']:.6f}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f'A005-R1 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
