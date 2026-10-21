"""Verify the M2.7 real-input binding; opens no test labels and trains nothing."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m27.binding import load_binding, verify_binding
from qpaf.m27.matched import ParityError

SOURCES = ('src/qpaf/m27/binding.py', 'src/qpaf/m27/matched.py', 'src/qpaf/m24/dataset.py',
           'src/qpaf/m24/trainer.py', 'scripts/verify_m27_binding.py')


def from_root(path):
    return path if path.is_absolute() else ROOT/path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', type=Path, default=Path('configs/m2.7/input_binding.json'))
    parser.add_argument('--output', type=Path, help='Create a verification JSON at this path')
    args = parser.parse_args(argv)
    binding_path = from_root(args.binding)
    report = {**verify_binding(load_binding(binding_path), ROOT),
              'binding_sha256': hashlib.sha256(binding_path.read_bytes()).hexdigest(),
              'source_sha256': {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
                                for path in SOURCES},
              'independent_review': 'PENDING'}
    output = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)+'\n'
    if args.output:
        target = from_root(args.output)
        if target.exists():
            raise FileExistsError(f'Create-once verification exists: {target}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding='utf-8', newline='\n')
        print(f'M2.7 binding evidence: {target}')
    else:
        print(output, end='')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (ParityError, ValueError, FileExistsError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        raise SystemExit(2)
