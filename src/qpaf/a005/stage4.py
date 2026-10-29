"""A005 Stage 4: matched QARF-SA-v2 / QPAF-SA-v2 runs on ViMDoc train + validation (A005 §5).

Each run (granularity × seed) has its own authorization file and writes one
create-once directory: the selected checkpoint, the epoch history, per-query
validation nDCG@10 and a fresh-process reload check (≤ 1e-7). The anchor w̄ is the
Stage 3 `train_fitted_static` refit. Confirmation qrels are not read.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from qpaf.m43.freeze import git, read, sha, write_json

from .stage2 import CACHE_FILES, split_inputs

ROOT_DIR = 'evidence/revisions/a005-s4-001'
STAGE3 = 'evidence/revisions/a005-s3-001/baselines.json'
SEEDS = (20260820, 20260821, 20260822)
GRANULARITIES = ('query', 'page')
METHOD = {'query': 'QARF-SA-v2', 'page': 'QPAF-SA-v2'}
QUERY_LENGTH_CAP = 64
RELOAD_TOLERANCE = 1e-7
SOURCES = ('src/qpaf/a005/__init__.py', 'src/qpaf/a005/losses.py', 'src/qpaf/a005/model.py',
           'src/qpaf/a005/trainer.py', 'src/qpaf/a005/vimdoc.py', 'src/qpaf/a005/stage2.py',
           'src/qpaf/a005/stage4.py', 'scripts/train_a005_stage4.py', 'tests/test_a005_trainer.py',
           'tests/test_a005_stage4.py', 'src/qpaf/m12/features.py', 'src/qpaf/m24/dataset.py',
           'src/qpaf/m24/evaluator.py', 'src/qpaf/m24/trainer.py')


class Stage4Error(ValueError):
    """An input, pin, authorization or stored record violates the A005 Stage 4 contract."""


def require(ok, message):
    if not ok:
        raise Stage4Error(message)


def run_name(granularity, seed):
    return f'{METHOD[granularity].lower()}-{seed}'


def run_dir(root, granularity, seed):
    return Path(root)/ROOT_DIR/'runs'/run_name(granularity, seed)


def check_authorization(root, cache, granularity, seed):
    """One APPROVED authorization per run, pinning sources, cache and the Stage 3 record."""
    root = Path(root)
    path = run_dir(root, granularity, seed)/'authorization.json'
    require(path.is_file(), f'authorization missing: {path.relative_to(root).as_posix()}')
    authorization = read(path)
    require(authorization.get('status') == 'APPROVED', 'Stage 4 authorization is not APPROVED')
    require((authorization['granularity'], authorization['seed']) == (granularity, seed),
            'authorization is for another run')
    require(set(authorization['source_files_sha256']) >= set(SOURCES), 'authorization does not pin every source')
    for relative, expected in authorization['source_files_sha256'].items():
        require(sha(root/relative) == expected, f'source differs from authorization: {relative}')
    for name in CACHE_FILES:
        require(sha(Path(cache)/name) == authorization['cache_sha256'][name], f'cache file differs: {name}')
    require(sha(root/STAGE3) == authorization['stage3_sha256'], 'Stage 3 record differs from authorization')
    return sha(path)


def validation_scores(model, records):
    """Fused page scores of every validation query, in record order."""
    from qpaf.m24.evaluator import predict
    from .trainer import BUDGET
    return {p['query_id']: p['scores'] for p in predict(model, records, BUDGET['batch_size'], QUERY_LENGTH_CAP)}


def per_query_ndcg(scores, records, qrels):
    from .model import document_metrics
    return {r.query_id: document_metrics(list(r.page_ids), scores[r.query_id], qrels[r.query_id])['ndcg_at_10']
            for r in records}


def load_checkpoint(path, anchor, granularity):
    import torch
    from .model import AnchoredFusionGate
    model = AnchoredFusionGate(anchor, granularity)
    model.load_state_dict(torch.load(path, weights_only=True))
    model.eval()
    return model


def reload_check(root, cache, checkpoint, anchor, granularity, expected):
    """Recompute validation scores in a fresh interpreter and return the max absolute difference."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)/'scores.json'
        code = ('import json,sys; sys.path.insert(0, sys.argv[1]+"/src"); '
                'from qpaf.a005.stage4 import reload_scores; '
                'json.dump(reload_scores(*sys.argv[1:6]), open(sys.argv[6], "w"))')
        subprocess.run([sys.executable, '-c', code, str(root), str(cache), str(checkpoint), json.dumps(anchor),
                        granularity, str(out)], check=True)
        fresh = json.loads(out.read_text())
    return max(abs(a-b) for q in expected for a, b in zip(expected[q], fresh[q]))


