"""R7 rules that need no corpus: label-free test records, the prediction seal, the single opening of the
sealed qrels, per-seed contrasts and the approval check.

Order is the contract: test predictions are written and hashed before the sealed qrels are read, and the
metrics are computed from the sealed prediction file, never from the in-memory scores.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from qpaf.m24.dataset import CHANNELS, ROLES, QueryRecord, _finite

SEEDS = (20260820, 20260821, 20260822)
BASELINES = ('bm25', 'bge_m3', 'colqwen25', 'uniform_combsum', 'rrf_k60', 'train_fitted_static', 'learned_qarf')
LEARNED = tuple(f'{method.lower()}_{seed}' for method in ('QARF', 'QPAF') for seed in SEEDS)
COLUMNS = (*BASELINES, *LEARNED)
SCOPE = ['R7-00', 'R7-01', 'R7-02', 'R7-03', 'R7-04', 'R7-05']
PERMISSIONS = {'device': 'cpu', 'modal': False, 'gpu': False, 'training': False, 'retriever_inference': False,
               'test_labels': 'ViDoSeek test 172 sealed qrels, deserialized once, only in R7-05',
               'vimdoc': False, 'network': False}
LIMITS = {'wall_time_seconds': 3600, 'invocations': 1, 'automatic_retries': 0}
RUN_ID = re.compile(r'RUN-QPAF-R7-TEST-001-\d{8}T\d{6}Z-A\d{2}')
TEST_QUERY_COUNT = 172


class SealedError(ValueError):
    """An R7 input, ordering or authorization rule is broken."""


def require(ok, message):
    if not ok:
        raise SealedError(message)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def label_free_records(rows, queries, splits, *, max_candidates=600):
    """Test records in build_records order with zero labels; no qrels are needed or read."""
    require(set(splits) == set(ROLES), 'splits must define train/validation/test')
    owner = {query_id: role for role in ROLES for query_id in splits[role]}
    require(len(owner) == sum(len(ids) for ids in splits.values()), 'split IDs overlap')
    grouped = {}
    for row in rows:
        query_id, page_id = row.get('query_id'), row.get('page_id')
        require(isinstance(query_id, str) and isinstance(page_id, str) and page_id.strip(),
                'rows need string query_id and nonempty page_id')
        require(query_id in owner, f'row query {query_id} is not in any split')
        if owner[query_id] != 'test':
            continue
        scores = tuple(row.get(channel) for channel in CHANNELS)
        require(all(_finite(v) for v in scores), f'query {query_id} page {page_id}: three finite scores required')
        pages = grouped.setdefault(query_id, {})
        require(page_id not in pages, f'query {query_id}: duplicate candidate page {page_id}')
        pages[page_id] = tuple(float(v) for v in scores)
    records = []
    for query_id in splits['test']:
        text, pages = queries.get(query_id), grouped.get(query_id)
        require(isinstance(text, str) and text.strip(), f'query {query_id}: missing query text')
        require(pages, f'query {query_id}: no candidate rows')
        require(len(pages) <= max_candidates, f'query {query_id}: {len(pages)} candidates exceed {max_candidates}')
        ordered = sorted(pages)
        records.append(QueryRecord(query_id, text, tuple(ordered), tuple(pages[p] for p in ordered),
                                   (0,)*len(ordered), 0))
    return records


def same_candidates(label_free, labeled):
    """The labeled records must be the label-free ones plus labels, nothing else."""
    require([(r.query_id, r.page_ids, r.raw_scores) for r in label_free] ==
            [(r.query_id, r.page_ids, r.raw_scores) for r in labeled], 'labeled test candidates differ')


def write_seal(output, predictions_name):
    """Hash the written prediction file before any label exists in the process."""
    path = Path(output)/predictions_name
    data = path.read_bytes()
    seal = {'file': predictions_name, 'sha256': sha_bytes(data), 'size_bytes': len(data),
            'sealed_utc': now(), 'sealed_qrels_deserialized': False}
    with (Path(output)/'prediction_seal.json').open('x', encoding='utf8', newline='\n') as stream:
        json.dump(seal, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return seal


def check_seal(output):
    """Refuse to open labels unless the seal exists and still matches the prediction bytes."""
    path = Path(output)/'prediction_seal.json'
    require(path.is_file(), 'test predictions are not sealed')
    seal = json.loads(path.read_text(encoding='utf8'))
    require(not seal['sealed_qrels_deserialized'], 'seal was written after labels were read')
    require(sha_bytes((Path(output)/seal['file']).read_bytes()) == seal['sha256'],
            'sealed test predictions changed')
    return seal


def open_sealed_qrels(path, expected_sha256, test_ids):
    """The one read of the sealed test labels: pinned bytes, exactly the 172 test IDs."""
    data = Path(path).read_bytes()
    require(sha_bytes(data) == expected_sha256, 'sealed test qrels hash differs')
    qrels = json.loads(data.decode('utf8'))
    require(isinstance(qrels, dict) and set(qrels) == set(test_ids) and len(test_ids) == TEST_QUERY_COUNT,
            'sealed qrels do not cover exactly the 172 test IDs')
    return qrels


def contrasts(per_query):
    """Per seed: QPAF minus matched QARF, and QPAF minus train_fitted_static (frozen_protocol.md §5)."""
    result = {}
    for seed in SEEDS:
        for name, other in ((f'qpaf_{seed}-qarf_{seed}', f'qarf_{seed}'),
                            (f'qpaf_{seed}-train_fitted_static', 'train_fitted_static')):
            mine, theirs = per_query[f'qpaf_{seed}'], per_query[other]
            require([r['query_id'] for r in mine] == [r['query_id'] for r in theirs], f'{name}: rows not paired')
            result[name] = [{'query_id': a['query_id'],
                             **{'delta_'+k: a[k]-b[k] for k in ('ndcg_at_10', 'recall_at_1', 'recall_at_3',
                                                                 'mrr_at_10')}}
                            for a, b in zip(mine, theirs)]
    return result


def check_approval(auth, *, run_id, clean, source_hashes, runtime, output_exists):
    """Pure checks; the approval text must be the Research Lead's recorded words."""
    require(auth.get('status') == 'APPROVED', 'R7 authorization is not APPROVED')
    require(auth.get('task_id') == 'TEST-172' and auth.get('roster_id') == 'R7', 'not the R7 authorization')
    require(RUN_ID.fullmatch(run_id or '') and auth.get('run_id') == run_id, 'run ID differs from authorization')
    require(auth.get('scope') == SCOPE, 'R7 scope differs')
    require(auth.get('permissions') == PERMISSIONS, 'R7 permissions differ')
    require(auth.get('limits') == LIMITS, 'only one bounded invocation without retries is authorized')
    approval = auth.get('approval') or {}
    require(all(isinstance(approval.get(k), str) and approval[k].strip() and 'PENDING' not in approval[k]
                for k in ('approver', 'approval_text', 'approved_utc')), 'explicit approval text/time required')
    require(datetime.fromisoformat(approval['approved_utc'].replace('Z', '+00:00')).tzinfo is not None,
            'approval time must include a timezone')
    require(re.fullmatch('[0-9a-f]{40}', auth.get('source_commit', '')), 'source commit missing')
    require(clean, 'tracked working tree must be clean')
    require(auth.get('source_files_sha256') == source_hashes, 'implementation source hashes differ')
    require(auth.get('runtime') == runtime, 'numerical runtime differs from authorization')
    require(not output_exists, 'run namespace already exists; a rerun needs an amendment')
