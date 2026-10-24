"""Train-only loss-alignment probe and the preregistered A004 gate; never trains.

On the 799 train queries and the 66-point static simplex grid, compare how the
A001 (v1) and A004 (v2) losses order fusion weights against train nDCG@10. Only
train labels are deserialized; validation, test and confirmation qrels are not.
"""
import json
from pathlib import Path
import subprocess

from qpaf.m12.losses import pairwise_logistic_loss
from qpaf.m24.dataset import build_records, iter_batches, read_score_rows, read_split_ids
from qpaf.m24.evaluator import evaluate
from qpaf.m24.trainer import learnable
from qpaf.m43.freeze import git, read, serialize, sha, write_json

from .losses import lambda_pairwise_logistic_loss

THRESHOLDS = {'spearman_max_inclusive': -0.5, 'ndcg_gap_max_inclusive': 0.01}
M44_CONFIG = 'configs/m4.4/evaluation.json'
V2_CONFIG = 'configs/m4.6/shared_base_v2.toml'
M43_FREEZE = 'evidence/revisions/m4.3-001/method_freeze.json'
QARF_CHECKPOINTS = ('results/m3.2/RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01/QARF/'
                    '20261022T040759-ff3934df/checkpoints/')


class ProbeError(ValueError):
    """An input, pin or stored probe record violates the M4.6 contract."""


def require(ok, message):
    if not ok:
        raise ProbeError(message)


def grid_points():
    """66 weights [bm25, dense, visual] on the 0.1 simplex, (i, j) lexicographic."""
    return [[i/10, j/10, (10-i-j)/10] for i in range(11) for j in range(11) if i+j <= 10]


def _ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks, start = [0.]*len(values), 0
    while start < len(order):
        end = start
        while end+1 < len(order) and values[order[end+1]] == values[order[start]]:
            end += 1
        for k in range(start, end+1):
            ranks[order[k]] = (start+end)/2+1
        start = end+1
    return ranks


def spearman(a, b):
    """Pearson correlation of average ranks (ties share their mean rank)."""
    ra, rb = _ranks(list(a)), _ranks(list(b))
    ma, mb = sum(ra)/len(ra), sum(rb)/len(rb)
    cov = sum((x-ma)*(y-mb) for x, y in zip(ra, rb))
    return cov/(sum((x-ma)**2 for x in ra)*sum((y-mb)**2 for y in rb))**0.5


def evaluate_gate(rank_correlation, min_loss_ndcg, max_ndcg):
    a = rank_correlation <= THRESHOLDS['spearman_max_inclusive']
    b = min_loss_ndcg >= max_ndcg-THRESHOLDS['ndcg_gap_max_inclusive']
    return {'G_A': 'PASS' if a else 'FAIL', 'G_B': 'PASS' if b else 'FAIL',
            'status': 'PASS' if a and b else 'REVISION_GATE_FAILED'}


def gate(grid_rows, loss_key):
    """Gate over grid rows; the first minimum in grid order wins a loss tie."""
    losses = [row[loss_key] for row in grid_rows]
    ndcg = [row['ndcg_at_10'] for row in grid_rows]
    best = min(range(len(losses)), key=lambda i: losses[i])
    rho = spearman(losses, ndcg)
    return {'loss': loss_key, 'spearman': rho, 'min_loss_weights': grid_rows[best]['weights'],
            'min_loss': losses[best], 'min_loss_ndcg': ndcg[best], 'max_ndcg': max(ndcg),
            **evaluate_gate(rho, ndcg[best], max(ndcg))}


def load_train(bundle):
    """Train records only; development qrels must not hold any test query ID."""
    bundle = Path(bundle)
    splits = read_split_ids(bundle/'inputs/splits')
    qrels = read(bundle/'inputs/qrels_development.json')
    require(not set(qrels) & set(splits['test']), 'development qrels contain test query IDs')
    train = {query_id: qrels[query_id] for query_id in splits['train']}
    return build_records(read_score_rows(bundle/'inputs/raw_scores.parquet'), read(bundle/'inputs/queries.json'),
                         train, splits, ('train',))['train']


