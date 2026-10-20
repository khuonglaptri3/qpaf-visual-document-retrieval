"""Upload a closed real-data handover once, then hash every downloaded byte.

Run using the project .venv (Modal SDK). This does not run inference, create a
CPU worker, mutate the source OCR Volume, or replace any GPU output file.
"""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import modal


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT/'results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    payload = (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode('utf-8')
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError('Create-once receipt differs: '+str(path))
    else:
        with path.open('xb') as stream:
            stream.write(payload)


def main():
    handover = load(RUN/'bundle/handover.json')
    if handover['status'] not in ('PASS', 'BLOCKED_COVERAGE'):
        raise ValueError('No closed coverage outcome')
    # A failed scientific coverage gate still deserves durable, honest evidence.
    listed = load(RUN/'bundle/hashes.json')
    for row in listed:
        path = RUN/'bundle'/row['path']
        if sha(path) != row['sha256'] or path.stat().st_size != row['size_bytes']:
            raise ValueError('Bundle changed: '+row['path'])
    if sha(ROOT/'scripts/run_m28_cache.py') != handover['finalizer_source_sha256']:
        raise ValueError('Finalizer source no longer matches handover')
    files = [(p, 'bundle/'+p.relative_to(RUN/'bundle').as_posix())
             for p in sorted((RUN/'bundle').rglob('*')) if p.is_file()]
    files += [(RUN/'source_snapshot.zip', 'source_snapshot.zip'),
              (ROOT/'scripts/run_m28_cache.py', 'finalizer_sources/run_m28_cache.py')]
    metadata = {
        RUN/'completed_stages_independent_replay.json': 'completed_stages_independent_replay.json',
        RUN/'closure_verification.json': 'closure_verification.json',
        RUN/'embedding_index_verification.json': 'embedding_index_verification.json',
        RUN/'source_snapshot_verification.json': 'source_snapshot_verification.json',
        RUN/'artifact_review.json': 'artifact_review.json',
        RUN/'uncovered_diagnosis.json': 'uncovered_diagnosis.json',
        RUN/'operational_notes.json': 'operational_notes.json',
        RUN/'status_verification.json': 'status_verification.json',
        RUN/'collection.json': 'collection.json',
        RUN/'execution.json': 'execution.json',
        ROOT/'results/m2.8/verification/software-checks.json': 'software-checks.json',
        ROOT/'results/m2.8/verification/code-review.json': 'code-review.json',
        ROOT/'results/m2.8/verification/ocr-review-html-removal.json': 'ocr-review-html-removal.json',
    }
    files += [(local, 'closure/'+name) for local, name in metadata.items()]
    manifest_path = RUN/'closure_upload_manifest.json'
    manifest = {'run_id': RUN.name, 'handover_status': handover['status'],
                'files': [{'path': remote, 'sha256': sha(local),
                           'size_bytes': local.stat().st_size} for local, remote in files]}
    save(manifest_path, manifest)
    files.append((manifest_path, 'closure_upload_manifest.json'))
    expected = {row['path']: row for row in manifest['files']}
    expected['closure_upload_manifest.json'] = {
        'path': 'closure_upload_manifest.json', 'sha256': sha(manifest_path),
        'size_bytes': manifest_path.stat().st_size}
    volume = modal.Volume.from_name('qpaf-m28-score-cache')
    prefix = '/runs/'+RUN.name+'/'
    def replay(item, allow_missing=False):
        local, remote = item
        h, size = hashlib.sha256(), 0
        try:
            for chunk in volume.read_file(prefix+remote):
                h.update(chunk)
                size += len(chunk)
        except FileNotFoundError:
            if allow_missing:
                return None
            raise
        if (h.hexdigest() != expected[remote]['sha256']
                or size != expected[remote]['size_bytes']):
            raise ValueError('Cloud readback mismatch: '+remote)
        return {'path': remote, 'size_bytes': size, 'sha256': h.hexdigest()}
    # Resume an interrupted upload by skipping only byte-identical cloud files.
    # Transport/auth failures propagate; only missing paths permit an upload.
    with ThreadPoolExecutor(max_workers=4) as pool:
        existing = list(pool.map(lambda item: replay(item, True), files))
    missing = [item for item, result in zip(files, existing) if result is None]
    if missing:
        with volume.batch_upload(force=False) as batch:
            for local, remote in missing:
                if (sha(local) != expected[remote]['sha256']
                        or local.stat().st_size != expected[remote]['size_bytes']):
                    raise ValueError('Local upload source changed after freeze: '+remote)
                batch.put_file(str(local), prefix+remote)
    with ThreadPoolExecutor(max_workers=4) as pool:
        verified = list(pool.map(replay, files))
    static_receipt = {'status': 'PASS', 'volume': 'qpaf-m28-score-cache', 'remote_path': prefix,
                      'handover_status': handover['status'], 'force_overwrite': False,
                      'verified_file_count': len(verified),
                      'verified_bytes': sum(r['size_bytes'] for r in verified), 'files': verified}
    receipt_path = RUN/'cloud_closure_verification.json'
    try:
        remote_receipt = b''.join(volume.read_file(prefix+'cloud_closure_verification.json'))
    except FileNotFoundError:
        remote_receipt = None
    existing_receipt = receipt_path.read_bytes() if receipt_path.exists() else remote_receipt
    if existing_receipt is not None:
        receipt = json.loads(existing_receipt)
        if ({k: v for k, v in receipt.items() if k != 'verified_utc'} != static_receipt
                or 'verified_utc' not in receipt):
            raise ValueError('Existing immutable cloud receipt differs')
        if remote_receipt is not None and remote_receipt != existing_receipt:
            raise ValueError('Local/cloud receipt bytes differ')
        if not receipt_path.exists():
            with receipt_path.open('xb') as stream:
                stream.write(existing_receipt)
    else:
        receipt = {**static_receipt, 'verified_utc': datetime.now(timezone.utc).isoformat()}
        save(receipt_path, receipt)
    if remote_receipt is None:
        with volume.batch_upload(force=False) as batch:
            batch.put_file(str(receipt_path), prefix+'cloud_closure_verification.json')
    if b''.join(volume.read_file(prefix+'cloud_closure_verification.json')) != receipt_path.read_bytes():
        raise ValueError('Cloud receipt readback mismatch')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
