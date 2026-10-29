"""Open the A005 ViMDoc confirmation once (create-once), or check only the sealed file's SHA-256."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005.stage5 import OUTPUT, SEALED_NAME, create, sealed_sha256  # noqa: E402
from qpaf.m43.freeze import sha  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True,
                        help='dir with candidate_scores.parquet, queries.jsonl and dev_qrels.json from Stage 1')
    parser.add_argument('--sealed', type=Path, help=f'sealed confirmation qrels (default: <cache>/{SEALED_NAME})')
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--check-hash', action='store_true',
                         help='compare the sealed file bytes with the prepare marker; the file is not parsed')
    actions.add_argument('--create', action='store_true',
                         help=f'score the confirmation split once and create {OUTPUT}')
    args = parser.parse_args(argv)
    sealed = args.sealed or args.cache/SEALED_NAME
    if not sealed.is_file():
        parser.error(f'sealed file not found: {sealed}')
    if args.check_hash:
        expected, found = sealed_sha256(ROOT), sha(sealed)
        print(f'sealed file sha256 {found}: {"MATCH" if found == expected else "MISMATCH, expected " + expected}')
        return 0 if found == expected else 2
    record = create(ROOT, args.cache, sealed)
    print(f"A005 Stage 5: {record['confirmation_query_count']} confirmation queries, "
          f"{record['queries_without_positive_candidate']} without a positive candidate")
    for name, entry in sorted(record['baselines'].items(), key=lambda kv: -kv[1]['ndcg_at_10']):
        print(f"{name:22s} {entry['ndcg_at_10']:.6f}")
    for name, runs in record['methods'].items():
        values = [entry['ndcg_at_10'] for entry in runs.values()]
        print(f"{name:22s} {sum(values)/len(values):.6f}  seeds {', '.join(f'{v:.6f}' for v in values)}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f'A005 Stage 5 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
