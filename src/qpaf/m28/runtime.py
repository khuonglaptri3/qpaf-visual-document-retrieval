"""Finite checksummed shards bound to an exact run/config/source identity."""
import os
from pathlib import Path
import uuid
from collections import Counter
import math
import re

import numpy as np

from qpaf.m11.artifacts import digest, read_json, write_json


def bm25_probe(queries, texts, k1, b, page_limit=16):
    """Independent scalar reference on selected pages with FULL corpus IDF/length."""
    docs = [Counter(re.findall(r'\w+', t.lower())) for t in texts]
    lengths = [sum(d.values()) for d in docs]
    average = sum(lengths)/len(docs)
    terms = {t for q in queries for t in re.findall(r'\w+', q.lower())}
    dfs = {t: sum(t in d for d in docs) for t in terms}
    result = []
    for query in queries:
        row = []
        for d, length in zip(docs[:page_limit], lengths[:page_limit]):
            value = 0.
            for term in re.findall(r'\w+', query.lower()):
                tf = d[term]
                if tf and average:
                    idf = math.log1p((len(docs)-dfs[term]+.5)/(dfs[term]+.5))
                    value += idf*tf*(k1+1)/(tf+k1*(1-b+b*length/average))
            row.append(value)
        result.append(row)
    return np.asarray(result, dtype=np.float64)


def require_cuda(torch):
    if not torch.cuda.is_available():
        raise RuntimeError('M2.8 requires a real CUDA GPU; CPU fallback is forbidden')
    device = torch.cuda.get_device_properties(0)
    return {'name': torch.cuda.get_device_name(0), 'total_memory_bytes': device.total_memory,
            'cuda_version': torch.version.cuda, 'torch_version': torch.__version__}


def save_array(path, array, identity):
    path = Path(path)
    a = np.asarray(array)
    if a.dtype.kind != 'f' or not a.size or not np.isfinite(a).all():
        raise ValueError('Shard must contain nonempty finite floating scores/embeddings')
    if path.exists() or path.with_suffix('.json').exists():
        raise FileExistsError(f'Shard already exists: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('wb') as f:
        np.save(f, a, allow_pickle=False)
    os.replace(tmp, path)
    write_json(path.with_suffix('.json'), {'identity': identity, 'shape': list(a.shape),
               'dtype': str(a.dtype), 'sha256': digest(path), 'size_bytes': path.stat().st_size})


def load_array(path, identity, shape=None):
    path = Path(path)
    meta_path = path.with_suffix('.json')
    if not path.is_file() or not meta_path.is_file():
        raise ValueError(f'Incomplete shard payload/receipt: {path}')
    meta = read_json(meta_path)
    if meta['identity'] != identity:
        raise ValueError(f'Shard identity mismatch: {path}')
    if digest(path) != meta['sha256'] or path.stat().st_size != meta['size_bytes']:
        raise ValueError(f'Shard hash/checksum mismatch: {path}')
    a = np.load(path, allow_pickle=False)
    if (list(a.shape) != meta['shape'] or str(a.dtype) != meta['dtype']
            or shape is not None and a.shape != tuple(shape)
            or a.dtype.kind != 'f' or not np.isfinite(a).all()):
        raise ValueError(f'Shard shape/dtype/finite mismatch: {path}')
    return a


def save_vectors(path, vectors, identity):
    import torch
    path = Path(path)
    if path.exists() or path.with_suffix('.json').exists():
        raise FileExistsError(path)
    if not vectors or any(v.ndim != 2 or not torch.isfinite(v).all() for v in vectors):
        raise ValueError('Invalid multi-vector embeddings')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    torch.save([v.detach().cpu().contiguous() for v in vectors], tmp)
    os.replace(tmp, path)
    write_json(path.with_suffix('.json'), {'identity': identity, 'sha256': digest(path),
               'size_bytes': path.stat().st_size, 'shapes': [list(v.shape) for v in vectors]})


def load_vectors(path, identity):
    import torch
    path = Path(path)
    meta = read_json(path.with_suffix('.json'))
    if meta['identity'] != identity or digest(path) != meta['sha256'] or path.stat().st_size != meta['size_bytes']:
        raise ValueError(f'Multi-vector identity/hash mismatch: {path}')
    vectors = torch.load(path, map_location='cpu', weights_only=True)
    if ([list(v.shape) for v in vectors] != meta['shapes']
            or any(v.ndim != 2 or not torch.isfinite(v).all() for v in vectors)):
        raise ValueError('Multi-vector shape/finite mismatch')
    return vectors
