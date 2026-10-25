"""Audit the frozen cache and replay three matched input streams without labels.

This deliberately does not call M3.1's label-bearing loader/collator. Its small
label-free batching adapter is anchored to the saved M3.1 fingerprints for every
non-label component, over all 20 pilot training epochs and the validation pass.
No model, loss, optimizer, checkpoint or evaluation function is used.
"""
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import zipfile

CHANNELS = ('bm25_score', 'dense_score', 'visual_score')
SCORE_COLUMNS = ('query_id', 'page_id', *CHANNELS)
SPLIT_FILES = {'train': 'train_ids.txt', 'validation': 'val_ids.txt', 'test': 'test_ids.txt'}
SEEDS = (20260820, 20260821, 20260822)
METHODS = {'QARF': 'query', 'QPAF': 'page'}
COMPONENTS = ('query_ids', 'query_texts', 'page_ids', 'raw_scores',
              'normalized_scores', 'features', 'mask')
ARCHIVE_ROOT = 'RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01'
ARCHIVE_SHA256 = '45e764f6bfe081063ea2488dbf5e26ffcaacf2e6f43ea3ad47f56a10c331d2d8'
M42 = 'results/m4.2/' + ARCHIVE_ROOT
INPUT_FILES = ('raw_scores.parquet', 'normalized_scores.parquet', 'candidate_set.parquet',
               'queries.json', 'candidate_freeze.json', 'shared_base.toml', 'matched.json',
               'splits/train_ids.txt', 'splits/val_ids.txt', 'splits/test_ids.txt')
SOURCE_FILES = ('src/qpaf/m52/__init__.py', 'src/qpaf/m52/cache_parity.py',
                'scripts/verify_m52_cache_parity.py', 'tests/test_m52_cache_parity.py')
PINS = {
    'g2a': ('evidence/revisions/m4.7-001/g2a_freeze.json',
            '26d9bab6e7d47fe7dd1e89f6bec2c95265641df5cde8d9bd25c867b9d3a73217'),
    'g2a_confirmation': ('evidence/revisions/m4.7-001/owner_confirmation.json',
                         '5f80b4312188721dc2c2033a85ce1a9631bffa32479c576e0500471e622b95e6'),
    'preregistration': ('evidence/revisions/m5.1-001/preregistration.json',
                        '45269eafe36907f99990027f067e724939da69db5ee351669d1e5e7854bf7e29'),
    'preregistration_confirmation': ('evidence/revisions/m5.1-001/owner_confirmation.json',
                                     'c9fa0a0ef637362a30f6dcc38f86cd59916620bd714b3d6330afa76de4e80bef'),
    'preregistration_event': ('evidence/revisions/m5.1-001/governance_events.jsonl',
                              '56b66568fa91262540f99b68da01fbf04152f6af40dd374c459183d7a612228a'),
    'm31_manifest': ('evidence/revisions/m3.1-001/manifest.json',
                     '0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893'),
    'm31_verification': ('evidence/revisions/m3.1-001/verification.json',
                         '6b7b6c9df6bddcdd98af202de24ff821c7c469aea3b343bef5081b71100e5c1d'),
    'm41_manifest': ('evidence/revisions/m4.1-001/manifest.json',
                     '03673b16ef666c6d8756939efebdbcc73ff1c61a5abcff6c743400e5da6c4668'),
    'm42_manifest': (M42 + '/manifest.json',
                     '4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86'),
    'm42_shared_inputs': (M42 + '/shared_inputs.json',
                          '51eaa23303cb7086c3709249f2b400172ee006b942f26f47ddacc80b508c3dd0'),
    'm43_freeze': ('evidence/revisions/m4.3-001/method_freeze.json',
                   '4015c74b54f5ac3d2cbce54f8424c0e9329c009595e81ced5eab0039af7761cc'),
}
POLICIES = {
    'active_primary_scope': 'evidence/revisions/m1.5-002/scoped_contract.md',
    **{key: 'evidence/M1_FINAL/02_protocol/' + filename for key, filename in (
        ('baseline', 'baseline_policy.md'), ('seed', 'seed_policy.md'),
        ('statistics', 'statistical_policy.md'), ('metric', 'metric_policy.md'),
        ('frozen_protocol', 'frozen_protocol.md'))},
}


