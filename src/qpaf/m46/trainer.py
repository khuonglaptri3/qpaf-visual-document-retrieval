"""M2.4 epoch trainer with the A004 loss; the frozen m24 trainer stays byte-identical.

Only the loss call and the config validator differ from `qpaf.m24.trainer.train`.
Model selection, checkpoints, RNG use and telemetry are the same, so QARF-v2 and
QPAF-v2 stay matched with each other and comparable with v1.
"""
from pathlib import Path
import time

from qpaf.m24.checkpoint import load_checkpoint, save_checkpoint
from qpaf.m24.config import METHODS
from qpaf.m24.dataset import iter_batches
from qpaf.m24.evaluator import evaluate, predict
from qpaf.m24.trainer import TrainingError, is_better, learnable

from .config import validate
from .losses import lambda_pairwise_logistic_loss


def build_model(config, method):
    """Same initial parameters as `qpaf.m24.trainer.build_model`; validates the v2 config."""
    import torch
    from qpaf.m12.model import FusionGate
    validate(config)
    if method not in METHODS:
        raise ValueError(f'method must be one of {sorted(METHODS)}')
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(config['training']['seed'])
        return FusionGate(METHODS[method], **config['gate']).double()


def train(config, method, train_records, validation_records, checkpoint_dir, *, resume=None,
          stop_after_epoch=None, log=print):
    """`stop_after_epoch` ends early like an interruption; `resume` continues from last.pt."""
    import torch
    from qpaf.m12.features import build_features

    training, cap = config['training'], config['features']['query_length_cap']
    metric, cutoff = config['evaluation']['selection_metric'], config['loss']['metric_cutoff']
    if not train_records or not validation_records:
        raise TrainingError('Training and validation records are both required')
    if not any(0 < sum(r.labels) < len(r.labels) for r in train_records):
        raise TrainingError('No training query has both a positive and a negative candidate')
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model = build_model(config, method)
    optimizer = torch.optim.Adam(model.parameters(), lr=training['learning_rate'],
                                 weight_decay=training['weight_decay'])
    generator = torch.Generator().manual_seed(training['seed'])
    history, steps, best, start = [], [], None, 1
    if resume is not None:
        payload = load_checkpoint(resume, config=config, method=method)
        model.load_state_dict(payload['model_state'])
        optimizer.load_state_dict(payload['optimizer_state'])
        generator.set_state(payload['generator_state'])
        history, best, start = payload['history'], payload['best'], payload['epoch']+1
        log(f'{method}: resumed after epoch {payload["epoch"]}')
    hashes = {}
    for epoch in range(start, training['epochs']+1):
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
            # Whole batch, as in m24: rows without both classes are skipped and counted by the loss.
            result = lambda_pairwise_logistic_loss(model(features).scores, batch.labels, batch.mask,
                                                   batch.page_ids, cutoff=cutoff)
            if not torch.isfinite(result.loss):
                raise TrainingError(f'{method} epoch {epoch} step {step}: nonfinite loss')
            result.loss.backward()
            if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise TrainingError(f'{method} epoch {epoch} step {step}: missing or nonfinite gradient')
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), training['max_grad_norm'])
            optimizer.step()
            losses.append(result.loss.item())
            skipped += result.skipped_queries
            steps.append({'epoch': epoch, 'step': step, 'loss': result.loss.item(),
                          'grad_norm': norm.item(), 'valid_queries': result.valid_queries,
                          'skipped_queries': result.skipped_queries, 'pairs': result.pairs})
        if any(not torch.isfinite(p).all() for p in model.parameters()):
            raise TrainingError(f'{method} epoch {epoch}: nonfinite parameters')
        aggregate, _ = evaluate(predict(model, validation_records, training['batch_size'], cap),
                                validation_records)
        improved = is_better(aggregate[metric], None if best is None else best['value'])
        if improved:
            best = {'epoch': epoch, 'metric': metric, 'value': aggregate[metric]}
        history.append({'epoch': epoch, 'train_loss': sum(losses)/len(losses) if losses else None,
                        'train_steps': len(losses), 'train_skipped_queries': skipped,
                        'seconds': time.perf_counter()-started,
                        **{f'validation_{k}': v for k, v in aggregate.items()}, 'selected': improved})
        state = dict(config=config, method=method, epoch=epoch, model=model, optimizer=optimizer,
                     generator=generator, history=history, best=best)
        hashes['last'] = save_checkpoint(checkpoint_dir/'last.pt', **state)
        if improved:
            hashes['best'] = save_checkpoint(checkpoint_dir/'best.pt', **state)
        log(f'{method} epoch {epoch}: train_loss={history[-1]["train_loss"]} '
            f'validation_{metric}={aggregate[metric]:.6f}{" *" if improved else ""}')
        if epoch == stop_after_epoch:
            break
    return {'model': model, 'history': history, 'steps': steps, 'best': best, 'checkpoint_sha256': hashes}
