"""R6-01..04: diagnostic QPAF training with one feature group masked out, plus paired statistics.

The pilot gate is `nn.Linear(13, 3)`. Removing input columns would change fan-in, hence the Kaiming
initialisation and the remaining weights, so the ablation would vary more than one factor. Instead the
omitted columns are multiplied by zero: their weights receive zero gradient, Adam (weight decay 0) leaves
them at their initial value, and they contribute nothing to any logit. The kept weights start from the
exact pilot initialisation. With nothing omitted the loop reproduces the M3.4 pilot run.
"""
import math
import os
from pathlib import Path
import time
import uuid

from qpaf.m11.artifacts import digest, object_hash
from qpaf.m12.features import FEATURE_NAMES

METHOD = 'QPAF'
FORMAT = 'qpaf-m56-ablation-checkpoint-v1'
METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')
TIE = 1e-12
# M5.1 preregistration order 5-8; one group removed per run from the full 13-feature contract, never cumulative.
ABLATIONS = {
    'R6-00': ('control_full_13_features', ()),
    'R6-01': ('remove_rank_feature_group', ('rr_bm25', 'rr_dense', 'rr_visual')),
    'R6-02': ('remove_gap_feature_group', ('gap_bm25', 'gap_dense', 'gap_visual')),
    'R6-03': ('remove_disagreement_feature_group',
              ('disagreement_bm25_dense', 'disagreement_bm25_visual', 'disagreement_dense_visual')),
    'R6-04': ('remove_query_length', ('query_length',)),
}


class AblationError(ValueError):
    """An ablation input, checkpoint or output violates the M5.6 contract."""


def require(ok, message):
    if not ok:
        raise AblationError(message)


def keep_vector(omitted):
    require(len(set(omitted)) == len(omitted) and set(omitted) <= set(FEATURE_NAMES), 'Unknown omitted feature')
    return [0. if name in omitted else 1. for name in FEATURE_NAMES]


def build_model(config, omitted):
    """The frozen pilot gate (same seed, same initial parameters) behind a fixed input-column mask."""
    import torch
    from torch import nn
    from qpaf.m12.features import FeatureBatch
    from qpaf.m24.trainer import build_model as build_gate

    class MaskedGate(nn.Module):
        def __init__(self):
            super().__init__()
            self.gate = build_gate(config, METHOD)
            # Not persistent: the mask is part of the contract recorded in the checkpoint, not a parameter.
            self.register_buffer('keep', torch.tensor(keep_vector(omitted), dtype=torch.float64), persistent=False)

        def forward(self, batch):
            return self.gate(FeatureBatch(batch.values*self.keep, batch.scores, batch.mask))

    return MaskedGate()


def save_checkpoint(path, *, config, omitted, epoch, model, optimizer, generator, history, best):
    import torch
    path = Path(path)
    payload = {'format': FORMAT, 'config_sha256': object_hash(config), 'method': METHOD,
               'feature_names': list(FEATURE_NAMES), 'omitted_features': list(omitted), 'epoch': epoch,
               'model_state': model.state_dict(), 'optimizer_state': optimizer.state_dict(),
               'generator_state': generator.get_state(), 'history': history, 'best': best}
    temp = path.with_name(f'{path.name}.{uuid.uuid4().hex}.tmp')
    torch.save(payload, temp)
    os.replace(temp, path)
    return digest(path)


def load_checkpoint(path, *, config, omitted, expected_sha256=None):
    import torch
    path = Path(path)
    require(path.is_file(), f'Checkpoint not found: {path}')
    require(expected_sha256 is None or digest(path) == expected_sha256, 'Checkpoint checksum mismatch')
    payload = torch.load(path, map_location='cpu', weights_only=True)
    require(isinstance(payload, dict) and payload.get('format') == FORMAT, 'Unknown checkpoint format')
    require(payload['config_sha256'] == object_hash(config), 'Checkpoint was trained with a different config')
    require((payload['method'], payload['feature_names'], payload['omitted_features']) ==
            (METHOD, list(FEATURE_NAMES), list(omitted)), 'Checkpoint method or feature mask mismatch')
    return payload