class CacheParityError(ValueError):
    """The receipt cannot certify the supplied input or source bytes."""


def require(condition, message):
    if not condition:
        raise CacheParityError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def inside(base, relative):
    base = Path(base).resolve()
    relative = Path(relative)
    require(not relative.is_absolute() and '..' not in relative.parts,
            'Input path must stay inside its declared directory')
    path = base / relative
    require(path.resolve().is_relative_to(base), 'Input path resolves outside its directory')
    require(not any(parent.is_symlink() for parent in (path, *path.parents) if parent != base.parent),
            'Symlink input paths are not supported')
    return path


def read_base_config(root):
    from qpaf.m24.config import validate
    config = tomllib.loads((Path(root) / 'configs/m2.7/shared_base.toml').read_text(encoding='utf-8'))
    validate(config)
    return config


def load_authority(root):
    """Only pinned metadata and ID files are read; qrels paths are never opened."""
    root = Path(root)
    records, pins = {}, {}
    for name, (relative, expected) in PINS.items():
        path = inside(root, relative)
        require(sha256(path) == expected, f'{name}: pinned hash differs')
        records[name] = read_json(path)
        pins[name] = {'path': relative, 'sha256': expected}
    g2a, prereg = records['g2a'], records['preregistration']
    require(records['g2a_confirmation']['decision'] == 'CONFIRMED' and
            records['g2a_confirmation']['freeze_sha256'] == PINS['g2a'][1],
            'G2A confirmation differs')
    require(records['preregistration_confirmation']['decision'] == 'ACCEPTED' and
            records['preregistration_confirmation']['preregistration_sha256'] == PINS['preregistration'][1],
            'M5.1 acceptance differs')
    require(prereg['seed_matrix'] == [
        {'seed': SEEDS[0], 'methods': ['QARF', 'QPAF'], 'state': 'completed_pilot', 'task': 'M3.2/M3.4'},
        {'seed': SEEDS[1], 'methods': ['QARF', 'QPAF'], 'state': 'pending', 'task': 'M5.3/R3'},
        {'seed': SEEDS[2], 'methods': ['QARF', 'QPAF'], 'state': 'pending', 'task': 'M5.4/R4'}],
        'Preregistered seed matrix differs')
    r2 = next(row for row in g2a['roster'] if row['id'] == 'R2')
    require(r2['task'] == 'M5.2' and r2['allowed_data'] == ['no_labels'] and
            r2['authorization'] == 'not_required' and r2['tier'] == 'core',
            'M5.2 data-access boundary differs')
    for name, relative in POLICIES.items():
        expected = prereg['pins_sha256'][name]
        require(sha256(inside(root, relative)) == expected, f'{name}: policy hash differs')
        pins[name] = {'path': relative, 'sha256': expected}
    method_sources = records['m43_freeze'].get('method_sources',
                                              records['m43_freeze'].get('source_sha256'))
    require(isinstance(method_sources, dict) and method_sources, 'Frozen method source pins missing')
    for relative, expected in method_sources.items():
        require(sha256(inside(root, relative)) == expected, f'Frozen method source hash differs: {relative}')
    m31, m42, shared = records['m31_manifest'], records['m42_manifest'], records['m42_shared_inputs']
    require(m31['verification_sha256'] == PINS['m31_verification'][1] and
            m42['authority_hashes']['m31_manifest']['sha256'] == PINS['m31_manifest'][1] and
            g2a['baselines']['bundle_manifest_sha256'] == PINS['m42_manifest'][1],
            'M3.1/M4.2/G2A lineage differs')
    files = {row['path']: row for row in m42['files']}
    require(files['shared_inputs.json']['sha256'] == PINS['m42_shared_inputs'][1],
            'Shared input manifest is not bound by M4.2')
    contract = {name: {'sha256': files['inputs/' + name]['sha256'],
                       'size_bytes': files['inputs/' + name]['size_bytes'],
                       'm42_path': 'inputs/' + name} for name in INPUT_FILES}
    links = {'raw_scores.parquet': 'score_cache', 'candidate_set.parquet': 'candidate_set',
             'queries.json': 'query_texts', 'candidate_freeze.json': 'candidate_freeze',
             'shared_base.toml': 'shared_base', 'matched.json': 'matched_manifest',
             'splits/train_ids.txt': 'split_train', 'splits/val_ids.txt': 'split_validation',
             'splits/test_ids.txt': 'split_test'}
    for filename, key in links.items():
        require(contract[filename]['sha256'] == m31['inputs'][key]['sha256'] ==
                shared['inputs'][key]['sha256'], f'M3.1/M4.2 input identity differs: {filename}')
        contract[filename]['m31_path'] = m31['inputs'][key]['path']
    require(contract['normalized_scores.parquet']['sha256'] ==
            shared['inputs']['artifact_normalized_scores']['sha256'], 'Normalized cache identity differs')
    require(contract['splits/test_ids.txt']['sha256'] == g2a['held_out']['ids_sha256'] ==
            prereg['test_plan']['ids_sha256'] and not g2a['held_out']['labels_opened'],
            'Sealed test ID contract differs')
    config = read_base_config(root)
    require(sha256(root / 'configs/m2.7/shared_base.toml') == contract['shared_base.toml']['sha256'] and
            sha256(root / 'configs/m2.7/matched.json') == contract['matched.json']['sha256'],
            'Matched base config hash differs')
    require(config['training']['seed'] == SEEDS[0], 'Pilot seed differs')
    m41 = records['m41_manifest']
    require(not m41['access']['confirmation_queries_and_labels_opened'] and
            not m41['access']['confirmation_evaluation_authorized'] and
            g2a['vimdoc']['status'] == 'NOT_RUN_DEFERRED', 'External access contract differs')
    id_groups, id_pins = [], {}
    for name, ref in m41['split']['files'].items():
        path = inside(root, 'evidence/revisions/m4.1-001/' + name)
        require(sha256(path) == ref['sha256'], 'External ID seal hash differs')
        ids = path.read_text(encoding='utf-8').splitlines()
        require(len(ids) == len(set(ids)) == ref['count'], 'External ID counts differ')
        id_groups.append(set(ids))
        id_pins[name] = ref
    require(sum(map(len, id_groups)) == len(set().union(*id_groups)) == m41['split']['union_count'],
            'External ID splits overlap')
    external = {'status': 'ID_SEAL_VERIFIED_LABELS_CLOSED', 'vimdoc': 'NOT_RUN_DEFERRED',
                'vimdoc_ids': id_pins, 'external_benchmark': 'DEFERRED_R9_UNCHANGED',
                'source_parquet_or_qrels_replayed': False,
                'held_out_test_ids_sha256': g2a['held_out']['ids_sha256'],
                'held_out_qrels_sha256_from_pinned_metadata_only': g2a['held_out']['sealed_qrels_sha256']}
    return {'pins': pins, 'contract': contract, 'config': config, 'runtime': {
        key: m31['environment'][key] for key in ('python', 'torch', 'numpy', 'pandas', 'pyarrow')},
        'historical': records['m31_verification']['parity']['methods'],
        'split_counts': shared['split_counts'],
        'expected_candidate_rows': records['m31_verification']['row_audit']['candidate_count'],
        'method_sources': method_sources, 'external_seal': external}


