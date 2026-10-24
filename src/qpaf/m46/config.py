"""v2 matched config: the M2.4 contract with only the A004 loss."""
import copy
from pathlib import Path
import tomllib

from qpaf.m24 import config as m24_config

LOSS = {'name': 'lambda_pairwise_logistic', 'reduction': 'query_mean', 'metric_cutoff': 10}
_V1_LOSS = {'name': 'pairwise_logistic', 'reduction': 'query_mean'}


def validate(config):
    if not isinstance(config, dict) or config.get('loss') != LOSS:
        raise ValueError(f'v2 config loss must be exactly {LOSS}')
    # Every other field keeps the M2.4 rules, checked by the frozen validator.
    m24_config.validate({**copy.deepcopy(config), 'loss': dict(_V1_LOSS)})


def load_config(path):
    with Path(path).open('rb') as stream:
        config = tomllib.load(stream)
    validate(config)
    return config
