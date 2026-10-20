"""Read-only M2.7 matched QARF/QPAF config verification; opens no labels and trains only on the synthetic fixture."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m27.matched import ParityError, check_parity, load_manifest

# Every file on the matched training path, so a later method-specific change is visible.
SOURCES = ('src/qpaf/m27/matched.py', 'src/qpaf/m24/config.py', 'src/qpaf/m24/dataset.py',
           'src/qpaf/m24/trainer.py', 'src/qpaf/m24/evaluator.py', 'src/qpaf/m24/checkpoint.py',
           'src/qpaf/m12/model.py', 'src/qpaf/m12/features.py', 'src/qpaf/m12/losses.py',
           'scripts/run_m24_pipeline.py', 'scripts/verify_m27_matched.py')


def from_root(path):
    return path if path.is_absolute() else ROOT/path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path('configs/m2.7/matched.json'),
                        help='matched manifest (relative paths resolve against the repo root)')
    parser.add_argument('--output', type=Path, help='Create a verification JSON at this path')
    args = parser.parse_args(argv)
    manifest_path = from_root(args.manifest)
    manifest = load_manifest(manifest_path)
    report = {
        **check_parity(manifest, ROOT),
        'task_id': manifest['task_id'], 'experiment_id': manifest['experiment_id'],
        'status': manifest['status'],
        'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'source_sha256': {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCES},
        'wall_time_cap_minutes': manifest['budget']['wall_time_minutes_per_run'],
        'independent_review': 'PENDING',
    }
    output = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)+'\n'
    if args.output:
        target = from_root(args.output)
        if target.exists():
            raise FileExistsError(f'Create-once verification exists: {target}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding='utf-8', newline='\n')
        print(f'M2.7 evidence: {target}')
    else:
        print(output, end='')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (ParityError, FileExistsError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        raise SystemExit(2)
