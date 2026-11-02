"""F9 held-out check on ViDoSeek TEST-172 (docs/feature_lab/F9_heldout_vidoseek.md): the label-free pieces.

Test queries enter the lab as LabQuery rows with no positives, so nothing before the sealed opening can depend
on a label. The prediction file is written byte-deterministically, so its SHA-256 pins every final score.
"""
import csv
import gzip
import io

import numpy as np

from .data import LabQuery, utf8_key
from .model import unit_max

ROWS = ('static', 'qarf', 'qpaf', 'f7_static_qwen4b', 'f9_qpaf_qwen4b')
RERANKED = {'f7_static_qwen4b': ('static', 0.8), 'f9_qpaf_qwen4b': ('qpaf', 0.9)}  # pre-registered base and λ


def label_free_query(record):
    """LabQuery of a label-free m24 QueryRecord (page units): pages in the lab's UTF-8 order, no positives."""
    order = sorted(range(len(record.page_ids)), key=lambda i: utf8_key(record.page_ids[i]))
    pages = tuple(record.page_ids[i] for i in order)
    raw = np.asarray(record.raw_scores, dtype=np.float64)[order]
    if raw.shape != (len(pages), 3) or not np.isfinite(raw).all():
        raise ValueError(f'query {record.query_id}: need finite [pages, 3] scores')
    return LabQuery(record.query_id, record.text, pages, raw, np.arange(len(pages)), pages,
                    np.zeros(len(pages), dtype=bool), 0)


def recall_at(q, page_scores, k):
    """Share of the query's relevant units in its top-k units (Recall@k as in HEAVEN, Appendix C.3)."""
    units = unit_max(page_scores, q.units, len(q.unit_ids))
    top = np.argsort(-units, kind='stable')[:k]
    return float(q.positive[top].sum()/q.relevant_total)


def predictions_bytes(queries, rows):
    """gzip CSV of query_id, page_id and one column per row, mtime 0 and round-trip floats, so equal scores hash equal."""
    text = io.StringIO(newline='')
    writer = csv.writer(text, lineterminator='\n')
    writer.writerow(['query_id', 'page_id', *ROWS])
    for r, q in enumerate(queries):
        for i, page_id in enumerate(q.page_ids):
            writer.writerow([q.query_id, page_id, *(format(float(rows[name][r][i]), '.17g') for name in ROWS)])
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='wb', mtime=0) as stream:
        stream.write(text.getvalue().encode('utf-8'))
    return out.getvalue()


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
