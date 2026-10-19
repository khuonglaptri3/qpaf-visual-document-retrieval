"""Collect the last missing canonical archives alongside the CLI's forward queue."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import modal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m11.artifacts import digest, read_json
from qpaf.m26.bundle import checked_path
RUN = ROOT / 'results/m2.6/RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01'
OUT = RUN / 'output'
VOLUME = modal.Volume.from_name('qpaf-m26-full-ocr')

def fetch(item):
    target = checked_path(OUT, item['path'])
    if target.is_file():
        if target.stat().st_size != item['size_bytes'] or digest(target) != item['sha256']:
            raise ValueError('Existing canonical archive differs')
        return
    temporary = target.with_name(target.name + '.canonical-prefetch.part')
    with temporary.open('wb') as stream:
        VOLUME.read_file_into_fileobj('/runs/' + RUN.name + '/output/' + item['path'], stream)
    if temporary.stat().st_size != item['size_bytes'] or digest(temporary) != item['sha256']:
        raise ValueError('Canonical archive checksum mismatch')
    temporary.replace(target)
    print('Canonical archive verified: ' + target.name, flush=True)

if __name__ == '__main__':
    manifest = read_json(OUT / 'hashes.json')
    items = [r for r in reversed(manifest) if r['path'].startswith('archives/')
             and not checked_path(OUT, r['path']).is_file()][:64]
    print(f'Prefetching {len(items)} canonical archives from the end of the queue', flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(fetch, items))
    print('Canonical prefetch finished; CLI full verification remains authoritative', flush=True)
