"""A005 Stage 2: ViMDoc train-only alignment gate in document units; never trains.

On the 1,600 ViMDoc train queries and the 66-point static grid, the A005 document
profile loss L(w) = min over log τ in [log 1e-3, 0] is compared with train
nDCG@10 under the A004 thresholds (A005 §4.3). The dev qrels file also holds
validation; only its train table is kept, and validation is never scored.
"""
import json
from pathlib import Path
import subprocess

from qpaf.m43.freeze import git, read, serialize, sha, write_json
from qpaf.m46.probe import THRESHOLDS, gate

from .losses import GOLDEN_ITERATIONS, LOG_TAU_BOUNDS, golden_minimum
from .vimdoc import doc_profile_loss, load_records, static_grid

AUTHORIZATION = 'evidence/revisions/a005-s2-001/authorization.json'
OUTPUT = 'evidence/revisions/a005-s2-001/alignment_probe.json'
SPLITS = 'evidence/revisions/m4.1-001'
CACHE_FILES = ('candidate_scores.parquet', 'queries.jsonl', 'dev_qrels.json')
SOURCES = ('src/qpaf/a005/__init__.py', 'src/qpaf/a005/losses.py', 'src/qpaf/a005/model.py',
           'src/qpaf/a005/vimdoc.py', 'src/qpaf/a005/stage2.py', 'scripts/probe_a005_stage2.py',
           'tests/test_a005_vimdoc.py', 'tests/test_a005_stage2.py', 'src/qpaf/m46/probe.py')


class Stage2Error(ValueError):
    """An input, pin, authorization or stored record violates the A005 Stage 2 contract."""


def require(ok, message):
    if not ok:
        raise Stage2Error(message)


def split_inputs(root, cache, role):
    """IDs of one dev role from the M4.1 seal, their qrels and texts, and the candidate rows of those queries only."""
    import pyarrow.parquet as pq
    require(role in ('train', 'validation'), f'not a dev role: {role}')
    ids = (Path(root)/SPLITS/f'{role}_ids.txt').read_text(encoding='utf-8').split()
    qrels = read(Path(cache)/'dev_qrels.json')[role]
    require(set(qrels) == set(ids), f'{role} qrels do not match the M4.1 {role} IDs')
    texts = {}
    for line in (Path(cache)/'queries.jsonl').read_text(encoding='utf-8').splitlines():
        query = json.loads(line)
        if query['query_id'] in qrels:
            texts[query['query_id']] = query['text']
    frame = pq.read_table(Path(cache)/'candidate_scores.parquet',
                          columns=['query_id', 'page_id', 'document_id', 'bm25', 'dense', 'visual'],
                          filters=[('query_id', 'in', ids)]).to_pandas()
    return load_records(frame, texts, qrels, ids), qrels


def run(root, cache):
    records, qrels = split_inputs(root, cache, 'train')
    rows, best = static_grid(records, qrels)
    golden = lambda f: golden_minimum(f, *LOG_TAU_BOUNDS)  # noqa: E731
    learnable = None
    for row in rows:
        (row['a005_profile_loss'], row['best_log_tau']), learnable = doc_profile_loss(
            records, qrels, row['weights'], golden)
    return {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': 2,
            'experiment_id': 'QPAF-A005-PRB-002', 'dataset': 'ViMDoc', 'split': 'train', 'unit': 'document',
            'query_count': len(records), 'learnable_query_count': learnable, 'grid': rows,
            'grid_best_weights': best, 'gate': gate(rows, 'a005_profile_loss'), 'thresholds': THRESHOLDS,
            'log_tau_bounds': list(LOG_TAU_BOUNDS), 'golden_iterations': GOLDEN_ITERATIONS,
            'inputs_sha256': {name: sha(Path(cache)/name) for name in CACHE_FILES},
            'validation_labels_used': False, 'confirmation_labels_opened': False, 'vidoseek_test_accessed': False,
            'training_executed': False, 'independent_review': 'WAIVED_BY_A006'}


def check_authorization(root, cache):
    """The run needs an APPROVED authorization whose source and cache pins match the files on disk."""
    path = Path(root)/AUTHORIZATION
    require(path.is_file(), f'authorization missing: {AUTHORIZATION}')
    authorization = read(path)
    require(authorization.get('status') == 'APPROVED', 'Stage 2 authorization is not APPROVED')
    require(set(authorization['source_files_sha256']) >= set(SOURCES), 'authorization does not pin every source')
    for relative, expected in authorization['source_files_sha256'].items():
        require(sha(Path(root)/relative) == expected, f'source differs from authorization: {relative}')
    for name in CACHE_FILES:
        require(sha(Path(cache)/name) == authorization['cache_sha256'][name], f'cache file differs: {name}')
    return sha(path)


def create(root, cache):
    root = Path(root).resolve()
    output = root/OUTPUT
    require(not output.exists(), f'output already exists: {OUTPUT}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'),
            'probe creation requires a clean tracked tree')
    authorization_sha256 = check_authorization(root, cache)
    record = {**run(root, cache), 'authorization_sha256': authorization_sha256,
              'source_commit': git(root, 'rev-parse', 'HEAD')}
    write_json(output, record)
    return record


def verify(root, cache):
    """Read-only: recompute and require the stored bytes, apart from the recorded commit and authorization."""
    root = Path(root).resolve()
    stored = (root/OUTPUT).read_bytes()
    record = json.loads(stored)
    recomputed = {**run(root, cache), 'authorization_sha256': record['authorization_sha256'],
                  'source_commit': record['source_commit']}
    require(serialize(recomputed) == stored, 'stored probe record differs from the recomputation')
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', record['source_commit'], 'HEAD'], cwd=root)
    require(ancestor.returncode == 0, 'probe source commit is not in this history')
    return {'status': 'PASS', 'sha256': sha(root/OUTPUT), 'gate': record['gate']['status']}
