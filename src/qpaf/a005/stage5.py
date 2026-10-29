"""A005 Stage 5: the one-time ViMDoc confirmation of the six baselines and six Stage 4 runs (A005 §6).

This is the only place the confirmation qrels are read. The sealed file is hashed against the
`prepare` marker before it is parsed. All 8,904 confirmation queries are scored: a query with
no relevant document in the candidate pool keeps nDCG@10 = 0 and is only counted. The record
is create-once; nothing here trains, re-selects an epoch, or changes a method.
"""
import json
from pathlib import Path

from qpaf.m43.freeze import git, read, sha, write_json

from .stage2 import CACHE_FILES, SPLITS
from .stage4 import GRANULARITIES, METHOD, QUERY_LENGTH_CAP, SEEDS, STAGE3, per_query_ndcg, run_dir, run_name
from .stage4 import load_checkpoint, validation_scores
from .vimdoc import baselines, load_records

OUTPUT = 'evidence/revisions/a005-s5-001/confirmation.json'
CONFIRMATION_IDS = SPLITS+'/confirmation_ids.txt'
PREPARE_MARKER = 'evidence/revisions/a005-s1-001/markers/prepare.json'
SEALED_NAME = 'confirmation_qrels.sealed.json'


class Stage5Error(ValueError):
    """An input, pin or stored record violates the A005 Stage 5 contract."""


def require(ok, message):
    if not ok:
        raise Stage5Error(message)


def sealed_sha256(root):
    """The pinned SHA-256 of the sealed confirmation qrels, read from the Stage 1 `prepare` marker at run time."""
    return read(Path(root)/PREPARE_MARKER)['confirmation_qrels_sealed_sha256']


def confirmation_inputs(root, cache, sealed_path):
    """Confirmation records and their document qrels; the sealed file is hashed before it is parsed."""
    import pyarrow.parquet as pq
    require(sha(sealed_path) == sealed_sha256(root), 'sealed file hash differs from the prepare marker')
    ids = (Path(root)/CONFIRMATION_IDS).read_text(encoding='utf-8').split()
    qrels = json.loads(Path(sealed_path).read_text(encoding='utf-8'))
    require(len(set(ids)) == len(ids) and set(qrels) == set(ids), 'sealed qrels do not match the M4.1 confirmation IDs')
    texts = {}
    for line in (Path(cache)/'queries.jsonl').read_text(encoding='utf-8').splitlines():
        query = json.loads(line)
        if query['query_id'] in qrels:
            texts[query['query_id']] = query['text']
    frame = pq.read_table(Path(cache)/'candidate_scores.parquet',
                          columns=['query_id', 'page_id', 'document_id', 'bm25', 'dense', 'visual'],
                          filters=[('query_id', 'in', ids)]).to_pandas()
    return load_records(frame, texts, qrels, ids), qrels


def stage4_results(root, cache):
    """The six recorded Stage 4 runs, each tied to its checkpoint, the Stage 3 record and this cache."""
    root = Path(root)
    pins = {name: sha(Path(cache)/name) for name in CACHE_FILES}
    results = {}
    for granularity in GRANULARITIES:
        for seed in SEEDS:
            directory = run_dir(root, granularity, seed)
            require((directory/'result.json').is_file(), f'Stage 4 run missing: {run_name(granularity, seed)}')
            result = read(directory/'result.json')
            require(result['reload_pass'] and result['finite_parameters'], f'Stage 4 run failed its checks: '
                    f'{run_name(granularity, seed)}')
            require((result['granularity'], result['seed']) == (granularity, seed), 'Stage 4 result is for another run')
            require((directory/'checkpoint.pt').is_file()
                    and sha(directory/'checkpoint.pt') == result['checkpoint_sha256'], 'Stage 4 checkpoint differs')
            require(result['stage3_sha256'] == sha(root/STAGE3), 'Stage 4 run used another Stage 3 record')
            require(result['inputs_sha256'] == pins, 'Stage 4 run used another cache')
            results[(granularity, seed)] = result
    return results


def uncovered_queries(records, qrels):
    """Queries whose candidate pool holds no page of a relevant document (they keep nDCG 0)."""
    from .model import document_of
    return sum(1 for r in records if not {document_of(p) for p in r.page_ids} & set(qrels[r.query_id]))


def run(root, cache, sealed_path):
    import torch
    root = Path(root)
    results = stage4_results(root, cache)
    records, qrels = confirmation_inputs(root, cache, sealed_path)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    stage3 = read(root/STAGE3)
    order = [r.query_id for r in records]
    roster = baselines(records, qrels, stage3['train_fitted_static_weights'])
    methods = {name: {} for name in METHOD.values()}
    for (granularity, seed), result in results.items():
        model = load_checkpoint(run_dir(root, granularity, seed)/'checkpoint.pt', stage3['stage4_anchor_weights'],
                                granularity)
        per_query = per_query_ndcg(validation_scores(model, records), records, qrels)
        methods[METHOD[granularity]][str(seed)] = {
            'ndcg_at_10': sum(per_query.values())/len(per_query), 'per_query': per_query,
            'checkpoint_sha256': result['checkpoint_sha256']}
    return {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': 5,
            'experiment_id': 'QPAF-A005-CNF-001', 'dataset': 'ViMDoc', 'split': 'confirmation', 'unit': 'document',
            'confirmation_query_count': len(records),
            'queries_without_positive_candidate': uncovered_queries(records, qrels),
            'train_fitted_static_weights': stage3['train_fitted_static_weights'],
            'anchor_weights': stage3['stage4_anchor_weights'], 'query_length_cap': QUERY_LENGTH_CAP,
            'baselines': {name: {'ndcg_at_10': entry['ndcg_at_10'], 'per_query': dict(zip(order, entry['per_query']))}
                          for name, entry in roster.items()},
            'methods': methods,
            'stage4_result_sha256': {run_name(g, s): sha(run_dir(root, g, s)/'result.json') for g, s in results},
            'inputs_sha256': {**{name: sha(Path(cache)/name) for name in CACHE_FILES},
                              SEALED_NAME: sha(sealed_path)},
            'stage3_sha256': sha(root/STAGE3),
            'confirmation_labels_opened': True, 'vidoseek_test_accessed': False,
            'independent_review': 'WAIVED_BY_A006'}


def create(root, cache, sealed_path):
    """Create-once. Refuses on an existing record, a missing Stage 4 run or a dirty tracked tree."""
    root = Path(root).resolve()
    require(not (root/OUTPUT).exists(), f'output already exists: {OUTPUT}')
    stage4_results(root, cache)
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'),
            'confirmation requires a clean tracked tree')
    record = {**run(root, cache, sealed_path), 'source_commit': git(root, 'rev-parse', 'HEAD')}
    (root/OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    write_json(root/OUTPUT, record)
    return record
