"""R7 / TEST-172: label-free preflight, the one authorized sealed run, or a read-only replay.

`preflight` never reads the sealed test qrels and writes nothing. `run` is create-once with no retry.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT))
from qpaf.m44.common import EvaluationError  # noqa: E402
from qpaf.r7.sealed import SealedError  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('preflight', help='R7-00 and label-free test scoring; no labels, no output')
    check.add_argument('--authorization', type=Path, required=True)
    run = commands.add_parser('run', help='execute the approved R7 once')
    run.add_argument('--authorization', type=Path, required=True)
    run.add_argument('--expected-authorization-sha256', required=True)
    run.add_argument('--run-id', required=True)
    verify = commands.add_parser('verify', help='replay a finished R7 run')
    verify.add_argument('--run', type=Path, required=True)
    verify.add_argument('--expected-manifest-sha256', required=True)
    args = parser.parse_args(argv)
    from qpaf.r7 import runner
    if args.command == 'preflight':
        state = runner.preflight(ROOT, json.loads(args.authorization.read_text(encoding='utf8')))
        runner.test_predictions(state, ROOT)
        report = {'status': 'PASS', **state['report']}
    elif args.command == 'run':
        manifest = runner.execute(ROOT, args.authorization, args.expected_authorization_sha256, args.run_id)
        report = {'status': manifest['status'], 'run_id': manifest['run_id'],
                  'elapsed_seconds': manifest['elapsed_seconds'], 'summary': manifest['summary']}
    else:
        report = runner.verify(ROOT, args.run, args.expected_manifest_sha256)
    # ASCII keeps legacy Windows consoles from failing after the work is done.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (SealedError, EvaluationError) as exc:
        print(f'R7 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
