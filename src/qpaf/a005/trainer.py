"""A005 Stage 4 trainer: anchored gate, listwise loss, selection over epochs 0–20 (A005 §2.3).

Budget and optimizer match v1 (A005 §2.5). Units are pages or, for ViMDoc,
documents (max fused page score). Validation labels enter only selection.
Checkpoint files, manifests and authorization checks belong to the Stage 4
runner; this module only trains and selects.
"""
import copy
import math
import time

from qpaf.m24.dataset import iter_batches
from qpaf.m24.evaluator import evaluate, predict
from qpaf.m24.trainer import TrainingError, learnable

from .losses import listwise_loss
from .model import AnchoredFusionGate, document_metrics, document_scores

BUDGET = {'learning_rate': 0.01, 'weight_decay': 0., 'max_grad_norm': 5., 'batch_size': 16, 'epochs': 20}


def build_model(anchor, granularity, seed):
    """Deterministic and identical for QARF-SA and QPAF-SA; the zero init leaves no seed dependence."""
    import torch
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        return AnchoredFusionGate(anchor, granularity)


def document_listwise_loss(scores, batch, relevant_documents, log_tau):
    """Query-mean listwise loss on documents; queries without a relevant and an irrelevant document are skipped."""
    import torch
    terms = []
    tau = torch.exp(log_tau)
    for row, query_id in enumerate(batch.query_ids):
        count = int(batch.mask[row].sum())
        documents, doc_scores = document_scores(scores[row, :count], batch.page_ids[row][:count])
        positive = torch.tensor([d in relevant_documents[query_id] for d in documents])
        if positive.all() or not positive.any():
            continue
        logits = doc_scores/tau
        terms.append(torch.logsumexp(logits, 0)-torch.logsumexp(logits[positive], 0))
    if not terms:
        return scores.new_zeros(()), 0
    return torch.stack(terms).mean(), len(terms)


def validation_metric(model, records, cap, relevant_documents=None):
    """Mean nDCG@10 on pages, or on documents when relevant_documents is given."""
    predictions = predict(model, records, BUDGET['batch_size'], cap)
    if relevant_documents is None:
        return evaluate(predictions, records)[0]['ndcg_at_10']
    values = [document_metrics(p['page_ids'], p['scores'], relevant_documents[p['query_id']])['ndcg_at_10']
              for p in predictions]
    return sum(values)/len(values)


def train(anchor, granularity, seed, train_records, validation_records, *, query_length_cap,
          train_relevant_documents=None, validation_relevant_documents=None, epochs=None, log=print):
    """Train one seed; epoch 0 (the anchor) competes in selection and later epochs must be strictly better."""
    import torch
    from qpaf.m12.features import build_features
    if not train_records or not validation_records:
        raise TrainingError('Training and validation records are both required')
    epochs = BUDGET['epochs'] if epochs is None else epochs
    model = build_model(anchor, granularity, seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=BUDGET['learning_rate'],
                                 weight_decay=BUDGET['weight_decay'])
    generator = torch.Generator().manual_seed(seed)
    value = validation_metric(model, validation_records, query_length_cap, validation_relevant_documents)
    best = {'epoch': 0, 'value': value, 'state': copy.deepcopy(model.state_dict())}
    history = [{'epoch': 0, 'train_loss': None, 'validation_ndcg_at_10': value, 'selected': True}]
    for epoch in range(1, epochs+1):
        started, losses = time.perf_counter(), []
        model.train()
        for batch in iter_batches(train_records, BUDGET['batch_size'], generator):
            features = build_features(batch.raw_scores, batch.texts, batch.page_ids, batch.mask,
                                      query_length_cap=query_length_cap)
            scores = model(features).scores
            if train_relevant_documents is None:
                if not learnable(batch.labels, batch.mask).any():
                    continue
                loss, valid = listwise_loss(scores, batch.labels, batch.mask, model.loss_log_tau())
            else:
                loss, valid = document_listwise_loss(scores, batch, train_relevant_documents, model.loss_log_tau())
            if not valid:
                continue
            if not torch.isfinite(loss):
                raise TrainingError(f'{granularity} epoch {epoch}: nonfinite loss')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise TrainingError(f'{granularity} epoch {epoch}: nonfinite gradient')
            torch.nn.utils.clip_grad_norm_(model.parameters(), BUDGET['max_grad_norm'])
            optimizer.step()
            losses.append(loss.item())
        if any(not torch.isfinite(p).all() for p in model.parameters()):
            raise TrainingError(f'{granularity} epoch {epoch}: nonfinite parameters')
        value = validation_metric(model, validation_records, query_length_cap, validation_relevant_documents)
        improved = value > best['value']
        if improved:
            best = {'epoch': epoch, 'value': value, 'state': copy.deepcopy(model.state_dict())}
        history.append({'epoch': epoch, 'train_loss': sum(losses)/len(losses) if losses else None,
                        'validation_ndcg_at_10': value, 'selected': improved,
                        'tau': math.exp(model.loss_log_tau().item()), 'seconds': time.perf_counter()-started})
        log(f'{granularity}-SA epoch {epoch}: validation nDCG@10 {value:.6f}{" *" if improved else ""}')
    model.load_state_dict(best['state'])
    return {'model': model, 'best_epoch': best['epoch'], 'best_value': best['value'], 'history': history}
