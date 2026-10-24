"""Create or verify the M4.7 G2A robustness-path freeze; never trains or reads test qrels."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m47.g2a import create, verify  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--output-dir', type=Path, help='write g2a_freeze.json there; refuses an existing record')
    actions.add_argument('--verify', type=Path, help='read-only recomputation of an existing record')
    args = parser.parse_args(argv)
    if args.verify:
        print(json.dumps(verify(ROOT, args.verify), ensure_ascii=True, indent=2))
    else:
        record = create(ROOT, args.output_dir)
        print(f"M4.7 G2A {record['main_method']['name']}: {record['status']} ({args.output_dir})")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f'M4.7 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
