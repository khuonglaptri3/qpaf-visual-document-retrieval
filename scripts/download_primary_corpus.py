"""Download/inventory the pinned primary corpus without rendering, OCR or inference."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m11.artifacts import digest

REPO = 'Qiuchen-Wang/ViDoSeek'
REVISION = 'e91a92ba5f38690696c7e66be5c5474b54c6e791'


def main():
    import zipfile
    from huggingface_hub import HfApi, hf_hub_download
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT/'data/raw/vidoseek-e91a92b')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--extract', action='store_true', help='Extract PDFs to <directory>/pdfs')
    parser.add_argument('--force', action='store_true', help='Overwrite manifest if it exists')
    args = parser.parse_args()
    if args.manifest.exists() and not args.force:
        raise FileExistsError(f'Manifest exists: {args.manifest}; pass --force to overwrite')
    info = HfApi().dataset_info(REPO, revision=REVISION, files_metadata=True)
    if info.sha != REVISION:
        raise ValueError('Dataset revision mismatch')
    remote = {f.rfilename:f for f in info.siblings}
    records = []
    for name in ('README.md', 'vidoseek.json', 'vidoseek_pdf_document.zip'):
        path = Path(hf_hub_download(REPO, name, repo_type='dataset', revision=REVISION,
                                   local_dir=str(args.directory)))
        sha = digest(path)
        meta = remote[name]
        if path.stat().st_size != meta.size:
            raise ValueError(f'Remote size mismatch: {name}')
        if meta.lfs:
            if sha != meta.lfs.sha256:
                raise ValueError(f'Remote LFS SHA256 mismatch: {name}')
        else:
            payload = path.read_bytes()
            blob = hashlib.sha1(f'blob {len(payload)}\0'.encode()+payload).hexdigest()
            if blob != meta.blob_id:
                raise ValueError(f'Remote Git blob mismatch: {name}')
        records.append({'filename':name, 'path':path.resolve().as_posix(),
                        'size_bytes':path.stat().st_size, 'sha256':sha,
                        'remote_git_blob':meta.blob_id,
                        'remote_lfs_sha256':meta.lfs.sha256 if meta.lfs else None,
                        'source_url':f'https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{name}'})
        print(f'Verified {name}: {path.stat().st_size} bytes', flush=True)
    manifest = {'schema_version':1, 'dataset':REPO, 'revision':REVISION,
                'license_declared_by_dataset_card':info.card_data.to_dict().get('license') if info.card_data else None,
                'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                'command':sys.argv, 'python':sys.version,
                'scope':'download_and_inventory_only; no OCR, model download or research inference',
                'files':records, 'independent_review':'PENDING'}
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    mode = 'w' if args.force else 'x'
    with args.manifest.open(mode, encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write('\n')

    if args.extract:
        zip_path = args.directory / 'vidoseek_pdf_document.zip'
        extract_target = args.directory / 'pdfs'
        print(f'Extracting {zip_path.name} to {extract_target}...', flush=True)
        extract_target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_target)
        print('Corpus extraction complete.', flush=True)


if __name__ == '__main__':
    main()
