"""M2.6 orchestration config; scientific extraction settings live in M2.3."""
from pathlib import Path, PurePosixPath
import tomllib

POLICY_SHA = 'c0fcf0b3b13b27070716179d75545ba33ae406cc99a74902737bcf2dad19c4b8'
EXPERIMENT = 'QPAF-M2_6-FULL-OCR-001'


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('Expected a portable relative path')
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ('..', '.') for p in value.split('/')):
        raise ValueError('Unsafe relative path')
    return path


def validate(config):
    keys = {'corpus': {'dataset', 'raw_directory', 'pdf_directory', 'split_freeze', 'page_manifest',
                       'document_count', 'page_count'},
            'policy': {'handover', 'path', 'sha256'},
            'execution': {'workers', 'cpu', 'ram_mib', 'max_pixels', 'ocr_timeout_seconds',
                          'wall_seconds', 'checkpoint_pages', 'png_compress_level', 'retries'},
            'modal': {'app_name', 'volume_name', 'mount_path', 'python_version', 'requirements_file'},
            'output': {'directory'}}
    if set(config) != {'schema_version', 'experiment_id', *keys}:
        raise ValueError('Missing or unknown M2.6 config sections')
    for section, expected in keys.items():
        if not isinstance(config[section], dict) or set(config[section]) != expected:
            raise ValueError('Missing or unknown M2.6 config fields: ' + section)
    if type(config['schema_version']) is not int or config['schema_version'] != 1 or config['experiment_id'] != EXPERIMENT:
        raise ValueError('Unexpected M2.6 experiment/schema')
    corpus, policy, execution = (config[k] for k in ('corpus', 'policy', 'execution'))
    if (corpus['dataset'], corpus['document_count'], corpus['page_count']) != ('Qiuchen-Wang/ViDoSeek', 292, 5385):
        raise ValueError('Full corpus must be the frozen 292-document / 5385-page ViDoSeek corpus')
    if policy['sha256'] != POLICY_SHA:
        raise ValueError('M2.3 policy hash changed')
    for name, expected in {'workers': 2, 'cpu': 4, 'ram_mib': 4096, 'max_pixels': 40000000,
                            'ocr_timeout_seconds': 15, 'retries': 0}.items():
        if type(execution[name]) is not int or execution[name] != expected:
            raise ValueError('Frozen resource setting changed: ' + name)
    for name, lower, upper in [('wall_seconds', 60, 86400), ('checkpoint_pages', 1, 100),
                                ('png_compress_level', 0, 9)]:
        if type(execution[name]) is not int or not lower <= execution[name] <= upper:
            raise ValueError('Invalid orchestration setting: ' + name)
    if config['modal']['mount_path'] != '/m26' or config['modal']['python_version'] != '3.11':
        raise ValueError('Unexpected Modal mount/Python runtime')
    for section, names in [('corpus', ['raw_directory', 'pdf_directory', 'split_freeze', 'page_manifest']),
                           ('policy', ['handover', 'path']), ('modal', ['requirements_file']),
                           ('output', ['directory'])]:
        for name in names:
            relative(config[section][name])
    return config


def load_config(path):
    with Path(path).open('rb') as stream:
        return validate(tomllib.load(stream))
