"""M5.5 CPU-only CLI. This module has no Modal/GPU execution command."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m55.runner import execute, restore_inputs, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    restore = sub.add_parser('restore-inputs')
    restore.add_argument('--archive', type=Path, required=True)
    run = sub.add_parser('run')
    run.add_argument('--authorization', type=Path, required=True)
    run.add_argument('--expected-authorization-sha256', required=True)
    run.add_argument('--run-id', required=True)
    check = sub.add_parser('verify')
    check.add_argument('--output', type=Path, required=True)
    check.add_argument('--expected-manifest-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'restore-inputs':
        result = restore_inputs(ROOT, args.archive)
    elif args.command == 'run':
        result = execute(ROOT, args.authorization, args.expected_authorization_sha256, args.run_id)
    else:
        result = verify(ROOT, args.output, args.expected_manifest_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
