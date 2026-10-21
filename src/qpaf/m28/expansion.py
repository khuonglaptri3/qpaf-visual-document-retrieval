"""QPAF-M1.5-A003: label-free top-document expansion of the M2.8 union.

The frozen top-k union ``C0`` is kept intact. Spare capacity under the
3 x top-k cap is filled with pages of the one document whose best page has
the highest full-corpus reciprocal-rank-fusion score. The builder accepts no
labels and never reads the content of query IDs, which embed source PDFs.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import numpy as np

from qpaf.m28 import bundle as base
from qpaf.m28.bundle import CHANNELS, NORMALIZATION_EPSILON


POLICY_ID = 'qpaf_m28_top_document_expansion_v1'
AMENDMENT_ID = 'QPAF-M1.5-A003'
RRF_K = 60
BASE_TOP_K = 200
EXPANSION_DOCUMENTS = 1
REASON = 'top_document_expansion'
FREEZE_SCHEMA = 'qpaf_m28_candidate_freeze_v2'
_PAGE_ID = re.compile(r'(.+)_page_(\d{4})')
_ARTIFACT_ROWS = {
    **base._ARTIFACT_ROWS,
    'candidate_expansion_log.parquet': 'expansion_log',
    'candidate_expansion_queries.parquet': 'query_summaries',
}


def document_ids(page_ids: list[str]) -> list[str]:
    """Map canonical M2.6 page IDs ``{document}_page_{NNNN}`` to documents."""
    documents = []
    for page_id in page_ids:
        match = _PAGE_ID.fullmatch(page_id) if isinstance(page_id, str) else None
        if match is None:
            raise ValueError(f'Non-canonical page ID: {page_id!r}')
        documents.append(match.group(1))
    return documents


def policy(top_k: int) -> dict:
    return {'policy_id': POLICY_ID, 'amendment_id': AMENDMENT_ID,
            'base_rule': 'raw_score_top_k_per_channel_union', 'top_k': top_k,
            'rrf_k': RRF_K, 'rrf_rank_scope': 'full_corpus',
            'rrf_sum_order': list(CHANNELS), 'rank_tie_break': 'page_id_ascending',
            'expansion_documents': EXPANSION_DOCUMENTS, 'document_score': 'max_page_rrf',
            'document_tie_break': 'document_id_ascending',
            'page_priority': 'rrf_descending_page_id_ascending',
            'max_candidates_per_query': len(CHANNELS)*top_k,
            'page_document_mapping': 'canonical_page_id_prefix',
            'uses_labels': False, 'reads_query_id_content': False}


def select_document(page_rrf: np.ndarray, documents: list[str]) -> str:
    """Pick the document with the highest best-page RRF; ties by document ID."""
    names = sorted(set(documents))
    codes = np.searchsorted(np.asarray(names), np.asarray(documents))
    best = np.full(len(names), -np.inf)
    np.maximum.at(best, codes, np.asarray(page_rrf, dtype=np.float64))
    return names[int(np.flatnonzero(best == best.max())[0])]


def _full_ranks(values: np.ndarray, page_names: np.ndarray) -> np.ndarray:
    order = np.lexsort((page_names, -values))
    ranks = np.empty(len(values), dtype=np.int64)
    ranks[order] = np.arange(1, len(values)+1)
    return ranks


def build_expanded_candidates(scores: dict[str, np.ndarray], query_ids: list[str],
                              page_ids: list[str], top_k: int = BASE_TOP_K) -> dict:
    """Freeze ``C0`` plus top-document pages, without accepting or reading labels.

    Query IDs are used only as row keys. Candidates within each query are
    page-ID ascending; ``top_lists`` are exactly the baseline channel lists.
    """
    documents = document_ids(page_ids)
    baseline = base.build_candidates(scores, query_ids, page_ids, top_k=top_k)
    arrays = base._validated_arrays(scores, query_ids, page_ids, top_k)
    page_names = np.asarray(page_ids)
    page_index = {page_id: index for index, page_id in enumerate(page_ids)}
    document_names = sorted(set(documents))
    codes = np.searchsorted(np.asarray(document_names), np.asarray(documents))
    depth = baseline['counts']['effective_top_k']
    cap = len(CHANNELS)*depth
    c0 = {query_id: set() for query_id in query_ids}
    for row in baseline['candidates']:
        c0[row['query_id']].add(page_index[row['page_id']])
    raw_rows, normalized_rows, candidates, log, summaries = [], [], [], [], []
    for query_index, query_id in enumerate(query_ids):
        rrf = np.zeros(len(page_ids), dtype=np.float64)
        for channel in CHANNELS:
            rrf = rrf+1.0/(RRF_K+_full_ranks(arrays[channel][query_index], page_names))
        selected = select_document(rrf, documents)
        selected_code = document_names.index(selected)
        members = np.flatnonzero(codes == selected_code)
        missing = sorted((int(i) for i in members if int(i) not in c0[query_id]),
                         key=lambda i: (-rrf[i], page_ids[i]))
        added = missing[:max(cap-len(c0[query_id]), 0)]
        for priority, index in enumerate(added, 1):
            log.append({'query_id': query_id, 'page_id': page_ids[index],
                        'document_id': selected, 'priority': priority,
                        'rrf_score': float(rrf[index]), 'reason': REASON})
        indices = sorted(c0[query_id] | set(added), key=page_ids.__getitem__)
        summaries.append({'query_id': query_id, 'selected_document_id': selected,
                          'selected_document_rrf': float(rrf[members].max()),
                          'base_count': len(c0[query_id]), 'added_count': len(added),
                          'final_count': len(indices)})
        raw = np.column_stack([arrays[channel][query_index, indices] for channel in CHANNELS])
        normalized = np.column_stack([base._normalize(raw[:, index]) for index in range(3)])
        for row_index, index in enumerate(indices):
            keys = {'query_id': query_id, 'page_id': page_ids[index]}
            candidates.append(dict(keys))
            raw_rows.append(dict(keys, **{f'{channel}_score': float(raw[row_index, column])
                                         for column, channel in enumerate(CHANNELS)}))
            normalized_rows.append(dict(keys, **{f'{channel}_score': float(normalized[row_index, column])
                                                for column, channel in enumerate(CHANNELS)}))
    counts = dict(baseline['counts'], candidate_count=len(candidates),
                  raw_row_count=len(raw_rows), normalized_row_count=len(normalized_rows),
                  document_count=len(document_names),
                  base_candidate_count=baseline['counts']['candidate_count'],
                  added_page_count=len(log), expansion_log_count=len(log),
                  queries_with_additions=sum(1 for row in summaries if row['added_count']),
                  max_candidates_per_query=cap)
    return {
        'raw_rows': raw_rows, 'normalized_rows': normalized_rows,
        'top_lists': baseline['top_lists'], 'candidates': candidates,
        'expansion_log': log, 'query_summaries': summaries,
        'query_ids': list(query_ids), 'page_ids': list(page_ids),
        'query_ids_sha256': baseline['query_ids_sha256'],
        'page_ids_sha256': baseline['page_ids_sha256'],
        'score_arrays_sha256': baseline['score_arrays_sha256'],
        'policy': policy(int(top_k)), 'counts': counts,
    }


def _schemas():
    import pyarrow as pa
    text = lambda name: pa.field(name, pa.string(), nullable=False)
    integer = lambda name: pa.field(name, pa.int64(), nullable=False)
    real = lambda name: pa.field(name, pa.float64(), nullable=False)
    return {**base._schemas(),
            'expansion_log': pa.schema([text('query_id'), text('page_id'), text('document_id'),
                                        integer('priority'), real('rrf_score'), text('reason')]),
            'query_summaries': pa.schema([text('query_id'), text('selected_document_id'),
                                          real('selected_document_rrf'), integer('base_count'),
                                          integer('added_count'), integer('final_count')])}


def _expanded_tables(bundle):
    """Check structural A003 invariants in memory before any file is created."""
    import pyarrow as pa
    if not isinstance(bundle, dict):
        raise ValueError('A constructed expansion bundle is required')
    query_ids = base._ids(bundle.get('query_ids'), 'query_ids')
    page_ids = base._ids(bundle.get('page_ids'), 'page_ids')
    documents = dict(zip(page_ids, document_ids(page_ids)))
    counts = bundle.get('counts')
    top_k = counts.get('top_k') if isinstance(counts, dict) else None
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError('Bundle needs a positive top_k')
    if bundle.get('policy') != policy(top_k):
        raise ValueError('Bundle policy differs from QPAF-M1.5-A003')
    tables = {}
    for kind, schema in _schemas().items():
        rows = bundle.get(kind)
        if not isinstance(rows, list) or (not rows and kind != 'expansion_log'):
            raise ValueError(f'{kind}: row list required')
        if any(not isinstance(row, dict) or list(row) != schema.names for row in rows):
            raise ValueError(f'{kind}: exact label-free schema required')
        tables[kind] = pa.Table.from_pylist(rows, schema=schema)
    query_order = {query_id: index for index, query_id in enumerate(query_ids)}
    keys = [(row['query_id'], row['page_id']) for row in bundle['candidates']]
    if (len(keys) != len(set(keys)) or {q for q, _ in keys} != set(query_ids)
            or any(q not in query_order or p not in documents for q, p in keys)
            or keys != sorted(keys, key=lambda key: (query_order[key[0]], key[1]))):
        raise ValueError('Candidates must cover all queries exactly once per sorted page')
    for kind in ('raw_rows', 'normalized_rows'):
        if [(row['query_id'], row['page_id']) for row in bundle[kind]] != keys:
            raise ValueError(f'{kind}: candidate keys/order mismatch')
        if any(not base._finite(row[f'{c}_score']) for row in bundle[kind] for c in CHANNELS):
            raise ValueError(f'{kind}: finite real scores required')
    top_union = {(row['query_id'], row['page_id']) for row in bundle['top_lists']}
    added = [(row['query_id'], row['page_id']) for row in bundle['expansion_log']]
    if (top_union & set(added) or len(added) != len(set(added))
            or top_union | set(added) != set(keys)
            or any(row['reason'] != REASON or documents[row['page_id']] != row['document_id']
                   for row in bundle['expansion_log'])):
        raise ValueError('Candidates must be exactly the baseline union plus logged pages')
    per_query = {query_id: 0 for query_id in query_ids}
    for query_id, _ in keys:
        per_query[query_id] += 1
    cap = len(CHANNELS)*min(top_k, len(page_ids))
    summaries = bundle['query_summaries']
    if ([row['query_id'] for row in summaries] != query_ids
            or any(row['final_count'] != per_query[row['query_id']]
                   or row['base_count']+row['added_count'] != row['final_count']
                   or row['final_count'] > cap for row in summaries)):
        raise ValueError('Per-query summaries or the candidate cap do not match the rows')
    for name, values in (('query_ids', query_ids), ('page_ids', page_ids)):
        if bundle.get(name+'_sha256') != base._hash_bytes(base._json_bytes(values)):
            raise ValueError(f'{name}: identity hash mismatch')
    return tables


def freeze_expanded_candidates(output: Path, bundle: dict, provenance: dict) -> dict:
    """Create the six immutable Parquet artifacts, then their freeze manifest."""
    import pyarrow.parquet as pq
    tables = _expanded_tables(bundle)
    if not isinstance(provenance, dict):
        raise ValueError('Provenance must be a JSON object')
    try:
        provenance = json.loads(base._json_bytes(provenance))
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
        artifacts[filename] = {'sha256': base._file_sha256(path), 'size_bytes': path.stat().st_size,
                               'row_count': table.num_rows, 'columns': table.column_names}
    manifest = {
        'schema_version': FREEZE_SCHEMA, 'status': 'FROZEN',
        'score_row_schema': 'qpaf_score_rows_v1', 'evaluation_unit': 'page',
        'created_utc': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
        'policy': dict(bundle['policy']), 'counts': dict(bundle['counts']),
        'artifacts': artifacts, 'provenance': provenance,
        'query_ids_sha256': bundle['query_ids_sha256'], 'page_ids_sha256': bundle['page_ids_sha256'],
        'score_arrays_sha256': dict(bundle['score_arrays_sha256']),
        'normalization': {'method': 'query_union_min_max_float64',
                          'constant_range_epsilon': NORMALIZATION_EPSILON},
        'ordering': {'queries': 'input_query_ids', 'candidates': 'page_id_ascending',
                     'channel_top_lists': 'raw_score_descending_page_id_ascending',
                     'expansion_log': 'input_query_ids_then_priority'},
    }
    with (output/'candidate_freeze.json').open('xb') as handle:
        handle.write(base._json_bytes(manifest))
    return manifest


def verify_expanded_candidates(output: Path, scores: dict, qids: list[str], pids: list[str],
                               top_k: int = BASE_TOP_K) -> dict:
    """Replay every candidate, addition, rank and normalized value from full arrays."""
    import pyarrow.parquet as pq
    output = Path(output)
    try:
        manifest_bytes = (output/'candidate_freeze.json').read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, ValueError) as exc:
        raise ValueError('Missing or invalid candidate freeze manifest') from exc
    expected = build_expanded_candidates(scores, qids, pids, top_k=top_k)
    tables = _expanded_tables(expected)
    if (not isinstance(manifest, dict) or manifest.get('schema_version') != FREEZE_SCHEMA
            or manifest.get('status') != 'FROZEN'
            or manifest.get('score_row_schema') != 'qpaf_score_rows_v1'
            or manifest.get('evaluation_unit') != 'page'
            or manifest.get('normalization') != {'method': 'query_union_min_max_float64',
                                                 'constant_range_epsilon': NORMALIZATION_EPSILON}):
        raise ValueError('Unsupported candidate freeze contract')
    for name in ('policy', 'counts', 'query_ids_sha256', 'page_ids_sha256', 'score_arrays_sha256'):
        if manifest.get(name) != expected[name]:
            raise ValueError(f'Candidate freeze {name} differs from complete score arrays')
    try:
        base._json_bytes(manifest['provenance'])
        created = datetime.fromisoformat(manifest['created_utc'].replace('Z', '+00:00'))
        if created.utcoffset() != timezone.utc.utcoffset(created):
            raise ValueError('Freeze time must use UTC')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError('Invalid freeze metadata') from exc
    artifacts = manifest.get('artifacts')
    if not isinstance(artifacts, dict) or set(artifacts) != set(_ARTIFACT_ROWS):
        raise ValueError('Candidate freeze must list exactly six artifacts')
    for filename, kind in _ARTIFACT_ROWS.items():
        path, expected_table, record = output/filename, tables[kind], artifacts[filename]
        if not isinstance(record, dict):
            raise ValueError(f'{filename}: invalid artifact record')
        try:
            if path.stat().st_size != record.get('size_bytes') or base._file_sha256(path) != record.get('sha256'):
                raise ValueError(f'{filename}: artifact size/hash mismatch')
            actual = pq.read_table(path)
        except OSError as exc:
            raise ValueError(f'{filename}: missing or unreadable artifact') from exc
        if (record.get('row_count') != expected_table.num_rows
                or record.get('columns') != expected_table.column_names
                or not actual.schema.equals(expected_table.schema, check_metadata=True)):
            raise ValueError(f'{filename}: exact Parquet schema/count mismatch')
        if not actual.equals(expected_table, check_metadata=True):
            raise ValueError(f'{filename}: content differs from full-array replay')
    return {'status': 'PASS', 'evaluation_unit': 'page', 'policy_id': POLICY_ID,
            'counts': expected['counts'],
            'candidate_freeze_sha256': base._hash_bytes(manifest_bytes), 'artifacts': artifacts}
