"""Aggregate the A005 Stage 5 confirmation into paired statistics and the verdict; reads no qrels, trains nothing."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005.stage6 import aggregate  # noqa: E402


def main():
    record = aggregate(ROOT)
    print(f"A005 Stage 6 over {record['confirmation_query_count']} queries")
    for name, report in record['vs_co_strongest'].items():
        print(f"QPAF-SA-v2 - {name}: {report['mean_of_seed_means']:+.6f} CI95 [{report['ci95'][0]:+.6f}, "
              f"{report['ci95'][1]:+.6f}] W/T/L {report['wtl']['wins']}/{report['wtl']['ties']}/{report['wtl']['losses']}")
    report = record['vs_qarf_sa']
    print(f"QPAF-SA-v2 - QARF-SA-v2: {report['mean_of_seed_means']:+.6f} CI95 [{report['ci95'][0]:+.6f}, "
          f"{report['ci95'][1]:+.6f}]")
    print(f"verdict: {record['verdict']}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f'A005 Stage 6 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
