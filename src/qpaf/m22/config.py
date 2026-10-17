"""Explicit calibration settings, with worker-side hard bounds."""
import math
from pathlib import Path
import re
import tomllib


def validate(config):
    try:
        if config['schema_version'] != 1 or config['sample']['split'] not in ('train', 'validation'):
            raise ValueError('M2.2 requires schema 1 and train/validation queries')
        if type(config['seed']) is not int:
            raise ValueError('Seed must be an integer')
        bounds = {'max_queries': 16, 'max_pages': 64, 'timeout_seconds': 1800,
                  'ram_mb': 32768, 'vram_mb': 22528, 'input_mb': 64, 'artifact_mb': 512}
        for name, upper in bounds.items():
            value = config['caps'][name]
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError(f'caps.{name} must be in 1..{upper}')
        for name, cap in [('query_count', 'max_queries'), ('page_count', 'max_pages')]:
            value = config['sample'][name]
            if type(value) is not int or not 1 <= value <= config['caps'][cap]:
                raise ValueError(f'sample.{name} exceeds hard bound')
        if config['sample']['selection'] != 'sha256(seed:id),id':
            raise ValueError('Unknown sampling policy')
        if config['caps']['retries'] != 0 or config['modal']['gpu'] != 'A10G':
            raise ValueError('M2.2 uses one A10G and no automatic retries')
        if config['modal']['cpu'] != 4 or config['modal']['mount_path'] != '/m22':
            raise ValueError('Unexpected runtime resource settings')
        for channel in ('dense', 'visual'):
            c = config[channel]
            if not re.fullmatch(r'[0-9a-f]{40}', c['revision']):
                raise ValueError('Model revisions must be full commit hashes')
            if (c['tokenizer_id'], c['tokenizer_revision']) != (c['model_id'], c['revision']):
                raise ValueError('Tokenizer must be pinned to the selected checkpoint')
            if c['device'] != 'cuda' or not 1 <= c['batch_size'] <= 4:
                raise ValueError('Invalid device/batch size')
        v = config['visual']
        if v['family'] != 'colqwen2_5' or v['model_id'] != 'vidore/colqwen2.5-v0.2':
            raise ValueError('M2.2 requires the selected ColQwen2.5 checkpoint')
        if not re.fullmatch(r'[0-9a-f]{40}', v['base_revision']):
            raise ValueError('Base revision must be pinned')
        if (v['processor_id'], v['processor_revision']) != (v['model_id'], v['revision']):
            raise ValueError('Processor checkpoint mismatch')
        if v['processor_local_snapshot'] is not True or v['processor_use_fast'] is not False:
            raise ValueError('Use the pinned local processor snapshot and slow image processor')
        if v['dtype'] not in ('float32', 'bfloat16') or v['attention'] != 'sdpa' or v['query_prefix'] != 'Query: ':
            raise ValueError('Unexpected visual inference contract')
        if not 3136 <= v['min_pixels'] <= v['max_pixels'] <= 602112:
            raise ValueError('Image pixel bound exceeded')
        for key, upper in [('query_batch_size', 8), ('score_batch_size', 16),
                           ('embedding_shard_size', 64), ('max_query_tokens', 256)]:
            if type(v[key]) is not int or not 1 <= v[key] <= upper:
                raise ValueError(f'Invalid visual.{key}')
        if v['query_suffix_tokens'] != 10 or v['mask_non_image_embeddings'] is not False:
            raise ValueError('Unexpected visual prompt/masking contract')
        d = config['dense']
        if d['model_id'] != 'BAAI/bge-m3' or d['dtype'] != 'float32' or not d['normalize_embeddings']:
            raise ValueError('Unexpected dense inference contract')
        if type(d['max_seq_length']) is not int or not 1 <= d['max_seq_length'] <= 8192:
            raise ValueError('Invalid dense sequence length')
        b = config['bm25']
        if not 0 < b['k1'] <= 3 or not 0 <= b['b'] <= 1 or b['tokenizer'] != 'unicode_word_lowercase':
            raise ValueError('Invalid BM25 contract')
        for key, upper in [('bm25_atol', 1e-12), ('dense_atol', 1e-5), ('dense_rtol', 1e-5),
                           ('visual_atol', .25), ('visual_rtol', .005),
                           ('visual_embedding_atol', .02), ('visual_embedding_rtol', .05)]:
            value = config['parity'][key]
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= upper:
                raise ValueError(f'Invalid parity tolerance {key}')
        t = config['text']
        if t['dpi'] != 150 or t['mode'] != 'native_or_ocr' or t['ocr_timeout'] != 120:
            raise ValueError('Keep the provisional M1 text preprocessing contract')
        if t['parser_version'] != '4.30.0' or t['ocr_engine_version'] != '5.3.0':
            raise ValueError('Text engines must be pinned')
    except (KeyError, TypeError) as exc:
        raise ValueError(f'Missing/malformed M2.2 config: {exc}') from exc


def load_config(path):
    with Path(path).open('rb') as stream:
        config = tomllib.load(stream)
    validate(config)
    return config
