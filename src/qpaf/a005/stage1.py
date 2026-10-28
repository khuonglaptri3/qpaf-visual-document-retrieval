"""A005 Stage 1 pure helpers: page shards, qrels split and sealing, score-matrix assembly.

Kept free of Modal and model imports so they can be tested locally. Page order
is the A007 v2 canonical order (ascending UTF-8 page ID); shard s holds the
pages whose canonical index i satisfies i % shards == s.
"""
import hashlib
import json

import numpy as np

from .candidates import CHANNELS, document_recall, query_candidates

MIN_MACRO_RECALL = 0.95


def shard_pages(pages, shards, shard):
    return [page for index, page in enumerate(pages) if index % shards == shard]


def shard_positions(total, shards, shard):
    """Canonical indices held by one shard, in shard order."""
    return np.arange(shard, total, shards)


def assemble_channel(total, shards, blocks):
    """Rebuild [queries, total] from per-shard [queries, shard_size] blocks."""
    queries = blocks[0].shape[0]
    out = np.empty((queries, total), dtype=np.float64)
    for shard, block in enumerate(blocks):
        positions = shard_positions(total, shards, shard)
        if block.shape != (queries, positions.size):
            raise ValueError(f'shard {shard} block shape {block.shape} != {(queries, positions.size)}')
        out[:, positions] = block
    if not np.isfinite(out).all():
        raise ValueError('assembled scores contain non-finite values')
    return out


def stem_document(stem):
    document, sep, number = stem.rpartition('_')
    if not sep or not document or not number:
        raise ValueError(f'malformed relevant page stem: {stem!r}')
    return document


def split_qrels(rows, split_ids):
    """Map each query's doc_ids (page stems) to sorted documents, split by the M4.1 ID sets.

    Returns {role: {query_id: [documents]}}; every query must have at least one document.
    """
    roles = {query_id: role for role, ids in split_ids.items() for query_id in ids}
    out = {role: {} for role in split_ids}
    for query_id, doc_ids in rows:
        role = roles.get(query_id)
        if role is None:
            raise ValueError(f'query {query_id!r} is in no M4.1 split')
        documents = sorted({stem_document(stem) for stem in doc_ids})
        if not documents:
            raise ValueError(f'query {query_id!r} has no relevant document')
        out[role][query_id] = documents
    for role, ids in split_ids.items():
        if set(out[role]) != set(ids):
            raise ValueError(f'{role}: qrels do not cover the sealed IDs exactly')
    return out


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode('utf-8')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def candidate_rows(query_ids, page_ids, documents, matrices):
    """Yield (query_id, union indices, raw [n,3], normalized [n,3]) per query; no labels involved."""
    if tuple(matrices) != CHANNELS:
        raise ValueError(f'channels must be {CHANNELS}')
    for row, query_id in enumerate(query_ids):
        union, raw, normalized = query_candidates({c: matrices[c][row] for c in CHANNELS})
        yield query_id, union, raw, normalized


def coverage(union_by_query, page_ids, documents_of_page, qrels):
    """Macro relevant-document recall over the queries in qrels and the queries with no relevant candidate."""
    recalls, missing = [], []
    for query_id, relevant in qrels.items():
        pages = [page_ids[i] for i in union_by_query[query_id]]
        value = document_recall(pages, relevant, documents_of_page.__getitem__)
        recalls.append(value)
        if value == 0:
            missing.append(query_id)
    macro = sum(recalls)/len(recalls)
    return {'queries': len(recalls), 'macro_document_recall': macro, 'queries_without_positive': len(missing),
            'pass': macro >= MIN_MACRO_RECALL and not missing}
