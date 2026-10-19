"""Overlap local extraction of immutable document ZIPs; canonical verification follows."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'results/m2.6/RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01'
OUT = RUN / 'output'
IDS = {r['page_id'] for r in json.loads((RUN / 'input_manifest.json').read_text())['scheduled_pages']}

def extract(path):
    count = size = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            parts = info.filename.split('/')
            if (len(parts) != 3 or parts[0] != 'pages' or parts[1] not in IDS
                    or not parts[1].startswith(path.stem + '_page_')
                    or not parts[2] or parts[2] in {'.', '..'} or '\\' in info.filename):
                raise ValueError('Unsafe prefetched archive member')
            target = OUT.joinpath(*parts)
            if not target.resolve().is_relative_to(OUT.resolve()):
                raise ValueError('Prefetched member escapes output')
            payload = archive.read(info)  # Includes ZIP CRC validation.
            if target.is_file():
                if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(payload).digest():
                    raise ValueError('Existing local raw artifact differs')
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.preextract.part')
            temporary.write_bytes(payload)
            temporary.replace(target)
            count += 1
            size += len(payload)
    return {'archive': path.name, 'files_extracted': count, 'bytes_extracted': size}

if __name__ == '__main__':
    paths = sorted((OUT / 'archives').glob('*.zip'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(extract, paths))
    receipt = {'status': 'PREFETCHED_EXTRACTION_ONLY_AWAITING_CANONICAL_FULL_VERIFICATION',
               'archives': len(records), 'files_extracted': sum(r['files_extracted'] for r in records),
               'bytes_extracted': sum(r['bytes_extracted'] for r in records)}
    (RUN / 'preextraction.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
