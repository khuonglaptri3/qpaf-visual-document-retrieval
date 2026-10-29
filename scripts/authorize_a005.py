"""Write a light-mode A005 authorization file for Stage 2, 3 or one Stage 4 run."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005.authorize import write_authorization  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=int, choices=(2, 3, 4), required=True)
    parser.add_argument('--cache', type=Path, required=True, help='dir with the Stage 1 cache files')
    parser.add_argument('--approval-text', required=True)
    parser.add_argument('--granularity', choices=('query', 'page'))
    parser.add_argument('--seed', type=int)
    args = parser.parse_args(argv)
    path = write_authorization(ROOT, args.cache, args.stage, args.approval_text,
                               granularity=args.granularity, seed=args.seed)
    print(path.relative_to(ROOT).as_posix())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
