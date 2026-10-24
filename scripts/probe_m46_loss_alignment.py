"""Create or verify the M4.6 train-only loss-alignment gate record; never trains or reads test qrels."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m46.probe import create, verify  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--output', type=Path, help='create the record; refuses an existing file')
    actions.add_argument('--verify', type=Path, help='read-only recomputation of an existing record')
    args = parser.parse_args(argv)
    if args.verify:
        print(json.dumps(verify(ROOT, args.verify), ensure_ascii=True, indent=2))
    else:
        record = create(ROOT, args.output)
        v1, v2 = record['gate_v1'], record['gate_v2']
        print(f"v1 loss: min {v1['min_loss_weights']} loss {v1['min_loss']:.5f} spearman {v1['spearman']:.3f}")
        print(f"v2 gate: {v2['status']} (G-A {v2['G_A']} spearman {v2['spearman']:.3f}; "
              f"G-B {v2['G_B']} min-loss nDCG {v2['min_loss_ndcg']:.4f} vs max {v2['max_ndcg']:.4f})")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f'M4.6 probe refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
