"""F9: the trained baseline QARF/QPAF gate as the first stage of the F5 reranker (docs/feature_lab/F9).

The gate is trained exactly as `scripts/run_lab.py --variant baseline` trains it (same folds, anchor, recipe,
seed and scoring batches), so the unit nDCG@10 of these page scores reproduces the committed baseline rows.
"""
import torch

from .data import fold_of
from .train import METHOD, RECIPE, collate, fit_anchor, gate_inputs, prepare, standardizer, train_model
from .variants import load_variant


def train_gates(train, seed, *, recipe=RECIPE, log=print):
    """Static anchor, feature standardization and the QARF/QPAF baseline gates fitted on prepared training items."""
    variant = load_variant('baseline')
    anchor = fit_anchor(train)
    mean, std = standardizer(train)
    inputs = gate_inputs(train, mean, std)
    models = {method: train_model(train, inputs, anchor, granularity, variant, seed, recipe, log)
              for granularity, method in METHOD.items()}
    return anchor, mean, std, models


def page_scores(model, items, mean, std, batch_size=64):
    """Page scores aligned with each item's page_ids, in the scoring batches of train.score_units."""
    inputs, out = gate_inputs(items, mean, std), []
    with torch.no_grad():
        for start in range(0, len(items), batch_size):
            chunk = items[start:start+batch_size]
            batch = collate(chunk, inputs[start:start+batch_size])
            scores, _ = model(batch['features'], batch['scores'], batch['mask'])
            out += [scores[row, :len(item.query.page_ids)].numpy().copy() for row, item in enumerate(chunk)]
    return out


def gate_page_scores(queries, seed, *, folds=5, recipe=RECIPE, log=print):
    """Out-of-fold page scores {'qarf'|'qpaf': [array aligned with q.page_ids per query]} and the fold anchors."""
    recipe = {**RECIPE, **recipe}
    prepared = prepare(queries, load_variant('baseline'), recipe['query_length_cap'])
    fold = [fold_of(q.query_id, folds) for q in queries]
    scores, anchors = {m: [None]*len(queries) for m in METHOD.values()}, []
    for k in range(folds):
        train = [item for item, f in zip(prepared, fold) if f != k]
        rows = [i for i, f in enumerate(fold) if f == k]
        anchor, mean, std, models = train_gates(train, seed, recipe=recipe, log=log)
        anchors.append(anchor)
        for method, model in models.items():
            for i, values in zip(rows, page_scores(model, [prepared[i] for i in rows], mean, std)):
                scores[method][i] = values
    return scores, anchors
