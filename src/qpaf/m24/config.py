"""Strict pipeline config; method-core sections keep the M1.2 contract."""
import math
from pathlib import Path
import tomllib

METHODS = {'QARF': 'query', 'QPAF': 'page'}
METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')


def load_config(path):
    with Path(path).open('rb') as stream:
        config = tomllib.load(stream)
    validate(config)
    return config


def validate(config):
    sections = {
        'data': {'schema', 'max_candidates', 'positive_threshold'},
        'features': {'schema', 'query_length_cap'},
        'gate': {'kind', 'hidden_dim', 'temperature'},
        'loss': {'name', 'reduction'},
        'training': {'seed', 'epochs', 'batch_size', 'optimizer', 'learning_rate',
                     'weight_decay', 'max_grad_norm'},
        'evaluation': {'selection_metric', 'reload_tolerance'},
    }
    if not isinstance(config, dict) or set(config) != {'schema_version', 'experiment_id', *sections}:
        raise ValueError('Missing or unknown M2.4 config section')
    if type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise ValueError('Unsupported M2.4 schema_version')
    if not isinstance(config['experiment_id'], str) or not config['experiment_id'].strip():
        raise ValueError('experiment_id must be a nonempty string')
    for name, keys in sections.items():
        if not isinstance(config[name], dict) or set(config[name]) != keys:
            raise ValueError(f'Missing or unknown config field in {name}')
    for section, key in [('data', 'max_candidates'), ('data', 'positive_threshold'),
                         ('features', 'query_length_cap'), ('gate', 'hidden_dim'),
                         ('training', 'epochs'), ('training', 'batch_size')]:
        value = config[section][key]
        if type(value) is not int or value < 1:
            raise ValueError(f'{section}.{key} must be a positive integer')
    seed = config['training']['seed']
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('training.seed must be an integer in [0, 2**32)')
    for section, key, minimum in [('gate', 'temperature', 0), ('training', 'learning_rate', 0),
                                  ('training', 'max_grad_norm', 0), ('evaluation', 'reload_tolerance', 0)]:
        value = config[section][key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= minimum:
            raise ValueError(f'{section}.{key} must be finite and positive')
    decay = config['training']['weight_decay']
    if type(decay) not in (int, float) or not math.isfinite(decay) or decay < 0:
        raise ValueError('training.weight_decay must be finite and nonnegative')
    if config['data']['schema'] != 'qpaf_score_rows_v1':
        raise ValueError('Unsupported score-row schema')
    if config['features']['schema'] != 'qpaf13_v1':
        raise ValueError('Unsupported feature schema')
    if config['gate']['kind'] not in ('linear', 'mlp'):
        raise ValueError('gate.kind must be linear or mlp')
    if config['loss'] != {'name': 'pairwise_logistic', 'reduction': 'query_mean'}:
        raise ValueError('Only query-mean pairwise logistic loss is implemented')
    if config['training']['optimizer'] != 'adam':
        raise ValueError('Only the adam optimizer is implemented')
    if config['evaluation']['selection_metric'] not in METRICS:
        raise ValueError(f'selection_metric must be one of {METRICS}')
