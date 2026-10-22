"""Fingerprint the exact M2.4 batch/feature path, without model or optimizer work."""
import hashlib
import json

import torch

from qpaf.m12.features import FEATURE_NAMES, build_features
from qpaf.m24.dataset import iter_batches


def _feed(digest, payload):
    digest.update(len(payload).to_bytes(8, 'little'))
    digest.update(payload)


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _tensor(digest, value):
    array = value.detach().cpu().contiguous().numpy()
    array = array.astype(array.dtype.newbyteorder('<'), copy=False)
    _feed(digest, _json([str(array.dtype), list(array.shape)]))
    _feed(digest, array.tobytes(order='C'))


def fingerprint_view(records, config):
    """Replay all development-seed train epochs and one fixed validation pass."""
    report = {}
    training = config['training']
    for role in ('train', 'validation'):
        values = records[role]
        if not values:
            raise ValueError(f'{role}: empty pilot records')
        hashes = {name: hashlib.sha256() for name in (
            'query_ids', 'query_texts', 'page_ids', 'raw_scores', 'normalized_scores',
            'features', 'mask', 'labels', 'relevant_total')}
        totals = {record.query_id: record.relevant_total for record in values}
        generator = torch.Generator().manual_seed(training['seed']) if role == 'train' else None
        epochs = training['epochs'] if role == 'train' else 1
        orders, active_rows, batches = [], 0, 0
        for _ in range(epochs):
            for batch in iter_batches(values, training['batch_size'], generator):
                features = build_features(batch.raw_scores, batch.texts, batch.page_ids, batch.mask,
                                          query_length_cap=config['features']['query_length_cap'])
                for name, value in (('query_ids', batch.query_ids), ('query_texts', batch.texts),
                                    ('page_ids', batch.page_ids),
                                    ('relevant_total', [totals[q] for q in batch.query_ids])):
                    _feed(hashes[name], _json(value))
                for name, value in (('raw_scores', batch.raw_scores), ('normalized_scores', features.scores),
                                    ('features', features.values), ('mask', features.mask), ('labels', batch.labels)):
                    _tensor(hashes[name], value)
                orders.append(tuple(batch.query_ids))
                active_rows += int(batch.mask.sum())
                batches += 1
        report[role] = {
            'queries': len(values), 'candidate_rows': sum(len(r.page_ids) for r in values),
            'epochs': epochs, 'batches': batches, 'active_candidate_rows_seen': active_rows,
            # Same serialization as the accepted M2.7-003 order digest.
            'batch_order_sha256': hashlib.sha256(json.dumps(orders).encode('utf-8')).hexdigest(),
            'components': {name: digest.hexdigest() for name, digest in hashes.items()},
        }
    return report


def compare_views(views, config):
    """Independent loaders/iterators must agree on every batch component."""
    previous_threads = torch.get_num_threads()
    deterministic = torch.are_deterministic_algorithms_enabled()
    try:
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        reports = {method: fingerprint_view(views[method], config) for method in ('QARF', 'QPAF')}
    finally:
        torch.set_num_threads(previous_threads)
        torch.use_deterministic_algorithms(deterministic)
    left, right = reports['QARF'], reports['QPAF']
    for role in ('train', 'validation'):
        if left[role] != right[role]:
            fields = [key for key in left[role] if left[role][key] != right[role][key]]
            raise ValueError(f'{role}: QARF/QPAF input parity failed: {fields}')
    return {
        'identical': True, 'seed': config['training']['seed'], 'feature_names': list(FEATURE_NAMES),
        'feature_count': len(FEATURE_NAMES),
        'record_counts': {role: left[role]['queries'] for role in left},
        'candidate_rows': {role: left[role]['candidate_rows'] for role in left},
        'methods': reports, 'training_executed': False, 'model_forward_executed': False,
        'test_labels_opened': False,
    }
