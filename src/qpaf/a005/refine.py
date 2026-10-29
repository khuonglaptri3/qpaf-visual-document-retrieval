"""A005-R1 refined training: small epsilon, 40 epochs with cosine LR, weight averaging over epochs 20–40.

Same model, features, loss and units as A005 Stage 4; only the schedule, epsilon and the way the final
model is formed change. Nothing here selects an epoch for the main model (best-epoch is kept only as an
ablation). Checkpoints and `result.json` are create-once; confirmation labels are never read.
"""
import copy
import math
from pathlib import Path
import time

from qpaf.m24.dataset import iter_batches
from qpaf.m24.trainer import TrainingError
from qpaf.m43.freeze import git, read, sha, write_json

from .stage2 import CACHE_FILES, split_inputs
from .stage4 import GRANULARITIES, QUERY_LENGTH_CAP, SEEDS, STAGE3, per_query_ndcg, validation_scores
from .trainer import BUDGET, document_listwise_loss, validation_metric

ROOT_DIR = 'evidence/revisions/a005-r1-001'
CONFIG = {'anchor': 'stage4_anchor_weights', 'epsilon': 1e-6, 'epochs': 40, 'average_from': 20,
          'learning_rate': BUDGET['learning_rate'], 'lr_schedule': 'cosine', 'weight_decay': BUDGET['weight_decay'],
          'max_grad_norm': BUDGET['max_grad_norm'], 'batch_size': BUDGET['batch_size'],
          'query_length_cap': QUERY_LENGTH_CAP}
VARIANTS = ('full', 'eps1e3', 'constlr')
OVERRIDES = {'full': {}, 'eps1e3': {'epsilon': 1e-3}, 'constlr': {'lr_schedule': 'constant'}}
NAME = {'query': 'qarf-sa-r1', 'page': 'qpaf-sa-r1'}


class RefineError(ValueError):
    """An input or stored record violates the A005-R1 contract."""


def require(ok, message):
    if not ok:
        raise RefineError(message)


def variant_config(variant):
    require(variant in VARIANTS, f'unknown variant: {variant}')
    return {**CONFIG, **OVERRIDES[variant]}


def cosine_lr(epoch, epochs=CONFIG['epochs']):
    """lr_e = 0.01·½(1+cos(π(e−1)/E)) for e = 1..E."""
    return CONFIG['learning_rate']*0.5*(1+math.cos(math.pi*(epoch-1)/epochs))


def build_model(anchor, granularity, seed, epsilon):
    """Deterministic and identical for both granularities; the zero init leaves no seed dependence."""
    import torch
    from .model import AnchoredFusionGate
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        return AnchoredFusionGate(anchor, granularity, epsilon=epsilon)


def train_refined(anchor, granularity, seed, train_records, validation_records, *, query_length_cap,
                  train_relevant_documents, validation_relevant_documents, variant='full', epochs=None,
                  average_from=None, on_epoch=None, log=print):
    """Train one seed. `epochs`, `average_from` and `on_epoch` exist for tests; the runner never sets them."""
    import torch
    from qpaf.m12.features import build_features
    if not train_records or not validation_records:
        raise TrainingError('Training and validation records are both required')
    config = variant_config(variant)
    config['epochs'] = epochs = config['epochs'] if epochs is None else epochs
    config['average_from'] = average_from = config['average_from'] if average_from is None else average_from
    require(1 <= average_from <= epochs, 'average_from must lie within the epochs')
    model = build_model(anchor, granularity, seed, config['epsilon'])
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'], weight_decay=config['weight_decay'])
    generator = torch.Generator().manual_seed(seed)
    value = validation_metric(model, validation_records, query_length_cap, validation_relevant_documents)
    best = {'epoch': 0, 'value': value, 'state': copy.deepcopy(model.state_dict())}
    history = [{'epoch': 0, 'lr': None, 'train_loss': None, 'validation_ndcg_at_10': value,
                'tau': math.exp(model.loss_log_tau().item())}]
    total, count = {}, 0
    for epoch in range(1, epochs+1):
        started, losses = time.perf_counter(), []
        lr = cosine_lr(epoch, epochs) if config['lr_schedule'] == 'cosine' else config['learning_rate']
        for group in optimizer.param_groups:
            group['lr'] = lr
        model.train()
        for batch in iter_batches(train_records, config['batch_size'], generator):
            features = build_features(batch.raw_scores, batch.texts, batch.page_ids, batch.mask,
                                      query_length_cap=query_length_cap)
            scores = model(features).scores
            loss, valid = document_listwise_loss(scores, batch, train_relevant_documents, model.loss_log_tau())
            if not valid:
                continue
            if not torch.isfinite(loss):
                raise TrainingError(f'{granularity} epoch {epoch}: nonfinite loss')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise TrainingError(f'{granularity} epoch {epoch}: nonfinite gradient')
            torch.nn.utils.clip_grad_norm_(model.parameters(), config['max_grad_norm'])
            optimizer.step()
            losses.append(loss.item())
        if any(not torch.isfinite(p).all() for p in model.parameters()):
            raise TrainingError(f'{granularity} epoch {epoch}: nonfinite parameters')
        if epoch >= average_from:
            for name, parameter in model.named_parameters():
                total[name] = total.get(name, 0)+parameter.detach().clone()
            count += 1
            if on_epoch is not None:
                on_epoch(epoch, copy.deepcopy(model))
        value = validation_metric(model, validation_records, query_length_cap, validation_relevant_documents)
        if value > best['value']:
            best = {'epoch': epoch, 'value': value, 'state': copy.deepcopy(model.state_dict())}
        history.append({'epoch': epoch, 'lr': lr, 'train_loss': sum(losses)/len(losses) if losses else None,
                        'validation_ndcg_at_10': value, 'tau': math.exp(model.loss_log_tau().item()),
                        'seconds': time.perf_counter()-started})
        log(f'{granularity}-SA-R1 {variant} epoch {epoch}: lr {lr:.6f} validation nDCG@10 {value:.6f}')
    averaged = build_model(anchor, granularity, seed, config['epsilon'])
    state = averaged.state_dict()
    for name, summed in total.items():
        state[name] = summed/count
    averaged.load_state_dict(state)
    best_model = build_model(anchor, granularity, seed, config['epsilon'])
    best_model.load_state_dict(best['state'])
    return {'averaged_model': averaged.eval(), 'best_epoch_model': best_model.eval(), 'best_epoch': best['epoch'],
            'best_value': best['value'], 'history': history, 'config': config}


