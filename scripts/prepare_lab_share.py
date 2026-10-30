"""Research Lead only: build the feature-lab share folder that the members unpack (docs/feature_lab/HUONG_DAN_CHAY.md).

Layout of --output:
  vimdoc/{candidate_scores.parquet, queries.jsonl, dev_qrels.json}  ViMDoc dev pool; the sealed confirmation qrels stay out
  assets/{vimdoc,vidoseek}_page_text.jsonl                          F1: {"page_id", "text"} for every OCR page
  assets/{vimdoc,vidoseek}_qemb.npz                                 F4: BGE-M3 dense query vectors, dev queries only
  MANIFEST.json                                                     SHA-256, size and row count of every file

ViMDoc OCR text and query vectors come from the A005 Stage 1 run on the Modal volume `qpaf-artifacts` (needs the
`modal` CLI on that workspace); every shard is checked against the SHA-256 in its _SUCCESS marker. ViDoSeek text
comes from the committed M2.6 resolved pages. ViDoSeek query vectors are encoded here with BAAI/bge-m3 at the
dense-channel revision (CLS, L2-normalized, as scripts/bge_m3_dense_retriever.py), which needs torch, transformers
and the model in the Hugging Face cache; the same encoder must reproduce the ViMDoc Stage 1 vectors (cosine check).
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VOLUME, RUN = 'qpaf-artifacts', 'a005/s1/RUN-QPAF-A005-INP-001'
SHARDS, VIMDOC_PAGES = 16, 76_347
VIMDOC_FILES = ('candidate_scores.parquet', 'queries.jsonl', 'dev_qrels.json')
VIMDOC_SPLITS = ROOT/'evidence/revisions/m4.1-001'
VIDOSEEK_BUNDLE = ROOT/'results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle'
VIDOSEEK_OCR = ROOT/'results/m2.6/RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01/output'
BGE_REVISION = '5617a9f61b028005a4858fdac845db406aefb181'
MIN_COSINE = 0.999


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def fetch(remote, local):
    """One file from the Stage 1 run on the Modal volume."""
    subprocess.run(['modal', 'volume', 'get', '--force', VOLUME, f'{RUN}/{remote}', str(local)], check=True,
                   capture_output=True, env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
    return local


def marker(remote, scratch):
    return json.loads(fetch(f'{remote}/_SUCCESS.json', scratch/'_SUCCESS.json').read_text(encoding='utf-8'))


def write_page_text(rows, path, required):
    """JSONL {"page_id", "text"} sorted by page ID; every candidate page must have text."""
    ids = [page_id for page_id, _ in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f'{path.name}: duplicate page IDs')
    missing = set(required)-set(ids)
    if missing:
        raise ValueError(f'{path.name}: {len(missing)} candidate pages without OCR text, e.g. {sorted(missing)[:3]}')
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        for page_id, text in sorted(rows):
            stream.write(json.dumps({'page_id': page_id, 'text': text}, ensure_ascii=False)+'\n')
    return len(rows)


def candidate_pages(path):
    import pyarrow.parquet as pq
    return set(pq.read_table(path, columns=['page_id']).column('page_id').to_pylist())


def vimdoc_page_text(scratch, out, required):
    rows = []
    for shard in range(SHARDS):
        remote = f'ocr/shard_{shard:02d}'
        expected = marker(remote, scratch)['ocr_jsonl_sha256']
        local = fetch(f'{remote}/ocr.jsonl', scratch/f'ocr_{shard:02d}.jsonl')
        if sha256(local) != expected:
            raise ValueError(f'{remote}/ocr.jsonl: SHA-256 differs from its _SUCCESS marker (corrupt download?)')
        rows += [(r['page_id'], r['text']) for r in map(json.loads, local.read_text(encoding='utf-8').splitlines())]
        print(f'  ViMDoc OCR shard {shard:02d}: {len(rows)} pages so far')
    if len(rows) != VIMDOC_PAGES:
        raise ValueError(f'ViMDoc OCR has {len(rows)} pages, expected {VIMDOC_PAGES}')
    return write_page_text(rows, out, required)


def vidoseek_page_text(out, required):
    import csv
    pages = json.loads((VIDOSEEK_OCR/'resolved_pages.json').read_text(encoding='utf-8'))
    with (VIDOSEEK_OCR/'page_hashes.csv').open(encoding='utf-8') as stream:
        expected = {row['page_id']: row['text_sha256'] for row in csv.DictReader(stream)}
    for page in pages:
        if hashlib.sha256(page['text'].encode('utf-8')).hexdigest() != expected[page['page_id']]:
            raise ValueError(f"ViDoSeek text of {page['page_id']} differs from page_hashes.csv")
    return write_page_text([(p['page_id'], p['text']) for p in pages], out, required)


def vimdoc_dev_ids():
    return [i for role in ('train', 'validation') for i in (VIMDOC_SPLITS/f'{role}_ids.txt').read_text(encoding='utf-8').split()]


def vidoseek_dev_ids():
    return [i for name in ('train_ids.txt', 'val_ids.txt') for i in (VIDOSEEK_BUNDLE/'splits'/name).read_text(encoding='utf-8').split()]


def vimdoc_query_vectors(scratch, cache):
    """Stage 1 bge_queries.pt rows follow prepare/queries.jsonl, which must equal the cache's queries.jsonl."""
    import torch
    expected = marker('query_embed', scratch)['bge_sha256']
    vectors = fetch('query_embed/bge_queries.pt', scratch/'bge_queries.pt')
    if sha256(vectors) != expected:
        raise ValueError('query_embed/bge_queries.pt: SHA-256 differs from its _SUCCESS marker')
    order = fetch('prepare/queries.jsonl', scratch/'queries.jsonl')
    if order.read_bytes() != (cache/'queries.jsonl').read_bytes():
        raise ValueError('Stage 1 prepare/queries.jsonl differs from the cache queries.jsonl')
    rows = [json.loads(line) for line in order.read_text(encoding='utf-8').splitlines()]
    matrix = torch.load(vectors).numpy()
    if matrix.shape != (len(rows), 1024):
        raise ValueError(f'bge_queries.pt has shape {matrix.shape}, expected ({len(rows)}, 1024)')
    index = {row['query_id']: i for i, row in enumerate(rows)}
    texts = {row['query_id']: row['text'] for row in rows}
    ids = vimdoc_dev_ids()
    return ids, matrix[[index[i] for i in ids]].astype(np.float32), [texts[i] for i in ids]


