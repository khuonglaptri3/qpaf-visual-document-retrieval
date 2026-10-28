"""M5.6 / R6 CPU-only CLI: authorized run, fresh-process reload and read-only verification."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m56.runner import execute, reload_outputs, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run')
    run.add_argument('--authorization', type=Path, required=True)
    run.add_argument('--expected-authorization-sha256', required=True)
    run.add_argument('--run-id', required=True)
    reload = sub.add_parser('reload')
    reload.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('verify')
    check.add_argument('--output', type=Path, required=True)
    check.add_argument('--expected-manifest-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'run':
        result = execute(ROOT, args.authorization, args.expected_authorization_sha256, args.run_id,
                         log=lambda line: print(line, file=sys.stderr, flush=True))
    elif args.command == 'reload':
        result = reload_outputs(ROOT, args.output)
    else:
        result = verify(ROOT, args.output, args.expected_manifest_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    main()
