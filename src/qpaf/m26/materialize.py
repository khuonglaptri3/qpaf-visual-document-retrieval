"""Fetch the immutable public source archive and verify every PDF before OCR."""
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile

from qpaf.m11.artifacts import digest, utc, write_json


def materialize_pdfs(run, inputs, *, archive_path=None):
    run = Path(run)
    directory = run / 'inputs/pdfs'
    directory.mkdir(parents=True, exist_ok=True)
    records = [r for r in inputs['source_files'] if Path(r['path']).name == 'vidoseek_pdf_document.zip']
    if len(records) != 1:
        raise ValueError('Expected exactly one frozen PDF source archive')
    source = records[0]
    dataset = inputs['dataset']
    if (dataset['name'], dataset['revision']) != ('Qiuchen-Wang/ViDoSeek', 'e91a92ba5f38690696c7e66be5c5474b54c6e791'):
        raise ValueError('Unexpected source dataset/revision')
    url = ('https://huggingface.co/datasets/Qiuchen-Wang/ViDoSeek/resolve/'
           + dataset['revision'] + '/vidoseek_pdf_document.zip')
    started = time.perf_counter()
    if archive_path is None:
        archive_path = run / 'inputs/vidoseek_pdf_document.zip'
        if not archive_path.exists():
            temporary = archive_path.with_name(archive_path.name + '.part')
            print('Fetching the pinned ViDoSeek source archive on the CPU worker...', flush=True)
            request = urllib.request.Request(url, headers={'User-Agent': 'qpaf-m26/1.0'})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as stream:
                shutil.copyfileobj(response, stream, length=1024 * 1024)
            if temporary.stat().st_size != source['size_bytes'] or digest(temporary) != source['sha256']:
                raise ValueError('Downloaded source archive hash/size mismatch')
            temporary.replace(archive_path)
    archive_path = Path(archive_path)
    if archive_path.stat().st_size != source['size_bytes'] or digest(archive_path) != source['sha256']:
        raise ValueError('Frozen source archive hash/size mismatch')
    with zipfile.ZipFile(archive_path) as archive:
        members = {}
        for item in archive.infolist():
            if not item.is_dir() and item.filename.lower().endswith('.pdf'):
                name = Path(item.filename).name
                if name in members:
                    raise ValueError('Duplicate PDF basename in frozen source archive')
                members[name] = item
        for record in inputs['documents']:
            name = record['document_id'] + '.pdf'
            if name not in members or members[name].file_size != record['size_bytes']:
                raise ValueError('Frozen PDF member missing or size mismatch: ' + name)
            path = directory / name
            if path.exists():
                if path.stat().st_size != record['size_bytes'] or digest(path) != record['sha256']:
                    raise ValueError('Existing materialized PDF hash mismatch: ' + name)
                continue
            temporary = path.with_name(path.name + '.part')
            with archive.open(members[name]) as source_stream, temporary.open('wb') as destination:
                shutil.copyfileobj(source_stream, destination, length=1024 * 1024)
            if temporary.stat().st_size != record['size_bytes'] or digest(temporary) != record['sha256']:
                raise ValueError('Extracted PDF hash mismatch: ' + name)
            temporary.replace(path)
    result = {'status': 'VERIFIED', 'transport': 'pinned_huggingface_archive', 'source_url': url,
              'source_archive_sha256': source['sha256'], 'source_archive_bytes': source['size_bytes'],
              'verified_documents': len(inputs['documents']), 'wall_seconds': time.perf_counter() - started,
              'completed_utc': utc()}
    write_json(run / 'materialization.json', result)
    print(f"Materialized and hash-verified {result['verified_documents']} source PDFs", flush=True)
    return result
