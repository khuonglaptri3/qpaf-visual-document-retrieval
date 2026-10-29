"""Summarize every feature-lab result under results/lab/ against the baseline variant (markdown)."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.lab.compare import load_results, summary  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=ROOT/'results/lab')
    parser.add_argument('--reference', default='baseline')
    parser.add_argument('--output', type=Path, help='also write the markdown here')
    args = parser.parse_args(argv)
    text = summary(load_results(args.results), args.reference)
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
