"""Capture a fresh read-only full closure replay using the base Python stack."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m11.artifacts import file_manifest
from qpaf.m24.dataset import read_split_ids

RUN = ROOT/'results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01'


def main():
    before = file_manifest(RUN/'bundle')
    command = [sys.executable, str(ROOT/'scripts/run_m28_cache.py'), '--verify', str(RUN)]
    start = time.perf_counter()
    process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    elapsed = time.perf_counter()-start
    if process.returncode:
        print(process.stdout+process.stderr)
        raise SystemExit(process.returncode)
    after = file_manifest(RUN/'bundle')
    if before != after:
        raise ValueError('Read-only verification changed bundle bytes')
    handover = json.loads(process.stdout)
    if handover != json.loads((RUN/'bundle/handover.json').read_text(encoding='utf-8')):
        raise ValueError('Verified handover differs from file')
    expected = json.loads((RUN/'bundle/split_ids.json').read_text(encoding='utf-8'))
    if read_split_ids(RUN/'bundle/splits') != expected:
        raise ValueError('M2.4 portable split loader differs from frozen IDs')
    result = {'status': 'PASS', 'scientific_handover_status': handover['status'],
              'verified_utc': datetime.now(timezone.utc).isoformat(),
              'command': command, 'exit_code': process.returncode, 'elapsed_seconds': elapsed,
              'bundle_file_count': len(after), 'bundle_bytes': sum(r['size_bytes'] for r in after),
              'read_only_bundle_bytes_unchanged': True, 'm24_portable_split_loader': 'PASS',
              'bundle_hashes_sha256': hashlib.sha256((RUN/'bundle/hashes.json').read_bytes()).hexdigest(),
              'finalizer_source_sha256': handover['finalizer_source_sha256'],
              'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    target = RUN/'closure_verification.json'
    if target.exists():
        raise FileExistsError('Closure verification is create-once')
    target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    (RUN/'closure_verification.txt').write_text(process.stdout+process.stderr, encoding='utf-8', newline='\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
