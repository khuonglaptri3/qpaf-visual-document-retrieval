"""Frozen M2.7 matched-config manifest: strict loading, resolution and semantic diff."""
import copy
import json
from pathlib import Path
import re

from qpaf.m24.config import load_config, validate

PENDING = 'PENDING_M2.8'
SHA256 = re.compile(r'[0-9a-f]{64}')
KEYS = {'schema_version', 'task_id', 'experiment_id', 'base_config', 'methods', 'allowed_semantic_diff',
        'seeds', 'run_order', 'shared_inputs', 'runtime', 'budget', 'loss_authority', 'status'}
FIXED = {
    'schema_version': 1, 'task_id': 'M2.7', 'experiment_id': 'QPAF-M2_7-MTH-001',
    'methods': {'QARF': {'gate_granularity': 'query'}, 'QPAF': {'gate_granularity': 'page'}},
    'allowed_semantic_diff': ['gate_granularity'],
    'run_order': ['QARF', 'independent_review', 'QPAF'],
    'runtime': {'device': 'cpu', 'dtype': 'float64', 'threads': 1, 'deterministic_algorithms': True,
                'requirements': 'requirements-learned-local.txt'},
    'budget': {'wall_time_minutes_per_run': 60, 'invocations_per_method_per_seed': 1,
               'retries_without_new_authorization': 0, 'shared_by_methods': True},
    'loss_authority': 'QPAF-M1.5-A001', 'status': 'FROZEN_CONFIG_PENDING_M2.8_INPUTS',
}
PINNED_INPUTS = ('split_manifest', 'm25_freeze')
PENDING_INPUTS = ('score_cache', 'qrels', 'candidate_set')


class ParityError(ValueError):
    """The matched configs are malformed or differ beyond gate granularity."""


def _unique_pairs(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ParityError(f'Duplicate key in matched manifest: {sorted(k for k in keys if keys.count(k) > 1)}')
    return dict(pairs)


def _is_seed(value):
    return type(value) is int and 0 <= value < 2**32


def _check_file_ref(name, ref):
    if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
        raise ParityError(f'{name} must have exactly path and sha256')
    if not isinstance(ref['path'], str) or not ref['path']:
        raise ParityError(f'{name}.path must be a nonempty string')
    if not isinstance(ref['sha256'], str) or not SHA256.fullmatch(ref['sha256']):
        raise ParityError(f'{name}.sha256 must be 64 lowercase hex characters')


def load_manifest(path):
    try:
        manifest = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_unique_pairs)
    except (OSError, json.JSONDecodeError) as exc:
        raise ParityError(f'Cannot read matched manifest {path}: {exc}') from exc
    if not isinstance(manifest, dict) or set(manifest) != KEYS:
        raise ParityError('Missing or unknown matched-manifest key')
    for key, expected in FIXED.items():
        # Comparing JSON text keeps true from passing as 1 inside frozen values.
        if json.dumps(manifest[key], sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ParityError(f'{key} differs from the frozen M2.7 contract')
    _check_file_ref('base_config', manifest['base_config'])
    seeds = manifest['seeds']
    if not isinstance(seeds, dict) or set(seeds) != {'development_gate', 'robustness', 'override_path'}:
        raise ParityError('seeds must have exactly development_gate, robustness and override_path')
    robustness = seeds['robustness']
    if (not isinstance(robustness, list) or not robustness or not all(map(_is_seed, robustness))
            or len(set(robustness)) != len(robustness)):
        raise ParityError('seeds.robustness must be distinct integers in [0, 2**32)')
    if not _is_seed(seeds['development_gate']) or seeds['development_gate'] not in robustness:
        raise ParityError('seeds.development_gate must be one of seeds.robustness')
    if seeds['override_path'] != 'training.seed':
        raise ParityError('seeds.override_path must be training.seed')
    inputs = manifest['shared_inputs']
    if not isinstance(inputs, dict) or set(inputs) != {*PINNED_INPUTS, *PENDING_INPUTS}:
        raise ParityError('Missing or unknown shared input')
    for name in PINNED_INPUTS:
        _check_file_ref(f'shared_inputs.{name}', inputs[name])
    for name in PENDING_INPUTS:
        if inputs[name] != PENDING:
            raise ParityError(f'shared_inputs.{name} must be {PENDING} until M2.8 delivers it')
    return manifest


def semantic_diff(left, right, prefix=''):
    """Dotted path -> [left, right] for every differing or one-sided leaf."""
    diff = {}
    for key in sorted(set(left) | set(right)):
        path = f'{prefix}{key}'
        a, b = left.get(key), right.get(key)
        if isinstance(a, dict) and isinstance(b, dict):
            diff.update(semantic_diff(a, b, f'{path}.'))
        elif key not in left or key not in right or type(a) is not type(b) or a != b:
            diff[path] = [a, b]
    return diff


def load_base(manifest, root, seed=None):
    """The M2.4-valid shared base, optionally with training.seed overridden."""
    config = load_config(Path(root)/manifest['base_config']['path'])
    if seed is not None:
        config['training']['seed'] = seed
        validate(config)
    return config


def resolve(manifest, method, seed, root):
    """Full semantic config of one run; the method name is the lookup key, not a field."""
    if method not in manifest['methods']:
        raise ParityError(f'Unknown method {method!r}; expected one of {sorted(manifest["methods"])}')
    config = copy.deepcopy(load_base(manifest, root, seed))
    config['gate_granularity'] = manifest['methods'][method]['gate_granularity']
    return config
