"""Fresh-process checkpoint reload for an M5.3 attempt (M5.1: finite outputs, reload difference <= tolerance).

Runs only in a child interpreter started by the supervisor or a reviewer. It reads the development qrels of
the sealed inputs to rebuild the validation records, never the sealed test qrels, and writes nothing.
"""
import json
import math
import os
from pathlib import Path


class ReloadError(ValueError):
    """The reloaded checkpoint does not reproduce the persisted run."""


def require(condition, message):
    if not condition:
        raise ReloadError(message)


def finite_values(value):
    """Count the numbers in a checkpoint payload, rejecting any that is not finite."""
    import torch
    if isinstance(value, torch.Tensor):
        require(bool(torch.isfinite(value).all()), 'non-finite checkpoint tensor')
        return value.numel()
    if isinstance(value, dict):
        return sum(finite_values(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(finite_values(item) for item in value)
    if type(value) in (int, float):
        require(math.isfinite(value), 'non-finite checkpoint number')
        return 1
    return 0


def compare(expected, actual, tolerance):
    """Same queries and candidate pages in order, finite outputs, and scores/weights within tolerance."""
    require(len(expected) == len(actual) and expected, 'reloaded query count differs')
    score_max = weight_max = 0.0
    for saved, fresh in zip(expected, actual):
        require((saved['query_id'], saved['page_ids']) == (fresh['query_id'], fresh['page_ids']),
                'reloaded query or candidate order differs')
        values = [*fresh['scores'], *(w for row in fresh['weights'] for w in row)]
        require(all(math.isfinite(v) for v in values), 'non-finite reloaded output')
        score_max = max(score_max, *(abs(a-b) for a, b in zip(saved['scores'], fresh['scores'])))
        weight_max = max(weight_max, *(abs(a-b) for old, new in zip(saved['weights'], fresh['weights'])
                                       for a, b in zip(old, new)))
    require(score_max <= tolerance, f'reloaded scores differ by {score_max} > {tolerance}')
    require(weight_max <= tolerance, f'reloaded weights differ by {weight_max} > {tolerance}')
    return {'queries': len(actual), 'candidates': sum(len(q['page_ids']) for q in actual),
            'score_max_abs_difference': score_max, 'weight_max_abs_difference': weight_max}


def replay(root, attempt, config_path, method, seal):
    import torch
    from qpaf.m11.artifacts import digest
    from qpaf.m24.checkpoint import load_checkpoint
    from qpaf.m24.config import load_config
    from qpaf.m24.dataset import build_records, read_score_rows, read_split_ids
    from qpaf.m24.evaluator import evaluate, predict
    from qpaf.m24.trainer import build_model

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    root = Path(root)
    attempt, seal = root/attempt, root/seal/'inputs'
    config = load_config(root/config_path)
    summary = json.loads((attempt/'summary.json').read_text(encoding='utf-8'))
    tolerance = config['evaluation']['reload_tolerance']
    checkpoints, values = {}, 0
    for name in ('best', 'last'):
        checkpoints[name] = load_checkpoint(attempt/f'checkpoints/{name}.pt', config=config, method=method,
                                            expected_sha256=summary['checkpoint_sha256'][name])
        values += finite_values(checkpoints[name])
    require(checkpoints['best']['epoch'] == summary['selected_epoch'], 'best checkpoint epoch differs')
    require(checkpoints['last']['epoch'] == config['training']['epochs'], 'last checkpoint epoch differs')
    qrels = json.loads((seal/'qrels_development.json').read_text(encoding='utf-8'))
    records = build_records(read_score_rows(seal/'score_cache.parquet'),
                            json.loads((seal/'query_texts.json').read_text(encoding='utf-8')), qrels,
                            read_split_ids(seal/'splits'), ('validation',),
                            positive_threshold=config['data']['positive_threshold'],
                            max_candidates=config['data']['max_candidates'])['validation']
    model = build_model(config, method)
    model.load_state_dict(checkpoints['best']['model_state'])
    actual = predict(model, records, config['training']['batch_size'], config['features']['query_length_cap'])
    expected = json.loads((attempt/'validation_predictions.json').read_text(encoding='utf-8'))
    report = compare(expected, actual, tolerance)
    metrics, _ = evaluate(actual, records)
    saved = json.loads((attempt/'validation_metrics.json').read_text(encoding='utf-8'))
    require(set(metrics) == set(saved), 'recomputed metric names differ')
    metric_max = max(abs(metrics[k]-saved[k]) for k in saved if isinstance(saved[k], float))
    require(metric_max <= tolerance, f'recomputed validation metrics differ by {metric_max}')
    return {'status': 'PASS', 'method': method, 'worker_pid': os.getpid(), 'parent_pid': os.getppid(),
            'tolerance': tolerance, **report, 'metric_max_abs_difference': metric_max,
            'checkpoint_numbers_checked': values, 'torch': torch.__version__,
            'checkpoint_sha256': {name: digest(attempt/f'checkpoints/{name}.pt') for name in ('best', 'last')}}
