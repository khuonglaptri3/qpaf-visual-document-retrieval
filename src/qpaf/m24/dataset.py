"""Score rows + qrels + split IDs -> validated per-query records and padded batches.

Score rows carry only frozen retriever scores. Labels come from a separate qrels
mapping and never reach feature construction, so a cache that also stores a
relevance column cannot leak it into the gate.
"""
from dataclasses import dataclass
import math
import numbers
from pathlib import Path

CHANNELS = ('bm25_score', 'dense_score', 'visual_score')
SCORE_COLUMNS = ('query_id', 'page_id', *CHANNELS)
ROLES = ('train', 'validation', 'test')


def _finite(value):
    # pandas yields numpy scalars; bool is an int subclass but never a score.
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)
SPLIT_FILES = {'train': 'train_ids.txt', 'validation': 'val_ids.txt', 'test': 'test_ids.txt'}


class DatasetError(ValueError):
    """Input data violates the M2.4 row/split/qrels contract."""


@dataclass(frozen=True)
class QueryRecord:
    query_id: str
    text: str
    page_ids: tuple
    raw_scores: tuple   # one (bm25, dense, visual) triple per candidate
    labels: tuple       # 0/1 per candidate, loss/metrics only
    relevant_total: int  # positives in qrels, including pages outside the candidate union


@dataclass(frozen=True)
class Batch:
    query_ids: list
    texts: list
    page_ids: list
    raw_scores: object  # torch [batch, candidates, 3]
    labels: object      # torch [batch, candidates]
    mask: object        # torch bool [batch, candidates]


def read_split_ids(directory):
    """Read M1.3-format ID files: one query ID per line, no blanks or duplicates."""
    splits = {}
    for role, name in SPLIT_FILES.items():
        lines = (Path(directory)/name).read_text(encoding='utf-8').splitlines()
        if any(not line.strip() or line != line.strip() for line in lines) or len(set(lines)) != len(lines):
            raise DatasetError(f'{name}: blank, padded or duplicate query IDs')
        splits[role] = lines
    return splits


def read_score_rows(path):
    """Load only the score columns from a parquet or CSV cache."""
    import pandas as pd
    path = Path(path)
    if path.suffix == '.parquet':
        frame = pd.read_parquet(path, columns=list(SCORE_COLUMNS))
    elif path.suffix == '.csv':
        frame = pd.read_csv(path, usecols=list(SCORE_COLUMNS), dtype={'query_id': str, 'page_id': str})
    else:
        raise DatasetError('Score rows must be .parquet or .csv')
    return frame.to_dict('records')


def build_records(rows, queries, qrels, splits, roles, *, positive_threshold=1, max_candidates=600):
    """Group rows by query for the requested roles; reject every contract violation.

    All split IDs are checked for disjointness, but rows/labels are materialized
    only for `roles`, so excluding 'test' keeps test labels unopened.
    """
    if set(splits) != set(ROLES) or any(role not in ROLES for role in roles) or not roles:
        raise DatasetError('Splits must define train/validation/test and roles must be a subset')
    owner = {}
    for role in ROLES:
        for query_id in splits[role]:
            if query_id in owner:
                raise DatasetError(f'Query {query_id} appears in both {owner[query_id]} and {role}')
            owner[query_id] = role
    grouped = {}
    for row in rows:
        query_id, page_id = row.get('query_id'), row.get('page_id')
        if not isinstance(query_id, str) or not isinstance(page_id, str) or not page_id.strip():
            raise DatasetError('Rows need string query_id and nonempty page_id')
        if query_id not in owner:
            raise DatasetError(f'Row query {query_id} is not in any split')
        if owner[query_id] not in roles:
            continue
        scores = tuple(row.get(channel) for channel in CHANNELS)
        if not all(_finite(value) for value in scores):
            raise DatasetError(f'Query {query_id} page {page_id}: three finite scores required')
        pages = grouped.setdefault(query_id, {})
        if page_id in pages:
            raise DatasetError(f'Query {query_id}: duplicate candidate page {page_id}')
        pages[page_id] = tuple(float(value) for value in scores)
    records = {role: [] for role in roles}
    for role in roles:
        for query_id in splits[role]:
            text, judged = queries.get(query_id), qrels.get(query_id)
            if not isinstance(text, str) or not text.strip():
                raise DatasetError(f'Query {query_id}: missing query text')
            if not isinstance(judged, dict) or not all(_finite(value) for value in judged.values()):
                raise DatasetError(f'Query {query_id}: qrels must map page IDs to finite relevance')
            positives = {page for page, value in judged.items() if value >= positive_threshold}
            if not positives:
                raise DatasetError(f'Query {query_id}: no relevant page in qrels')
            pages = grouped.get(query_id)
            if not pages:
                raise DatasetError(f'Query {query_id}: no candidate rows (uncovered query)')
            if len(pages) > max_candidates:
                raise DatasetError(f'Query {query_id}: {len(pages)} candidates exceed cap {max_candidates}')
            ordered = sorted(pages)
            records[role].append(QueryRecord(
                query_id, text, tuple(ordered), tuple(pages[page] for page in ordered),
                tuple(int(page in positives) for page in ordered), len(positives)))
    return records


def collate(records, dtype=None):
    """Pad records to the widest candidate list; padding is masked out."""
    import torch
    if not records:
        raise DatasetError('Cannot collate an empty batch')
    dtype = dtype or torch.float64
    width = max(len(record.page_ids) for record in records)
    raw = torch.zeros((len(records), width, 3), dtype=dtype)
    labels = torch.zeros((len(records), width), dtype=dtype)
    mask = torch.zeros((len(records), width), dtype=torch.bool)
    page_ids = []
    for index, record in enumerate(records):
        count = len(record.page_ids)
        raw[index, :count] = torch.tensor(record.raw_scores, dtype=dtype)
        labels[index, :count] = torch.tensor(record.labels, dtype=dtype)
        mask[index, :count] = True
        page_ids.append([*record.page_ids, *[''] * (width-count)])
    return Batch([r.query_id for r in records], [r.text for r in records], page_ids, raw, labels, mask)


def iter_batches(records, batch_size, generator=None):
    """Fixed order without a generator; seeded permutation with one."""
    import torch
    order = (torch.randperm(len(records), generator=generator).tolist() if generator is not None
             else list(range(len(records))))
    for start in range(0, len(order), batch_size):
        yield collate([records[index] for index in order[start:start+batch_size]])
