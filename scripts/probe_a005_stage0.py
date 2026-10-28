"""Create or verify the A005 Stage 0 train-only alignment gate record; never trains or reads test qrels."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005.probe import OUTPUT, create, verify  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--create', action='store_true', help=f'create {OUTPUT}; needs an APPROVED authorization')
    actions.add_argument('--verify', action='store_true', help='read-only recomputation of the stored record')
    args = parser.parse_args(argv)
    if args.verify:
        print(json.dumps(verify(ROOT), ensure_ascii=True, indent=2))
    else:
        g = create(ROOT)['gate']
        print(f"A005 Stage 0 gate: {g['status']} (G-A {g['G_A']} spearman {g['spearman']:.3f}; "
              f"G-B {g['G_B']} min-loss nDCG {g['min_loss_ndcg']:.4f} vs max {g['max_ndcg']:.4f}; "
              f"min-loss weights {g['min_loss_weights']})")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f'A005 Stage 0 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
