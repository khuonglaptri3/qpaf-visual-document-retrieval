"""Read and verify every cloud embedding receipt after GPU completion.

Payload hashes were produced and checked inside the GPU worker. This local
audit downloads the much smaller receipts, checks their manifest hashes, links
them to retained payload hashes, and proves full namespace/shape coverage.
It does not claim to download/recompute all visual embedding payloads.
"""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT/'results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    manifest = load(RUN/'remote/portable_manifest.json')
    if manifest['status'] != 'COMPLETE':
        raise ValueError('GPU run is incomplete')
    records = {row['path']: row for row in manifest['embedding_files']}
    volume = modal.Volume.from_name('qpaf-m28-score-cache')
    prefix = '/runs/'+RUN.name+'/'
    base = load(RUN/'remote/summary.json')['identity']
    def fetch(name):
        row = records[name]
        payload = b''.join(volume.read_file(prefix+name))
        if (len(payload) != row['size_bytes']
                or hashlib.sha256(payload).hexdigest() != row['sha256']):
            raise ValueError('Embedding receipt cloud hash differs: '+name)
        target = (RUN/'remote'/name).resolve()
        if not target.is_relative_to((RUN/'remote').resolve()):
            raise ValueError('Unsafe artifact path')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != payload:
            raise ValueError('Existing receipt differs')
        if not target.exists():
            target.write_bytes(payload)
        return name, json.loads(payload)
    names = sorted(name for name in records if name.endswith('.json'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = dict(pool.map(fetch, names))
    pages, sequences = [], []
    query_count = None
    for name, receipt in receipts.items():
        identity = receipt['identity']
        if any(identity.get(key) != value for key, value in base.items()):
            raise ValueError('Embedding identity mismatch')
        payload_name = name[:-5]+('.pt' if '/embeddings/' in name else '.npy')
        payload_record = records[payload_name]
        if (payload_record['sha256'] != receipt['sha256']
                or payload_record['size_bytes'] != receipt['size_bytes']):
            raise ValueError('Embedding payload/receipt binding mismatch')
        if identity['kind'] == 'visual_pages':
            start, stop = identity['start'], identity['stop']
            if len(receipt['shapes']) != stop-start:
                raise ValueError('Visual page range mismatch')
            for length, width in receipt['shapes']:
                if length <= 0 or width != 128:
                    raise ValueError('Invalid visual vector shape')
                sequences.append(length)
            pages.extend(range(start, stop))
        elif identity['kind'] == 'visual_queries':
            query_count = len(receipt['shapes'])
            if any(length <= 0 or width != 128 for length, width in receipt['shapes']):
                raise ValueError('Invalid visual query vector shape')
    inputs = load(RUN/'input_manifest.json')
    if sorted(pages) != list(range(inputs['page_count'])) or query_count != inputs['query_count']:
        raise ValueError('Incomplete/duplicate visual embedding namespace')
    result = {'status': 'PASS', 'identity': base, 'uses_qrels': False,
              'manifest_sha256': hashlib.sha256((RUN/'remote/portable_manifest.json').read_bytes()).hexdigest(),
              'verified_receipt_count': len(receipts),
              'visual_page_shard_count': sum(r['identity']['kind'] == 'visual_pages' for r in receipts.values()),
              'visual_page_count': len(pages), 'visual_query_count': query_count,
              'visual_embedding_width': 128, 'page_sequence_length_min': min(sequences),
              'page_sequence_length_max': max(sequences),
              'embedding_payload_file_count': len(records)-len(receipts),
              'embedding_payload_bytes': sum(row['size_bytes'] for name, row in records.items()
                                             if not name.endswith('.json')),
              'all_visual_payloads_downloaded_or_recomputed_locally': False,
              'payload_integrity_basis': 'GPU worker saved/read hashes, COMPLETE portable manifest, verified receipt bindings',
              'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    target = RUN/'embedding_index_verification.json'
    payload = (json.dumps(result, indent=2)+'\n').encode('utf-8')
    if target.exists() and target.read_bytes() != payload:
        raise ValueError('Existing immutable embedding audit differs')
    if not target.exists():
        target.write_bytes(payload)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
