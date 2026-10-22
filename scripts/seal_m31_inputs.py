"""Create or read-only replay the M3.1 matched pilot input seal; trains nothing."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m31.seal import read_json, seal_inputs, verify_seal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--output', type=Path, help='Create a new seal; refuses an existing directory')
    actions.add_argument('--verify', type=Path, help='Read-only replay of an existing seal')
    parser.add_argument('--expected-manifest-sha256', help='Manifest pin from the committed M3.1 evidence')
    parser.add_argument('--config', type=Path, default=ROOT/'configs/m3.1/seal.json')
    parser.add_argument('--payload-root', type=Path, default=ROOT,
                        help='Root containing the original bound M2.8 result paths')
    args = parser.parse_args(argv)
    if args.verify and not args.expected_manifest_sha256:
        parser.error('--verify requires --expected-manifest-sha256 from the reviewed evidence')
    report = (verify_seal(ROOT, args.verify, expected_manifest_sha256=args.expected_manifest_sha256) if args.verify else
              seal_inputs(ROOT, args.payload_root, args.output, read_json(args.config)))
    print(json.dumps({'task_id': 'M3.1', 'status': report['status'],
                      'record_counts': report['parity']['record_counts'],
                      'candidate_rows': report['parity']['candidate_rows'],
                      'parity_identical': report['parity']['identical'],
                      'training_executed': report['training_executed'],
                      'test_labels_opened': report['test_labels_opened']}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(f'M3.1 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
