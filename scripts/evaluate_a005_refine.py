"""A005-R1 evaluation: the validation ablation table (create-once), or the one-time post-hoc confirmation."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005.refine_eval import CONFIRMATION_OUTPUT, VALIDATION_OUTPUT, confirmation_record, validation_table  # noqa: E402
from qpaf.a005.stage5 import SEALED_NAME, sealed_sha256  # noqa: E402
from qpaf.m43.freeze import sha  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True, help='dir with the Stage 1 cache files')
    parser.add_argument('--sealed', type=Path, help=f'sealed confirmation qrels (default: <cache>/{SEALED_NAME})')
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--validation', action='store_true', help=f'write {VALIDATION_OUTPUT}')
    actions.add_argument('--check-hash', action='store_true', help='compare the sealed file bytes with the marker')
    actions.add_argument('--confirm', action='store_true', help=f'score the confirmation once: {CONFIRMATION_OUTPUT}')
    args = parser.parse_args(argv)
    sealed = args.sealed or args.cache/SEALED_NAME
    if args.validation:
        record = validation_table(ROOT, args.cache)
        print(f"static {record['train_fitted_static']:.6f}")
        for granularity, rows in record['rows'].items():
            for row in rows:
                print(f"{granularity:5s} {row['id']:26s} {row['ndcg_at_10']:.6f} {row['delta_vs_static']:+.6f}")
        return 0
    if not sealed.is_file():
        parser.error(f'sealed file not found: {sealed}')
    if args.check_hash:
        expected, found = sealed_sha256(ROOT), sha(sealed)
        print(f'sealed file sha256 {found}: {"MATCH" if found == expected else "MISMATCH, expected " + expected}')
        return 0 if found == expected else 2
    record = confirmation_record(ROOT, args.cache, sealed)
    for name, value in record['ndcg_at_10'].items():
        print(f'{name:36s} {value:.6f}')
    for name, report in record['comparisons'].items():
        wtl = report['wtl']
        print(f"{name}: {report['mean_of_seed_means']:+.6f} CI95 [{report['ci95'][0]:+.6f}, {report['ci95'][1]:+.6f}] "
              f"W/T/L {wtl['wins']}/{wtl['ties']}/{wtl['losses']}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f'A005-R1 evaluation refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
