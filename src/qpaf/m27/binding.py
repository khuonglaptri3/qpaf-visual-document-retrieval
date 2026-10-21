"""Bind the accepted M2.8 real inputs to the frozen M2.7 matched manifest.

``matched.json`` stays byte-identical (it is hash-bound by M2.7-002, M2.10 and
D1); this separate binding pins it by SHA-256 and adds the real score cache,
candidate set, qrels, query texts and splits. Real-row parity replays the
trainer's seeded batch iterator for both methods; nothing is trained.
"""
import hashlib
import json
from pathlib import Path

from qpaf.m27.matched import _check_file_ref, _unique_pairs, check_parity, load_manifest, resolve

KEYS = {'schema_version', 'task_id', 'binding_id', 'status', 'matched_manifest', 'policy_id',
        'source_run_id', 'handover', 'inputs', 'splits'}
INPUTS = ('score_cache', 'candidate_set', 'candidate_freeze', 'qrels_development',
          'qrels_test_sealed', 'query_texts')
ROLES = ('train', 'validation', 'test')
STATUS = 'BOUND_REAL_INPUTS_PENDING_INDEPENDENT_REVIEW'
# Handover field that must carry the same hash as each bound file.
HANDOVER_HASHES = {'score_cache': 'score_cache_sha256', 'candidate_freeze': 'candidate_freeze_sha256',
                   'qrels_development': 'qrels_development_sha256',
                   'qrels_test_sealed': 'qrels_test_sha256', 'query_texts': 'query_texts_sha256'}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_binding(path):
    try:
        binding = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_unique_pairs)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'Cannot read input binding {path}: {exc}') from exc
    if not isinstance(binding, dict) or set(binding) != KEYS:
        raise ValueError('Missing or unknown input-binding key')
    if (binding['schema_version'] != 1 or binding['task_id'] != 'M2.7' or binding['status'] != STATUS
            or not isinstance(binding['policy_id'], str) or not isinstance(binding['source_run_id'], str)):
        raise ValueError('Input binding identity or status differs from the M2.7 contract')
    _check_file_ref('matched_manifest', binding['matched_manifest'])
    _check_file_ref('handover', binding['handover'])
    if set(binding['inputs']) != set(INPUTS) or set(binding['splits']) != set(ROLES):
        raise ValueError('Input binding must list exactly the required inputs and split roles')
    for group in ('inputs', 'splits'):
        for name, ref in binding[group].items():
            _check_file_ref(f'{group}.{name}', ref)
    return binding


def _verified(root, name, ref):
    path = Path(root)/ref['path']
    if not path.is_file():
        raise ValueError(f'{name}: bound file is missing: {ref["path"]}')
    if _sha256(path) != ref['sha256']:
        raise ValueError(f'{name}: bound file hash differs: {ref["path"]}')
    return path


def real_row_parity(manifest, root, binding):
    """Build real M2.4 records once; replay each method's seeded batch order without training."""
    import torch
    from qpaf.m24.dataset import build_records, iter_batches, read_score_rows
    root = Path(root)
    inputs, splits_ref = binding['inputs'], binding['splits']
    splits = {role: Path(root/splits_ref[role]['path']).read_text(encoding='utf-8').splitlines()
              for role in ROLES}
    base = resolve(manifest, 'QARF', None, root)
    rows = read_score_rows(root/inputs['score_cache']['path'])
    queries = json.loads((root/inputs['query_texts']['path']).read_text(encoding='utf-8'))
    qrels = json.loads((root/inputs['qrels_development']['path']).read_text(encoding='utf-8'))
    records = build_records(rows, queries, qrels, splits, ('train', 'validation'),
                            positive_threshold=base['data']['positive_threshold'],
                            max_candidates=base['data']['max_candidates'])
    seeds = {}
    for seed in manifest['seeds']['robustness']:
        orders = {}
        for method in ('QARF', 'QPAF'):
            training = resolve(manifest, method, seed, root)['training']
            generator = torch.Generator().manual_seed(training['seed'])
            order = []
            for _ in range(training['epochs']):
                order.extend(tuple(batch.query_ids) for batch in
                             iter_batches(records['train'], training['batch_size'], generator))
            orders[method] = order
        if orders['QARF'] != orders['QPAF'] or not orders['QARF']:
            raise ValueError(f'QARF/QPAF real-row batch order differs at seed {seed}')
        seeds[str(seed)] = {'batches': len(orders['QARF']), 'batch_order_sha256': hashlib.sha256(
            json.dumps(orders['QARF']).encode('utf-8')).hexdigest()}
    return {'identical': True, 'training_executed': False, 'epochs': base['training']['epochs'],
            'batches': sum(value['batches'] for value in seeds.values()), 'seeds': seeds,
            'record_counts': {role: len(value) for role, value in records.items()},
            'candidate_rows': {role: sum(len(r.page_ids) for r in value) for role, value in records.items()},
            'max_candidates_per_record': max(len(r.page_ids) for value in records.values() for r in value)}


def verify_binding(binding, root):
    """Fail closed unless every bound input matches the accepted M2.8 handover."""
    root = Path(root)
    matched_path = root/binding['matched_manifest']['path']
    if _sha256(matched_path) != binding['matched_manifest']['sha256']:
        raise ValueError('The frozen matched manifest differs from its bound hash')
    manifest = load_manifest(matched_path)
    synthetic = check_parity(manifest, root)
    handover = json.loads(_verified(root, 'handover', binding['handover']).read_text(encoding='utf-8'))
    if (handover.get('status') != 'PASS' or handover.get('uncovered_query_ids') != []
            or not handover.get('macro_candidate_recall', 0) >= 0.95
            or not 0 < handover.get('max_candidates_per_query', 0) <= 600
            or handover.get('policy_id') != binding['policy_id']):
        raise ValueError('The bound M2.8 handover has not passed the coverage gate under this policy')
    files = {}
    for name, ref in binding['inputs'].items():
        _verified(root, name, ref)
        field = HANDOVER_HASHES.get(name)
        if field and handover.get(field) != ref['sha256']:
            raise ValueError(f'{name}: bound hash differs from the M2.8 handover')
        files[name] = dict(ref, verified=True)
    for role, ref in binding['splits'].items():
        _verified(root, f'splits.{role}', ref)
        if handover.get('split_role_sha256', {}).get(role) != ref['sha256']:
            raise ValueError(f'splits.{role}: bound hash differs from the M2.8 handover')
        files[f'split_{role}'] = dict(ref, verified=True)
    return {'status': 'PASS', 'binding_id': binding['binding_id'], 'policy_id': binding['policy_id'],
            'source_run_id': binding['source_run_id'],
            'matched_manifest_sha256': binding['matched_manifest']['sha256'],
            'handover_sha256': binding['handover']['sha256'], 'bound_files': files,
            'synthetic_parity': synthetic,
            'real_row_parity': real_row_parity(manifest, root, binding),
            'test_labels_opened': False, 'training_executed': False}