def measure(batches, records, scores_of, cutoff):
    """Query-mean v1 and v2 losses over learnable queries, train nDCG@10 and mean weights."""
    import torch
    totals, predictions = {'v1_loss': [0., 0], 'v2_loss': [0., 0]}, []
    weight_sum, weight_count = torch.zeros(3, dtype=torch.float64), 0
    with torch.no_grad():
        for batch, features in batches:
            scores, weights = scores_of(features)
            valid = learnable(batch.labels, batch.mask)
            if valid.any():
                ids = [page for page, keep in zip(batch.page_ids, valid.tolist()) if keep]
                for key, result in (
                        ('v1_loss', pairwise_logistic_loss(scores[valid], batch.labels[valid], batch.mask[valid])),
                        ('v2_loss', lambda_pairwise_logistic_loss(scores[valid], batch.labels[valid],
                                                                  batch.mask[valid], ids, cutoff=cutoff))):
                    totals[key][0] += result.loss.item()*result.valid_queries
                    totals[key][1] += result.valid_queries
            weight_sum += weights[batch.mask].sum(0)
            weight_count += int(batch.mask.sum())
            for row, query_id in enumerate(batch.query_ids):
                count = int(batch.mask[row].sum())
                predictions.append({'query_id': query_id, 'page_ids': batch.page_ids[row][:count],
                                    'scores': scores[row, :count].tolist()})
    aggregate, _ = evaluate(predictions, records)
    return {'v1_loss': totals['v1_loss'][0]/totals['v1_loss'][1],
            'v2_loss': totals['v2_loss'][0]/totals['v2_loss'][1],
            'ndcg_at_10': aggregate['ndcg_at_10'], 'mean_weights': (weight_sum/weight_count).tolist()}


def run(root):
    import torch
    from qpaf.m12.features import build_features
    from qpaf.m24.checkpoint import load_checkpoint
    from qpaf.m24.config import load_config
    from qpaf.m24.trainer import build_model
    from qpaf.m42.active_primary import verify_files
    from .config import load_config as load_v2
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    root = Path(root).resolve()
    pins = read(root/M44_CONFIG)['bundle']
    bundle = root/pins['run_path']
    verify_files(bundle, pins['manifest_sha256'])
    records = load_train(bundle)
    v1, cutoff = load_config(bundle/'inputs/shared_base.toml'), load_v2(root/V2_CONFIG)['loss']['metric_cutoff']
    cap, size = v1['features']['query_length_cap'], v1['training']['batch_size']
    batches = [(batch, build_features(batch.raw_scores, batch.texts, batch.page_ids, batch.mask, query_length_cap=cap))
               for batch in iter_batches(records, size)]

    def static(weights):
        w = torch.tensor(weights, dtype=torch.float64)
        return lambda features: ((features.scores*w).sum(-1), w.expand(*features.scores.shape))

    grid = [{'weights': weights, **{k: v for k, v in measure(batches, records, static(weights), cutoff).items()
                                    if k != 'mean_weights'}} for weights in grid_points()]
    qpaf = read(root/M43_FREEZE)['frozen_method']['checkpoint']['path']
    checkpoints = {}
    for name, method, relative in (('QARF best.pt (epoch 1)', 'QARF', QARF_CHECKPOINTS+'best.pt'),
                                   ('QARF last.pt (epoch 20)', 'QARF', QARF_CHECKPOINTS+'last.pt'),
                                   ('QPAF best.pt (epoch 19)', 'QPAF', qpaf)):
        model = build_model(v1, method)
        model.load_state_dict(load_checkpoint(root/relative, config=v1, method=method)['model_state'])
        model.eval()
        output = lambda features, model=model: (lambda out: (out.scores, out.weights))(model(features))  # noqa: E731
        checkpoints[name] = {'method': method, 'path': relative, 'sha256': sha(root/relative),
                             **measure(batches, records, output, cutoff)}
    return {'schema_version': 1, 'task_id': 'M4.6', 'experiment_id': 'QPAF-M4_6-GAT-001',
            'split': 'train', 'query_count': len(records), 'grid': grid, 'checkpoints': checkpoints,
            'gate_v1': gate(grid, 'v1_loss'), 'gate_v2': gate(grid, 'v2_loss'), 'thresholds': THRESHOLDS,
            'inputs_sha256': {'m42_manifest': pins['manifest_sha256'], 'v2_config': sha(root/V2_CONFIG),
                              'm43_freeze': sha(root/M43_FREEZE)},
            'test_labels_opened': False, 'validation_labels_used': False, 'training_executed': False}


def create(root, output):
    root, output = Path(root).resolve(), Path(output)
    require(not output.exists(), f'output already exists: {output}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'),
            'probe creation requires a clean tracked tree')
    record = {**run(root), 'source_commit': git(root, 'rev-parse', 'HEAD')}
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, record)
    return record


def verify(root, output):
    """Read-only: recompute and require the stored bytes, apart from a historical source commit."""
    root, output = Path(root).resolve(), Path(output)
    stored = output.read_bytes()
    record = json.loads(stored)
    recomputed = {**run(root), 'source_commit': record['source_commit']}
    require(serialize(recomputed) == stored, 'stored probe record differs from the recomputation')
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', record['source_commit'], 'HEAD'], cwd=root)
    require(ancestor.returncode == 0, 'probe source commit is not in this history')
    return {'status': 'PASS', 'sha256': sha(output), 'gate_v2': record['gate_v2']['status']}
