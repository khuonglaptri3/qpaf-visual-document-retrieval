"""Feature-lab cross-validation: per-fold static anchor, R1 training recipe, out-of-fold unit nDCG@10.

Every development query is scored exactly once, by models that never saw its labels. The recipe is
A005-R1 (cosine LR, weight averaging over the second half of training, no epoch selection), so no
validation set is needed inside a fold and nothing is selected on the queries being scored.
"""
from dataclasses import dataclass
import math
import time

import numpy as np
import torch

from qpaf.m12.features import FEATURE_NAMES, build_features
from qpaf.m46.probe import grid_points

from .data import fold_of
from .model import LabGate, listwise_loss, max_pool, unit_max, unit_ndcg

RECIPE = {'epochs': 40, 'average_from': 20, 'learning_rate': 0.01, 'weight_decay': 0., 'batch_size': 16,
          'max_grad_norm': 5., 'epsilon': 1e-6, 'query_length_cap': 64}
SEEDS = (20260820, 20260821, 20260822)
METHOD = {'query': 'qarf', 'page': 'qpaf'}


class LabTrainingError(RuntimeError):
    """Training produced a non-finite value or an input broke the harness contract."""


@dataclass(frozen=True)
class Prepared:
    query: object       # data.LabQuery
    base: np.ndarray    # [pages, 13] M1.2 features
    norm: np.ndarray    # [pages, 3] per-query min-max scores
    extra: np.ndarray   # [pages, k] variant features, unstandardized


def prepare(queries, variant, query_length_cap=RECIPE['query_length_cap']):
    """Base features once per query, plus the variant's label-free extra features."""
    prepared, width = [], None
    for q in queries:
        batch = build_features(torch.as_tensor(q.raw[None]), [q.text], [list(q.page_ids)],
                               query_length_cap=query_length_cap)
        extra = np.zeros((len(q.page_ids), 0))
        if variant.page_features is not None:
            extra = np.asarray(variant.page_features(q.query_id, q.text, q.page_ids, q.raw.copy()), dtype=np.float64)
        if extra.ndim != 2 or extra.shape[0] != len(q.page_ids) or not np.isfinite(extra).all():
            raise LabTrainingError(f'{variant.name}: page_features must return finite [pages, k] for {q.query_id}')
        if width not in (None, extra.shape[1]):
            raise LabTrainingError(f'{variant.name}: page_features width changed at {q.query_id}')
        width = extra.shape[1]
        prepared.append(Prepared(q, batch.values[0].numpy(), batch.scores[0].numpy(), extra))
    return prepared


def fit_anchor(items):
    """Train-fold static weights over the 66-point grid; ties keep the earlier grid point (A005 rule)."""
    grid = np.asarray(grid_points())
    total = np.zeros(len(grid))
    for item in items:
        q = item.query
        total += unit_ndcg(unit_max(item.norm@grid.T, q.units, len(q.unit_ids)), q.positive, q.relevant_total)
    best = max(range(len(grid)), key=lambda i: (total[i], -i))
    return grid[best].tolist()


def standardizer(items):
    """Mean/std of the extra features over the training fold's pages; a constant column keeps std 1."""
    if not items or items[0].extra.shape[1] == 0:
        return np.zeros(0), np.ones(0)
    stacked = np.concatenate([item.extra for item in items])
    std = stacked.std(axis=0)
    return stacked.mean(axis=0), np.where(std > 1e-12, std, 1.)


def gate_inputs(items, mean, std):
    return [torch.from_numpy(np.concatenate([item.base, (item.extra-mean)/std], axis=1)) for item in items]


def collate(items, inputs):
    """Padded tensors; padded pages point at a dummy last unit that unit_mask excludes."""
    width = max(len(item.query.page_ids) for item in items)
    unit_count = max(len(item.query.unit_ids) for item in items)+1
    batch = {'features': torch.zeros((len(items), width, inputs[0].shape[1]), dtype=torch.float64),
             'scores': torch.zeros((len(items), width, 3), dtype=torch.float64),
             'mask': torch.zeros((len(items), width), dtype=torch.bool),
             'units': torch.full((len(items), width), unit_count-1, dtype=torch.long),
             'unit_mask': torch.zeros((len(items), unit_count), dtype=torch.bool),
             'positive': torch.zeros((len(items), unit_count), dtype=torch.bool), 'unit_count': unit_count}
    for row, (item, x) in enumerate(zip(items, inputs)):
        n, u = len(item.query.page_ids), len(item.query.unit_ids)
        batch['features'][row, :n] = x
        batch['scores'][row, :n] = torch.from_numpy(item.norm)
        batch['mask'][row, :n] = True
        batch['units'][row, :n] = torch.from_numpy(item.query.units)
        batch['unit_mask'][row, :u] = True
        batch['positive'][row, :u] = torch.from_numpy(item.query.positive)
    return batch


def cosine_lr(epoch, recipe):
    return recipe['learning_rate']*0.5*(1+math.cos(math.pi*(epoch-1)/recipe['epochs']))


def build_model(anchor, granularity, feature_dim, variant, seed, recipe):
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        calibrator = variant.calibrator() if variant.calibrator is not None else None
        return LabGate(anchor, granularity, feature_dim, hidden=variant.hidden, calibrator=calibrator,
                       epsilon=recipe['epsilon'])