def encoder():
    """BAAI/bge-m3 dense query encoder on CPU: CLS token, L2-normalized, max 512 tokens."""
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoModel, AutoTokenizer
    path = snapshot_download('BAAI/bge-m3', revision=BGE_REVISION)
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    model = AutoModel.from_pretrained(path, local_files_only=True, torch_dtype=torch.float32).eval()

    def encode(texts, batch_size=32):
        out = []
        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                inputs = tokenizer(texts[start:start+batch_size], max_length=512, padding=True, truncation=True,
                                   return_tensors='pt')
                out.append(torch.nn.functional.normalize(model(**inputs).last_hidden_state[:, 0], dim=-1).numpy())
        return np.concatenate(out).astype(np.float32)
    return encode


def save_vectors(path, ids, vectors):
    if not np.isfinite(vectors).all() or np.abs(np.linalg.norm(vectors, axis=1)-1).max() > 1e-3:
        raise ValueError(f'{path.name}: non-finite or non-normalized vectors')
    np.savez(path, ids=np.array(ids), vectors=vectors)
    return len(ids)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--vimdoc-cache', required=True, type=Path, help='Stage 1 cache dir with the three ViMDoc files')
    parser.add_argument('--output', required=True, type=Path, help='new share folder, outside the repository')
    parser.add_argument('--zip', action='store_true', help='also write <output>.zip')
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f'{args.output} exists; choose a new folder')
    (args.output/'vimdoc').mkdir(parents=True)
    (args.output/'assets').mkdir()
    rows = {}
    for name in VIMDOC_FILES:
        shutil.copy2(args.vimdoc_cache/name, args.output/'vimdoc'/name)
    assets = args.output/'assets'
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        print('ViMDoc OCR text from Modal ...')
        rows['assets/vimdoc_page_text.jsonl'] = vimdoc_page_text(
            scratch, assets/'vimdoc_page_text.jsonl', candidate_pages(args.vimdoc_cache/'candidate_scores.parquet'))
        print('ViMDoc query vectors from Modal ...')
        ids, vectors, texts = vimdoc_query_vectors(scratch, args.vimdoc_cache)
        rows['assets/vimdoc_qemb.npz'] = save_vectors(assets/'vimdoc_qemb.npz', ids, vectors)
    print('ViDoSeek OCR text from M2.6 ...')
    rows['assets/vidoseek_page_text.jsonl'] = vidoseek_page_text(
        assets/'vidoseek_page_text.jsonl', candidate_pages(VIDOSEEK_BUNDLE/'raw_scores.parquet'))
    print('ViDoSeek query vectors (local BGE-M3) ...')
    encode = encoder()
    cosine = float((encode(texts[:64])*vectors[:64]).sum(axis=1).min())
    if cosine < MIN_COSINE:
        raise ValueError(f'local BGE-M3 does not reproduce the Stage 1 ViMDoc vectors (min cosine {cosine:.5f})')
    queries = json.loads((VIDOSEEK_BUNDLE/'queries.json').read_text(encoding='utf-8'))
    ids = vidoseek_dev_ids()
    rows['assets/vidoseek_qemb.npz'] = save_vectors(assets/'vidoseek_qemb.npz', ids, encode([queries[i] for i in ids]))
    files = sorted(p for p in args.output.rglob('*') if p.is_file())
    manifest = {'schema': 'qpaf-lab-share-v1', 'created_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'source_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                                                text=True).stdout.strip(),
                'vimdoc_stage1_run': f'{VOLUME}:{RUN}', 'bge_m3_revision': BGE_REVISION,
                'vidoseek_encoder_check_min_cosine': cosine,
                'files': {p.relative_to(args.output).as_posix(): {'sha256': sha256(p), 'bytes': p.stat().st_size,
                                                                  'rows': rows.get(p.relative_to(args.output).as_posix())}
                          for p in files}}
    (args.output/'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True)+'\n', encoding='utf-8')
    if args.zip:
        shutil.make_archive(str(args.output), 'zip', args.output)
    print(json.dumps({k: v['rows'] for k, v in manifest['files'].items()}, indent=1))


if __name__ == '__main__':
    main()
