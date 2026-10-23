"""Execute or replay Khương's approved active-primary M4.2 baseline freeze."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from qpaf.m42.active_primary import execute, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--authorization',type=Path)
    parser.add_argument('--expected-authorization-sha256')
    parser.add_argument('--verify',action='store_true')
    parser.add_argument('--expected-manifest-sha256')
    parser.add_argument('--replay-fit',action='store_true')
    args = parser.parse_args()
    if args.verify:
        if not args.expected_manifest_sha256:
            parser.error('Verification requires the committed external manifest pin')
        result = verify(ROOT,args.output,args.expected_manifest_sha256,replay_fit=args.replay_fit)
    else:
        if not args.authorization or not args.expected_authorization_sha256:
            parser.error('Execution requires the reviewed authorization and its hash')
        result = execute(ROOT,args.output,args.authorization,args.expected_authorization_sha256)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,KeyError) as exc:
        raise SystemExit(f'M4.2 refused: {exc}')
