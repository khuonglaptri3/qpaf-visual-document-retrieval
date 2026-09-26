"""TOML and explicit CLI overrides; importing this module never contacts a cloud."""
import json
import math
from pathlib import Path, PurePosixPath
import re
import tomllib


def load_config(path, overrides=()):
    with Path(path).open('rb') as stream:
        config = tomllib.load(stream)
    for override in overrides:
        key, sep, value = override.partition('=')
        if not sep:
            raise ValueError('Override must be section.key=JSON')
        parts = key.split('.')
        target = config
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                raise ValueError(f'Unknown config key: {key}')
            target = target[part]
        if parts[-1] not in target:
            raise ValueError(f'Unknown config key: {key}')
        try:
            target[parts[-1]] = json.loads(value)
        except json.JSONDecodeError as exc:
            if not value or value[:1] in '[{"':
                raise ValueError(f'Malformed JSON override: {key}') from exc
            target[parts[-1]] = value
    validate(config)
    return config


def validate(config):
    try:
        if config['schema_version'] != 1:
            raise ValueError('Unsupported config schema_version')
        positive = ['text.dpi', 'text.ocr_timeout', 'dense.batch_size',
                    'dense.max_seq_length', 'visual.batch_size',
                    'visual.query_batch_size', 'visual.score_batch_size', 'visual.embedding_shard_size',
                    'visual.max_pixels', 'retrieval.candidate_k', 'oracle.metric_k',
                    'oracle.bootstrap_samples', 'modal.cpu', 'modal.memory_mb',
                    'modal.timeout']
        for key in positive + ['selection.count', 'text.min_native_chars']:
            section, name = key.split('.')
            value = config[section][name]
            minimum = 1 if key in positive else 0
            if type(value) is not int or value < minimum:
                raise ValueError(f'{key} must be an integer >= {minimum}')
        for section in ['selection', 'oracle', 'execution']:
            if type(config[section]['seed']) is not int:
                raise ValueError(f'{section}.seed must be an integer')
        if config['modal']['timeout'] > 86400:
            raise ValueError('Modal function timeout cannot exceed 86400 seconds')
        for section, name in [('dataset', 'revision'), ('dense', 'revision'),
                              ('visual', 'revision'), ('visual', 'base_revision')]:
            if not isinstance(config[section][name], str) or not re.fullmatch(r'[0-9a-f]{40}', config[section][name]):
                raise ValueError(f'{section}.{name} must be a pinned 40-character commit')
        if config['dataset']['adapter'] != 'vidoseek':
            raise ValueError('Only the vidoseek adapter is implemented')
        if config['text']['mode'] not in {'native', 'ocr', 'native_or_ocr'}:
            raise ValueError('Unsupported text extraction mode')
        if config['retrieval']['normalization'] != 'minmax':
            raise ValueError('Only minmax normalization is implemented')
        if config['visual']['dtype'] not in {'float32', 'float16', 'bfloat16'}:
            raise ValueError('Unsupported visual.dtype')
        if config['visual']['attention'] not in {'eager', 'sdpa'}:
            raise ValueError('visual.attention must be eager or sdpa')
        for section in ['dense', 'visual']:
            if config[section]['device'] not in {'cpu', 'cuda'}:
                raise ValueError(f'{section}.device must be cpu or cuda')
        for section, name in [('bm25', 'k1'), ('bm25', 'b'), ('oracle', 'tie_tolerance')]:
            value = config[section][name]
            if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                raise ValueError(f'{section}.{name} must be finite and nonnegative')
        if config['bm25']['k1'] <= 0 or config['bm25']['b'] > 1:
            raise ValueError('BM25 requires k1 > 0 and 0 <= b <= 1')
        for name in ['app_name', 'volume_name', 'gpu', 'python_version', 'requirements_file']:
            if not isinstance(config['modal'][name], str) or not config['modal'][name].strip():
                raise ValueError(f'modal.{name} must be a nonempty string')
        mount = PurePosixPath(config['modal']['mount_path'])
        if not mount.is_absolute() or '..' in mount.parts or str(mount) == '/':
            raise ValueError('modal.mount_path must be an absolute non-root POSIX path')
        relative_path(config['modal']['workspace'])
        for name in ['annotation_file', 'corpus_file']:
            relative_path(config['dataset'][name])
        for name in ['secret_names', 'apt_packages']:
            if not isinstance(config['modal'][name], list) or any(not isinstance(v, str) or not v for v in config['modal'][name]):
                raise ValueError(f'modal.{name} must be a list of names')
        if not isinstance(config['output']['local_dir'], str) or not config['output']['local_dir']:
            raise ValueError('output.local_dir must be nonempty')
        from .oracle import weight_sets
        weight_sets(config)
    except (KeyError, TypeError) as exc:
        raise ValueError(f'Missing or malformed config field: {exc}') from exc


def relative_path(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError(f'Unsafe relative path: {value!r}')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or str(path) == '.':
        raise ValueError(f'Unsafe relative path: {value!r}')
    return path
