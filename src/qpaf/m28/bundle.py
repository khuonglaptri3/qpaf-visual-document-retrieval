"""Label-free candidate freeze, followed by a separate page-coverage audit.

Candidate construction accepts only complete retriever arrays and identifiers.
The raw trainer cache always contains the five ``qpaf_score_rows_v1`` fields.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import numbers
from pathlib import Path

import numpy as np


CHANNELS = ('bm25', 'dense', 'visual')
SCORE_COLUMNS = ('query_id', 'page_id', 'bm25_score', 'dense_score', 'visual_score')
NORMALIZATION_EPSILON = 1e-15
_ARTIFACT_ROWS = {
    'raw_scores.parquet': 'raw_rows',
    'normalized_scores.parquet': 'normalized_rows',
    'channel_top_lists.parquet': 'top_lists',
    'candidate_set.parquet': 'candidates',
}


def _ids(values, name):
    if (not isinstance(values, list) or not values or
            any(not isinstance(value, str) or not value or value != value.strip()
                or any(character in value for character in '\r\n\t') for value in values) or
            len(set(values)) != len(values)):
        raise ValueError(f'{name}: unique, nonempty, unpadded string IDs required')
    return values


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False)+'\n').encode('utf-8')


def _hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _validated_arrays(scores, query_ids, page_ids, top_k):
    _ids(query_ids, 'query_ids')
    _ids(page_ids, 'page_ids')
    if isinstance(top_k, (bool, np.bool_)) or not isinstance(top_k, numbers.Integral) or top_k < 1:
        raise ValueError('top_k must be a positive integer')
    if not isinstance(scores, dict) or set(scores) != set(CHANNELS):
        raise ValueError('Exactly the bm25, dense and visual full score arrays are required')
    arrays = {}
    for channel in CHANNELS:
        values = scores[channel]
        if (not isinstance(values, np.ndarray) or values.shape != (len(query_ids), len(page_ids))
                or values.dtype.kind not in 'fiu'):
            raise ValueError(f'{channel}: a real numeric query-by-page array is required')
        values = np.ascontiguousarray(values, dtype=np.float64)
        if not np.isfinite(values).all():
            raise ValueError(f'{channel}: every corpus score must be finite')
        arrays[channel] = values
    return arrays


def _normalize(values):
    low, high = float(np.min(values)), float(np.max(values))
    with np.errstate(over='ignore'):
        width = np.float64(high)-np.float64(low)
    if width <= NORMALIZATION_EPSILON:
        return np.zeros_like(values, dtype=np.float64)
    if not np.isfinite(width):
        # Retain finite float64 results even when finite extrema span > float64 max.
        scale = max(abs(low), abs(high))
        return (values/scale-low/scale)/(high/scale-low/scale)
    return (values-low)/width


def build_candidates(scores: dict[str, np.ndarray], query_ids: list[str],
                     page_ids: list[str], top_k: int = 200) -> dict:
    """Freeze each raw-score top-k union, without accepting or accessing labels.

    Query order follows ``query_ids``; candidates within each query are page-ID
    ascending. Each channel ranks by descending raw score, then ascending page ID.
    """
    arrays = _validated_arrays(scores, query_ids, page_ids, top_k)
    page_names = np.asarray(page_ids)
    depth = min(int(top_k), len(page_ids))
    raw_rows, normalized_rows, top_lists, candidates = [], [], [], []
    for query_index, query_id in enumerate(query_ids):
        union = set()
        for channel in CHANNELS:
            order = np.lexsort((page_names, -arrays[channel][query_index]))[:depth]
            union.update(int(index) for index in order)
            for rank, page_index in enumerate(order, 1):
                top_lists.append({'query_id': query_id, 'page_id': page_ids[page_index],
                                  'channel': channel, 'rank': rank,
                                  'raw_score': float(arrays[channel][query_index, page_index])})
        indices = sorted(union, key=page_ids.__getitem__)
        raw = np.column_stack([arrays[channel][query_index, indices] for channel in CHANNELS])
        normalized = np.column_stack([_normalize(raw[:, index]) for index in range(3)])
        for row_index, page_index in enumerate(indices):
            keys = {'query_id': query_id, 'page_id': page_ids[page_index]}
            candidates.append(dict(keys))
            raw_rows.append(dict(keys, **{f'{channel}_score': float(raw[row_index, index])
                                         for index, channel in enumerate(CHANNELS)}))
            normalized_rows.append(dict(keys, **{
                f'{channel}_score': float(normalized[row_index, index])
                for index, channel in enumerate(CHANNELS)}))
    return {
        'raw_rows': raw_rows, 'normalized_rows': normalized_rows,
        'top_lists': top_lists, 'candidates': candidates,
        'query_ids': list(query_ids), 'page_ids': list(page_ids),
        'query_ids_sha256': _hash_bytes(_json_bytes(query_ids)),
        'page_ids_sha256': _hash_bytes(_json_bytes(page_ids)),
        'score_arrays_sha256': {channel: _hash_bytes(memoryview(arrays[channel]).cast('B'))
                                for channel in CHANNELS},
        'counts': {'query_count': len(query_ids), 'page_count': len(page_ids),
                   'candidate_count': len(candidates), 'raw_row_count': len(raw_rows),
                   'normalized_row_count': len(normalized_rows),
                   'channel_top_list_count': len(top_lists), 'top_k': int(top_k),
                   'effective_top_k': depth},
    }


def _schemas():
    import pyarrow as pa
    keys = [pa.field(name, pa.string(), nullable=False) for name in SCORE_COLUMNS[:2]]
    scores = pa.schema(keys+[pa.field(name, pa.float64(), nullable=False)
                             for name in SCORE_COLUMNS[2:]])
    return {'raw_rows': scores, 'normalized_rows': scores,
            'top_lists': pa.schema(keys+[pa.field('channel', pa.string(), nullable=False),
                                        pa.field('rank', pa.int64(), nullable=False),
                                        pa.field('raw_score', pa.float64(), nullable=False)]),
            'candidates': pa.schema(keys)}


def _finite(value):
    return (isinstance(value, numbers.Real) and not isinstance(value, (bool, np.bool_))
            and math.isfinite(value))


def _bundle_tables(bundle):
    """Validate all in-memory contracts before creating any publication files."""
    import pyarrow as pa
    if not isinstance(bundle, dict):
        raise ValueError('A constructed candidate bundle is required')
    query_ids = _ids(bundle.get('query_ids'), 'query_ids')
    page_ids = _ids(bundle.get('page_ids'), 'page_ids')
    tables, rows_by_kind = {}, {}
    query_set, page_set = set(query_ids), set(page_ids)
    for kind, schema in _schemas().items():
        rows = bundle.get(kind)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f'{kind}: nonempty row list required')
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(schema.names):
                raise ValueError(f'{kind}: exact label-free schema required')
            if row['query_id'] not in query_set or row['page_id'] not in page_set:
                raise ValueError(f'{kind}: unknown query/page ID')
            for name in ('bm25_score', 'dense_score', 'visual_score', 'raw_score'):
                if name in row and not _finite(row[name]):
                    raise ValueError(f'{kind}: finite real scores required')
            if kind == 'top_lists' and (row['channel'] not in CHANNELS or
                    isinstance(row['rank'], (bool, np.bool_)) or
                    not isinstance(row['rank'], numbers.Integral) or row['rank'] < 1):
                raise ValueError('top_lists: valid channel and integer rank required')
        rows_by_kind[kind] = rows
        tables[kind] = pa.Table.from_pylist(rows, schema=schema)
    keys = [(row['query_id'], row['page_id']) for row in rows_by_kind['candidates']]
    query_order = {query_id: index for index, query_id in enumerate(query_ids)}
    if (len(keys) != len(set(keys)) or {q for q, _ in keys} != query_set or
            keys != sorted(keys, key=lambda key: (query_order[key[0]], key[1]))):
        raise ValueError('Candidates must cover all queries exactly once per sorted page')
    for kind in ('raw_rows', 'normalized_rows'):
        if [(row['query_id'], row['page_id']) for row in rows_by_kind[kind]] != keys:
            raise ValueError(f'{kind}: candidate keys/order mismatch')
    counts = bundle.get('counts')
    top_k = counts.get('top_k') if isinstance(counts, dict) else None
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError('Bundle needs a positive top_k')
    depth = min(top_k, len(page_ids))
    expected_counts = {'query_count': len(query_ids), 'page_count': len(page_ids),
                       'candidate_count': len(keys), 'raw_row_count': len(keys),
                       'normalized_row_count': len(keys),
                       'channel_top_list_count': len(query_ids)*len(CHANNELS)*depth,
                       'top_k': top_k, 'effective_top_k': depth}
    if counts != expected_counts:
        raise ValueError('Bundle counts do not match its rows')
    expected_tops = []
    top_union = set()
    raw_by_query = {query_id: [] for query_id in query_ids}
    normalized_by_query = {query_id: [] for query_id in query_ids}
    for raw, normalized in zip(rows_by_kind['raw_rows'], rows_by_kind['normalized_rows']):
        raw_by_query[raw['query_id']].append(raw)
        normalized_by_query[normalized['query_id']].append(normalized)
    for query_id in query_ids:
        raw = raw_by_query[query_id]
        if not depth <= len(raw) <= len(CHANNELS)*depth:
            raise ValueError('Query candidate count is incompatible with channel depth')
        for channel in CHANNELS:
            channel_rows = sorted(raw, key=lambda row: (-row[f'{channel}_score'], row['page_id']))[:depth]
            for rank, row in enumerate(channel_rows, 1):
                expected_tops.append({'query_id': query_id, 'page_id': row['page_id'],
                                      'channel': channel, 'rank': rank,
                                      'raw_score': row[f'{channel}_score']})
                top_union.add((query_id, row['page_id']))
            normalized = _normalize(np.asarray([row[f'{channel}_score'] for row in raw],
                                               dtype=np.float64))
            if any(row[f'{channel}_score'] != float(value) for row, value in
                   zip(normalized_by_query[query_id], normalized)):
                raise ValueError('Union min-max normalization mismatch')
    if rows_by_kind['top_lists'] != expected_tops or top_union != set(keys):
        raise ValueError('Channel top lists do not exactly produce the candidate union')
    for name, values in (('query_ids', query_ids), ('page_ids', page_ids)):
        if bundle.get(name+'_sha256') != _hash_bytes(_json_bytes(values)):
            raise ValueError(f'{name}: identity hash mismatch')
    hashes = bundle.get('score_arrays_sha256')
    if (not isinstance(hashes, dict) or set(hashes) != set(CHANNELS) or
            any(not isinstance(value, str) or len(value) != 64 or
                any(character not in '0123456789abcdef' for character in value)
                for value in hashes.values())):
        raise ValueError('Full score-array hashes are required')
    return tables


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def freeze_candidates(output: Path, bundle: dict, provenance: dict) -> dict:
    """Create the four immutable Parquet artifacts, then their freeze manifest.

    An existing artifact or partial publication causes failure; nothing is ever
    overwritten. The caller may open relevance only after this returns.
    """
    import pyarrow.parquet as pq
    tables = _bundle_tables(bundle)
    if not isinstance(provenance, dict):
        raise ValueError('Provenance must be a JSON object')
    try:
        provenance = json.loads(_json_bytes(provenance))
    except (TypeError, ValueError) as exc:
        raise ValueError('Provenance must contain finite JSON values') from exc
    output = Path(output)
    paths = [output/name for name in (*_ARTIFACT_ROWS, 'candidate_freeze.json')]
    if any(path.exists() for path in paths):
        raise FileExistsError('Candidate publication is create-once; an artifact already exists')
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for filename, kind in _ARTIFACT_ROWS.items():
        path, table = output/filename, tables[kind]
        with path.open('xb') as handle:
            pq.write_table(table, handle, compression='zstd', use_dictionary=False,
                           version='2.6', data_page_version='1.0')
        artifacts[filename] = {'sha256': _file_sha256(path), 'size_bytes': path.stat().st_size,
                               'row_count': table.num_rows, 'columns': table.column_names}
    manifest = {
        'schema_version': 'qpaf_m28_candidate_freeze_v1', 'status': 'FROZEN',
        'score_row_schema': 'qpaf_score_rows_v1', 'evaluation_unit': 'page',
        'created_utc': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
        'counts': dict(bundle['counts']), 'artifacts': artifacts, 'provenance': provenance,
        'query_ids_sha256': bundle['query_ids_sha256'], 'page_ids_sha256': bundle['page_ids_sha256'],
        'score_arrays_sha256': dict(bundle['score_arrays_sha256']),
        'normalization': {'method': 'query_union_min_max_float64',
                          'constant_range_epsilon': NORMALIZATION_EPSILON},
        'ordering': {'queries': 'input_query_ids', 'candidates': 'page_id_ascending',
                     'channel_top_lists': 'raw_score_descending_page_id_ascending'},
    }
    with (output/'candidate_freeze.json').open('xb') as handle:
        handle.write(_json_bytes(manifest))
    return manifest


def verify_candidates(output: Path, scores: dict, qids: list[str], pids: list[str],
                      top_k: int = 200) -> dict:
    """Replay every candidate, rank and normalized value against complete arrays."""
    import pyarrow.parquet as pq
    output = Path(output)
    manifest_path = output/'candidate_freeze.json'
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, ValueError) as exc:
        raise ValueError('Missing or invalid candidate freeze manifest') from exc
    expected = build_candidates(scores, qids, pids, top_k=top_k)
    tables = _bundle_tables(expected)
    if (not isinstance(manifest, dict) or
            manifest.get('schema_version') != 'qpaf_m28_candidate_freeze_v1' or
            manifest.get('status') != 'FROZEN' or
            manifest.get('score_row_schema') != 'qpaf_score_rows_v1' or
            manifest.get('evaluation_unit') != 'page' or
            manifest.get('normalization') != {'method': 'query_union_min_max_float64',
                                              'constant_range_epsilon': NORMALIZATION_EPSILON}):
        raise ValueError('Unsupported candidate freeze contract')
    for name in ('counts', 'query_ids_sha256', 'page_ids_sha256', 'score_arrays_sha256'):
        if manifest.get(name) != expected[name]:
            raise ValueError(f'Candidate freeze {name} differs from complete score arrays')
    if not isinstance(manifest.get('provenance'), dict):
        raise ValueError('Invalid freeze provenance')
    try:
        _json_bytes(manifest['provenance'])
        created = datetime.fromisoformat(manifest['created_utc'].replace('Z', '+00:00'))
        if created.utcoffset() != timezone.utc.utcoffset(created):
            raise ValueError('Freeze time must use UTC')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError('Invalid freeze metadata') from exc
    artifacts = manifest.get('artifacts')
    if not isinstance(artifacts, dict) or set(artifacts) != set(_ARTIFACT_ROWS):
        raise ValueError('Candidate freeze must list exactly four artifacts')
    for filename, kind in _ARTIFACT_ROWS.items():
        path, expected_table = output/filename, tables[kind]
        record = artifacts[filename]
        if not isinstance(record, dict):
            raise ValueError(f'{filename}: invalid artifact record')
        try:
            if path.stat().st_size != record.get('size_bytes') or _file_sha256(path) != record.get('sha256'):
                raise ValueError(f'{filename}: artifact size/hash mismatch')
            actual = pq.read_table(path)
        except OSError as exc:
            raise ValueError(f'{filename}: missing or unreadable artifact') from exc
        if (record.get('row_count') != expected_table.num_rows or
                record.get('columns') != expected_table.column_names or
                not actual.schema.equals(expected_table.schema, check_metadata=True)):
            raise ValueError(f'{filename}: exact Parquet schema/count mismatch')
        if not actual.equals(expected_table, check_metadata=True):
            raise ValueError(f'{filename}: content differs from full-array replay')
    return {'status': 'PASS', 'evaluation_unit': 'page', 'counts': expected['counts'],
            'candidate_freeze_sha256': _hash_bytes(manifest_bytes),
            'artifacts': artifacts}


def _coverage_summary(rows):
    uncovered = [row['query_id'] for row in rows if row['captured_relevant'] == 0]
    macro = math.fsum(row['recall'] for row in rows)/len(rows) if rows else None
    return {'status': 'PASS' if not uncovered and (macro is None or macro >= 0.95) else 'BLOCKED',
            'query_count': len(rows), 'macro_recall': macro,
            'uncovered_query_ids': uncovered,
            'candidate_count': sum(row['candidate_count'] for row in rows),
            'relevant_total': sum(row['relevant_total'] for row in rows),
            'captured_relevant': sum(row['captured_relevant'] for row in rows)}


def audit_coverage(candidates: list[dict], qrels: dict, query_ids: list[str],
                   splits: dict[str, list[str]]) -> dict:
    """Audit page recall after freeze, retaining every requested query.

    The caller must publish ``candidate_freeze.json`` before loading ``qrels``.
    Every positive page in the supplied full qrels contributes to the denominator,
    including pages absent from the union. This computes no ranking metrics.
    """
    _ids(query_ids, 'query_ids')
    query_set = set(query_ids)
    if not isinstance(splits, dict) or set(splits) != {'train', 'validation', 'test'}:
        raise ValueError('Splits must define train, validation and test')
    owner = {}
    for role, ids in splits.items():
        if not isinstance(ids, list):
            raise ValueError(f'{role}: split IDs must be a list')
        if ids:
            _ids(ids, f'{role} split')
        for query_id in ids:
            if query_id not in query_set or query_id in owner:
                raise ValueError('Split IDs overlap or contain an unknown query')
            owner[query_id] = role
    if set(owner) != query_set:
        raise ValueError('Splits must cover every query; query dropping is forbidden')
    if not isinstance(qrels, dict) or set(qrels) != query_set:
        raise ValueError('Full qrels must cover exactly the requested query namespace')
    positives = {}
    for query_id in query_ids:
        judged = qrels[query_id]
        if not isinstance(judged, dict) or not all(_finite(value) for value in judged.values()):
            raise ValueError(f'{query_id}: page qrels must contain finite real relevance')
        if judged:
            _ids(list(judged), f'{query_id} qrels page IDs')
        positives[query_id] = {page for page, value in judged.items() if value >= 1}
    if not isinstance(candidates, list):
        raise ValueError('Candidates must be a list of query/page rows')
    grouped = {query_id: set() for query_id in query_ids}
    for row in candidates:
        if not isinstance(row, dict) or set(row) != {'query_id', 'page_id'}:
            raise ValueError('Candidate rows must contain exactly query_id and page_id')
        query_id, page_id = row['query_id'], row['page_id']
        if not isinstance(query_id, str) or query_id not in query_set:
            raise ValueError('Candidate has an unknown or invalid query ID')
        _ids([page_id], 'candidate page IDs')
        if page_id in grouped[query_id]:
            raise ValueError('Duplicate candidate key')
        grouped[query_id].add(page_id)
    per_query = []
    for query_id in query_ids:
        total = len(positives[query_id])
        captured = len(positives[query_id] & grouped[query_id])
        per_query.append({'query_id': query_id, 'candidate_count': len(grouped[query_id]),
                          'relevant_total': total, 'captured_relevant': captured,
                          'recall': captured/total if total else 0.0})
    result = _coverage_summary(per_query)
    result.update({'evaluation_unit': 'page', 'minimum_macro_recall': 0.95,
                   'require_zero_uncovered_queries': True, 'per_query': per_query,
                   'by_split': {role: _coverage_summary([row for row in per_query
                                                        if owner[row['query_id']] == role])
                                for role in splits}})
    return result
