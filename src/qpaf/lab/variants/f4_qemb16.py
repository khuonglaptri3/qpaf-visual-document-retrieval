"""F4: 16-d PCA of the BGE-M3 query embedding as a query-level gate input (docs/feature_lab/F4).

Asset `query_embeddings`: .npz with `ids` and `vectors` [Q, 1024] for the development queries only. The PCA is
fit on every query in the file without labels; every page of a query gets the same 16 values.
"""
import numpy as np

from . import Variant

DIMS = 16


def query_table(path, dims=DIMS):
    """Label-free PCA over every query in the file; returns {query_id: [dims]}."""
    data = np.load(path)
    vectors = data['vectors'].astype(np.float64)
    centered = vectors-vectors.mean(axis=0)
    _, _, components = np.linalg.svd(centered, full_matrices=False)
    return dict(zip(data['ids'].tolist(), centered@components[:dims].T))


def query_features(path):
    table = query_table(path)

    def page_features(query_id, text, page_ids, raw):
        if query_id not in table:
            raise KeyError(f'query_embeddings has no vector for query {query_id}')
        return np.repeat(table[query_id][None], len(page_ids), axis=0)
    return page_features


def build(assets):
    return Variant('f4_qemb16', page_features=query_features(assets['query_embeddings']))
