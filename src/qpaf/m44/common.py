"""Shared M4.4 inputs: restored M4.2 bundle, validation-only records, authorization, CSV.gz."""
import csv
from datetime import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
CONFIG = 'configs/m4.4/evaluation.json'
_EXPANSION = 'results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle/'
# Byte-identical local origins of the Git-ignored M4.2 payload (see shared_inputs.json).
RESTORE_SOURCES = {
    'inputs/candidate_expansion_log.parquet': _EXPANSION+'candidate_expansion_log.parquet',
    'inputs/candidate_expansion_queries.parquet': _EXPANSION+'candidate_expansion_queries.parquet',
    'inputs/candidate_set.parquet': _EXPANSION+'candidate_set.parquet',
    'inputs/channel_top_lists.parquet': _EXPANSION+'channel_top_lists.parquet',
    'inputs/normalized_scores.parquet': _EXPANSION+'normalized_scores.parquet',
    'inputs/raw_scores.parquet': _EXPANSION+'raw_scores.parquet',
    'inputs/learned_qarf/best.pt': 'results/m3.2/RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01/'
                                   'QARF/20261022T040759-ff3934df/checkpoints/best.pt',
}


class EvaluationError(ValueError):
    """An input, authorization or output violates the frozen M4.4 contract."""


def require(ok, message):
    if not ok:
        raise EvaluationError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def write_json(path, data):
    with Path(path).open('x', encoding='utf8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def write_csv_gz(path, header, rows):
    """Deterministic bytes: no gzip timestamp/name; repr(float) round-trips exactly."""
    text = io.StringIO()
    writer = csv.writer(text, lineterminator='\n')
    writer.writerow(header)
    for row in rows:
        writer.writerow([repr(value) if type(value) is float else value for value in row])
    with Path(path).open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, filename='') as stream:
        stream.write(text.getvalue().encode('utf8'))


def read_csv_gz(path):
    with gzip.open(path, 'rt', encoding='utf8', newline='') as stream:
        return list(csv.DictReader(stream))


def restore_files(bundle, files, sources):
    """Copy only missing files whose source bytes match the manifest; never overwrite."""
    restored = []
    for entry in files:
        target = Path(bundle)/entry['path']
        if target.exists():
            require(sha(target) == entry['sha256'], f'existing bundle file differs: {entry["path"]}')
            continue
        source = sources.get(entry['path'])
        require(source is not None and Path(source).is_file() and sha(source) == entry['sha256'],
                f'no byte-identical source for {entry["path"]}')
        target.parent.mkdir(parents=True, exist_ok=True)
        with Path(source).open('rb') as incoming, target.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        require(sha(target) == entry['sha256'], f'restored bytes differ: {entry["path"]}')
        restored.append(entry['path'])
    return restored


def restore_inputs(root):
    root = Path(root).resolve()
    config = read(root/CONFIG)
    bundle = root/config['bundle']['run_path']
    require(sha(bundle/'manifest.json') == config['bundle']['manifest_sha256'], 'M4.2 manifest pin differs')
    return restore_files(bundle, read(bundle/'manifest.json')['files'],
                         {path: root/source for path, source in RESTORE_SOURCES.items()})


def validation_qrels(qrels, splits):
    """Development qrels may hold train/validation only; keep exactly the validation IDs."""
    require(not set(qrels) & set(splits['test']), 'development qrels contain test query IDs')
    require(set(splits['validation']) <= set(qrels), 'development qrels miss validation queries')
    return {query_id: qrels[query_id] for query_id in splits['validation']}


