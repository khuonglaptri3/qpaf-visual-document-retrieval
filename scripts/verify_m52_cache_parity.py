"""Restore label-free inputs, create M5.2 evidence, or verify it read-only."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m52.cache_parity import (CacheParityError, create, load_authority,
                                  restore_inputs, sha256, verify)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--restore-from-archive', type=Path, metavar='M42_ZIP')
    actions.add_argument('--create', type=Path, metavar='NEW_EVIDENCE_DIR')
    actions.add_argument('--verify', type=Path, metavar='EVIDENCE_DIR')
    parser.add_argument('--inputs-dir', type=Path, default=Path('.cache/m52-inputs'))
    parser.add_argument('--expected-receipt-sha256', help='reviewed Git/PR hash; required by --verify')
    args = parser.parse_args(argv)
    if args.verify and not args.expected_receipt_sha256:
        parser.error('--verify requires --expected-receipt-sha256 from the reviewed receipt')
    if not args.verify and args.expected_receipt_sha256:
        parser.error('--expected-receipt-sha256 applies only to --verify')
    progress = lambda message: print('M5.2 ' + message, file=sys.stderr, flush=True)
    if args.restore_from_archive:
        authority = load_authority(ROOT)
        result = restore_inputs(args.restore_from_archive, args.inputs_dir, authority['contract'])
    elif args.create:
        receipt = create(ROOT, args.inputs_dir, args.create, progress)
        result = {'status': receipt['status'], 'task_id': 'M5.2',
                  'cache_identity_sha256': sha256(args.create / 'cache_identity.json'),
                  'method_input_replays': len(receipt['matrix']), 'labels_deserialized': False,
                  'independent_human_review': receipt['independent_human_review']}
    else:
        result = verify(ROOT, args.inputs_dir, args.verify, args.expected_receipt_sha256, progress)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (CacheParityError, OSError, KeyError, ValueError) as exc:
        print(f'M5.2 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
