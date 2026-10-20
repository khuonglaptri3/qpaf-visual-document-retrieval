"""Prepare, launch, collect and verify the real GPU M2.8 retrieval cache."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

import numpy as np
from qpaf.m11.artifacts import digest, file_manifest, object_hash, read_json, source_provenance, utc, write_json, verify_manifest
from qpaf.m18.namespace import format_canonical_run_id
from qpaf.m28.preflight import load_config, prepare_inputs
from qpaf.m28.runtime import load_array


def prepare(config_path):
    config = load_config(config_path)
    run_id = format_canonical_run_id(config['experiment_id'], datetime.now(timezone.utc))
    folder = ROOT/config['output_directory']/run_id
    folder.mkdir(parents=True, exist_ok=False)
    write_json(folder/'resolved_config.json', config)
    prepare_inputs(ROOT, config, folder)
    source = source_provenance(ROOT, config['execution']['requirements_file'])
    write_json(folder/'source.json', source)
    with zipfile.ZipFile(folder/'source_snapshot.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for row in source['files']:
            if row['path'] == 'selected_image_requirements':
                continue
            path = ROOT/row['path']
            if digest(path) != row['sha256']:
                raise ValueError('Source changed during snapshot: '+row['path'])
            archive.write(path, row['path'])
        archive.write(folder/'resolved_config.json', 'm28_resolved_config.json')
    print(f'PREPARED {folder}', flush=True)
    return folder


def latest_execution(folder):
    markers = [p for p in Path(folder).glob('execution*.json')
               if p.name == 'execution.json' or p.name.startswith('execution-resume-')]
    if not markers:
        raise ValueError('No GPU invocation marker exists')
    records = [(p, read_json(p)) for p in markers]
    return max(records, key=lambda item: datetime.fromisoformat(item[1]['started_utc']))


def launch(folder, resume=False):
    import modal
    from qpaf.m28.worker import build_app
    config = read_json(folder/'resolved_config.json')
    source = read_json(folder/'source.json')
    current = source_provenance(ROOT, config['execution']['requirements_file'])
    if current['digest'] != source['digest']:
        raise ValueError('Source changed after preflight; prepare a fresh run')
    marker = folder/'execution.json'
    if marker.exists() and not resume:
        raise FileExistsError('Run already invoked; use status/collect or explicit resume')
    if resume and marker.exists():
        old = latest_execution(folder)[1]
        # Do not race a still-running GPU worker on the same Volume.
        try:
            modal.FunctionCall.from_id(old['function_call_id']).get(timeout=1)
        except TimeoutError:
            raise RuntimeError('Previous GPU invocation is still running; resume is refused')
        marker = folder/('execution-resume-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    app, worker = build_app(config, ROOT)
    with modal.enable_output(), app.run(detach=True):
        call = worker.spawn(config, folder.name, source, read_json(folder/'input_manifest.json'),
                            read_json(folder/'queries.json'), resume)
        write_json(marker, {'started_utc': utc(), 'app_id': app.app_id, 'function_call_id': call.object_id,
                   'gpu_requested': config['execution']['gpu'], 'volume': config['modal']['volume_name'],
                   'remote_path': '/runs/'+folder.name, 'resume': resume})
        print(json.dumps(read_json(marker), indent=2), flush=True)


def collect(folder):
    import modal
    config = read_json(folder/'resolved_config.json')
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    prefix = '/runs/'+folder.name+'/'
    remote = folder/'remote'
    remote.mkdir(exist_ok=True)

    def fetch(rel, expected=None):
        path = (remote/rel).resolve()
        if not path.is_relative_to(remote.resolve()):
            raise ValueError('Unsafe remote artifact path')
        if path.is_file():
            if expected and digest(path) == expected['sha256'] and path.stat().st_size == expected['size_bytes']:
                return
            if expected:
                raise ValueError('Existing local artifact differs: '+rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name+'.part')
        with temp.open('wb') as stream:
            for chunk in volume.read_file(prefix+rel):
                stream.write(chunk)
        if expected and (digest(temp) != expected['sha256'] or temp.stat().st_size != expected['size_bytes']):
            raise ValueError('Downloaded artifact hash mismatch: '+rel)
        os.replace(temp, path)

    fetch('portable_manifest.json')
    manifest = read_json(remote/'portable_manifest.json')
    rows = manifest['files']
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda row: fetch(row['path'], row), rows))
    write_json(folder/'collection.json', {'collected_utc': utc(), 'status': manifest['status'],
               'portable_manifest_sha256': digest(remote/'portable_manifest.json'),
               'verified_artifact_count': len(rows), 'bytes': sum(r['size_bytes'] for r in rows)})
    print(json.dumps(read_json(folder/'collection.json'), indent=2), flush=True)


def _scores(folder):
    remote = folder/'remote'
    verify_collection(folder)
    summary = read_json(remote/'summary.json')
    config = read_json(folder/'resolved_config.json')
    source = read_json(folder/'source.json')
    inputs = read_json(folder/'input_manifest.json')
    verify_prepared_inputs(folder, inputs)
    identity = {'config_sha256': object_hash(config), 'source_sha256': source['digest'],
                'input_sha256': object_hash(inputs)}
    environment = read_json(remote/'environment.json')
    if (summary['status'] != 'COMPLETE' or summary['identity'] != identity
            or read_json(remote/'input_manifest.json') != inputs
            or read_json(remote/'source.json') != source
            or read_json(remote/'resolved_config.json') != config
            or environment['inference_device'] != 'cuda' or not environment['uses_real_data']
            or not environment['gpu']['name'] or environment['training_executed']):
        raise ValueError('Incomplete or mismatched real GPU execution evidence')
    for channel in ('bm25', 'dense', 'visual'):
        stage = read_json(remote/channel/'summary.json')
        parity = read_json(remote/channel/'parity.json')
        if (stage['status'] != 'PASS' or stage['identity'] != identity or not parity
                or any(v.get('passed') is not True for v in parity.values())):
            raise ValueError('Incomplete/failed stage or parity evidence: '+channel)
    scores = {c: load_array(remote/c/'scores.npy', {**identity, 'kind': c+'_full'},
                           (inputs['query_count'], inputs['page_count'])) for c in ('bm25', 'dense', 'visual')}
    return scores, inputs, identity


def verify_collection(folder):
    remote = folder/'remote'
    receipt = read_json(folder/'collection.json')
    manifest_path = remote/'portable_manifest.json'
    manifest = read_json(manifest_path)
    rows = manifest['files']
    if (receipt['status'] != 'COMPLETE' or manifest['status'] != 'COMPLETE'
            or digest(manifest_path) != receipt['portable_manifest_sha256']
            or len(rows) != receipt['verified_artifact_count']
            or sum(r['size_bytes'] for r in rows) != receipt['bytes']):
        raise ValueError('Collection receipt/portable manifest hash or completeness mismatch')
    verify_manifest(remote, rows)


def verify_prepared_inputs(folder, inputs):
    queries = read_json(folder/'queries.json')
    if (object_hash(queries) != inputs['query_texts_sha256']
            or queries != read_json(folder/'remote'/'queries.json')):
        raise ValueError('Local query text differs from frozen GPU inputs')
    splits = read_json(folder/'split_ids.json')
    check = inputs['split_verification']
    if set(splits) != {'train', 'validation', 'test'}:
        raise ValueError('Invalid split role namespace')
    for role, ids in splits.items():
        if (not isinstance(ids, list) or len(ids) != check['role_counts'][role]
                or any(not isinstance(q, str) or not q or q != q.strip() or '\n' in q or '\r' in q for q in ids)
                or hashlib.sha256(''.join(q+'\n' for q in ids).encode('utf-8')).hexdigest() != check['role_sha256'][role]):
            raise ValueError('Local split differs from frozen preflight: '+role)
    union = [q for ids in splits.values() for q in ids]
    if len(set(union)) != len(union) or sorted(union) != inputs['query_ids']:
        raise ValueError('Frozen split union/overlap mismatch')


def _write_once(path, value):
    if path.exists():
        if read_json(path) != value:
            raise FileExistsError('Existing immutable artifact differs: '+str(path))
    else:
        write_json(path, value)


def finalize(folder, verify_only=False):
    from qpaf.m28.bundle import build_candidates, freeze_candidates, verify_candidates, audit_coverage
    from qpaf.m24.dataset import read_score_rows, build_records
    from qpaf.m25.leakage import audit_score_rows
    output = folder/'bundle'
    if verify_only and not (output/'handover.json').is_file():
        raise ValueError('Missing immutable handover.json; verify never creates evidence')
    scores, inputs, identity = _scores(folder)
    qids, pids = inputs['query_ids'], inputs['page_ids']
    bundle = build_candidates(scores, qids, pids)
    provenance = {'run_id': folder.name, **identity,
                  'm26_preprocessing_identity_sha256': inputs['preprocessing_identity_sha256'],
                  'm27_manifest_sha256': inputs['m27_manifest_sha256'], 'uses_qrels': False}
    if not (output/'candidate_freeze.json').exists():
        if verify_only:
            raise ValueError('No candidate freeze exists')
        freeze_candidates(output, bundle, provenance)
    verification = verify_candidates(output, scores, qids, pids)
    if read_json(output/'candidate_freeze.json')['provenance'] != provenance:
        raise ValueError('Candidate freeze provenance differs from GPU run inputs/source')
    # The first access to relevance occurs only after durable candidate freeze
    # and full-array independent replay have both completed.
    annotation = ROOT/inputs['annotation']['path']
    if digest(annotation) != inputs['annotation']['sha256']:
        raise ValueError('Qrels source changed after label-free cache construction')
    qrels = {}
    for row in read_json(annotation)['examples']:
        meta = row['meta_info']
        stem = Path(meta['file_name']).stem
        refs = meta['reference_page']
        if row['uid'] in qrels or not refs or any(type(p) is not int or p < 1 for p in refs):
            raise ValueError('Invalid source qrels')
        judged = {f'{stem}_page_{p:04d}': 1 for p in refs}
        if not set(judged).issubset(pids):
            raise ValueError('Qrels point outside canonical M2.6 page namespace')
        qrels[row['uid']] = judged
    splits = read_json(folder/'split_ids.json')
    coverage = audit_coverage(bundle['candidates'], qrels, qids, splits)
    raw_rows = read_score_rows(output/'raw_scores.parquet')
    row_audit = audit_score_rows(raw_rows, splits, roles=('train', 'validation', 'test'))
    records = build_records(raw_rows, read_json(folder/'queries.json'), qrels, splits, ('train', 'validation'))
    development_qrels = {q: qrels[q] for role in ('train', 'validation') for q in splits[role]}
    test_qrels = {q: qrels[q] for q in splits['test']}
    for name, value in [('qrels_development.json', development_qrels), ('qrels_test_sealed.json', test_qrels),
                        ('coverage_report.json', coverage), ('candidate_verification.json', verification)]:
        if verify_only and (not (output/name).exists() or read_json(output/name) != value):
            raise ValueError('Missing/changed closure artifact: '+name)
        _write_once(output/name, value)
    handover = {'schema_version': 1, 'task_id': 'M2.8', 'run_id': folder.name,
        'status': 'PASS' if coverage['status'] == 'PASS' else 'BLOCKED_COVERAGE',
        'evaluation_unit': 'page', 'query_count': len(qids), 'page_count': len(pids),
        'candidate_count': bundle['counts']['candidate_count'],
        'candidate_freeze_sha256': digest(output/'candidate_freeze.json'),
        'score_cache_sha256': digest(output/'raw_scores.parquet'),
        'qrels_development_sha256': digest(output/'qrels_development.json'),
        'qrels_test_sha256': digest(output/'qrels_test_sealed.json'),
        'query_texts_sha256': digest(folder/'queries.json'), 'splits_sha256': digest(folder/'split_ids.json'),
        'coverage_report_sha256': digest(output/'coverage_report.json'),
        'macro_candidate_recall': coverage['macro_recall'], 'uncovered_query_ids': coverage['uncovered_query_ids'],
        'm24_m25_row_audit': row_audit,
        'm24_development_record_counts': {r: len(v) for r, v in records.items()},
        'test_labels_used_only_for_frozen_candidate_coverage': True,
        'test_ranking_metrics_computed': False, 'training_executed': False,
        'finalizer_source_sha256': digest(Path(__file__)), **identity}
    if verify_only and read_json(output/'handover.json') != handover:
        raise ValueError('Immutable handover.json differs from full verification replay')
    _write_once(output/'handover.json', handover)
    print(json.dumps(handover, indent=2), flush=True)
    return handover


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=ROOT/'configs/m2.8/cache.json')
    group = p.add_mutually_exclusive_group()
    group.add_argument('--prepare-only', action='store_true')
    group.add_argument('--execute-prepared', type=Path)
    group.add_argument('--collect', type=Path)
    group.add_argument('--finalize', type=Path)
    group.add_argument('--verify', type=Path)
    group.add_argument('--status', type=Path)
    p.add_argument('--resume', action='store_true')
    args = p.parse_args()
    if args.collect:
        collect(args.collect.resolve())
    elif args.finalize or args.verify:
        finalize((args.finalize or args.verify).resolve(), bool(args.verify))
    elif args.status:
        import modal
        record = latest_execution(args.status)[1]
        try:
            result = modal.FunctionCall.from_id(record['function_call_id']).get(timeout=1)
            print(json.dumps(result, indent=2))
        except TimeoutError:
            print('RUNNING')
    else:
        folder = args.execute_prepared.resolve() if args.execute_prepared else prepare(args.config)
        if not args.prepare_only:
            launch(folder, args.resume)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    main()