def load_context(root):
    """Verified bundle, frozen QPAF record and the 171 validation records; no test labels."""
    from qpaf.m24.config import load_config
    from qpaf.m24.dataset import build_records, read_score_rows, read_split_ids
    from qpaf.m42.active_primary import verify_files
    root = Path(root).resolve()
    config = read(root/CONFIG)
    bundle = root/config['bundle']['run_path']
    manifest = verify_files(bundle, config['bundle']['manifest_sha256'])
    require(read(bundle/'_SUCCESS.json')['manifest_sha256'] == config['bundle']['manifest_sha256'],
            'M4.2 success marker pin differs')
    require(sha(root/config['freeze']['path']) == config['freeze']['sha256'], 'M4.3 freeze pin differs')
    freeze = read(root/config['freeze']['path'])
    require(freeze['branch_disposition']['m4_branch'] == 'continue_qpaf', 'M4.3 freeze is not continue_qpaf')
    checkpoint = freeze['frozen_method']['checkpoint']
    require(sha(root/checkpoint['path']) == checkpoint['sha256'], 'frozen QPAF checkpoint bytes differ')
    for name, ref in config['saved_predictions'].items():
        require(sha(root/ref['path']) == ref['sha256'], f'saved {name} predictions differ')
    shared = read(bundle/'shared_inputs.json')
    splits = read_split_ids(bundle/'inputs/splits')
    require(len(splits['validation']) == config['validation_query_count'], 'validation ID count differs')
    qrels = validation_qrels(read(bundle/'inputs/qrels_development.json'), splits)
    records = build_records(read_score_rows(bundle/'inputs/raw_scores.parquet'),
                            read(bundle/'inputs/queries.json'), qrels, splits, ('validation',))['validation']
    require([r.query_id for r in records] == splits['validation'], 'validation records differ from split order')
    recall = sum(sum(r.labels)/r.relevant_total for r in records)/len(records)
    uncovered = sum(not any(r.labels) for r in records)
    require(recall >= config['minimum_macro_candidate_recall'] and not uncovered,
            'validation candidate coverage below the frozen gate')
    learned_config = load_config(bundle/'inputs/shared_base.toml')
    return {'config': config, 'bundle': bundle, 'bundle_manifest': manifest, 'shared': shared,
            'splits': splits, 'records': records, 'freeze': freeze, 'learned_config': learned_config,
            'contracts': read(bundle/'baseline_contracts.json'),
            'static_weights': read(bundle/'train_fit.json')['weights'],
            'coverage': {'query_count': len(records), 'macro_relevant_page_recall': recall,
                         'uncovered_queries': uncovered},
            'access': {'validation_qrels_deserialized': True, 'train_qrels_used': False,
                       'test_labels_deserialized': False, 'vimdoc_confirmation_accessed': False}}


def check_approval(auth, *, experiment_id, run_id, head, clean, config_sha256, output_exists):
    """Pure authorization checks; the approval must be the approver's recorded words."""
    approval = auth.get('approval') or {}
    require(auth.get('status') == 'APPROVED', 'authorization is not APPROVED')
    for key in ('approver', 'approval_text', 'approved_utc'):
        value = approval.get(key)
        require(isinstance(value, str) and value.strip() and 'PENDING' not in value,
                f'authorization approval {key} is missing')
    datetime.fromisoformat(approval['approved_utc'].replace('Z', '+00:00'))
    experiment = (auth.get('experiments') or {}).get(experiment_id)
    require(experiment is not None, f'{experiment_id} is not authorized')
    require(experiment['run_id'] == run_id, 'run ID differs from the authorization')
    require(auth['source_commit'] == head, 'HEAD differs from the authorized source commit')
    require(clean, 'execution requires a clean tracked tree')
    require(auth['config']['sha256'] == config_sha256, 'evaluation config differs from the authorization')
    require(not output_exists, 'run namespace already exists; retries need a new authorization')
    return experiment


SOURCE_FILES = (CONFIG, 'src/qpaf/m44/__init__.py', 'src/qpaf/m44/common.py', 'src/qpaf/m44/evaluation.py',
                'src/qpaf/m44/oracle.py', 'scripts/run_m44_evaluation.py', 'tests/test_m44_evaluation.py',
                'src/qpaf/m25/baselines.py', 'src/qpaf/m24/evaluator.py', 'src/qpaf/m24/dataset.py',
                'src/qpaf/m24/config.py', 'src/qpaf/m24/checkpoint.py', 'src/qpaf/m24/trainer.py',
                'src/qpaf/m12/model.py', 'src/qpaf/m12/features.py', 'src/qpaf/m42/active_primary.py',
                'scripts/audit_m35_paired.py', 'scripts/audit_m36_integrity.py', 'src/oracle_study/qpaf.py',
                'src/oracle_study/metrics.py', 'src/oracle_study/profiles.py',
                'scripts/qpaf_candidate_oracle_optimized.py')


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def runtime_versions():
    import platform
    import numpy
    import pandas
    import pyarrow
    import torch
    return {'python': platform.python_version(), 'torch': torch.__version__, 'numpy': numpy.__version__,
            'pandas': pandas.__version__, 'pyarrow': pyarrow.__version__}


