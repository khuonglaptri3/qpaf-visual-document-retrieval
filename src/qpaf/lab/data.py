"""Feature-lab inputs: one record per development query, label units and cross-validation folds.

Only the train and validation roles are loaded; test (ViDoSeek) and confirmation (ViMDoc) labels are
never read. A unit is what qrels label: the document on ViMDoc, the page itself on ViDoSeek. Labels
live in `positive`/`relevant_total` and never reach a variant's feature hook (see variants.Variant).
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

DATASETS = ('vimdoc', 'vidoseek')
DEV_ROLES = ('train', 'validation')
VIMDOC_SPLITS = 'evidence/revisions/m4.1-001'
FOLDS = 5


class LabDataError(ValueError):
    """An input file violates the feature-lab data contract."""


def require(ok, message):
    if not ok:
        raise LabDataError(message)


@dataclass(frozen=True)
class LabQuery:
    query_id: str
    text: str
    page_ids: tuple       # ascending UTF-8 page ID
    raw: np.ndarray       # [pages, 3] raw bm25/dense/visual scores
    units: np.ndarray     # [pages] index into unit_ids
    unit_ids: tuple       # ascending unit ID; ties in ranking go to the smaller index
    positive: np.ndarray  # [units] bool, loss and metrics only
    relevant_total: int   # relevant units in qrels, including units outside the candidate pool


def utf8_key(value):
    return value.encode('utf-8')


def make_query(query_id, text, page_ids, raw, unit_of_page, relevant_units, relevant_total):
    """Sort pages by UTF-8 ID and index their units; `relevant_units` may name units outside the pool."""
    require(isinstance(text, str) and text.strip(), f'query {query_id}: missing text')
    require(len(page_ids) == len(set(page_ids)) > 0, f'query {query_id}: empty or duplicate pages')
    order = sorted(range(len(page_ids)), key=lambda i: utf8_key(page_ids[i]))
    pages = tuple(page_ids[i] for i in order)
    raw = np.asarray(raw, dtype=np.float64)[order]
    require(raw.shape == (len(pages), 3) and np.isfinite(raw).all(), f'query {query_id}: need finite [pages, 3] scores')
    unit_ids = tuple(sorted({unit_of_page[p] for p in pages}, key=utf8_key))
    index = {unit: i for i, unit in enumerate(unit_ids)}
    relevant = set(relevant_units)
    require(relevant and relevant_total >= len(relevant & set(unit_ids)), f'query {query_id}: bad relevant units')
    return LabQuery(query_id, text, pages, raw, np.array([index[unit_of_page[p]] for p in pages]),
                    unit_ids, np.array([u in relevant for u in unit_ids]), int(relevant_total))


def fold_of(query_id, folds=FOLDS):
    """Label-free, order-free fold: SHA-256 of the query ID modulo the fold count."""
    return int(hashlib.sha256(query_id.encode('utf-8')).hexdigest(), 16) % folds


def load_vimdoc(root, data):
    """Dev pool from a Stage 1 cache dir: candidate_scores.parquet, queries.jsonl, dev_qrels.json."""
    import pyarrow.parquet as pq
    root, data = Path(root), Path(data)
    ids = [i for role in DEV_ROLES for i in (root/VIMDOC_SPLITS/f'{role}_ids.txt').read_text(encoding='utf-8').split()]
    dev = json.loads((data/'dev_qrels.json').read_text(encoding='utf-8'))
    qrels = {query_id: documents for role in DEV_ROLES for query_id, documents in dev[role].items()}
    require(set(qrels) == set(ids), 'dev qrels do not match the M4.1 train/validation IDs')
    texts = {}
    for line in (data/'queries.jsonl').read_text(encoding='utf-8').splitlines():
        query = json.loads(line)
        if query['query_id'] in qrels:
            texts[query['query_id']] = query['text']
    frame = pq.read_table(data/'candidate_scores.parquet',
                          columns=['query_id', 'page_id', 'document_id', 'bm25', 'dense', 'visual'],
                          filters=[('query_id', 'in', ids)]).to_pandas()
    queries = []
    for query_id, group in frame.groupby('query_id', sort=False):
        pages = list(group['page_id'])
        queries.append(make_query(query_id, texts.get(query_id), pages, group[['bm25', 'dense', 'visual']].to_numpy(),
                                  dict(zip(pages, group['document_id'])), qrels[query_id], len(set(qrels[query_id]))))
    require({q.query_id for q in queries} == set(ids), 'candidate rows do not cover every dev query')
    return sorted(queries, key=lambda q: utf8_key(q.query_id))


def load_vidoseek(root, data):
    """Dev pool from an M2.8 bundle: raw_scores.parquet, queries.json, qrels_development.json, splits/.

    The bundle also holds qrels_test_sealed.json; it is never opened here.
    """
    from qpaf.m24.dataset import build_records, read_score_rows, read_split_ids
    data = Path(data)
    qrels = json.loads((data/'qrels_development.json').read_text(encoding='utf-8'))
    records = build_records(read_score_rows(data/'raw_scores.parquet'),
                            json.loads((data/'queries.json').read_text(encoding='utf-8')),
                            qrels, read_split_ids(data/'splits'), DEV_ROLES)
    queries = []
    for record in (r for role in DEV_ROLES for r in records[role]):
        pages = list(record.page_ids)
        relevant = {page for page, value in qrels[record.query_id].items() if value >= 1}
        queries.append(make_query(record.query_id, record.text, pages, record.raw_scores, {p: p for p in pages},
                                  relevant, record.relevant_total))
    return sorted(queries, key=lambda q: utf8_key(q.query_id))


def load(dataset, root, data):
    require(dataset in DATASETS, f'dataset must be one of {DATASETS}')
    return (load_vimdoc if dataset == 'vimdoc' else load_vidoseek)(root, data)
