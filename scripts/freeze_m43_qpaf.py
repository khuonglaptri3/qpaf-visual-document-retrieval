"""Create or verify the M4.3 frozen-QPAF record; never trains or reads test qrels."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m43.freeze import FreezeError, create, verify  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--output-dir', type=Path, help='create a new revision; refuses an existing directory')
    actions.add_argument('--verify', type=Path, help='read-only replay of an existing revision')
    args = parser.parse_args(argv)
    if args.verify:
        # ASCII keeps legacy Windows consoles from failing after the work is done.
        print(json.dumps(verify(ROOT, args.verify), ensure_ascii=True, indent=2))
    else:
        record = create(ROOT, args.output_dir)
        print(f"M4.3 frozen QPAF {record['frozen_method']['checkpoint']['sha256']} "
              f"({record['branch_disposition']['m4_branch']}): {args.output_dir}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (FreezeError, ValueError) as exc:
        print(f'M4.3 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
