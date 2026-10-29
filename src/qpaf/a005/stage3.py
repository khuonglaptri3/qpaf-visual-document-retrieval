"""A005 Stage 3: ViMDoc deployable baselines on validation and the co-strongest set; never trains a model.

`train_fitted_static` is refit on ViMDoc train only (66-point grid, earlier point on
ties) and becomes the Stage 4 anchor w̄. Every roster member is scored on the 400
validation queries in document units; members within 1e-12 of the best mean are
co-strongest (baseline_policy.md item 4). Confirmation qrels are not read.
"""
import json
from pathlib import Path
import subprocess

from qpaf.m43.freeze import git, read, serialize, sha, write_json

from .stage2 import CACHE_FILES, split_inputs
from .vimdoc import baselines, static_grid

AUTHORIZATION = 'evidence/revisions/a005-s3-001/authorization.json'
OUTPUT = 'evidence/revisions/a005-s3-001/baselines.json'
STAGE2 = 'evidence/revisions/a005-s2-001/alignment_probe.json'
CO_STRONGEST_TOLERANCE = 1e-12
SOURCES = ('src/qpaf/a005/__init__.py', 'src/qpaf/a005/model.py', 'src/qpaf/a005/vimdoc.py',
           'src/qpaf/a005/stage2.py', 'src/qpaf/a005/stage3.py', 'scripts/baselines_a005_stage3.py',
           'tests/test_a005_vimdoc.py', 'tests/test_a005_stage3.py', 'src/qpaf/m46/probe.py')
LEARNED_QARF_DEVIATION = (
    'Learned QARF-v1 (A001) trains on page labels; ViMDoc has document qrels only and A005 forbids writing them '
    'onto pages, so QARF-v1 is not run. Its role as the learned query-level comparator is taken by the matched '
    'QARF-SA-v2 of Stage 4, which shares the anchor, loss, config and seeds with QPAF-SA-v2.')


class Stage3Error(ValueError):
    """An input, pin, authorization or stored record violates the A005 Stage 3 contract."""


def require(ok, message):
    if not ok:
        raise Stage3Error(message)


def co_strongest(roster):
    best = max(entry['ndcg_at_10'] for entry in roster.values())
    return sorted(name for name, entry in roster.items() if entry['ndcg_at_10'] >= best-CO_STRONGEST_TOLERANCE)


def run(root, cache):
    train, train_qrels = split_inputs(root, cache, 'train')
    _, weights = static_grid(train, train_qrels)
    validation, validation_qrels = split_inputs(root, cache, 'validation')
    roster = baselines(validation, validation_qrels, weights)
    order = [r.query_id for r in validation]
    for entry in roster.values():
        entry['per_query'] = dict(zip(order, entry['per_query']))
    return {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': 3,
            'experiment_id': 'QPAF-A005-BSL-001', 'dataset': 'ViMDoc', 'split': 'validation', 'unit': 'document',
            'train_query_count': len(train), 'validation_query_count': len(validation),
            'train_fitted_static_weights': weights, 'roster': roster,
            'co_strongest': co_strongest(roster), 'co_strongest_tolerance': CO_STRONGEST_TOLERANCE,
            'stage4_anchor_weights': weights, 'deviations': {'learned_qarf_v1': LEARNED_QARF_DEVIATION},
            'inputs_sha256': {name: sha(Path(cache)/name) for name in CACHE_FILES},
            'stage2_probe_sha256': sha(Path(root)/STAGE2),
            'confirmation_labels_opened': False, 'vidoseek_test_accessed': False,
            'training_executed': False, 'independent_review': 'WAIVED_BY_A006'}


def check_authorization(root, cache):
    """APPROVED authorization with matching source and cache pins, after a passing Stage 2 gate."""
    root = Path(root)
    require((root/STAGE2).is_file() and read(root/STAGE2)['gate']['status'] == 'PASS',
            'Stage 3 needs a passing Stage 2 gate')
    path = root/AUTHORIZATION
    require(path.is_file(), f'authorization missing: {AUTHORIZATION}')
    authorization = read(path)
    require(authorization.get('status') == 'APPROVED', 'Stage 3 authorization is not APPROVED')
    require(set(authorization['source_files_sha256']) >= set(SOURCES), 'authorization does not pin every source')
    for relative, expected in authorization['source_files_sha256'].items():
        require(sha(root/relative) == expected, f'source differs from authorization: {relative}')
    for name in CACHE_FILES:
        require(sha(Path(cache)/name) == authorization['cache_sha256'][name], f'cache file differs: {name}')
    return sha(path)


def create(root, cache):
    root = Path(root).resolve()
    require(not (root/OUTPUT).exists(), f'output already exists: {OUTPUT}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'),
            'baseline creation requires a clean tracked tree')
    authorization_sha256 = check_authorization(root, cache)
    record = {**run(root, cache), 'authorization_sha256': authorization_sha256,
              'source_commit': git(root, 'rev-parse', 'HEAD')}
    write_json(root/OUTPUT, record)
    return record


def verify(root, cache):
    """Read-only: recompute and require the stored bytes, apart from the recorded commit and authorization."""
    root = Path(root).resolve()
    stored = (root/OUTPUT).read_bytes()
    record = json.loads(stored)
    recomputed = {**run(root, cache), 'authorization_sha256': record['authorization_sha256'],
                  'source_commit': record['source_commit']}
    require(serialize(recomputed) == stored, 'stored baseline record differs from the recomputation')
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', record['source_commit'], 'HEAD'], cwd=root)
    require(ancestor.returncode == 0, 'baseline source commit is not in this history')
    return {'status': 'PASS', 'sha256': sha(root/OUTPUT), 'co_strongest': record['co_strongest']}
