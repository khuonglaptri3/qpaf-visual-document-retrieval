"""Build, audit and verify the QPAF-M1.5-A003 expanded M2.8 candidate cache.

Reuses the full score matrices of the frozen M2.8 GPU run; nothing is
re-encoded. ``--develop`` freezes label-free candidates and only then audits
train/validation coverage. ``--finalize`` runs after development review: it
opens test qrels for coverage alone, checks the M2.4/M2.5 loaders and writes
the handover. ``--verify`` replays everything read-only.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m11.artifacts import digest, file_manifest, object_hash, read_json, source_provenance, utc, write_json
from qpaf.m18.namespace import format_canonical_run_id
from qpaf.m28 import bundle as base
from qpaf.m28 import expansion
from qpaf.m28.runtime import load_array

CONFIG = ROOT/'configs/m2.8/expansion.json'
ROLES = ('train', 'validation', 'test')
SPLIT_FILES = {'train': 'train_ids.txt', 'validation': 'val_ids.txt', 'test': 'test_ids.txt'}


def _check(path, expected, name):
    if digest(path) != expected:
        raise ValueError(f'{name} hash mismatch: {path}')


def _keys_sha256(rows):
    import hashlib
    keys = sorted({(row['query_id'], row['page_id']) for row in rows})
    return hashlib.sha256(''.join(f'{q}\t{p}\n' for q, p in keys).encode('utf-8')).hexdigest()


def _write_once(path, value):
    if path.exists():
        if read_json(path) != value:
            raise FileExistsError('Existing immutable artifact differs: '+str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, value)


def _bytes_once(path, payload, verify_only):
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError('Immutable input artifact changed: '+str(path))
    elif verify_only:
        raise ValueError('Missing immutable input artifact: '+str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(payload)


def load_config(path=CONFIG):
    config = read_json(path)
    policy = config['policy']
    if (policy['policy_id'] != expansion.POLICY_ID or policy['top_k'] != expansion.BASE_TOP_K
            or policy['rrf_k'] != expansion.RRF_K
            or policy['expansion_documents'] != expansion.EXPANSION_DOCUMENTS
            or policy['max_candidates_per_query'] != len(base.CHANNELS)*policy['top_k']
            or config['amendment']['id'] != expansion.AMENDMENT_ID):
        raise ValueError('Expansion config differs from the A003 policy constants')
    _check(ROOT/config['amendment']['path'], config['amendment']['sha256'], 'A003 amendment')
    return config


def load_source(config):
    """Verify the frozen M2.8 run and load its three complete score matrices."""
    source_run = config['source_run']
    folder = ROOT/source_run['path']
    if folder.name != source_run['run_id']:
        raise ValueError('Source run path and ID differ')
    remote = folder/'remote'
    manifest_path = remote/'portable_manifest.json'
    if (read_json(folder/'collection.json')['portable_manifest_sha256'] != source_run['portable_manifest_sha256']
            or digest(manifest_path) != source_run['portable_manifest_sha256']):
        raise ValueError('Source portable manifest differs from the frozen collection')
    rows = {row['path']: row for row in read_json(manifest_path)['files']}
    for channel in base.CHANNELS:
        for name in ('scores.json', 'scores.npy'):
            rel, path = f'{channel}/{name}', remote/channel/name
            if not path.is_file():
                raise FileNotFoundError(
                    f'Missing {path}. Fetch /runs/{folder.name}/{rel} from Modal Volume '
                    'qpaf-m28-score-cache; its SHA-256 is fixed by portable_manifest.json.')
            if path.stat().st_size != rows[rel]['size_bytes'] or digest(path) != rows[rel]['sha256']:
                raise ValueError(f'Source score payload differs from portable manifest: {rel}')
    resolved = read_json(folder/'resolved_config.json')
    source = read_json(folder/'source.json')
    inputs = read_json(folder/'input_manifest.json')
    identity = {'config_sha256': object_hash(resolved), 'source_sha256': source['digest'],
                'input_sha256': object_hash(inputs)}
    summary = read_json(remote/'summary.json')
    if summary['status'] != 'COMPLETE' or summary['identity'] != identity:
        raise ValueError('Source GPU run is incomplete or its identity differs')
    scores = {channel: load_array(remote/channel/'scores.npy', {**identity, 'kind': channel+'_full'},
                                  (inputs['query_count'], inputs['page_count']))
              for channel in base.CHANNELS}
    bundle = folder/'bundle'
    for name, key in (('candidate_freeze.json', 'candidate_freeze_sha256'),
                      ('handover.json', 'handover_sha256'),
                      ('coverage_report.json', 'coverage_report_sha256'),
                      ('split_ids.json', 'split_ids_sha256'), ('queries.json', 'query_texts_sha256')):
        _check(bundle/name, source_run[key], 'Source '+name)
    return folder, scores, inputs, identity


def replay_baseline(folder, scores, inputs):
    """Rebuild C0 and require identity with the frozen M2.8-001 candidate set."""
    freeze = read_json(folder/'bundle/candidate_freeze.json')
    handover = read_json(folder/'bundle/handover.json')
    baseline = base.build_candidates(scores, inputs['query_ids'], inputs['page_ids'],
                                     top_k=freeze['counts']['top_k'])
    keys_sha256 = _keys_sha256(baseline['candidates'])
    checks = {name: baseline[name] == freeze[name]
              for name in ('counts', 'query_ids_sha256', 'page_ids_sha256', 'score_arrays_sha256')}
    checks['candidate_keys_sha256'] = keys_sha256 == handover['m24_m25_row_audit']['candidate_keys_sha256']
    if not all(checks.values()):
        raise ValueError(f'Rebuilt C0 differs from the frozen M2.8-001 freeze: {checks}')
    return {'status': 'PASS', 'checks': checks, 'counts': baseline['counts'],
            'candidate_keys_sha256': keys_sha256,
            'score_arrays_sha256': baseline['score_arrays_sha256']}


def _provenance(config, run, identity):
    return {'source_run_id': config['source_run']['run_id'], 'source_identity': identity,
            'source_portable_manifest_sha256': config['source_run']['portable_manifest_sha256'],
            'baseline_candidate_freeze_sha256': config['source_run']['candidate_freeze_sha256'],
            'amendment_id': config['amendment']['id'], 'amendment_sha256': config['amendment']['sha256'],
            'policy_id': expansion.POLICY_ID, 'expansion_config_sha256': object_hash(config),
            'expansion_source_sha256': read_json(run/'source.json')['digest'], 'uses_qrels': False}


def _label_free_summary(bundle, splits):
    rows = bundle['query_summaries']
    owner = {q: role for role, ids in splits.items() for q in ids}

    def stats(values):
        return {'min': min(values), 'mean': sum(values)/len(values), 'max': max(values)}
    return {'counts': bundle['counts'], 'final_count': stats([r['final_count'] for r in rows]),
            'added_count': stats([r['added_count'] for r in rows]),
            'added_by_split': {role: sum(r['added_count'] for r in rows if owner[r['query_id']] == role)
                               for role in ROLES},
            'selected_document_fully_inside_c0': sum(1 for r in rows if r['added_count'] == 0
                                                     and r['final_count'] < bundle['counts']['max_candidates_per_query']),
            'c0_at_cap': sum(1 for r in rows if r['base_count'] == bundle['counts']['max_candidates_per_query'])}


def _development_coverage(bundle, qrels, splits, query_ids):
    dev = set(splits['train'])|set(splits['validation'])
    ids = [q for q in query_ids if q in dev]
    candidates = [row for row in bundle['candidates'] if row['query_id'] in dev]
    return base.audit_coverage(candidates, qrels, ids, {'train': splits['train'],
                                                        'validation': splits['validation'], 'test': []})


def develop(config_path=CONFIG):
    config = load_config(config_path)
    timings = {}
    start = time.perf_counter()
    folder, scores, inputs, identity = load_source(config)
    timings['load_and_verify_source_seconds'] = time.perf_counter()-start
    run_id = format_canonical_run_id(config['experiment_id'], datetime.now(timezone.utc))
    run = ROOT/config['output_directory']/run_id
    run.mkdir(parents=True, exist_ok=False)
    write_json(run/'resolved_config.json', config)
    write_json(run/'source.json', source_provenance(ROOT))
    start = time.perf_counter()
    baseline = replay_baseline(folder, scores, inputs)
    timings['baseline_replay_seconds'] = time.perf_counter()-start
    write_json(run/'baseline_replay.json', baseline)
    qids, pids, top_k = inputs['query_ids'], inputs['page_ids'], config['policy']['top_k']
    start = time.perf_counter()
    bundle = expansion.build_expanded_candidates(scores, qids, pids, top_k=top_k)
    timings['expansion_build_seconds'] = time.perf_counter()-start
    output = run/'bundle'
    expansion.freeze_expanded_candidates(output, bundle, _provenance(config, run, identity))
    start = time.perf_counter()
    verification = expansion.verify_expanded_candidates(output, scores, qids, pids, top_k=top_k)
    timings['independent_replay_seconds'] = time.perf_counter()-start
    write_json(output/'candidate_verification.json', verification)
    splits = read_json(folder/'bundle/split_ids.json')
    write_json(output/'expansion_summary.json', _label_free_summary(bundle, splits))
    # Relevance is first accessed here: development qrels only, after the
    # candidate freeze and its full-array replay. Test qrels stay unopened.
    dev_path = folder/'bundle/qrels_development.json'
    _check(dev_path, config['source_run']['qrels_development_sha256'], 'Development qrels')
    coverage = _development_coverage(bundle, read_json(dev_path), splits, qids)
    write_json(output/'development_coverage.json', coverage)
    baseline_coverage = read_json(folder/'bundle/coverage_report.json')['by_split']
    report = {
        'schema_version': 1, 'task_id': 'M2.8', 'phase': 'development', 'run_id': run_id,
        'policy_id': expansion.POLICY_ID, 'amendment_id': expansion.AMENDMENT_ID,
        'status': coverage['status'], 'created_utc': utc(),
        'candidate_freeze_sha256': digest(output/'candidate_freeze.json'),
        'roles': ['train', 'validation'], 'test_qrels_opened': False,
        'test_ranking_metrics_computed': False, 'training_executed': False,
        'coverage': {role: coverage['by_split'][role] for role in ('train', 'validation')},
        'development_overall': {k: coverage[k] for k in ('status', 'query_count', 'macro_recall',
                                                         'uncovered_query_ids', 'candidate_count')},
        'baseline_development_coverage': {role: baseline_coverage[role] for role in ('train', 'validation')},
        'label_free_summary': read_json(output/'expansion_summary.json'), 'timings': timings,
    }
    write_json(run/'development_report.json', report)
    print(json.dumps({k: report[k] for k in ('run_id', 'status', 'development_overall')}, indent=2), flush=True)
    return run


def finalize(run, verify_only=False):
    from qpaf.m24.dataset import build_records, read_score_rows
    from qpaf.m25.leakage import audit_score_rows
    run = Path(run)
    output = run/'bundle'
    if verify_only and not (output/'handover.json').is_file():
        raise ValueError('Missing immutable handover.json; verify never creates evidence')
    config = read_json(run/'resolved_config.json')
    if config != load_config(CONFIG):
        raise ValueError('Run config differs from the committed A003 expansion config')
    report = read_json(run/'development_report.json')
    if report['status'] != 'PASS' or report['run_id'] != run.name:
        raise ValueError('Development coverage did not pass; A003 forbids tuning, so stop here')
    folder, scores, inputs, identity = load_source(config)
    if read_json(run/'baseline_replay.json') != replay_baseline(folder, scores, inputs):
        raise ValueError('Baseline replay differs from the development record')
    qids, pids, top_k = inputs['query_ids'], inputs['page_ids'], config['policy']['top_k']
    bundle = expansion.build_expanded_candidates(scores, qids, pids, top_k=top_k)
    verification = expansion.verify_expanded_candidates(output, scores, qids, pids, top_k=top_k)
    if read_json(output/'candidate_verification.json') != verification:
        raise ValueError('Candidate verification differs from the development replay')
    if read_json(output/'candidate_freeze.json')['provenance'] != _provenance(config, run, identity):
        raise ValueError('Candidate freeze provenance differs from the source run and config')
    splits = read_json(folder/'bundle/split_ids.json')
    dev_path = folder/'bundle/qrels_development.json'
    _check(dev_path, config['source_run']['qrels_development_sha256'], 'Development qrels')
    dev_qrels = read_json(dev_path)
    if (read_json(output/'development_coverage.json') != _development_coverage(bundle, dev_qrels, splits, qids)
            or read_json(output/'expansion_summary.json') != _label_free_summary(bundle, splits)):
        raise ValueError('Development records differ from replay')
    # Test qrels are opened only now, for coverage of the frozen set.
    test_path = folder/'bundle/qrels_test_sealed.json'
    _check(test_path, config['source_run']['qrels_test_sha256'], 'Test qrels')
    qrels = {**dev_qrels, **read_json(test_path)}
    coverage = base.audit_coverage(bundle['candidates'], qrels, qids, splits)
    raw_rows = read_score_rows(output/'raw_scores.parquet')
    row_audit = audit_score_rows(raw_rows, splits, roles=ROLES)
    records = build_records(raw_rows, read_json(folder/'bundle/queries.json'), qrels, splits,
                            ('train', 'validation'))
    if not verify_only:
        _write_once(output/'coverage_report.json', coverage)
    if read_json(output/'coverage_report.json') != coverage:
        raise ValueError('Coverage report differs from replay')
    for name in ('queries.json', 'split_ids.json', 'qrels_development.json', 'qrels_test_sealed.json'):
        _bytes_once(output/name, (folder/'bundle'/name).read_bytes(), verify_only)
    split_hashes = {}
    for role, filename in SPLIT_FILES.items():
        _bytes_once(output/'splits'/filename, (folder/'bundle/splits'/filename).read_bytes(), verify_only)
        split_hashes[role] = digest(output/'splits'/filename)
    counts = bundle['counts']
    handover = {
        'schema_version': 2, 'task_id': 'M2.8', 'run_id': run.name,
        'status': 'PASS' if coverage['status'] == 'PASS' else 'BLOCKED_COVERAGE',
        'policy_id': expansion.POLICY_ID, 'amendment_id': expansion.AMENDMENT_ID,
        'amendment_sha256': config['amendment']['sha256'],
        'source_run_id': config['source_run']['run_id'],
        'baseline_candidate_freeze_sha256': config['source_run']['candidate_freeze_sha256'],
        'evaluation_unit': 'page', 'query_count': len(qids), 'page_count': len(pids),
        'base_candidate_count': counts['base_candidate_count'],
        'added_page_count': counts['added_page_count'], 'candidate_count': counts['candidate_count'],
        'max_candidates_per_query': max(r['final_count'] for r in bundle['query_summaries']),
        'candidate_freeze_sha256': digest(output/'candidate_freeze.json'),
        'score_cache_sha256': digest(output/'raw_scores.parquet'),
        'qrels_development_sha256': digest(output/'qrels_development.json'),
        'qrels_test_sha256': digest(output/'qrels_test_sealed.json'),
        'query_texts_sha256': digest(output/'queries.json'), 'splits_sha256': digest(output/'split_ids.json'),
        'score_cache_path': 'raw_scores.parquet', 'query_texts_path': 'queries.json',
        'qrels_development_path': 'qrels_development.json', 'qrels_test_sealed_path': 'qrels_test_sealed.json',
        'split_ids_path': 'split_ids.json', 'splits_directory': 'splits', 'split_role_sha256': split_hashes,
        'coverage_report_sha256': digest(output/'coverage_report.json'),
        'macro_candidate_recall': coverage['macro_recall'],
        'uncovered_query_ids': coverage['uncovered_query_ids'],
        'm24_m25_row_audit': row_audit,
        'm24_development_record_counts': {role: len(value) for role, value in records.items()},
        'development_report_sha256': digest(run/'development_report.json'),
        'test_labels_used_only_for_frozen_candidate_coverage': True,
        'test_ranking_metrics_computed': False, 'training_executed': False,
        'finalizer_source_sha256': digest(Path(__file__)), 'source_identity': identity}
    if verify_only and read_json(output/'handover.json') != handover:
        raise ValueError('Immutable handover.json differs from full verification replay')
    _write_once(output/'handover.json', handover)
    hashes = file_manifest(output, exclude=('hashes.json',))
    if verify_only and (not (output/'hashes.json').is_file() or read_json(output/'hashes.json') != hashes):
        raise ValueError('Bundle byte/hash manifest differs from verification replay')
    _write_once(output/'hashes.json', hashes)
    print(json.dumps({k: handover[k] for k in ('run_id', 'status', 'candidate_count', 'added_page_count',
                                               'macro_candidate_recall', 'uncovered_query_ids')}, indent=2),
          flush=True)
    return handover


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--develop', action='store_true')
    group.add_argument('--finalize', type=Path)
    group.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.develop:
        develop()
    elif args.finalize:
        finalize(args.finalize)
    else:
        finalize(args.verify, verify_only=True)


if __name__ == '__main__':
    main()