def reload_scores(root, cache, checkpoint, anchor, granularity):
    import torch
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    records, _ = split_inputs(root, cache, 'validation')
    return validation_scores(load_checkpoint(checkpoint, json.loads(anchor), granularity), records)


def create(root, cache, granularity, seed, log=print):
    import torch
    from .trainer import BUDGET, train
    root = Path(root).resolve()
    require(granularity in GRANULARITIES and seed in SEEDS, 'unknown run')
    directory = run_dir(root, granularity, seed)
    require(not (directory/'result.json').exists(), f'run already recorded: {run_name(granularity, seed)}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'), 'training requires a clean tracked tree')
    authorization_sha256 = check_authorization(root, cache, granularity, seed)
    if granularity == 'page':
        for qarf_seed in SEEDS:
            require((run_dir(root, 'query', qarf_seed)/'result.json').is_file(),
                    'matched QARF-SA runs must be recorded before QPAF-SA')
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    stage3 = read(root/STAGE3)
    anchor = stage3['stage4_anchor_weights']
    train_records, train_qrels = split_inputs(root, cache, 'train')
    validation_records, validation_qrels = split_inputs(root, cache, 'validation')
    result = train(anchor, granularity, seed, train_records, validation_records, query_length_cap=QUERY_LENGTH_CAP,
                   train_relevant_documents=train_qrels, validation_relevant_documents=validation_qrels, log=log)
    model = result['model']
    model.eval()
    checkpoint = directory/'checkpoint.pt'
    require(not checkpoint.exists(), 'checkpoint already exists')
    torch.save(model.state_dict(), checkpoint)
    scores = validation_scores(model, validation_records)
    per_query = per_query_ndcg(scores, validation_records, validation_qrels)
    reload = reload_check(root, cache, checkpoint, anchor, granularity, scores)
    finite = all(torch.isfinite(p).all() for p in model.parameters())
    static = stage3['roster']['train_fitted_static']['ndcg_at_10']
    record = {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': 4,
              'experiment_id': f'QPAF-A005-MTH-{run_name(granularity, seed)}', 'method': METHOD[granularity],
              'granularity': granularity, 'seed': seed, 'anchor_weights': anchor, 'budget': BUDGET,
              'query_length_cap': QUERY_LENGTH_CAP, 'best_epoch': result['best_epoch'],
              'validation_ndcg_at_10': result['best_value'],
              'validation_ndcg_at_10_recomputed': sum(per_query.values())/len(per_query),
              'epoch0_validation_ndcg_at_10': result['history'][0]['validation_ndcg_at_10'],
              'train_fitted_static_validation_ndcg_at_10': static,
              'gain_over_train_fitted_static': result['best_value']-static,
              'history': result['history'], 'per_query_validation_ndcg_at_10': per_query,
              'checkpoint_sha256': sha(checkpoint), 'reload_max_abs_difference': reload,
              'reload_pass': reload <= RELOAD_TOLERANCE, 'finite_parameters': bool(finite),
              'inputs_sha256': {name: sha(Path(cache)/name) for name in CACHE_FILES},
              'stage3_sha256': sha(root/STAGE3), 'authorization_sha256': authorization_sha256,
              'source_commit': git(root, 'rev-parse', 'HEAD'), 'confirmation_labels_opened': False,
              'vidoseek_test_accessed': False, 'independent_review': 'WAIVED_BY_A006'}
    write_json(directory/'result.json', record)
    return record


def no_deviation_rule(root):
    """A005 §4.4: NO_LEARNED_DEVIATION when validation selects epoch 0 for at least two QPAF-SA seeds."""
    epochs = {seed: read(run_dir(root, 'page', seed)/'result.json')['best_epoch'] for seed in SEEDS}
    zero = sum(1 for epoch in epochs.values() if epoch == 0)
    return {'qpaf_sa_best_epochs': epochs, 'epoch0_selections': zero,
            'status': 'NO_LEARNED_DEVIATION' if zero >= 2 else 'PROCEED'}
