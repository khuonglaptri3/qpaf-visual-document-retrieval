"""Collect immutable completed stages while the independent visual stage runs."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import modal

folder = Path(__file__).resolve().parents[1]/'RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01'
record = json.loads((folder/'execution.json').read_text(encoding='utf-8'))
volume = modal.Volume.from_name(record['volume'])
remote_prefix = record['remote_path'].strip('/')
local = folder/'remote'
local.mkdir(exist_ok=True)
rows = []
for stage in ('bm25', 'dense'):
    status = json.loads(b''.join(volume.read_file('/'+remote_prefix+'/'+stage+'/summary.json')))
    if status['status'] != 'PASS':
        raise ValueError('Prefetch only completed immutable stages')
    for row in volume.listdir('/'+remote_prefix+'/'+stage):
        path = PurePosixPath(row.path.strip('/'))
        rel = path.relative_to(remote_prefix)
        if path.suffix in ('.json', '.npy'):
            rows.append((path.as_posix(), rel.as_posix()))

def fetch(item):
    path, rel = item
    target = local/rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    temp = target.with_name(target.name+'.prefetch-part')
    with temp.open('wb') as stream:
        for data in volume.read_file('/'+path):
            stream.write(data)
    os.replace(temp, target)
    if target.name == 'scores.npy' or target.stat().st_size > 4000000:
        print(f'PREFETCH {rel}: {target.stat().st_size} bytes', flush=True)

with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(fetch, rows))
print(f'PREFETCH COMPLETE: {len(rows)} files', flush=True)