def train(config, omitted, train_records, validation_records, checkpoint_dir, *, log=print):
    """The M2.4 trainer loop (seeded order, pairwise loss, clipping, validation selection) on the masked gate."""
    import torch
    from qpaf.m12.features import build_features
    from qpaf.m12.losses import pairwise_logistic_loss
    from qpaf.m24.dataset import iter_batches
    from qpaf.m24.evaluator import evaluate, predict
    from qpaf.m24.trainer import TrainingError, is_better, learnable

    training, cap = config['training'], config['features']['query_length_cap']
    metric = config['evaluation']['selection_metric']
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=False)
    model = build_model(config, omitted)
    optimizer = torch.optim.Adam(model.parameters(), lr=training['learning_rate'],
                                 weight_decay=training['weight_decay'])
    generator = torch.Generator().manual_seed(training['seed'])
    history, steps, best, hashes = [], [], None, {}
    for epoch in range(1, training['epochs']+1):
        started, losses, skipped = time.perf_counter(), [], 0
        model.train()
        for step, batch in enumerate(iter_batches(train_records, training['batch_size'], generator)):
            valid = learnable(batch.labels, batch.mask)
            if not valid.any():
                skipped += len(batch.query_ids)
                continue
            features = build_features(batch.raw_scores, batch.texts, batch.page_ids, batch.mask,
                                      query_length_cap=cap)
            optimizer.zero_grad(set_to_none=True)
            result = pairwise_logistic_loss(model(features).scores, batch.labels, batch.mask)
            if not torch.isfinite(result.loss):
                raise TrainingError(f'epoch {epoch} step {step}: nonfinite loss')
            result.loss.backward()
            if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise TrainingError(f'epoch {epoch} step {step}: missing or nonfinite gradient')
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), training['max_grad_norm'])
            optimizer.step()
            losses.append(result.loss.item())
            skipped += result.skipped_queries
            steps.append({'epoch': epoch, 'step': step, 'loss': result.loss.item(),
                          'grad_norm': norm.item(), 'valid_queries': result.valid_queries,
                          'skipped_queries': result.skipped_queries, 'pairs': result.pairs})
        if any(not torch.isfinite(p).all() for p in model.parameters()):
            raise TrainingError(f'epoch {epoch}: nonfinite parameters')
        aggregate, _ = evaluate(predict(model, validation_records, training['batch_size'], cap),
                                validation_records)
        improved = is_better(aggregate[metric], None if best is None else best['value'])
        if improved:
            best = {'epoch': epoch, 'metric': metric, 'value': aggregate[metric]}
        history.append({'epoch': epoch, 'train_loss': sum(losses)/len(losses) if losses else None,
                        'train_steps': len(losses), 'train_skipped_queries': skipped,
                        'seconds': time.perf_counter()-started,
                        **{f'validation_{k}': v for k, v in aggregate.items()}, 'selected': improved})
        state = dict(config=config, omitted=omitted, epoch=epoch, model=model, optimizer=optimizer,
                     generator=generator, history=history, best=best)
        hashes['last'] = save_checkpoint(checkpoint_dir/'last.pt', **state)
        if improved:
            hashes['best'] = save_checkpoint(checkpoint_dir/'best.pt', **state)
        log(f'epoch {epoch}: validation_{metric}={aggregate[metric]:.6f}{" *" if improved else ""}')
    return {'model': model, 'history': history, 'steps': steps, 'best': best, 'checkpoint_sha256': hashes}


def masked_weights_unchanged(config, omitted, state):
    """Omitted-column weights must still equal the initial ones, proving they never influenced training."""
    initial = build_model(config, omitted).state_dict()['gate.gate.weight']
    columns = [FEATURE_NAMES.index(name) for name in omitted]
    return bool((state['gate.gate.weight'][:, columns] == initial[:, columns]).all())


def paired_statistics(deltas, *, resamples=10000, seed=20260820):
    """Query-paired mean, percentile 95% bootstrap CI and W/T/L (|delta| <= 1e-12 is a tie), as in M3.5."""
    import numpy as np
    require(deltas and all(len(values) == len(deltas[METRICS[0]]) for values in deltas.values()),
            'Paired deltas must cover the same queries for every metric')
    rng = np.random.default_rng(seed)
    count = len(deltas[METRICS[0]])
    samples = rng.integers(0, count, size=(resamples, count))
    result = {}
    for metric in METRICS:
        delta = np.asarray(deltas[metric], dtype=np.float64)
        require(np.isfinite(delta).all(), f'{metric}: nonfinite paired delta')
        ci = np.percentile(delta[samples].mean(axis=1), [2.5, 97.5], method='linear')
        wins, ties = int((delta > TIE).sum()), int((np.abs(delta) <= TIE).sum())
        result[metric] = {'mean_delta': float(delta.mean()), 'median_delta': float(np.median(delta)),
                          'ci95': [float(ci[0]), float(ci[1])],
                          'wtl': {'wins': wins, 'ties': ties, 'losses': count-wins-ties}}
    return result


def per_query_deltas(candidate, reference):
    """candidate - reference per query and metric; both lists must name the same queries in the same order."""
    require([r['query_id'] for r in candidate] == [r['query_id'] for r in reference], 'Paired query order differs')
    return {m: [float(a[m])-float(b[m]) for a, b in zip(candidate, reference)] for m in METRICS}


def finite(values):
    return all(math.isfinite(v) for v in values)
