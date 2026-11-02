"""F9: the trained baseline QARF/QPAF gate as the first stage of the F5 reranker (docs/feature_lab/F9).

The gate is trained exactly as `scripts/run_lab.py --variant baseline` trains it (same folds, anchor, recipe,
seed and scoring batches), so the unit nDCG@10 of these page scores reproduces the committed baseline rows.
"""
import numpy as np
import torch

from .data import fold_of
from .train import METHOD, RECIPE, collate, fit_anchor, gate_inputs, prepare, standardizer, train_model
from .variants import load_variant


def gate_page_scores(queries, seed, *, folds=5, recipe=RECIPE, log=print, batch_size=64):
    """Out-of-fold page scores {'qarf'|'qpaf': [array aligned with q.page_ids per query]} and the fold anchors."""
    recipe = {**RECIPE, **recipe}
    variant = load_variant('baseline')
    prepared = prepare(queries, variant, recipe['query_length_cap'])
    fold = [fold_of(q.query_id, folds) for q in queries]
    scores, anchors = {m: [None]*len(queries) for m in METHOD.values()}, []
    for k in range(folds):
        train = [item for item, f in zip(prepared, fold) if f != k]
        rows = [i for i, f in enumerate(fold) if f == k]
        held = [prepared[i] for i in rows]
        anchor = fit_anchor(train)
        anchors.append(anchor)
        mean, std = standardizer(train)
        train_inputs, held_inputs = gate_inputs(train, mean, std), gate_inputs(held, mean, std)
        for granularity, method in METHOD.items():
            model = train_model(train, train_inputs, anchor, granularity, variant, seed, recipe, log)
            with torch.no_grad():  # same batches as train.score_units
                for start in range(0, len(held), batch_size):
                    chunk = held[start:start+batch_size]
                    batch = collate(chunk, held_inputs[start:start+batch_size])
                    page_scores, _ = model(batch['features'], batch['scores'], batch['mask'])
                    for row, item in enumerate(chunk):
                        scores[method][rows[start+row]] = page_scores[row, :len(item.query.page_ids)].numpy().copy()
    return scores, anchors
