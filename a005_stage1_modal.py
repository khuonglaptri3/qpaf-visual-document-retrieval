"""A005 Stage 1: ViMDoc label-free score cache (OCR, BM25, BGE-M3, ColQwen2.5, candidate union).

Steps write create-once outputs under /vol/a005/s1/<run>/ with a _SUCCESS marker;
the entrypoint skips a step or shard whose marker exists and never overwrites.
The `doc_ids` column is read once in `prepare`, immediately split into dev qrels
(train + validation) and a sealed confirmation file that nothing in Stage 1 reads.

    modal run a005_stage1_modal.py --pages-sha256 9dc27715...0b84
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import modal

APP_NAME = 'qpaf-a005-stage1'
RUN = 'RUN-QPAF-A005-INP-001'
ROOT = Path(__file__).resolve().parent
VOL = Path('/vol')
DATASET = 'datasets/vimdoc/25657f1fe0358f49147148ca89e231291ba42788'
ARCHIVE = f'{DATASET}/ViMDoc_pages.tar.gz'
PARQUET = f'{DATASET}/data/ViMDoc-00000-of-00001.parquet'
PARQUET_SHA256 = '7ccac6c8715cc338c041e9276583b9dbd79a818131a9b13a5abf4b9ced73bcc0'
PAGES = 'audits/vimdoc/vimdoc_identity_v2/canonical_pages.jsonl'
OUT = f'a005/s1/{RUN}'
SHARDS = 16

volume = modal.Volume.from_name('qpaf-artifacts', create_if_missing=False)
hf_secret = modal.Secret.from_name('huggingface-secret', required_keys=['HF_TOKEN'])
app = modal.App(APP_NAME)
LOCAL = [('src/qpaf/a005/stage1.py', '/root/qpaf/a005/stage1.py'),
         ('src/qpaf/a005/candidates.py', '/root/qpaf/a005/candidates.py'),
         ('src/qpaf/a005/__init__.py', '/root/qpaf/a005/__init__.py'),
         ('evidence/revisions/m4.1-001/train_ids.txt', '/root/ids/train_ids.txt'),
         ('evidence/revisions/m4.1-001/validation_ids.txt', '/root/ids/validation_ids.txt'),
         ('evidence/revisions/m4.1-001/confirmation_ids.txt', '/root/ids/confirmation_ids.txt'),
         ('configs/vimdoc_m3_local_v1.json', '/root/configs/vimdoc_m3_local_v1.json'),
         ('scripts/colqwen25_retriever.py', '/root/scripts/colqwen25_retriever.py'),
         ('scripts/bge_m3_dense_retriever.py', '/root/scripts/bge_m3_dense_retriever.py')]


def _with_local(image):
    image = image.run_commands('mkdir -p /root/qpaf && touch /root/qpaf/__init__.py')
    for local, remote in LOCAL:
        image = image.add_local_file(str(ROOT/local), remote)
    return image


ocr_image = _with_local(modal.Image.debian_slim(python_version='3.11')
                        .apt_install('tesseract-ocr=5.3.0-2', 'tesseract-ocr-eng=1:4.1.0-2')
                        .pip_install('pillow==11.3.0', 'pytesseract==0.3.13', 'numpy==2.2.6'))
gpu_image = _with_local(modal.Image.debian_slim(python_version='3.11').apt_install('poppler-utils')
                        .pip_install_from_requirements(str(ROOT/'requirements-lock.txt'), extra_options='--require-hashes')
                        .env({'NLTK_DATA': '/root/nltk_data'})
                        .run_commands('python -c "import nltk; [nltk.download(r, download_dir=\'/root/nltk_data\', '
                                      'quiet=True) for r in (\'punkt\', \'punkt_tab\', \'stopwords\')]"'))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _out(*parts):
    return VOL/OUT/Path(*parts)


def _done(directory):
    return (directory/'_SUCCESS.json').is_file()


def _finish(directory, report):
    with (directory/'_SUCCESS.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
    volume.commit()
    return report


def _pages(pages_sha256):
    data = (VOL/PAGES).read_bytes()
    if sha256(data) != pages_sha256:
        raise ValueError('v2 canonical pages differ from the pinned hash')
    return [json.loads(line) for line in data.decode('utf-8').splitlines()]


def _ids(role):
    return Path(f'/root/ids/{role}_ids.txt').read_text(encoding='utf-8').splitlines()


@app.function(image=gpu_image, cpu=2, memory=8192, timeout=1800, volumes={str(VOL): volume}, retries=0)
def prepare() -> dict:
    import sys
    import pyarrow.parquet as pq
    sys.path.insert(0, '/root')
    from qpaf.a005.stage1 import canonical_bytes, sha256_bytes, split_qrels
    directory = _out('prepare')
    if _done(directory):
        return json.loads((directory/'_SUCCESS.json').read_text(encoding='utf-8'))
    if sha256((VOL/PARQUET).read_bytes()) != PARQUET_SHA256:
        raise ValueError('ViMDoc parquet differs from the pinned hash')
    directory.mkdir(parents=True, exist_ok=False)
    splits = {role: _ids(role) for role in ('train', 'validation', 'confirmation')}
    texts = pq.read_table(VOL/PARQUET, columns=['id', 'query']).to_pydict()
    queries = sorted(zip(texts['id'], texts['query']), key=lambda row: row[0].encode('utf-8'))
    if sorted(q for q, _ in queries) != sorted(i for ids in splits.values() for i in ids):
        raise ValueError('query IDs differ from the M4.1 sealed splits')
    query_bytes = b''.join(canonical_bytes({'query_id': q, 'text': t}) for q, t in queries)
    (directory/'queries.jsonl').write_bytes(query_bytes)
    labels = pq.read_table(VOL/PARQUET, columns=['id', 'doc_ids']).to_pydict()
    qrels = split_qrels(zip(labels['id'], labels['doc_ids']), splits)
    del labels
    dev = {'train': qrels['train'], 'validation': qrels['validation']}
    dev_bytes, sealed_bytes = canonical_bytes(dev), canonical_bytes(qrels['confirmation'])
    del qrels
    (directory/'dev_qrels.json').write_bytes(dev_bytes)
    (directory/'confirmation_qrels.sealed.json').write_bytes(sealed_bytes)
    return _finish(directory, {'queries': len(queries), 'queries_sha256': sha256_bytes(query_bytes),
                               'dev_qrels_sha256': sha256_bytes(dev_bytes),
                               'confirmation_qrels_sealed_sha256': sha256_bytes(sealed_bytes),
                               'confirmation_qrels_read_after_sealing': False})


@app.function(image=ocr_image, cpu=4, memory=8192, timeout=5400, volumes={str(VOL): volume}, retries=0)
def ocr_shard(pages_sha256: str, shard: int) -> dict:
    import io
    import subprocess
    import sys
    import tarfile
    from concurrent.futures import ProcessPoolExecutor
    sys.path.insert(0, '/root')
    from qpaf.a005.stage1 import canonical_bytes, shard_pages
    directory = _out('ocr', f'shard_{shard:02d}')
    if _done(directory):
        return json.loads((directory/'_SUCCESS.json').read_text(encoding='utf-8'))
    directory.mkdir(parents=True, exist_ok=False)
    pages = shard_pages(_pages(pages_sha256), SHARDS, shard)
    wanted = {page['canonical_asset_path']: page for page in pages}
    found, started = {}, time.perf_counter()
    with tarfile.open(VOL/ARCHIVE, 'r|gz') as archive, tarfile.open(directory/'images.tar', 'x') as images:
        for member in archive:
            page = wanted.get(member.name)
            if page is None:
                continue
            payload = archive.extractfile(member).read()
            if sha256(payload) != page['asset_sha256']:
                raise ValueError(f'asset hash mismatch: {member.name}')
            info = tarfile.TarInfo(page['page_id'])
            info.size = len(payload)
            images.addfile(info, io.BytesIO(payload))
            found[page['page_id']] = payload
            if len(found) == len(wanted):
                break
    extract_seconds = time.perf_counter()-started
    if len(found) != len(wanted):
        raise ValueError(f'shard {shard}: {len(found)} of {len(wanted)} assets found')
    order = [page['page_id'] for page in pages]
    started = time.perf_counter()
    with ProcessPoolExecutor(4) as pool:
        texts = list(pool.map(_ocr, [found[p] for p in order], chunksize=8))
    rows = b''
    empty = 0
    for page_id, text in zip(order, texts):
        if '\x00' in text:
            raise ValueError(f'NUL in OCR text: {page_id}')
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        empty += not text.strip()
        rows += canonical_bytes({'page_id': page_id, 'status': 'SUCCESS' if text.strip() else 'SUCCESS_EMPTY',
                                 'text': text, 'text_sha256': sha256(text.encode('utf-8')),
                                 'character_count': len(text)})
    (directory/'ocr.jsonl').write_bytes(rows)
    version = subprocess.run(['tesseract', '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    return _finish(directory, {'shard': shard, 'pages': len(order), 'empty_pages': empty,
                               'extract_seconds': extract_seconds, 'ocr_seconds': time.perf_counter()-started,
                               'ocr_jsonl_sha256': sha256(rows), 'images_tar_sha256': sha256((directory/'images.tar').read_bytes()),
                               'tesseract_version': version})


def _ocr(payload):
    import io
    from PIL import Image
    import pytesseract
    image = Image.open(io.BytesIO(payload))
    image.load()
    return pytesseract.image_to_string(image.convert('RGB'), lang='eng', config='--oem 3 --psm 3')


def _models():
    return json.loads(Path('/root/configs/vimdoc_m3_local_v1.json').read_text(encoding='utf-8'))['retrievers']


def _queries():
    rows = (_out('prepare', 'queries.jsonl')).read_text(encoding='utf-8').splitlines()
    return [json.loads(line) for line in rows]


@app.function(image=gpu_image, gpu='L4', cpu=4, memory=32768, timeout=3600, secrets=[hf_secret],
              volumes={str(VOL): volume}, retries=0)
def query_embed() -> dict:
    import sys
    import torch
    from huggingface_hub import snapshot_download
    sys.path.insert(0, '/root')
    from scripts.bge_m3_dense_retriever import BGEM3DenseRetriever
    from scripts.colqwen25_retriever import ColQwen25Retriever
    volume.reload()
    directory = _out('query_embed')
    if _done(directory):
        return json.loads((directory/'_SUCCESS.json').read_text(encoding='utf-8'))
    directory.mkdir(parents=True, exist_ok=False)
    texts = [row['text'] for row in _queries()]
    models, started = _models(), time.perf_counter()
    visual = models['visual']
    colqwen = ColQwen25Retriever(base_model_id=visual['base_id'], base_revision=visual['base_revision'],
                                 adapter_model_id=visual['id'], adapter_revision=visual['revision'])
    torch.save(colqwen.forward_queries(texts, batch_size=8), directory/'colqwen_queries.pt')
    del colqwen
    torch.cuda.empty_cache()
    dense = models['dense']
    bge = BGEM3DenseRetriever(snapshot_download(dense['id'], revision=dense['revision']))
    torch.save(bge.forward_queries(texts, batch_size=32), directory/'bge_queries.pt')
    return _finish(directory, {'queries': len(texts), 'seconds': time.perf_counter()-started,
                               'colqwen_sha256': sha256((directory/'colqwen_queries.pt').read_bytes()),
                               'bge_sha256': sha256((directory/'bge_queries.pt').read_bytes())})


@app.function(image=gpu_image, gpu='L4', cpu=4, memory=32768, timeout=7200, secrets=[hf_secret],
              volumes={str(VOL): volume}, retries=0)
def gpu_shard(shard: int) -> dict:
    import io
    import sys
    import tarfile
    import numpy as np
    import torch
    from huggingface_hub import snapshot_download
    from PIL import Image
    sys.path.insert(0, '/root')
    from scripts.bge_m3_dense_retriever import BGEM3DenseRetriever
    from scripts.colqwen25_retriever import ColQwen25Retriever
    volume.reload()
    directory = _out('gpu', f'shard_{shard:02d}')
    if _done(directory):
        return json.loads((directory/'_SUCCESS.json').read_text(encoding='utf-8'))
    directory.mkdir(parents=True, exist_ok=False)
    source = _out('ocr', f'shard_{shard:02d}')
    rows = [json.loads(line) for line in (source/'ocr.jsonl').read_text(encoding='utf-8').splitlines()]
    payloads = {}
    with tarfile.open(source/'images.tar') as archive:
        for member in archive:
            payloads[member.name] = archive.extractfile(member).read()

    class LazyImages:
        """Decode on access; holding every decoded page would need about 50 GB of RAM."""
        def __init__(self, keys):
            self.keys = keys

        def __len__(self):
            return len(self.keys)

        def __getitem__(self, index):
            image = Image.open(io.BytesIO(payloads[self.keys[index]]))
            image.load()
            return image.convert('RGB')
    ordered = LazyImages([row['page_id'] for row in rows])
    queries = _out('query_embed')
    models, timings = _models(), {}
    visual = models['visual']
    started = time.perf_counter()
    colqwen = ColQwen25Retriever(base_model_id=visual['base_id'], base_revision=visual['base_revision'],
                                 adapter_model_id=visual['id'], adapter_revision=visual['revision'])
    passages = colqwen.forward_passages(ordered, batch_size=2)
    timings['colqwen_encode_seconds'] = time.perf_counter()-started
    started = time.perf_counter()
    visual_scores = colqwen.processor.score(torch.load(queries/'colqwen_queries.pt'), passages,
                                            batch_size=128, device='cuda').float().cpu().numpy()
    timings['maxsim_seconds'] = time.perf_counter()-started
    del colqwen, passages
    torch.cuda.empty_cache()
    dense = models['dense']
    started = time.perf_counter()
    bge = BGEM3DenseRetriever(snapshot_download(dense['id'], revision=dense['revision']))
    page_dense = bge.forward_passages([row['text'] for row in rows], batch_size=8)
    dense_scores = BGEM3DenseRetriever.get_scores(torch.load(queries/'bge_queries.pt'), page_dense).numpy()
    timings['bge_seconds'] = time.perf_counter()-started
    for name, array in (('visual', visual_scores), ('dense', dense_scores)):
        if not np.isfinite(array).all():
            raise ValueError(f'shard {shard}: non-finite {name} scores')
        np.save(directory/f'{name}.npy', array.astype(np.float32))
    return _finish(directory, {'shard': shard, 'pages': len(rows), 'shape': list(visual_scores.shape), **timings,
                               'visual_sha256': sha256((directory/'visual.npy').read_bytes()),
                               'dense_sha256': sha256((directory/'dense.npy').read_bytes()),
                               'gpu': torch.cuda.get_device_name(0)})


@app.function(image=gpu_image, cpu=2, memory=49152, timeout=21600, volumes={str(VOL): volume}, retries=0)
def bm25(pages_sha256: str) -> dict:
    import sys
    import numpy as np
    sys.path.insert(0, '/root')
    from vidore_benchmark.retrievers.bm25_retriever import BM25Retriever
    volume.reload()
    directory = _out('bm25')
    if _done(directory):
        return json.loads((directory/'_SUCCESS.json').read_text(encoding='utf-8'))
    directory.mkdir(parents=True, exist_ok=False)
    pages = [page['page_id'] for page in _pages(pages_sha256)]
    texts = {}
    for shard in range(SHARDS):
        for line in _out('ocr', f'shard_{shard:02d}', 'ocr.jsonl').read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            texts[row['page_id']] = row['text']
    corpus = [texts[page] for page in pages]
    queries = [row['text'] for row in _queries()]
    retriever = BM25Retriever(device='cpu')
    # Parity: the chunked scoring below must equal the library call on a slice.
    reference = retriever.get_scores_bm25(queries[:20], corpus).numpy()
    started = time.perf_counter()
    index = retriever.bm25_okapi_class(retriever.preprocess_text(dict(enumerate(corpus))))
    tokenized = retriever.preprocess_text(dict(enumerate(queries)))
    import shutil
    local = Path('/tmp/bm25.npy')
    scores = np.lib.format.open_memmap(local, mode='w+', dtype=np.float64, shape=(len(queries), len(corpus)))
    for row, query in enumerate(tokenized):
        scores[row] = index.get_scores(query)
    scores.flush()
    parity = float(np.abs(scores[:20]-reference).max())
    if parity != 0. or not np.isfinite(scores).all():
        raise ValueError(f'BM25 parity {parity} or non-finite scores')
    del scores
    shutil.copyfile(local, directory/'bm25.npy')
    return _finish(directory, {'shape': [len(queries), len(corpus)], 'seconds': time.perf_counter()-started,
                               'parity_max_abs_difference_first_20_queries': parity,
                               'bm25_sha256': sha256((directory/'bm25.npy').read_bytes())})


@app.function(image=gpu_image, cpu=4, memory=65536, timeout=10800, volumes={str(VOL): volume}, retries=0)
def assemble(pages_sha256: str) -> dict:
    import sys
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    sys.path.insert(0, '/root')
    from qpaf.a005.stage1 import assemble_channel, candidate_rows, coverage
    volume.reload()
    directory = _out('cache')
    if _done(directory):
        return json.loads((directory/'_SUCCESS.json').read_text(encoding='utf-8'))
    directory.mkdir(parents=True, exist_ok=False)
    pages = _pages(pages_sha256)
    page_ids = [page['page_id'] for page in pages]
    documents = {page['page_id']: page['document_id'] for page in pages}
    query_ids = [row['query_id'] for row in _queries()]
    total = len(page_ids)
    matrices = {'bm25': np.load(_out('bm25', 'bm25.npy'), mmap_mode='r')}
    for name in ('dense', 'visual'):
        blocks = [np.load(_out('gpu', f'shard_{s:02d}', f'{name}.npy')) for s in range(SHARDS)]
        matrices[name] = assemble_channel(total, SHARDS, blocks)
    matrices = {c: matrices[c] for c in ('bm25', 'dense', 'visual')}
    columns = {k: [] for k in ('query_id', 'page_id', 'document_id', 'bm25', 'dense', 'visual',
                               'bm25_norm', 'dense_norm', 'visual_norm')}
    unions, sizes = {}, []
    for query_id, union, raw, normalized in candidate_rows(query_ids, page_ids, documents, matrices):
        unions[query_id] = union.tolist()
        sizes.append(int(union.size))
        for i, index in enumerate(union.tolist()):
            columns['query_id'].append(query_id)
            columns['page_id'].append(page_ids[index])
            columns['document_id'].append(documents[page_ids[index]])
            for j, channel in enumerate(('bm25', 'dense', 'visual')):
                columns[channel].append(float(raw[i, j]))
                columns[channel+'_norm'].append(float(normalized[i, j]))
    pq.write_table(pa.table(columns), directory/'candidate_scores.parquet')
    dev = json.loads(_out('prepare', 'dev_qrels.json').read_text(encoding='utf-8'))
    reports = {role: coverage(unions, page_ids, documents, dev[role]) for role in ('train', 'validation')}
    return _finish(directory, {'queries': len(query_ids), 'rows': len(columns['query_id']),
                               'union_size_min': min(sizes), 'union_size_max': max(sizes),
                               'union_size_mean': sum(sizes)/len(sizes), 'coverage': reports,
                               'candidate_scores_sha256': sha256((directory/'candidate_scores.parquet').read_bytes()),
                               'labels_used': 'dev qrels for the coverage report only, after the union was frozen'})


@app.local_entrypoint()
def main(pages_sha256: str):
    print(json.dumps(prepare.remote(), indent=2))
    for report in ocr_shard.starmap([(pages_sha256, s) for s in range(SHARDS)]):
        print('ocr', report['shard'], report['pages'], round(report['ocr_seconds']))
    print(json.dumps(query_embed.remote(), indent=2))
    bm25_call = bm25.spawn(pages_sha256)
    for report in gpu_shard.map(range(SHARDS)):
        print('gpu', report['shard'], report['shape'], round(report['colqwen_encode_seconds']))
    print(json.dumps(bm25_call.get(), indent=2))
    print(json.dumps(assemble.remote(pages_sha256), indent=2))