def train_model(items, inputs, anchor, granularity, variant, seed, recipe=RECIPE, log=print):
    """One model on one training fold; returns the average of the parameters over epochs average_from..epochs."""
    model = build_model(anchor, granularity, inputs[0].shape[1], variant, seed, recipe)
    optimizer = torch.optim.Adam(model.parameters(), lr=recipe['learning_rate'], weight_decay=recipe['weight_decay'])
    generator = torch.Generator().manual_seed(seed)
    loss_fn, aggregate = variant.loss or listwise_loss, variant.aggregate or max_pool
    anchor_weights = torch.as_tensor(anchor, dtype=torch.float64)
    total, count = {}, 0
    for epoch in range(1, recipe['epochs']+1):
        for group in optimizer.param_groups:
            group['lr'] = cosine_lr(epoch, recipe)
        model.train()
        losses = []
        order = torch.randperm(len(items), generator=generator).tolist()
        for start in range(0, len(order), recipe['batch_size']):
            chosen = order[start:start+recipe['batch_size']]
            batch = collate([items[i] for i in chosen], [inputs[i] for i in chosen])
            page_scores, _ = model(batch['features'], batch['scores'], batch['mask'])
            unit_scores = aggregate(page_scores, batch['units'], batch['unit_count'])
            with torch.no_grad():
                static = torch.where(batch['mask'], batch['scores']@anchor_weights, 0.)
                anchor_scores = aggregate(static, batch['units'], batch['unit_count'])
            loss, valid = loss_fn(unit_scores, batch['unit_mask'], batch['positive'], model.loss_log_tau(),
                                  anchor_scores)
            if not valid:
                continue
            if not torch.isfinite(loss):
                raise LabTrainingError(f'{variant.name} {granularity} epoch {epoch}: nonfinite loss')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), recipe['max_grad_norm'])
            optimizer.step()
            losses.append(loss.item())
        if any(not torch.isfinite(p).all() for p in model.parameters()):
            raise LabTrainingError(f'{variant.name} {granularity} epoch {epoch}: nonfinite parameters')
        if epoch >= recipe['average_from']:
            for name, parameter in model.named_parameters():
                total[name] = total.get(name, 0)+parameter.detach().clone()
            count += 1
        if epoch % 10 == 0 or epoch == recipe['epochs']:
            log(f'  {variant.name} {METHOD[granularity]} seed {seed} epoch {epoch}: '
                f'loss {sum(losses)/max(len(losses), 1):.5f}')
    averaged = build_model(anchor, granularity, inputs[0].shape[1], variant, seed, recipe)
    state = averaged.state_dict()
    for name, summed in total.items():
        state[name] = summed/count
    averaged.load_state_dict(state)
    return averaged.eval()


def score_units(model, items, inputs, variant, batch_size=64):
    """Per-query unit scores [units] of the trained model."""
    aggregate, out = variant.aggregate or max_pool, []
    with torch.no_grad():
        for start in range(0, len(items), batch_size):
            batch = collate(items[start:start+batch_size], inputs[start:start+batch_size])
            page_scores, _ = model(batch['features'], batch['scores'], batch['mask'])
            unit_scores = aggregate(page_scores, batch['units'], batch['unit_count'])
            out += [unit_scores[row, :len(item.query.unit_ids)].numpy()
                    for row, item in enumerate(items[start:start+batch_size])]
    return out


def run_experiment(queries, variant, *, granularities=('query', 'page'), seeds=SEEDS[:1], folds=5,
                   recipe=RECIPE, log=print):
    """Out-of-fold per-query nDCG@10 for the fold static anchor and each trained granularity."""
    started = time.perf_counter()
    recipe = {**RECIPE, **recipe}
    prepared = prepare(queries, variant, recipe['query_length_cap'])
    fold = [fold_of(item.query.query_id, folds) for item in prepared]
    per_seed = {METHOD[g]: {str(s): {} for s in seeds} for g in granularities}
    static, anchors, sizes = {}, [], []
    for k in range(folds):
        train = [item for item, f in zip(prepared, fold) if f != k]
        held = [item for item, f in zip(prepared, fold) if f == k]
        if not train or not held:
            raise LabTrainingError(f'fold {k} is empty; use fewer folds')
        anchor = fit_anchor(train)
        anchors.append(anchor)
        sizes.append(len(held))
        log(f'fold {k}: {len(train)} train / {len(held)} held-out queries, anchor {anchor}')
        for item in held:
            q = item.query
            static[q.query_id] = unit_ndcg(unit_max(item.norm@np.asarray(anchor), q.units, len(q.unit_ids)),
                                           q.positive, q.relevant_total)
        mean, std = standardizer(train)
        train_inputs, held_inputs = gate_inputs(train, mean, std), gate_inputs(held, mean, std)
        for granularity in granularities:
            for seed in seeds:
                model = train_model(train, train_inputs, anchor, granularity, variant, seed, recipe, log)
                for item, scores in zip(held, score_units(model, held, held_inputs, variant)):
                    per_seed[METHOD[granularity]][str(seed)][item.query.query_id] = unit_ndcg(
                        scores, item.query.positive, item.query.relevant_total)
    per_query = {'static': static}
    for method, by_seed in per_seed.items():
        per_query[method] = {q: float(np.mean([by_seed[s][q] for s in by_seed])) for q in static}
    return {'variant': variant.name, 'hidden': variant.hidden, 'folds': folds, 'fold_sizes': sizes,
            'fold_anchors': anchors, 'seeds': list(seeds), 'granularities': list(granularities),
            'recipe': recipe, 'feature_dim': len(FEATURE_NAMES)+prepared[0].extra.shape[1],
            'queries': len(prepared), 'queries_without_positive': sum(not i.query.positive.any() for i in prepared),
            'mean': {m: float(np.mean(list(v.values()))) for m, v in per_query.items()},
            'per_query': per_query, 'per_seed': per_seed, 'seconds': time.perf_counter()-started}
