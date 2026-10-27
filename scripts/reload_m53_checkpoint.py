"""Reload an M5.3 attempt's checkpoints in this fresh process and print the parity report as JSON (read-only)."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m53.reload import replay


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True, help='Attempt directory, relative to the repository root')
    parser.add_argument('--config', required=True, help='The authorized seed config, relative to the root')
    parser.add_argument('--method', required=True, choices=('QARF', 'QPAF'))
    parser.add_argument('--seal', required=True, help='The M3.1 seal run path, relative to the root')
    args = parser.parse_args(argv)
    print(json.dumps(replay(ROOT, args.attempt, args.config, args.method, args.seal), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
