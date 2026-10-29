"""A005 Stage 1 BM25 re-run in a second workspace; returns only candidate-sized arrays.

The original bm25.npy (RUN-QPAF-A005-INP-001) could not be downloaded intact. This
app recomputes it with the code and pinned image of a005_stage1_modal.bm25, requires
the full-matrix SHA-256 to equal the original marker, and writes the BM25 top-200
and the BM25 scores on the union with the uploaded dense/visual top-200
(qpaf.a005.bm25_rerun). Inputs are label-free and hash-checked on both sides.

    modal run a005_stage1_bm25_modal.py --inputs <dir> --expected-sha256 a28f354e...
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import modal

APP_NAME = 'qpaf-a005-stage1-bm25'
RUN = 'RUN-QPAF-A005-INP-001-BM25'
ROOT = Path(__file__).resolve().parent
VOL = Path('/vol')
SHARDS = 16
INPUTS = ['canonical_pages.jsonl', 'queries.jsonl', 'tops.npz']+[f'ocr_{s:02d}.jsonl' for s in range(SHARDS)]

volume = modal.Volume.from_name('qpaf-a005-bm25', create_if_missing=True)
app = modal.App(APP_NAME)
LOCAL = [('src/qpaf/a005/candidates.py', '/root/qpaf/a005/candidates.py'),
         ('src/qpaf/a005/bm25_rerun.py', '/root/qpaf/a005/bm25_rerun.py'),
         ('src/qpaf/a005/__init__.py', '/root/qpaf/a005/__init__.py')]
image = (modal.Image.debian_slim(python_version='3.11').apt_install('poppler-utils')
         .pip_install_from_requirements(str(ROOT/'requirements-lock.txt'), extra_options='--require-hashes')
         .env({'NLTK_DATA': '/root/nltk_data'})
         .run_commands('python -c "import nltk; [nltk.download(r, download_dir=\'/root/nltk_data\', '
                       'quiet=True) for r in (\'punkt\', \'punkt_tab\', \'stopwords\')]"')
         .run_commands('mkdir -p /root/qpaf && touch /root/qpaf/__init__.py'))
for _local, _remote in LOCAL:
    image = image.add_local_file(str(ROOT/_local), _remote)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 24), b''):
            digest.update(block)
    return digest.hexdigest()


@app.function(image=image, cpu=2, memory=49152, timeout=10800, volumes={str(VOL): volume}, retries=0)
def bm25_union(input_sha256: dict, expected_sha256: str) -> dict:
    import sys
    import numpy as np
    sys.path.insert(0, '/root')
    from vidore_benchmark.retrievers.bm25_retriever import BM25Retriever
    from qpaf.a005.bm25_rerun import channel_tops, union_scores
    volume.reload()
    base = VOL/RUN
    out = base/'out'
    if (out/'_SUCCESS.json').is_file():
        return json.loads((out/'_SUCCESS.json').read_text(encoding='utf-8'))
    for name, expected in input_sha256.items():
        if sha256_file(base/'inputs'/name) != expected:
            raise ValueError(f'input differs after upload: {name}')
    read = lambda name: (base/'inputs'/name).read_text(encoding='utf-8').splitlines()  # noqa: E731
    pages = [json.loads(line)['page_id'] for line in read('canonical_pages.jsonl')]
    texts = {}
    for shard in range(SHARDS):
        for line in read(f'ocr_{shard:02d}.jsonl'):
            row = json.loads(line)
            texts[row['page_id']] = row['text']
    corpus = [texts[page] for page in pages]
    queries = [json.loads(line)['text'] for line in read('queries.jsonl')]
    retriever = BM25Retriever(device='cpu')
    reference = retriever.get_scores_bm25(queries[:20], corpus).numpy()
    started = time.perf_counter()
    index = retriever.bm25_okapi_class(retriever.preprocess_text(dict(enumerate(corpus))))
    tokenized = retriever.preprocess_text(dict(enumerate(queries)))
    local = Path('/tmp/bm25.npy')
    scores = np.lib.format.open_memmap(local, mode='w+', dtype=np.float64, shape=(len(queries), len(corpus)))
    for row, query in enumerate(tokenized):
        scores[row] = index.get_scores(query)
    scores.flush()
    parity = float(np.abs(scores[:20]-reference).max())
    if parity != 0. or not np.isfinite(scores).all():
        raise ValueError(f'BM25 parity {parity} or non-finite scores')
    del scores
    matrix_sha256 = sha256_file(local)
    if matrix_sha256 != expected_sha256:
        raise ValueError(f'recomputed BM25 matrix {matrix_sha256} differs from the original {expected_sha256}')
    matrix = np.load(local, mmap_mode='r')
    tops = np.load(base/'inputs'/'tops.npz')
    bm25_top, union, values = [], [], []
    for start in range(0, len(queries), 512):
        rows = np.asarray(matrix[start:start+512])
        top = channel_tops(rows)
        u, v = union_scores(rows, top, tops['dense_top'][start:start+512], tops['visual_top'][start:start+512])
        bm25_top.append(top), union.append(u), values.append(v)
    out.mkdir(parents=True, exist_ok=False)
    np.savez(out/'bm25_union.npz', bm25_top=np.concatenate(bm25_top), union=np.concatenate(union),
             values=np.concatenate(values))
    report = {'shape': [len(queries), len(corpus)], 'seconds': time.perf_counter()-started,
              'parity_max_abs_difference_first_20_queries': parity, 'bm25_matrix_sha256': matrix_sha256,
              'matches_original_marker': True, 'bm25_union_sha256': sha256_file(out/'bm25_union.npz'),
              'inputs_sha256': input_sha256}
    with (out/'_SUCCESS.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
    volume.commit()
    return report


@app.local_entrypoint()
def main(inputs: str, expected_sha256: str):
    directory = Path(inputs)
    input_sha256 = {name: sha256_file(directory/name) for name in INPUTS}
    try:
        present = {entry.path for entry in volume.listdir(f'{RUN}/inputs')}
    except Exception:  # noqa: BLE001 - first launch: nothing uploaded yet
        present = set()
    with volume.batch_upload() as batch:
        for name in INPUTS:
            if f'{RUN}/inputs/{name}' not in present:
                batch.put_file(str(directory/name), f'{RUN}/inputs/{name}')
    print(json.dumps(bm25_union.remote(input_sha256, expected_sha256), indent=2))