def restore_inputs(archive, output, contract, expected_archive_sha256=ARCHIVE_SHA256):
    """Read only ten named ZIP members; never extract qrels or checkpoints."""
    archive, output = Path(archive), Path(output)
    require(not output.exists(), 'Input output directory already exists')
    require(set(contract) == set(INPUT_FILES), 'Input allowlist differs')
    require(sha256(archive) == expected_archive_sha256, 'M4.2 archive hash differs')
    payloads = {}
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        for name in INPUT_FILES:
            member = ARCHIVE_ROOT + '/inputs/' + name
            require(names.count(member) == 1, f'Archive member missing or duplicated: {name}')
            require(z.getinfo(member).file_size == contract[name]['size_bytes'],
                    f'Archive member size differs: {name}')
            payload = z.read(member)
            require(hashlib.sha256(payload).hexdigest() == contract[name]['sha256'],
                    f'Archive member hash differs: {name}')
            payloads[name] = payload
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in payloads.items():
        target = inside(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(payload)
    result = {'status': 'PASS', 'archive_sha256': expected_archive_sha256,
              'files': list(INPUT_FILES), 'label_files_deserialized': False,
              'checkpoints_loaded': False}
    (output / 'preparation_receipt.json').write_bytes(encoded(result))
    return result


def check_input_files(inputs, contract):
    inputs = Path(inputs)
    require(set(contract) == set(INPUT_FILES), 'Input allowlist differs')
    actual = {path.relative_to(inputs).as_posix() for path in inputs.rglob('*') if path.is_file()}
    require(actual in (set(INPUT_FILES), set(INPUT_FILES) | {'preparation_receipt.json'}),
            'Input directory must contain only allowlisted files')
    for name, ref in contract.items():
        path = inside(inputs, name)
        require(path.stat().st_size == ref['size_bytes'] and sha256(path) == ref['sha256'],
                f'Input hash/size differs: {name}')


def read_label_free_table(path, columns):
    import pyarrow.parquet as pq
    parquet = pq.ParquetFile(path)
    require(parquet.schema_arrow.names == list(columns), f'Label-free schema differs: {Path(path).name}')
    return parquet.read(columns=list(columns))


@dataclass(frozen=True)
class LabelFreeRecord:
    query_id: str
    text: str
    page_ids: tuple
    raw_scores: object


def audit_tables(raw, normalized, candidates, splits, queries, cap):
    """Validate all cache rows, then construct development records without qrels."""
    import numpy as np
    require(raw.column_names == normalized.column_names == list(SCORE_COLUMNS) and
            candidates.column_names == ['query_id', 'page_id'], 'Label-free table schema differs')
    keys = raw.select(['query_id', 'page_id'])
    require(keys.equals(candidates) and keys.equals(normalized.select(['query_id', 'page_id'])),
            'Candidate/raw/normalized keys or order differ')
    require(set(splits) == set(SPLIT_FILES), 'Frozen split roles differ')
    ids = [q for role in SPLIT_FILES for q in splits[role]]
    require(ids and all(isinstance(q, str) and q and q == q.strip() for q in ids) and
            len(ids) == len(set(ids)), 'Empty, duplicate or overlapping split IDs')
    require(isinstance(queries, dict) and all(isinstance(queries.get(q), str) and queries[q].strip()
                                            for q in ids), 'Missing or empty query text')
    qids, pages = (raw.column(key).to_pylist() for key in ('query_id', 'page_id'))
    require(qids and set(qids) == set(ids), 'Cache query IDs differ from split IDs')
    values = np.column_stack([raw.column(c).to_numpy() for c in CHANNELS])
    unit = np.column_stack([normalized.column(c).to_numpy() for c in CHANNELS])
    require(values.dtype.kind == unit.dtype.kind == 'f' and np.isfinite(values).all() and
            np.isfinite(unit).all(), 'Three finite floating scores required')
    groups, start, max_difference, max_count = {}, 0, 0., 0
    key_digest = hashlib.sha256()
    while start < len(qids):
        query_id, end = qids[start], start + 1
        while end < len(qids) and qids[end] == query_id:
            end += 1
        page_ids = pages[start:end]
        require(query_id not in groups and all(isinstance(p, str) and p and p == p.strip() for p in page_ids),
                'Invalid page IDs or noncontiguous query order')
        require(len(page_ids) == len(set(page_ids)) and page_ids == sorted(page_ids),
                'Duplicate candidates or noncanonical page order')
        require(0 < end - start <= cap, 'Candidate cap exceeded')
        scores = values[start:end]
        span = np.ptp(scores, axis=0)
        expected = (scores - scores.min(axis=0)) / np.where(span == 0, 1., span)
        difference = float(np.max(np.abs(expected - unit[start:end])))
        require(difference <= 1e-12, 'Frozen normalization differs')
        max_difference, max_count = max(max_difference, difference), max(max_count, len(page_ids))
        groups[query_id] = (tuple(page_ids), scores)
        _feed(key_digest, _json([query_id, page_ids]))
        start = end
    records = {role: [LabelFreeRecord(q, queries[q], *groups[q]) for q in splits[role]]
               for role in ('train', 'validation')}
    return records, {'candidate_rows': len(qids), 'query_count': len(ids),
                     'split_counts': {role: len(splits[role]) for role in SPLIT_FILES},
                     'candidate_rows_by_split': {role: sum(len(groups[q][0]) for q in splits[role])
                                                 for role in SPLIT_FILES},
                     'candidate_keys_and_order_sha256': key_digest.hexdigest(),
                     'max_candidates_per_query': max_count,
                     'normalization_max_abs_difference': max_difference,
                     'label_files_deserialized': False, 'coverage_recomputed': False}


def load_label_free_inputs(inputs, contract, cap):
    check_input_files(inputs, contract)
    inputs = Path(inputs)
    splits = {role: inside(inputs, 'splits/' + name).read_text(encoding='utf-8').splitlines()
              for role, name in SPLIT_FILES.items()}
    return audit_tables(read_label_free_table(inputs / 'raw_scores.parquet', SCORE_COLUMNS),
                        read_label_free_table(inputs / 'normalized_scores.parquet', SCORE_COLUMNS),
                        read_label_free_table(inputs / 'candidate_set.parquet', ('query_id', 'page_id')),
                        splits, read_json(inputs / 'queries.json'), cap)


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
    """Same seeded order, padding and feature builder as M2.4, with no label tensor."""
    import torch
    from qpaf.m12.features import build_features
    report = {}
    for role in ('train', 'validation'):
        values = records[role]
        require(bool(values), f'{role}: empty records')
        hashes = {name: hashlib.sha256() for name in COMPONENTS}
        training = config['training']
        generator = torch.Generator().manual_seed(training['seed']) if role == 'train' else None
        epochs = training['epochs'] if role == 'train' else 1
        orders, active_rows, batches = [], 0, 0
        for _ in range(epochs):
            order = (torch.randperm(len(values), generator=generator).tolist() if generator is not None
                     else list(range(len(values))))
            for start in range(0, len(order), training['batch_size']):
                batch = [values[index] for index in order[start:start + training['batch_size']]]
                width = max(len(record.page_ids) for record in batch)
                raw = torch.zeros((len(batch), width, 3), dtype=torch.float64)
                mask = torch.zeros((len(batch), width), dtype=torch.bool)
                page_ids = []
                for index, record in enumerate(batch):
                    count = len(record.page_ids)
                    raw[index, :count] = torch.tensor(record.raw_scores, dtype=torch.float64)
                    mask[index, :count] = True
                    page_ids.append([*record.page_ids, *[''] * (width - count)])
                query_ids, texts = [r.query_id for r in batch], [r.text for r in batch]
                features = build_features(raw, texts, page_ids, mask,
                                          query_length_cap=config['features']['query_length_cap'])
                for name, value in [('query_ids', query_ids), ('query_texts', texts), ('page_ids', page_ids)]:
                    _feed(hashes[name], _json(value))
                for name, value in [('raw_scores', raw), ('normalized_scores', features.scores),
                                    ('features', features.values), ('mask', features.mask)]:
                    _tensor(hashes[name], value)
                orders.append(tuple(query_ids))
                active_rows += int(mask.sum())
                batches += 1
        report[role] = {'queries': len(values), 'candidate_rows': sum(len(r.page_ids) for r in values),
                        'epochs': epochs, 'batches': batches, 'active_candidate_rows_seen': active_rows,
                        'batch_order_sha256': hashlib.sha256(json.dumps(orders).encode('utf-8')).hexdigest(),
                        'components': {name: value.hexdigest() for name, value in hashes.items()}}
    return report


def compare_methods(methods):
    require(set(methods) == set(METHODS) and methods['QARF'] == methods['QPAF'],
            'Matched QARF/QPAF input parity failed')


def check_historical(current, historical):
    for role in ('train', 'validation'):
        expected = copy.deepcopy(historical[role])
        expected['components'] = {name: expected['components'][name] for name in COMPONENTS}
        require(current[role] == expected, f'{role}: historical M3.1 non-label fingerprints differ')


def resolve_matrix(base):
    matrix = []
    for seed in SEEDS:
        for method, granularity in METHODS.items():
            config = copy.deepcopy(base)
            config['training']['seed'] = seed
            matrix.append({'seed': seed, 'method': method, 'gate_granularity': granularity, 'config': config})
    return matrix


def validate_matrix(matrix, base):
    require(matrix == resolve_matrix(base), 'Matched seed/config matrix differs')


def runtime_versions():
    return {'python': sys.version.split()[0],
            **{name: version(name) for name in ('torch', 'numpy', 'pandas', 'pyarrow')}}


def source_commit(root):
    """Official evidence must bind committed M5.2 implementation bytes."""
    root = Path(root)
    result = subprocess.run(['git', 'status', '--porcelain=v1', '--', *SOURCE_FILES], cwd=root,
                            capture_output=True, check=True)
    require(not result.stdout, 'Commit the M5.2 source/test files before creating official evidence')
    for relative in SOURCE_FILES:
        result = subprocess.run(['git', 'ls-files', '--error-unmatch', relative], cwd=root, capture_output=True)
        require(result.returncode == 0, f'M5.2 source is not committed: {relative}')
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip()


def collect(root, inputs, created_at, commit, progress=None):
    import torch
    from qpaf.m12.features import FEATURE_NAMES
    root, inputs = Path(root), Path(inputs)
    authority = load_authority(root)
    runtime = runtime_versions()
    require(runtime == authority['runtime'], f'Historical numerical runtime differs: {runtime}')
    check_input_files(inputs, authority['contract'])
    require(tomllib.loads((inputs / 'shared_base.toml').read_text(encoding='utf-8')) == authority['config'],
            'Restored shared config differs')
    matrix = resolve_matrix(authority['config'])
    validate_matrix(matrix, authority['config'])
    threads, deterministic = torch.get_num_threads(), torch.are_deterministic_algorithms_enabled()
    warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    audit, validation, results = None, None, []
    try:
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        with torch.inference_mode():
            for seed in SEEDS:
                pair = {}
                for entry in (row for row in matrix if row['seed'] == seed):
                    # Each method reads and constructs its own view, with no shared record objects.
                    records, current_audit = load_label_free_inputs(inputs, authority['contract'],
                                                                  entry['config']['data']['max_candidates'])
                    require(current_audit['candidate_rows'] == authority['expected_candidate_rows'] and
                            current_audit['split_counts'] == authority['split_counts'],
                            'Frozen candidate/split counts differ')
                    if audit is None:
                        audit = current_audit
                    require(audit == current_audit, 'Input audit differs between methods/seeds')
                    fingerprint = fingerprint_view(records, entry['config'])
                    if seed == SEEDS[0]:
                        check_historical(fingerprint, authority['historical'][entry['method']])
                    if validation is None:
                        validation = fingerprint['validation']
                    require(validation == fingerprint['validation'], 'Validation input stream differs')
                    pair[entry['method']] = fingerprint
                    results.append(dict(entry, fingerprints=fingerprint))
                    if progress:
                        progress(f"seed {seed} {entry['method']}: input replay PASS")
                compare_methods(pair)
    finally:
        torch.set_num_threads(threads)
        torch.use_deterministic_algorithms(deterministic, warn_only=warn_only)
    return {'schema_version': 1, 'task_id': 'M5.2', 'roster_id': 'R2', 'owner': 'Khương',
            'experiment_id': 'QPAF-M5_2-AUD-001', 'experiment_class': 'data_audit',
            'evidence_class': 'engineering_evidence', 'status': 'TECHNICAL_PASS',
            'independent_human_review': 'PENDING_USER_REVIEW', 'created_at_utc': created_at,
            'source_commit': commit, 'source_files_sha256': {name: sha256(root / name) for name in SOURCE_FILES},
            'frozen_method_sources_sha256': authority['method_sources'], 'authority_pins': authority['pins'],
            'input_contract': authority['contract'], 'runtime': dict(runtime, device='cpu', dtype='float64',
                                                                    threads=1, deterministic_algorithms=True),
            'feature_names': list(FEATURE_NAMES), 'feature_count': len(FEATURE_NAMES),
            'cache_audit': audit, 'matrix': results, 'external_seal': authority['external_seal'],
            'checks': {'matched_input_parity_all_three_seeds': 'PASS',
                       'seed_20260820_historical_nonlabel_replay': 'PASS',
                       'validation_stream_identical_all_seeds': 'PASS', 'seed_only_config_change': 'PASS'},
            'order_rule': 'Cache/candidate order is fixed; QARF/QPAF training streams match within each '
                          'seed. The frozen seeded shuffle may differ across seeds.',
            'boundaries': {'labels_deserialized': False, 'model_forward_executed': False,
                           'training_executed': False, 'checkpoints_loaded': False,
                           'ranking_metrics_computed': False, 'candidate_coverage_recomputed': False,
                           'test_labels_opened': False, 'vimdoc_confirmation_accessed': False,
                           'execution_authorization': 'NOT_GRANTED_BY_THIS_RECEIPT'}}


def render_readme(receipt, receipt_hash):
    audit = receipt['cache_audit']
    return f'''# M5.2 — Biên nhận cache cho ba seed

Owner: Khương. Roster: R2. Kết quả kỹ thuật: PASS; nghiệm thu/review của người
phụ trách vẫn `PENDING_USER_REVIEW`. Đây là data audit / engineering evidence,
không phải kết quả chất lượng QPAF hay authorization huấn luyện.

`cache_identity.json` SHA-256: `{receipt_hash}`.
Implementation commit: `{receipt['source_commit']}`.

Đã kiểm {audit['query_count']} query, {audit['candidate_rows']} candidate rows;
split counts: {json.dumps(audit['split_counts'], sort_keys=True)}.
Raw/normalized/candidate keys và thứ tự khớp; normalization sai khác tối đa
{audit['normalization_max_abs_difference']}. Sáu input replay (hai method × ba
seed 20260820/21/22) khớp theo từng cặp. Seed đầu khớp toàn bộ fingerprints
không nhãn của M3.1 qua 20 epoch train và một lượt validation. Đây là replay
dữ liệu, không thực hiện bước tối ưu hoặc model forward.

Cache/candidate order giữ nguyên. Shuffle train có thể khác giữa seed theo
RNG đã freeze; QARF/QPAF phải cùng batch order trong mỗi seed. Validation
giữ cùng stream cho mọi seed. 13 feature, loss/config/budget/evaluator đã
khóa không bị sửa. Nhãn development/test và checkpoint không được nạp.
ViMDoc chỉ kiểm seal ID; nguồn Parquet/qrels ngoài không được mở lại.
ViMDoc và benchmark ngoài tiếp tục deferred theo G2A.

## Chạy lại

Dùng Python 3.13.7, Torch 2.11.0+cpu, NumPy 2.5.4, pandas 3.0.6, PyArrow
26.0.0. Tải gói M4.2 theo `docs/06_handover/m4.2-baseline-handoff.md`, rồi:

```powershell
python scripts/verify_m52_cache_parity.py --restore-from-archive <M42.zip> --inputs-dir .cache/m52-inputs
python scripts/verify_m52_cache_parity.py --verify evidence/revisions/m5.2-001 --inputs-dir .cache/m52-inputs --expected-receipt-sha256 {receipt_hash}
```

Restore chỉ đọc mười ZIP member không nhãn, từ chối thư mục đã tồn tại.
Verify chỉ đọc, kiểm lại payload/source hashes và replay toàn bộ ma trận;
dùng receipt hash từ bản Git/PR đã review. Không dùng chế độ create để
ghi đè revision này. Chi tiết và giới hạn: `docs/06_handover/m5.2-cache-parity-handoff.md`.

Phát dùng đúng input hashes/config của receipt cho M5.3/M5.4 và xin
authorization riêng. QARF cần được review trước QPAF matched; checkpoint
reload/finite-output checks thuộc các task chạy seed. Không mở TEST-172 ở M5.2.
'''


def verification_record(receipt_hash, readme_hash):
    return {'schema_version': 1, 'task_id': 'M5.2', 'status': 'PASS',
            'cache_identity_sha256': receipt_hash, 'readme_sha256': readme_hash,
            'independent_human_review': 'PENDING_USER_REVIEW',
            'scope': 'Label-free cache identity and six matched input-stream replays',
            'scientific_result': False, 'execution_authorization': 'NOT_GRANTED_BY_THIS_RECEIPT'}


def create(root, inputs, output, progress=None):
    output = Path(output)
    require(not output.exists(), 'M5.2 evidence directory already exists')
    receipt = collect(root, inputs, datetime.now(timezone.utc).isoformat(timespec='seconds'),
                      source_commit(root), progress)
    data = encoded(receipt)
    receipt_hash = hashlib.sha256(data).hexdigest()
    readme = render_readme(receipt, receipt_hash).encode('utf-8')
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in [('cache_identity.json', data), ('README.md', readme),
                          ('verification.json', encoded(verification_record(
                              receipt_hash, hashlib.sha256(readme).hexdigest())))]:
        with (output / name).open('xb') as stream:
            stream.write(payload)
    return receipt


def verify(root, inputs, output, expected_receipt_sha256, progress=None):
    output = Path(output)
    require(isinstance(expected_receipt_sha256, str) and
            re.fullmatch('[0-9a-f]{64}', expected_receipt_sha256) is not None,
            'A reviewed expected receipt hash is required')
    path = inside(output, 'cache_identity.json')
    require(sha256(path) == expected_receipt_sha256, 'M5.2 receipt hash differs')
    require({p.name for p in output.iterdir()} == {'cache_identity.json', 'README.md', 'verification.json'},
            'M5.2 evidence file set differs')
    saved = read_json(path)
    require(re.fullmatch('[0-9a-f]{40}', saved['source_commit']) is not None, 'Invalid source commit')
    require(datetime.fromisoformat(saved['created_at_utc']).tzinfo is not None, 'Missing UTC timestamp')
    expected = collect(root, inputs, saved['created_at_utc'], saved['source_commit'], progress)
    require(path.read_bytes() == encoded(expected), 'M5.2 receipt differs from replayed inputs/source')
    readme = render_readme(expected, expected_receipt_sha256).encode('utf-8')
    require(inside(output, 'README.md').read_bytes() == readme, 'M5.2 handoff differs')
    verification = verification_record(expected_receipt_sha256, hashlib.sha256(readme).hexdigest())
    require(inside(output, 'verification.json').read_bytes() == encoded(verification),
            'M5.2 verification record differs')
    return {'status': 'PASS', 'task_id': 'M5.2', 'read_only': True,
            'cache_identity_sha256': expected_receipt_sha256, 'matched_seed_count': len(SEEDS),
            'method_input_replays': len(expected['matrix']), 'labels_deserialized': False,
            'training_executed': False, 'independent_human_review': 'PENDING_USER_REVIEW'}
