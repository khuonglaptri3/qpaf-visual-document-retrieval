"""Prefetch immutable terminal records while the worker packages raw evidence."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parents[2]
RUN = 'RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01'
OUT = ROOT / 'results/m2.6' / RUN / 'output'
VOLUME = modal.Volume.from_name('qpaf-m26-full-ocr')

def fetch(name):
    target = OUT / name
    if target.exists():
        return
    temporary = target.with_name(target.name + '.prefetch.part')
    with temporary.open('wb') as stream:
        VOLUME.read_file_into_fileobj('/runs/' + RUN + '/output/' + name, stream)
    if name.endswith('.json'):
        json.loads(temporary.read_bytes())
    temporary.replace(target)
    print('Prefetched terminal metadata: ' + name, flush=True)

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(fetch, ['resolved_pages.json', 'page_hashes.csv', 'failures.json']))
    from collections import Counter
    rows = json.loads((OUT / 'resolved_pages.json').read_bytes())
    print(json.dumps({'pages': len(rows), 'technical_failures': sum(r['technical_failure'] for r in rows),
                      'extraction_statuses': dict(Counter(r['extraction_status'] for r in rows)),
                      'text_sources': dict(Counter(r['text_source'] for r in rows)),
                      'warning_pages': sum(bool(r['warnings']) for r in rows)}, indent=2))