def run_dir(root, variant, granularity, seed):
    return Path(root)/ROOT_DIR/'runs'/f'{variant}-{NAME[granularity]}-{seed}'


def load_model(path, anchor, granularity, epsilon):
    import torch
    model = build_model(anchor, granularity, 0, epsilon)
    model.load_state_dict(torch.load(path, weights_only=True))
    return model.eval()


def create_run(root, cache, variant, granularity, seed, log=print, **overrides):
    """One create-once run directory: averaged.pt, best_epoch.pt and result.json. `overrides` are test-only."""
    import torch
    root = Path(root).resolve()
    require(variant in VARIANTS and granularity in GRANULARITIES and seed in SEEDS, 'unknown run')
    directory = run_dir(root, variant, granularity, seed)
    require(not (directory/'result.json').exists(), f'run already recorded: {directory.name}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'), 'training requires a clean tracked tree')
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    anchor = read(root/STAGE3)['stage4_anchor_weights']
    train_records, train_qrels = split_inputs(root, cache, 'train')
    validation_records, validation_qrels = split_inputs(root, cache, 'validation')
    result = train_refined(anchor, granularity, seed, train_records, validation_records,
                           query_length_cap=QUERY_LENGTH_CAP, train_relevant_documents=train_qrels,
                           validation_relevant_documents=validation_qrels, variant=variant, log=log, **overrides)
    directory.mkdir(parents=True, exist_ok=True)
    validation, checkpoints = {}, {}
    for key, file in (('averaged', 'averaged.pt'), ('best_epoch_model', 'best_epoch.pt')):
        model = result['averaged_model' if key == 'averaged' else 'best_epoch_model']
        require(all(torch.isfinite(p).all() for p in model.parameters()), f'{key}: nonfinite parameters')
        require(not (directory/file).exists(), f'checkpoint already exists: {file}')
        torch.save(model.state_dict(), directory/file)
        per_query = per_query_ndcg(validation_scores(model, validation_records), validation_records, validation_qrels)
        validation[key] = {'ndcg_at_10': sum(per_query.values())/len(per_query), 'per_query': per_query}
        checkpoints[file] = sha(directory/file)
    record = {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': 'R1',
              'experiment_id': f'QPAF-A005-R1-{directory.name}', 'variant': variant, 'granularity': granularity,
              'seed': seed, 'anchor_weights': anchor, 'config': result['config'], 'history': result['history'],
              'best_epoch': result['best_epoch'], 'validation': validation, 'checkpoint_sha256': checkpoints,
              'inputs_sha256': {name: sha(Path(cache)/name) for name in CACHE_FILES},
              'stage3_sha256': sha(root/STAGE3), 'source_commit': git(root, 'rev-parse', 'HEAD'),
              'post_hoc': True, 'confirmation_labels_opened': False, 'vidoseek_test_accessed': False}
    write_json(directory/'result.json', record)
    return record
