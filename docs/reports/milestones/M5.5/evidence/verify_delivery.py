"""One-off successor verification; never changes historical CPU output or pins."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m44.common import restore_files  # noqa: E402
from qpaf.m55 import runner  # noqa: E402

MANIFEST_PIN = 'f141871d5adbd90c11fad5084d6c08a599009e3bd0bbbe5f60513e8eebff03be'
RUN = ROOT/'results/m5.5/RUN-QPAF-M5_5-ABL-001-20261027T033016Z-A01'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_hashes():
    paths = set(RUN.rglob('*'))
    paths.update((ROOT/'results/m5.5/verification').rglob('*'))
    paths.update((ROOT/'evidence/revisions/m5.5-001').rglob('*'))
    paths.update(ROOT/name for name in (*runner.SOURCE_FILES, *runner.AUTHORITY_PINS))
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore-from', type=Path)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError('Successor receipt exists; choose a new path')
    before = historical_hashes()
    auth = json.loads((RUN/'authorization.json').read_text(encoding='utf-8'))
    runner.validate_bindings(ROOT, auth)
    assert digest(RUN/'manifest.json') == MANIFEST_PIN
    restored = []
    if args.restore_from:
        bundle = ROOT/'results/m4.2'/runner.BUNDLE_NAME
        assert digest(bundle/'manifest.json') == runner.BUNDLE_MANIFEST_SHA256
        assert digest(args.restore_from/'manifest.json') == runner.BUNDLE_MANIFEST_SHA256
        files = json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))['files']
        # Validate every source/target before restoring any missing payload.
        for entry in files:
            relative = Path(entry['path'])
            assert not relative.is_absolute() and '..' not in relative.parts
            source, target = args.restore_from/relative, bundle/relative
            assert source.is_file() and digest(source) == entry['sha256'], relative
            assert not target.exists() or digest(target) == entry['sha256'], relative
        restored = restore_files(bundle, files,
                                 {entry['path']: args.restore_from/entry['path'] for entry in files})
    result = runner.verify(ROOT, RUN, MANIFEST_PIN) if args.verify else None
    after = historical_hashes()
    assert before == after, 'Historical bytes changed during continuation verification'
    receipt = {'checked_utc': datetime.now(timezone.utc).isoformat(),
               'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                                   text=True).strip(),
               'command': [sys.executable, *sys.argv], 'status': 'PASS',
               'restored_missing_payloads': restored, 'verification': result,
               'historical_bytes_unchanged': True, 'historical_files_sha256': after,
               'runtime': runner.runtime_versions(), 'new_scientific_run': False,
               'gpu_or_modal_called': False, 'independent_human_acceptance': 'PENDING'}
    with args.receipt.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'historical_files_sha256'}, indent=2))


if __name__ == '__main__':
    main()
