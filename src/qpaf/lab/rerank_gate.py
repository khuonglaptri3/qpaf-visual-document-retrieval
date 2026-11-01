"""F6: a learned, anchored λ for the F5 interpolation, per query (QARF-λ) or per page (QPAF-λ) (docs/feature_lab/F6).

λ = sigmoid(logit(λ0) + Δθ(x)), Δθ linear and zero-initialized, λ0 the train-fold best constant λ of F5, so every
model scores exactly like F5 at initialization. Inputs are label-free: query-level confidence of the static
fusion and of the reranker, plus (QPAF) the page's own scores, ranks and OCR. Training is the lab recipe
(qpaf.lab.train.RECIPE) with the lab listwise loss over the units of the top-K pages; units outside the top-K
always rank below and cannot change, so they are left out of the loss.
"""
import math

import numpy as np
import torch
from torch import nn

from qpaf.a005.losses import LOG_TAU_BOUNDS

from .model import listwise_loss
from .rerank import TOP_K, minmax, top_pages
from .train import RECIPE, cosine_lr

QUERY_FEATURES = ('fused_margin', 'rerank_max', 'rerank_margin', 'rerank_agrees_top1', 'rerank_std', 'log_query_words')
PAGE_FEATURES = ('rerank_raw', 'rerank_norm', 'fused_norm', 'fused_rank', 'rerank_rank', 'ocr_empty', 'log_ocr_chars')
LAMBDA_CLAMP = (0.05, 0.95)


def query_tensors(q, anchor, rerank, page_text, k=TOP_K):
    """Fixed-size arrays for one query: top-k fused/rerank values, features, local units and positives."""
    fused = minmax(q.raw)@np.asarray(anchor)
    top = top_pages(q, anchor, k)
    raw = np.array([rerank[q.query_id][q.page_ids[i]] for i in top])
    order = np.argsort(-raw, kind='stable')
    by_rerank = np.empty(len(top))
    by_rerank[order] = np.arange(len(top))
    query = [fused[top[0]]-fused[top[1]], raw.max(), raw[order[0]]-raw[order[1]], float(order[0] == 0), raw.std(),
             math.log1p(len(q.text.split()))]
    chars = np.array([len(page_text[q.page_ids[i]].strip()) for i in top])
    page = np.stack([raw, minmax(raw), minmax(fused[top]), np.arange(len(top))/len(top), by_rerank/len(top),
                     (chars == 0).astype(float), np.log1p(chars)], axis=1)
    units = q.units[top]
    local = {u: j for j, u in enumerate(dict.fromkeys(units.tolist()))}
    return {'f': minmax(fused[top]), 'r': minmax(raw), 'x': np.concatenate([np.tile(query, (len(top), 1)), page], 1),
            'units': np.array([local[u] for u in units.tolist()]), 'positive': q.positive[list(local)],
            'unit_count': len(local)}


class LambdaGate(nn.Module):
    def __init__(self, lambda0, feature_dim):
        super().__init__()
        lam = min(max(lambda0, LAMBDA_CLAMP[0]), LAMBDA_CLAMP[1])
        self.register_buffer('base', torch.tensor(math.log(lam/(1-lam)), dtype=torch.float64))
        self.delta = nn.Linear(feature_dim, 1, dtype=torch.float64)
        nn.init.zeros_(self.delta.weight)
        nn.init.zeros_(self.delta.bias)
        self.log_tau = nn.Parameter(torch.zeros((), dtype=torch.float64))

    def forward(self, x):
        return torch.sigmoid(self.base+self.delta(x).squeeze(-1))


def stack(items, columns, mean, std):
    x = torch.from_numpy(np.stack([(it['x'][:, columns]-mean)/std for it in items]))
    f = torch.from_numpy(np.stack([it['f'] for it in items]))
    r = torch.from_numpy(np.stack([it['r'] for it in items]))
    units = torch.from_numpy(np.stack([it['units'] for it in items]))
    positive = torch.zeros((len(items), TOP_K), dtype=torch.bool)
    unit_mask = torch.zeros((len(items), TOP_K), dtype=torch.bool)
    for row, it in enumerate(items):
        positive[row, :it['unit_count']] = torch.from_numpy(it['positive'])
        unit_mask[row, :it['unit_count']] = True
    return x, f, r, units, positive, unit_mask


def unit_scores(lam, f, r, units):
    page = (1-lam)*f+lam*r
    return page.new_full((page.shape[0], TOP_K), -1.).scatter_reduce(1, units, page, reduce='amax', include_self=False)


def columns_for(granularity):
    width = len(QUERY_FEATURES)+len(PAGE_FEATURES)
    return list(range(len(QUERY_FEATURES))) if granularity == 'query' else list(range(width))


def train_gate(items, lambda0, granularity, seed, recipe=RECIPE):
    """Averaged gate over epochs average_from..epochs, plus the train-fold feature mean/std it expects."""
    columns = columns_for(granularity)
    stacked = np.concatenate([it['x'][:, columns] for it in items])
    mean, std = stacked.mean(0), stacked.std(0)
    std = np.where(std > 1e-12, std, 1.)
    x, f, r, units, positive, unit_mask = stack(items, columns, mean, std)
    torch.manual_seed(seed)
    model = LambdaGate(lambda0, len(columns))
    optimizer = torch.optim.Adam(model.parameters(), lr=recipe['learning_rate'], weight_decay=recipe['weight_decay'])
    generator = torch.Generator().manual_seed(seed)
    total, count = {}, 0
    for epoch in range(1, recipe['epochs']+1):
        for group in optimizer.param_groups:
            group['lr'] = cosine_lr(epoch, recipe)
        order = torch.randperm(len(items), generator=generator)
        for start in range(0, len(order), recipe['batch_size']):
            b = order[start:start+recipe['batch_size']]
            scores = unit_scores(model(x[b]), f[b], r[b], units[b])
            loss, valid = listwise_loss(scores, unit_mask[b], positive[b], model.log_tau.clamp(*LOG_TAU_BOUNDS))
            if not valid:
                continue
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), recipe['max_grad_norm'])
            optimizer.step()
        if epoch >= recipe['average_from']:
            for name, p in model.named_parameters():
                total[name] = total.get(name, 0)+p.detach().clone()
            count += 1
    averaged = LambdaGate(lambda0, len(columns))
    state = averaged.state_dict()
    state.update({name: value/count for name, value in total.items()})
    averaged.load_state_dict(state)
    return averaged.eval(), columns, mean, std


def page_lambdas(model, columns, mean, std, item):
    """λ for each top-k page of one query, in top_pages order."""
    with torch.no_grad():
        return model(torch.from_numpy((item['x'][:, columns]-mean)/std)).numpy()
