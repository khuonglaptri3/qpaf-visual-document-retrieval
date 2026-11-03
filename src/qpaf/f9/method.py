"""F9: the QPAF gate on three frozen channels, then Qwen3-Reranker-4B on its top-K (docs/feature_lab/F9_gate_rerank.md).

Composes the unchanged lab code behind the sealed held-out results (F9_heldout_vidoseek.md, F9_heldout_vimdoc.md):
the gate is trained as `scripts/lab_heldout.py prepare` trains it, the top-K pages are fused as `seal` fuses them, and
λ is the best constant λ of a pooled labeled table as `scripts/lab_rerank.py` picks it (ties keep the smaller λ).
The reranker itself runs elsewhere (scripts/modal_lab_rerank.py); this module only turns its scores into rankings.
"""
from dataclasses import dataclass

import numpy as np

from qpaf.lab.heldout import RERANKED
from qpaf.lab.rerank import LAMBDAS, TOP_K, fuse_scores, top_of, unit_score
from qpaf.lab.rerank_stack import page_scores, train_gates
from qpaf.lab.train import RECIPE, SEEDS, prepare
from qpaf.lab.variants import load_variant

RERANKER = ('Qwen/Qwen3-Reranker-4B', '22e683669bc0f0bd69640a1354a6d0aebcfeede5')
ROW = 'f9_qpaf_qwen4b'
LAMBDA = {dataset: rows[ROW][1] for dataset, rows in RERANKED.items()}  # pre-registered, from the pooled dev table
BLOCK = 500  # queries prepared at once; bounds memory on the 4.2M ViMDoc candidate rows


@dataclass(frozen=True)
class F9Model:
    anchor: list    # static weights over bm25/dense/visual
    mean: object    # feature standardization of the gate (None when only ranking from stored scores)
    std: object
    gate: object    # trained QPAF LabGate (None when only ranking from stored scores)
    lam: float
    seed: int
    top_k: int = TOP_K
    recipe: dict = None


def fit(dev_queries, lam, *, seed=SEEDS[0], recipe=RECIPE, log=print):
    """Train the baseline QPAF gate on the dev queries exactly as `scripts/lab_heldout.py prepare` does."""
    recipe = {**RECIPE, **recipe}
    train = prepare(dev_queries, load_variant('baseline'), recipe['query_length_cap'])
    anchor, mean, std, models = train_gates(train, seed, recipe=recipe, log=log)
    return F9Model(anchor, mean, std, models['qpaf'], lam, seed, TOP_K, recipe)


def first_stage(model, queries, block=BLOCK):
    """QPAF page scores aligned with each query's page_ids, prepared in blocks as in `prepare`."""
    variant, scores = load_variant('baseline'), []
    recipe = model.recipe or RECIPE
    for start in range(0, len(queries), block):
        items = prepare(queries[start:start+block], variant, recipe['query_length_cap'])
        scores += page_scores(model.gate, items, model.mean, model.std)
    return scores


def pairs(queries, first, k=TOP_K):
    """[query_id, page_id] of each query's top-k pages under the first stage, in page order."""
    return [[q.query_id, q.page_ids[i]] for q, scores in zip(queries, first)
            for i in sorted(int(i) for i in top_of(scores, k))]


def rerank_score(rerank, q, i):
    """Reranker score of page i of query q; strict, a missing pair is an error and never a default."""
    try:
        return rerank[(q.query_id, q.page_ids[i])]
    except KeyError:
        raise KeyError(f'no reranker score for query {q.query_id}, page {q.page_ids[i]}') from None


def top_scores(q, first_row, rerank, k=TOP_K):
    """{page index: reranker score} of the query's top-k pages under the first stage."""
    return {int(i): rerank_score(rerank, q, i) for i in top_of(first_row, k)}


def final_scores(first, rerank_by_index, lam, k=TOP_K):
    """Page scores of one query: 2 + (1−λ)·minmax(gate) + λ·minmax(rerank) on the top-k, the gate score elsewhere."""
    return fuse_scores(first, rerank_by_index, lam, k)


def rank(model, queries, first, rerank):
    """Final page scores per query from the first stage and a {(query_id, page_id): score} reranker table."""
    return [final_scores(row, top_scores(q, row, rerank, model.top_k), model.lam, model.top_k)
            for q, row in zip(queries, first)]


def lambda_table(queries, first, rerank, lambdas=LAMBDAS, k=TOP_K):
    """[queries, len(lambdas)] unit nDCG@10 of the constant-λ interpolation on each query's first-stage scores."""
    table = np.zeros((len(queries), len(lambdas)))
    for row, (q, scores) in enumerate(zip(queries, first)):
        by_index = top_scores(q, scores, rerank, k)
        table[row] = [unit_score(q, final_scores(scores, by_index, lam, k)) for lam in lambdas]
    return table


def fit_lambda(queries, first, rerank, lambdas=LAMBDAS, k=TOP_K):
    """Best constant λ on a labeled pooled table (lab_rerank.best_lambda); ties keep the smaller λ."""
    total = lambda_table(queries, first, rerank, lambdas, k).sum(axis=0)
    return lambdas[max(range(len(lambdas)), key=lambda i: (total[i], -i))]
