"""F9 held-out checks (docs/feature_lab/F9_heldout_vidoseek.md, F9_heldout_vimdoc.md): the label-free pieces.

Test queries enter the lab as LabQuery rows with no positives, so nothing before the sealed opening can depend
on a label. Prediction files are written byte-deterministically, so their SHA-256 pins every final score.
ViDoSeek seals every page score; ViMDoc (4.2M candidate pages) seals each row's top-10 units, which fixes
nDCG@10 and Recall@1/@3 exactly.
"""
import csv
import gzip
import io
import json

import numpy as np

from .data import LabQuery, utf8_key
from .model import DISCOUNT, unit_max

ROWS = ('static', 'qarf', 'qpaf', 'f7_static_qwen4b', 'f9_qpaf_qwen4b')
RERANKED = {  # pre-registered base and λ: the best constant λ of the pooled out-of-fold dev table
    'vidoseek': {'f7_static_qwen4b': ('static', 0.8), 'f9_qpaf_qwen4b': ('qpaf', 0.9)},
    'vimdoc': {'f7_static_qwen4b': ('static', 0.8), 'f9_qpaf_qwen4b': ('qpaf', 0.5)},
}
RANKED = 10


def label_free_units_query(query_id, text, page_ids, raw, unit_of_page):
    """LabQuery with no positives, pages and units in the lab's UTF-8 order (as data.make_query)."""
    order = sorted(range(len(page_ids)), key=lambda i: utf8_key(page_ids[i]))
    pages = tuple(page_ids[i] for i in order)
    raw = np.asarray(raw, dtype=np.float64)[order]
    if len(set(pages)) != len(pages) or raw.shape != (len(pages), 3) or not np.isfinite(raw).all():
        raise ValueError(f'query {query_id}: need unique pages and finite [pages, 3] scores')
    unit_ids = tuple(sorted({unit_of_page[p] for p in pages}, key=utf8_key))
    index = {unit: i for i, unit in enumerate(unit_ids)}
    return LabQuery(query_id, text, pages, raw, np.array([index[unit_of_page[p]] for p in pages]), unit_ids,
                    np.zeros(len(unit_ids), dtype=bool), 0)


def label_free_query(record):
    """LabQuery of a label-free m24 QueryRecord, whose units are its pages."""
    return label_free_units_query(record.query_id, record.text, record.page_ids, record.raw_scores,
                                  {p: p for p in record.page_ids})


def recall_at(q, page_scores, k):
    """Share of the query's relevant units in its top-k units (Recall@k as in HEAVEN, Appendix C.3)."""
    units = unit_max(page_scores, q.units, len(q.unit_ids))
    top = np.argsort(-units, kind='stable')[:k]
    return float(q.positive[top].sum()/q.relevant_total)


def top_units(q, page_scores, k=RANKED):
    """The k best units as [unit_id, max page score], ranked like model.unit_ndcg (score desc, index asc)."""
    units = unit_max(page_scores, q.units, len(q.unit_ids))
    return [[q.unit_ids[i], float(units[i])] for i in np.argsort(-units, kind='stable')[:k]]


def ranking_metrics(ranked, relevant, relevant_total):
    """nDCG@10 and Recall@1/@3 from a top-10 unit list; equal to unit_ndcg and recall_at on the full scores."""
    hits = np.array([unit in relevant for unit in ranked[:RANKED]], dtype=float)
    ideal = DISCOUNT[:min(RANKED, relevant_total)].sum()
    return {'ndcg10': float((hits*DISCOUNT[:len(hits)]).sum()/ideal), 'recall1': float(hits[:1].sum()/relevant_total),
            'recall3': float(hits[:3].sum()/relevant_total)}


def predictions_bytes(queries, rows):
    """gzip CSV of query_id, page_id and one column per row, mtime 0 and round-trip floats, so equal scores hash equal."""
    text = io.StringIO(newline='')
    writer = csv.writer(text, lineterminator='\n')
    writer.writerow(['query_id', 'page_id', *ROWS])
    for r, q in enumerate(queries):
        for i, page_id in enumerate(q.page_ids):
            writer.writerow([q.query_id, page_id, *(format(float(rows[name][r][i]), '.17g') for name in ROWS)])
    return gzip_bytes(text.getvalue().encode('utf-8'))


def read_predictions(data, queries):
    """Rows of a predictions_bytes file as {row: [array aligned with q.page_ids]}; the page order must match."""
    lines = list(csv.reader(io.StringIO(gzip.decompress(data).decode('utf-8'), newline='')))
    if lines[0] != ['query_id', 'page_id', *ROWS]:
        raise ValueError('prediction columns differ')
    body, out, at = lines[1:], {name: [] for name in ROWS}, 0
    for q in queries:
        block = body[at:at+len(q.page_ids)]
        at += len(q.page_ids)
        if [(line[0], line[1]) for line in block] != [(q.query_id, p) for p in q.page_ids]:
            raise ValueError(f'query {q.query_id}: prediction pages differ')
        for j, name in enumerate(ROWS):
            out[name].append(np.array([float(line[2+j]) for line in block]))
    if at != len(body):
        raise ValueError('prediction file has extra rows')
    return out


def rankings_bytes(queries, rankings):
    """gzip JSON lines of each query's top-10 units per row ({row: [[unit_id, score], ...]}), mtime 0."""
    lines = [json.dumps({'query_id': q.query_id, **{name: rankings[name][r] for name in ROWS}})
             for r, q in enumerate(queries)]
    return gzip_bytes(('\n'.join([json.dumps({'rows': list(ROWS), 'top': RANKED}), *lines])+'\n').encode('utf-8'))


def read_rankings(data, queries):
    """Rows of a rankings_bytes file as {row: [ranked unit IDs per query]}; the query order must match."""
    header, *lines = gzip.decompress(data).decode('utf-8').rstrip('\n').split('\n')
    if json.loads(header) != {'rows': list(ROWS), 'top': RANKED} or len(lines) != len(queries):
        raise ValueError('ranking file header or length differs')
    out = {name: [] for name in ROWS}
    for q, line in zip(queries, lines):
        entry = json.loads(line)
        if entry['query_id'] != q.query_id:
            raise ValueError(f'ranking order differs at {q.query_id}')
        for name in ROWS:
            out[name].append([unit for unit, _ in entry[name]])
    return out


def gzip_bytes(data):
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='wb', mtime=0) as stream:
        stream.write(data)
    return out.getvalue()