def write_text(path, text):
    with Path(path).open('x', encoding='utf8', newline='\n') as stream:
        stream.write(text)


def files_manifest(output):
    """Every result file except the markers and the manifest that lists them."""
    return [{'path': p.relative_to(output).as_posix(), 'sha256': sha(p), 'size_bytes': p.stat().st_size}
            for p in sorted(Path(output).rglob('*'))
            if p.is_file() and not p.name.startswith('_') and p.name != 'manifest.json']


def execute_attempt(root, authorization, expected_sha256, experiment_id, run_id, produce, *, results_root=None):
    """Shared create-once attempt: _ATTEMPTED first, then outputs, manifest and one final marker."""
    import time
    from datetime import timezone
    root = Path(root).resolve()
    auth, experiment = check_authorization(root, authorization, expected_sha256, experiment_id, run_id)
    context = load_context(root)
    output = Path(results_root or root/'results/m4.4')/run_id
    output.mkdir(parents=True, exist_ok=False)
    commit = git(root, 'rev-parse', 'HEAD')
    write_json(output/'_ATTEMPTED.json', {'run_id': run_id, 'experiment_id': experiment_id, 'git_head': commit,
                                         'authorization_sha256': expected_sha256,
                                         'started_utc': datetime.now(timezone.utc).isoformat()})
    start = time.monotonic()
    limit = experiment['wall_time_seconds']
    deadline = lambda: require(time.monotonic()-start <= limit, f'{experiment_id} exceeded {limit}s wall time')
    try:
        summary = produce(context, output, deadline)
        deadline()
        write_json(output/'access.json', {**context['access'], 'coverage': context['coverage'],
                                         'new_training_executed': False})
        elapsed = time.monotonic()-start
        manifest = {'schema_version': 1, 'task_id': 'M4.4', 'experiment_id': experiment_id, 'run_id': run_id,
                    'experiment_class': experiment['experiment_class'],
                    'evidence_class': experiment['evidence_class'],
                    'status': 'PASS_VALIDATION_EVALUATION_PENDING_INDEPENDENT_REVIEW', 'source_commit': commit,
                    'authorization_sha256': expected_sha256, 'config_sha256': sha(root/CONFIG),
                    'bundle_manifest_sha256': context['config']['bundle']['manifest_sha256'],
                    'freeze_sha256': context['config']['freeze']['sha256'],
                    'source_hashes': {name: sha(root/name) for name in SOURCE_FILES},
                    'runtime': runtime_versions(), 'elapsed_seconds': elapsed, 'files': files_manifest(output),
                    'validation_query_count': len(context['records']), 'summary': summary,
                    'test_labels_deserialized': False}
        write_json(output/'manifest.json', manifest)
        write_json(output/'_SUCCESS.json', {'manifest_sha256': sha(output/'manifest.json'),
                                           'status': manifest['status'], 'wall_seconds': elapsed})
        return manifest
    except Exception as exc:
        write_json(output/'_FAILED.json', {'status': 'FAILED', 'error': str(exc), 'automatic_retry': False})
        raise


def verify_run(output, expected_manifest_sha256):
    output = Path(output)
    require(sha(output/'manifest.json') == expected_manifest_sha256, 'run manifest pin differs')
    manifest = read(output/'manifest.json')
    require(read(output/'_SUCCESS.json')['manifest_sha256'] == expected_manifest_sha256, 'success marker pin differs')
    require(not (output/'_FAILED.json').exists(), 'run carries a failure marker')
    require(files_manifest(output) == manifest['files'], 'run files differ from the manifest')
    for name, digest in manifest['source_hashes'].items():
        require(sha(ROOT/name) == digest, f'source changed since the run: {name}')
    return manifest


def check_authorization(root, path, expected_sha256, experiment_id, run_id):
    root = Path(root).resolve()
    require(Path(path).is_file() and sha(path) == expected_sha256, 'authorization pin differs')
    auth = read(path)
    git = lambda *args: subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    experiment = check_approval(
        auth, experiment_id=experiment_id, run_id=run_id, head=git('rev-parse', 'HEAD'),
        clean=not git('status', '--porcelain', '--untracked-files=no'),
        config_sha256=sha(root/auth['config']['path']), output_exists=(root/'results/m4.4'/run_id).exists())
    return auth, experiment
