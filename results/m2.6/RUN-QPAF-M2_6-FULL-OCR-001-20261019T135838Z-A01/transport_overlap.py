"""Operator-only transport overlap; never modifies scientific OCR outputs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
import modal

RUN = 'RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01'
ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / 'results/m2.6' / RUN
VOLUME = modal.Volume.from_name('qpaf-m26-full-ocr')
APP = modal.App('qpaf-m26-stream-collection')


def export_completed_docs(run_id):
    import hashlib
    import json
    from pathlib import Path
    import zipfile
    import shutil
    import time
    from collections import deque
    from concurrent.futures import ThreadPoolExecutor
    import modal
    volume = modal.Volume.from_name('qpaf-m26-full-ocr')
    volume.reload()
    run = Path('/m26/runs') / run_id
    if run_id != 'RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01':
        raise ValueError('Operator export is restricted to this exact run')
    source = run / 'output'
    transfer = run / 'transfer'
    transfer.mkdir(exist_ok=True)
    inputs = json.loads((run / 'input_manifest.json').read_text())
    by_doc = {}
    for row in inputs['scheduled_pages']:
        by_doc.setdefault(row['document_id'], []).append(row['page_id'])
    created = 0
    started = time.monotonic()
    for doc, ids in sorted(by_doc.items()):
        receipt = transfer / (doc + '.json')
        if receipt.exists() or created >= 8 or time.monotonic() - started > 90:
            continue
        if not all((source / 'pages' / page / 'record.json').is_file() for page in ids):
            continue
        path = transfer / (doc + '.zip')
        temporary = transfer / (doc + '.zip.part')
        members = []
        for page in sorted(ids):
            row = json.loads((source / 'pages' / page / 'record.json').read_text())
            items = {r['path']: r['sha256'] for r in row['artifacts'].values()}
            items['pages/' + page + '/record.json'] = None
            for relative, expected in sorted(items.items()):
                if not relative.startswith('pages/' + page + '/') or '..' in relative.split('/'):
                    raise ValueError('Unsafe completed page artifact path')
                members.append((source / relative, relative, expected))
        def load_member(item):
            file, relative, expected = item
            info = zipfile.ZipInfo.from_file(file, relative)
            info.compress_type = zipfile.ZIP_STORED
            payload = file.read_bytes()
            if len(payload) != info.file_size or expected is not None and hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError('Completed source artifact changed')
            return info, payload
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as archive:
            with ThreadPoolExecutor(max_workers=8) as pool:
                iterator = iter(members)
                queue = deque()
                for _ in range(min(8, len(members))):
                    queue.append(pool.submit(load_member, next(iterator)))
                while queue:
                    info, payload = queue.popleft().result()
                    archive.writestr(info, payload)
                    item = next(iterator, None)
                    if item is not None:
                        queue.append(pool.submit(load_member, item))
        temporary.replace(path)
        with path.open('rb') as stream:
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        data = {'document_id': doc, 'sha256': sha, 'size_bytes': path.stat().st_size,
                'remote_path': 'runs/' + run_id + '/transfer/' + path.name}
        receipt.write_text(json.dumps(data) + '\n')
        created += 1
        print(f'Exported {doc}, bytes={data["size_bytes"]}, elapsed={time.monotonic()-started:.1f}s', flush=True)
    volume.commit()
    results = [json.loads(p.read_text()) for p in sorted(transfer.glob('*.json'))]
    progress = json.loads((run / 'progress.json').read_text())
    return {'archives': results, 'worker_progress': progress}


EXPORT = APP.function(image=modal.Image.debian_slim(python_version='3.11'), serialized=True,
                      cpu=2, memory=4096, timeout=900, max_containers=1,
                      volumes={'/m26': VOLUME})(export_completed_docs)


def fetch(record):
    doc = record['document_id']
    if len(doc) != 40 or any(c not in '0123456789abcdef' for c in doc):
        raise ValueError('Unsafe document ID')
    if record['remote_path'] != 'runs/' + RUN + '/transfer/' + doc + '.zip':
        raise ValueError('Unexpected operator transfer path')
    directory = LOCAL / 'output/archives'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (doc + '.zip')
    if path.exists():
        with path.open('rb') as stream:
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        if sha == record['sha256'] and path.stat().st_size == record['size_bytes']:
            return record
        raise ValueError('Existing archive differs from the immutable document export')
    temporary = directory / (doc + '.zip.stream.part')
    with temporary.open('wb') as stream:
        VOLUME.read_file_into_fileobj('/' + record['remote_path'], stream)
    with temporary.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    if sha != record['sha256'] or temporary.stat().st_size != record['size_bytes']:
        raise ValueError('Stream archive checksum mismatch')
    temporary.replace(path)
    print('Collected completed document ' + doc + f" ({record['size_bytes']} bytes)", flush=True)
    # Remove only this operator's redundant transport ZIP, never any OCR output.
    VOLUME.remove_file('/' + record['remote_path'])
    return record


def main():
    fetched = {}
    pending = {}
    with modal.enable_output(), APP.run(detach=True):
        (LOCAL / 'stream_collection_app.json').write_text(json.dumps({'app_id': APP.app_id,
             'purpose': 'transport overlap only; final worker manifest remains authoritative'}, indent=2) + '\n')
        with ThreadPoolExecutor(max_workers=16) as pool:
            while True:
                snapshot = EXPORT.remote(RUN)
                submitted = 0
                for record in snapshot['archives']:
                    doc = record['document_id']
                    if doc not in fetched and doc not in pending:
                        pending[doc] = pool.submit(fetch, record)
                        submitted += 1
                for doc, future in list(pending.items()):
                    if future.done():
                        fetched[doc] = future.result()
                        del pending[doc]
                (LOCAL / 'stream_collection_progress.json').write_text(json.dumps({
                    'documents_collected': len(fetched), 'bytes_collected': sum(r['size_bytes'] for r in fetched.values()),
                    'worker_progress': snapshot['worker_progress']}, indent=2) + '\n')
                print(f"Stream collection: {len(fetched)}/292 documents, {len(pending)} transfers pending; worker={snapshot['worker_progress']}", flush=True)
                if len(fetched) == 292 or snapshot['worker_progress']['status'] != 'RUNNING':
                    for future in as_completed(list(pending.values())):
                        record = future.result()
                        fetched[record['document_id']] = record
                    break
                time.sleep(1 if submitted else 15)


if __name__ == '__main__':
    main()
