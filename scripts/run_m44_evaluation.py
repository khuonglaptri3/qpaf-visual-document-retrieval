"""M4.4 validation evaluation: restore inputs, execute an authorized run, or verify one.

Never deserializes test qrels. `execute` is create-once with no retry.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT))
from qpaf.m44.common import EvaluationError, restore_inputs  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('restore-inputs', help='copy missing M4.2 payload from byte-identical local sources')
    execute = commands.add_parser('execute', help='run one authorized experiment once')
    execute.add_argument('--experiment', choices=('MTH', 'ORC'), required=True)
    execute.add_argument('--authorization', type=Path, required=True)
    execute.add_argument('--expected-authorization-sha256', required=True)
    execute.add_argument('--run-id', required=True)
    verify = commands.add_parser('verify', help='read-only replay of a finished run')
    verify.add_argument('--experiment', choices=('MTH', 'ORC'), required=True)
    verify.add_argument('--run', type=Path, required=True)
    verify.add_argument('--expected-manifest-sha256', required=True)
    args = parser.parse_args(argv)
    if args.command == 'restore-inputs':
        report = {'status': 'PASS', 'restored': restore_inputs(ROOT)}
    elif args.command == 'execute':
        from qpaf.m44.evaluation import execute_mth
        from qpaf.m44.oracle import execute_orc
        run = execute_mth if args.experiment == 'MTH' else execute_orc
        manifest = run(ROOT, args.authorization, args.expected_authorization_sha256, args.run_id)
        report = {'status': manifest['status'], 'run_id': manifest['run_id'],
                  'elapsed_seconds': manifest['elapsed_seconds'], 'summary': manifest['summary']}
    else:
        from qpaf.m44.evaluation import verify_mth
        from qpaf.m44.oracle import verify_orc
        report = (verify_mth if args.experiment == 'MTH' else verify_orc)(
            ROOT, args.run, args.expected_manifest_sha256)
    # ASCII keeps legacy Windows consoles from failing after the work is done.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except EvaluationError as exc:
        print(f'M4.4 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
