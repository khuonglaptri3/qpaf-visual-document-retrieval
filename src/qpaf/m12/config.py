"""Shared method-core configuration; no cloud or model dependencies."""
import math
from pathlib import Path
import tomllib


def load_config(path):
    with Path(path).open('rb') as stream:
        config = tomllib.load(stream)
    validate(config)
    return config


def validate(config):
    sections = {
        'features': {'schema', 'query_length_cap'},
        'gate': {'kind', 'hidden_dim', 'temperature'},
        'loss': {'name', 'reduction'},
        'verification': {'seed', 'steps', 'learning_rate'},
    }
    if not isinstance(config, dict) or set(config) != {'schema_version', *sections}:
        raise ValueError('Missing or unknown method-core config section')
    if type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise ValueError('Unsupported method-core schema_version')
    for name, keys in sections.items():
        if not isinstance(config[name], dict) or set(config[name]) != keys:
            raise ValueError(f'Missing or unknown config field in {name}')
    for section, key in [('features', 'query_length_cap'), ('gate', 'hidden_dim'),
                         ('verification', 'steps')]:
        value = config[section][key]
        if type(value) is not int or value < 1:
            raise ValueError(f'{section}.{key} must be a positive integer')
    seed = config['verification']['seed']
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('verification.seed must be an integer in [0, 2**32)')
    for section, key in [('gate', 'temperature'), ('verification', 'learning_rate')]:
        value = config[section][key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{section}.{key} must be finite and positive')
    if config['features']['schema'] != 'qpaf13_v1':
        raise ValueError('Unsupported feature schema')
    if config['gate']['kind'] not in ('linear', 'mlp'):
        raise ValueError('gate.kind must be linear or mlp')
    if config['loss'] != {'name': 'pairwise_logistic', 'reduction': 'query_mean'}:
        raise ValueError('Only query-mean pairwise logistic loss is implemented')
