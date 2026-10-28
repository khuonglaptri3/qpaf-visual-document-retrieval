"""A005 Stage 0: ViDoSeek train-only alignment gate for the listwise loss; never trains.

On the 799 train queries and the 66-point static grid, the A005 profile loss
L(w) = min over log τ in [log 1e-3, 0] is compared with train nDCG@10 under the
A004 thresholds (A005 §4.3). Only train labels are deserialized; validation,
test and ViMDoc labels are not.
"""
import json
from pathlib import Path
import subprocess

from qpaf.m24.dataset import iter_batches
from qpaf.m24.evaluator import evaluate
from qpaf.m43.freeze import git, read, serialize, sha, write_json
from qpaf.m46.probe import THRESHOLDS, gate, grid_points, load_train

from .losses import GOLDEN_ITERATIONS, LOG_TAU_BOUNDS, golden_minimum, listwise_loss

AUTHORIZATION = 'evidence/revisions/a005-s0-001/authorization.json'
OUTPUT = 'evidence/revisions/a005-s0-001/alignment_probe.json'
M44_CONFIG = 'configs/m4.4/evaluation.json'
M46_PROBE = 'evidence/revisions/m4.6-001/loss_alignment_probe.json'
SOURCES = ('src/qpaf/a005/__init__.py', 'src/qpaf/a005/losses.py', 'src/qpaf/a005/probe.py',
           'scripts/probe_a005_stage0.py', 'tests/test_a005_probe.py',
           'src/qpaf/m46/probe.py', 'src/qpaf/m24/dataset.py', 'src/qpaf/m24/evaluator.py',
           'src/qpaf/m24/trainer.py', 'src/qpaf/m12/features.py')


class ProbeError(ValueError):
    """An input, pin, authorization or stored record violates the A005 Stage 0 contract."""


def require(ok, message):
    if not ok:
        raise ProbeError(message)


def grid_row(batches, records, weights):
    """Static fused scores for one grid point: train nDCG@10 and the profiled listwise loss."""
    import torch
    w = torch.tensor(weights, dtype=torch.float64)
    fused, predictions = [], []
    for batch, features in batches:
        scores = (features.scores*w).sum(-1)
        fused.append((scores, batch.labels, batch.mask))
        for row, query_id in enumerate(batch.query_ids):
            count = int(batch.mask[row].sum())
            predictions.append({'query_id': query_id, 'page_ids': batch.page_ids[row][:count],
                                'scores': scores[row, :count].tolist()})

    def loss(log_tau):
        total, count = 0., 0
        for scores, labels, mask in fused:
            value, valid = listwise_loss(scores, labels, mask, log_tau)
            total, count = total+value.item()*valid, count+valid
        return total/count
    profile, log_tau = golden_minimum(loss, *LOG_TAU_BOUNDS)
    aggregate, _ = evaluate(predictions, records)
    return {'weights': weights, 'ndcg_at_10': aggregate['ndcg_at_10'], 'a005_profile_loss': profile,
            'best_log_tau': log_tau}


def run(root):
    import torch
    from qpaf.m12.features import build_features
    from qpaf.m24.config import load_config
    from qpaf.m42.active_primary import verify_files
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    root = Path(root).resolve()
    pins = read(root/M44_CONFIG)['bundle']
    bundle = root/pins['run_path']
    verify_files(bundle, pins['manifest_sha256'])
    records = load_train(bundle)
    config = load_config(bundle/'inputs/shared_base.toml')
    cap, size = config['features']['query_length_cap'], config['training']['batch_size']
    batches = [(batch, build_features(batch.raw_scores, batch.texts, batch.page_ids, batch.mask, query_length_cap=cap))
               for batch in iter_batches(records, size)]
    grid = [grid_row(batches, records, weights) for weights in grid_points()]
    m46 = {tuple(row['weights']): row['ndcg_at_10'] for row in read(root/M46_PROBE)['grid']}
    replay = max(abs(row['ndcg_at_10']-m46[tuple(row['weights'])]) for row in grid)
    return {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': 0,
            'experiment_id': 'QPAF-A005-PRB-001', 'dataset': 'ViDoSeek', 'split': 'train', 'unit': 'page',
            'query_count': len(records), 'grid': grid, 'gate': gate(grid, 'a005_profile_loss'),
            'thresholds': THRESHOLDS, 'log_tau_bounds': list(LOG_TAU_BOUNDS),
            'golden_iterations': GOLDEN_ITERATIONS, 'm46_grid_ndcg_max_abs_difference': replay,
            'inputs_sha256': {'m42_manifest': pins['manifest_sha256'], 'm46_probe': sha(root/M46_PROBE)},
            'test_labels_opened': False, 'validation_labels_used': False, 'vimdoc_accessed': False,
            'training_executed': False, 'independent_review': 'WAIVED_BY_A006'}


def check_authorization(root):
    """The run needs an APPROVED authorization whose source pins match the files on disk."""
    path = Path(root)/AUTHORIZATION
    require(path.is_file(), f'authorization missing: {AUTHORIZATION}')
    authorization = read(path)
    require(authorization.get('status') == 'APPROVED', 'Stage 0 authorization is not APPROVED')
    for relative, expected in authorization['source_files_sha256'].items():
        require(sha(Path(root)/relative) == expected, f'source differs from authorization: {relative}')
    require(set(authorization['source_files_sha256']) >= set(SOURCES), 'authorization does not pin every source')
    return sha(path)


def create(root):
    root = Path(root).resolve()
    output = root/OUTPUT
    require(not output.exists(), f'output already exists: {OUTPUT}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'),
            'probe creation requires a clean tracked tree')
    authorization_sha256 = check_authorization(root)
    record = {**run(root), 'authorization_sha256': authorization_sha256,
              'source_commit': git(root, 'rev-parse', 'HEAD')}
    require(record['m46_grid_ndcg_max_abs_difference'] <= 1e-12, 'grid nDCG does not replay the M4.6 probe')
    write_json(output, record)
    return record


def verify(root):
    """Read-only: recompute and require the stored bytes, apart from the recorded commit and authorization."""
    root = Path(root).resolve()
    stored = (root/OUTPUT).read_bytes()
    record = json.loads(stored)
    recomputed = {**run(root), 'authorization_sha256': record['authorization_sha256'],
                  'source_commit': record['source_commit']}
    require(serialize(recomputed) == stored, 'stored probe record differs from the recomputation')
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', record['source_commit'], 'HEAD'], cwd=root)
    require(ancestor.returncode == 0, 'probe source commit is not in this history')
    return {'status': 'PASS', 'sha256': sha(root/OUTPUT), 'gate': record['gate']['status']}
