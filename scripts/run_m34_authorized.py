"""Run the approved M3.4 QPAF command once under supervision, matched to the accepted M3.2 QARF run."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m34.supervisor import supervise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', type=Path, default=ROOT/'evidence/revisions/m3.4-001/authorization.json')
    parser.add_argument('--expected-authorization-sha256', required=True,
                        help='Pin recorded outside the authorization file when it was approved')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--actor', required=True, help='Who is executing; recorded in the markers')
    args = parser.parse_args(argv)
    result = supervise(ROOT, args.authorization, args.expected_authorization_sha256, args.run_id, actor=args.actor)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(f'M3.4 refused: {exc}', file=sys.stderr)
        raise SystemExit(3)
