"""Bounded CPU calibration contract, separate from the M2.2 retriever preset."""
import re
import tomllib
from pathlib import Path


def validate(config):
    try:
        if config['schema_version'] != 1 or config['experiment_id'] != 'QPAF-M2_3-CAL-001':
            raise ValueError('Unexpected calibration schema/experiment')
        sample, text, caps = config['sample'], config['text'], config['caps']
        if type(config['seed']) is not int:
            raise ValueError('Seed must be an integer')
        for field, upper in {'max_documents': 32, 'max_pages': 128, 'max_probe_pages': 240,
                             'max_pixels': 40000000, 'workers': 2, 'wall_seconds': 1800,
                             'ram_mib': 4096, 'input_mib': 384, 'artifact_mib': 1024}.items():
            if type(caps[field]) is not int or not 1 <= caps[field] <= upper:
                raise ValueError(f'Invalid cap: {field}')
        if sample['document_count'] != 30 or sample['pages_per_document'] != 4:
            raise ValueError('The first protocol fixes 30 documents x 4 pages')
        if (sample['stratum_documents'] != [6, 12, 12]
                or sample['stratum_holdout_documents'] != [2, 4, 4]
                or sample['probe_pages_per_document'] != 8 or sample['reference_pages'] != 40):
            raise ValueError('Sampling protocol changed; declare a new protocol')
        if sample['document_count'] * 4 + 1 > caps['max_pages'] or caps['max_documents'] < 31:
            raise ValueError('Sample exceeds caps')
        if text['dpis'] != [150, 300] or text['review_image_dpi'] != 300:
            raise ValueError('Expected paired 150/300-DPI calibration')
        if (text['parser_version'], text['engine_version'], text['oem'], text['psm']) != ('4.30.0', '5.3.0', 3, 3):
            raise ValueError('Extraction engine/command must be pinned')
        if text['language'] != 'eng' or text['preprocessing'] != 'none' or text['omp_threads'] != 1:
            raise ValueError('Unexpected language/preprocessing/thread policy')
        if not re.fullmatch(r'[0-9a-f]{64}', text['traineddata_sha256']):
            raise ValueError('traineddata SHA-256 required')
        if text['page_timeout_seconds'] != 120 or caps['retries'] != 0:
            raise ValueError('Timeout/retry policy changed')
        if config['modal']['cpu'] != 4 or config['modal']['mount_path'] != '/m23' or 'gpu' in config['modal']:
            raise ValueError('CPU-only runtime required')
        if not 0 < caps['planning_budget_usd'] <= 1:
            raise ValueError('First-run planning budget exceeds $1')
        for name in ('directory', 'review_directory'):
            value = Path(config['output'][name])
            if value.is_absolute() or '..' in value.parts:
                raise ValueError('Outputs must stay in the workspace')
    except (KeyError, TypeError) as exc:
        raise ValueError('Incomplete M2.3 configuration') from exc


def load_config(path):
    with Path(path).open('rb') as stream:
        config = tomllib.load(stream)
    validate(config)
    return config
