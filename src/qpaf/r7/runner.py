"""Create-once R7 execution, a label-free preflight and a read-only replay. Local CPU only.

`preflight` runs only R7-00 and the label-free test scoring checks; it never opens the sealed qrels and
writes nothing. `execute` opens them once, after the test predictions are written and sealed.
"""
import json
from pathlib import Path
import subprocess
import time

from qpaf.m44.common import files_manifest, load_context, read, runtime_versions, sha, write_csv_gz, write_json
from qpaf.m44.evaluation import (_scripts, _wide_rows, check_parity, evaluate_all, learned_predictions, read_wide,
                                 write_per_query)
from .sealed import (BASELINES, COLUMNS, LIMITS, SEEDS, TEST_QUERY_COUNT, check_approval, check_seal, contrasts,
                     label_free_records, now, open_sealed_qrels, require, same_candidates, write_seal)

AUTHORIZATION_PATH = 'evidence/revisions/r7-001/authorization.json'
G2A = ('evidence/revisions/m4.7-001/g2a_freeze.json',
       '26d9bab6e7d47fe7dd1e89f6bec2c95265641df5cde8d9bd25c867b9d3a73217')
FREEZE = 'evidence/revisions/m4.3-001/method_freeze.json'
REFERENCE = 'results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01'
METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')
STATIC_WEIGHTS = [0.0, 0.1, 0.9]
SOURCE_FILES = ('src/qpaf/r7/__init__.py', 'src/qpaf/r7/sealed.py', 'src/qpaf/r7/runner.py',
                'scripts/run_r7_test172.py', 'tests/test_r7_test172.py',
                'src/qpaf/m44/common.py', 'src/qpaf/m44/evaluation.py', 'src/qpaf/m44/oracle.py',
                'src/qpaf/m42/active_primary.py', 'src/qpaf/m25/baselines.py', 'scripts/audit_m35_paired.py',
                'scripts/audit_m36_integrity.py', 'src/oracle_study/qpaf.py', 'src/oracle_study/profiles.py',
                'src/oracle_study/metrics.py', 'scripts/qpaf_candidate_oracle_optimized.py',
                'src/qpaf/m24/dataset.py', 'src/qpaf/m24/evaluator.py', 'src/qpaf/m24/checkpoint.py',
                'src/qpaf/m24/config.py', 'src/qpaf/m24/trainer.py', 'src/qpaf/m12/features.py',
                'src/qpaf/m12/model.py')
STATUS = 'PASS_TEST172_SEALED_EVALUATION_PENDING_INDEPENDENT_VERIFICATION'
RERUN_RULE = ('Not rerun under this authorization once the sealed qrels were read; '
              'a rerun needs an amendment and Thanh\'s review first.')


def source_hashes(root):
    return {p: sha(Path(root)/p) for p in SOURCE_FILES}


def _git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf8').strip()


def check_bindings(root, auth):
    """Every pinned byte on disk matches; the sealed qrels are hashed, never parsed."""
    root = Path(root)
    require(sha(root/G2A[0]) == G2A[1], 'G2A freeze differs')
    g2a = read(root/G2A[0])
    held = auth['held_out']
    require(held['ids_sha256'] == g2a['held_out']['ids_sha256'] and
            held['sealed_qrels_sha256'] == g2a['held_out']['sealed_qrels_sha256'] and
            held['query_count'] == TEST_QUERY_COUNT and not held['opened_before_this_run'],
            'held-out contract differs from G2A')
    require(sha(root/held['ids']) == held['ids_sha256'], 'test ID file differs')
    require(sha(root/held['sealed_qrels']) == held['sealed_qrels_sha256'], 'sealed qrels bytes differ')
    for group in ('authority_pins', 'input_pins'):
        for relative, digest in auth[group].items():
            require(sha(root/relative) == digest, f'{group} hash differs: {relative}')
    for relative, digest in read(root/FREEZE)['source_sha256'].items():
        require(sha(root/relative) == digest, f'frozen method source differs: {relative}')
    checkpoints = auth['method_checkpoints']
    require(set(checkpoints) == {f'{m}/{s}' for m in ('QARF', 'QPAF') for s in SEEDS}, 'method set differs')
    require(checkpoints['QPAF/20260820']['checkpoint_sha256'] == g2a['main_method']['checkpoint_sha256'] and
            checkpoints['QARF/20260820']['checkpoint_sha256'] == g2a['matched_comparator']['checkpoint_sha256'],
            'pilot checkpoints differ from G2A')
    for key, entry in checkpoints.items():
        attempt = root/entry['attempt']
        require(sha(attempt/'checkpoints/best.pt') == entry['checkpoint_sha256'], f'{key}: checkpoint differs')
        require(sha(attempt/'validation_predictions.json') == entry['validation_predictions_sha256'],
                f'{key}: saved validation predictions differ')


def _configs(root, auth):
    from qpaf.m24.config import validate
    configs = {}
    for key, entry in auth['method_checkpoints'].items():
        config = read(Path(root)/entry['attempt']/'resolved_config.json')
        validate(config)
        require(config['training']['seed'] == int(key.split('/')[1]), f'{key}: config seed differs')
        configs[key] = config
    return configs


def _reference_per_query(root):
    import csv
    manifest = read(Path(root)/REFERENCE/'manifest.json')
    pinned = {f['path']: f['sha256'] for f in manifest['files']}
    require(sha(Path(root)/REFERENCE/'per_query_metrics.csv') == pinned['per_query_metrics.csv'],
            'M4.4 per-query reference differs')
    with (Path(root)/REFERENCE/'per_query_metrics.csv').open(encoding='utf8', newline='') as stream:
        return {(r['method'], r['query_id']): r for r in csv.DictReader(stream)}


def _baseline_predictions(context, records):
    from qpaf.m25.baselines import predictions
    return {m: predictions(records, m, weights=STATIC_WEIGHTS if m == 'train_fitted_static' else None)
            for m in BASELINES[:-1]}


def _learned(context, records, configs, root):
    """QARF/QPAF x3 from the accepted checkpoints, and learned_qarf from the M4.2 bundle copy."""
    result = {}
    for key, config in configs.items():
        method, seed = key.split('/')
        entry = context['auth']['method_checkpoints'][key]
        result[f'{method.lower()}_{seed}'] = learned_predictions(
            {**context, 'records': records, 'learned_config': config}, method,
            Path(root)/entry['checkpoint'], entry['checkpoint_sha256'])
    bundle_qarf = context['shared']['inputs']['qarf_checkpoint']
    require(bundle_qarf['sha256'] == context['contracts']['learned_qarf']['checkpoint_sha256'],
            'learned QARF differs from the M4.2 contract')
    result['learned_qarf'] = learned_predictions({**context, 'records': records,
                                                  'learned_config': configs['QARF/20260820']},
                                                 'QARF', context['bundle']/bundle_qarf['path'], bundle_qarf['sha256'])
    require([p['scores'] for p in result['learned_qarf']] == [p['scores'] for p in result['qarf_20260820']],
            'learned_qarf and QARF seed 20260820 disagree')
    return result


def preflight(root, auth):
    """R7-00 plus label-free test scoring. Reads validation qrels and test score rows, never test labels."""
    from qpaf.m24.dataset import read_score_rows
    root = Path(root).resolve()
    check_bindings(root, auth)
    context = {**load_context(root), 'auth': auth}
    require(context['contracts']['train_fitted_static']['weights'] == STATIC_WEIGHTS and
            context['static_weights'] == STATIC_WEIGHTS, 'frozen static weights differ')
    configs = _configs(root, auth)
    report = {'learned_parity': {}, 'baseline_reference_max_abs_difference': 0.0}
    learned = _learned(context, context['records'], configs, root)
    for key, entry in auth['method_checkpoints'].items():
        method, seed = key.split('/')
        saved = read(root/entry['attempt']/'validation_predictions.json')
        report['learned_parity'][key] = check_parity(saved, learned[f'{method.lower()}_{seed}'], tolerance=1e-7)
    reference = _reference_per_query(root)
    validation = {**_baseline_predictions(context, context['records']), 'learned_qarf': learned['learned_qarf']}
    worst = 0.0
    for method, rows in evaluate_all(validation, context['records'])[1].items():
        for row in rows:
            saved = reference[(method, row['query_id'])]
            worst = max(worst, *(abs(row[k]-float(saved[k])) for k in METRICS))
    require(worst <= 1e-12, f'baselines differ from M4.4 validation by {worst}')
    report['baseline_reference_max_abs_difference'] = worst
    rows = read_score_rows(context['bundle']/'inputs/raw_scores.parquet')
    queries = read(context['bundle']/'inputs/queries.json')
    config = context['learned_config']
    test = label_free_records(rows, queries, context['splits'], max_candidates=config['data']['max_candidates'])
    require(len(test) == TEST_QUERY_COUNT and [r.query_id for r in test] == context['splits']['test'],
            'label-free test records differ from the 172 pinned IDs')
    report.update({'validation_queries': len(context['records']), 'test_queries': len(test),
                   'test_candidates': sum(len(r.page_ids) for r in test), 'test_labels_deserialized': False})
    return {'context': context, 'configs': configs, 'rows': rows, 'queries': queries, 'test': test,
            'report': report}


def test_predictions(state, root):
    """Every R7 column on the label-free test records; all scores finite."""
    import math
    test = state['test']
    result = {**_baseline_predictions(state['context'], test), **_learned(state['context'], test,
                                                                         state['configs'], root)}
    require(set(result) == set(COLUMNS), 'prediction columns differ')
    require(all(math.isfinite(x) for rows in result.values() for p in rows for x in p['scores']),
            'non-finite test score')
    return result


def score(output, labeled, deadline):
    """Metrics from the sealed prediction bytes; oracle rows and per-seed contrasts after the opening."""
    from qpaf.m24.evaluator import evaluate
    from qpaf.m44.oracle import GRIDS, NAMES, oracle_scores
    paired_statistics = _scripts()[0].paired_statistics
    sealed = read_wide(Path(output)/'test_predictions.csv.gz', labeled, COLUMNS)
    metrics, per_query = evaluate_all(sealed, labeled)
    oracle, details = {}, {}
    for grid in GRIDS:
        rows, details[grid] = oracle_scores(labeled, grid, deadline=deadline)
        oracle.update(rows)
    for name in NAMES:
        metrics[name], per_query[name] = evaluate(oracle[name], labeled)
    deadline()
    stats = {name: paired_statistics(rows, resamples=10000, seed=20260820)
             for name, rows in contrasts(per_query).items()}
    recall = sum(sum(r.labels)/r.relevant_total for r in labeled)/len(labeled)
    table = {'split': 'test', 'query_count': len(labeled),
             'deployable': [{'method': m, **{k: metrics[m][k] for k in METRICS}} for m in BASELINES],
             'methods': [{'method': m, **{k: metrics[m][k] for k in METRICS}} for m in COLUMNS[len(BASELINES):]],
             'oracle_context': [{'method': n, 'selection_eligible': False, **{k: metrics[n][k] for k in METRICS}}
                                for n in NAMES],
             'notes': ['Single sealed opening of ViDoSeek test 172; nothing is selected from these numbers.',
                       'Oracle rows use test labels; they are non-deployable upper bounds.',
                       'Per-seed contrasts only; seed-averaged statistics belong to R8/M5.7.']}
    return {'table': table, 'paired': {'resamples': 10000, 'rng': 'numpy default_rng(20260820)',
                                       'contrasts': stats},
            'per_query': per_query, 'oracle': oracle, 'details': details,
            'coverage': {'query_count': len(labeled), 'macro_relevant_page_recall': recall,
                         'uncovered_queries': sum(not any(r.labels) for r in labeled),
                         'gate': 'reported only; checking it after the opening could not change the run'}}


def _write_scored(output, labeled, result):
    from qpaf.m44.oracle import NAMES
    write_csv_gz(Path(output)/'oracle_predictions.csv.gz', ['query_id', 'page_id', *NAMES],
                 _wide_rows(result['oracle'], labeled, NAMES))
    write_per_query(Path(output)/'per_query_metrics.csv', result['per_query'])
    write_json(Path(output)/'metrics_table.json', result['table'])
    write_json(Path(output)/'paired_per_seed.json', result['paired'])
    write_json(Path(output)/'oracle_details.json', result['details'])


def check_authorization(root, path, pin, run_id):
    root = Path(root).resolve()
    require(len(pin or '') == 64 and sha(path) == pin, 'authorization external pin differs')
    require(Path(path).resolve() == (root/AUTHORIZATION_PATH).resolve(), 'authorization namespace differs')
    auth = read(path)
    check_approval(auth, run_id=run_id, clean=not _git(root, 'status', '--porcelain', '-uno'),
                   source_hashes=source_hashes(root), runtime=runtime_versions(),
                   output_exists=(root/'results/r7'/run_id).exists())
    head = _git(root, 'rev-parse', 'HEAD')
    ancestry = subprocess.run(['git', 'merge-base', '--is-ancestor', auth['source_commit'], head], cwd=root)
    require(ancestry.returncode == 0, 'implementation commit is not an ancestor of execution HEAD')
    changed = _git(root, 'diff', '--name-only', auth['source_commit'], head).splitlines()
    require(set(changed) <= {AUTHORIZATION_PATH}, 'changes after implementation include more than authorization')
    committed = subprocess.check_output(['git', 'show', head+':'+AUTHORIZATION_PATH], cwd=root)
    require(committed == Path(path).read_bytes(), 'authorization must be committed before execution')
    return auth, head


def execute(root, authorization, expected_sha256, run_id, *, results_root=None):
    """R7-00 .. R7-05 once; _ATTEMPTED first, the seal before the labels, one final marker."""
    from qpaf.m24.dataset import build_records
    root = Path(root).resolve()
    auth, head = check_authorization(root, authorization, expected_sha256, run_id)
    output = Path(results_root or root/'results/r7')/run_id
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'_ATTEMPTED.json', {'run_id': run_id, 'git_head': head, 'authorization_sha256': expected_sha256,
                                         'started_utc': now()})
    start, opened = time.monotonic(), False
    deadline = lambda: require(time.monotonic()-start <= LIMITS['wall_time_seconds'],
                               f'R7 exceeded {LIMITS["wall_time_seconds"]}s wall time')
    try:
        state = preflight(root, auth)
        write_json(output/'preflight.json', state['report'])
        predictions = test_predictions(state, root)
        deadline()
        write_csv_gz(output/'test_predictions.csv.gz', ['query_id', 'page_id', *COLUMNS],
                     _wide_rows(predictions, state['test'], COLUMNS))
        seal = write_seal(output, 'test_predictions.csv.gz')
        del predictions
        deadline()
        check_seal(output)
        context, config = state['context'], state['context']['learned_config']
        qrels = open_sealed_qrels(root/auth['held_out']['sealed_qrels'], auth['held_out']['sealed_qrels_sha256'],
                                  context['splits']['test'])
        opened = True
        write_json(output/'_LABELS_OPENED.json', {'opened_utc': now(), 'prediction_seal_sha256': seal['sha256']})
        labeled = build_records(state['rows'], state['queries'], qrels, context['splits'], ('test',),
                                positive_threshold=config['data']['positive_threshold'],
                                max_candidates=config['data']['max_candidates'])['test']
        same_candidates(state['test'], labeled)
        result = score(output, labeled, deadline)
        _write_scored(output, labeled, result)
        deadline()
        write_json(output/'access.json', {'test_labels_deserialized': True, 'sealed_qrels_reads': 1,
                                         'validation_qrels_deserialized': True, 'train_qrels_used': False,
                                         'vimdoc_accessed': False, 'new_training_executed': False,
                                         'coverage': result['coverage']})
        elapsed = time.monotonic()-start
        manifest = {'schema_version': 1, 'task_id': 'TEST-172', 'roster_id': 'R7', 'run_id': run_id,
                    'experiment_id': auth['experiment_id'], 'status': STATUS, 'source_commit': auth['source_commit'],
                    'git_head': head, 'authorization_sha256': expected_sha256,
                    'prediction_seal_sha256': seal['sha256'], 'source_hashes': source_hashes(root),
                    'runtime': runtime_versions(), 'elapsed_seconds': elapsed, 'files': files_manifest(output),
                    'summary': {'ndcg_at_10': {row['method']: row['ndcg_at_10']
                                               for block in ('deployable', 'methods')
                                               for row in result['table'][block]}}}
        write_json(output/'manifest.json', manifest)
        write_json(output/'_SUCCESS.json', {'manifest_sha256': sha(output/'manifest.json'), 'status': STATUS,
                                           'wall_seconds': elapsed})
        return manifest
    except Exception as exc:
        write_json(output/'_FAILED.json', {'status': 'FAILED', 'error': str(exc), 'labels_opened': opened,
                                          'automatic_retry': False, 'rerun_rule': RERUN_RULE})
        raise


def verify(root, output, expected_manifest_sha256):
    """Replay a finished run: hashes, label-free re-prediction equal to the seal, then the scored outputs."""
    from qpaf.m24.dataset import build_records
    root, output = Path(root).resolve(), Path(output)
    require(sha(output/'manifest.json') == expected_manifest_sha256, 'run manifest pin differs')
    manifest = read(output/'manifest.json')
    require(read(output/'_SUCCESS.json')['manifest_sha256'] == expected_manifest_sha256, 'success marker differs')
    require(not (output/'_FAILED.json').exists() and (output/'_LABELS_OPENED.json').is_file(), 'run markers differ')
    require(files_manifest(output) == manifest['files'], 'run files differ from the manifest')
    require(source_hashes(root) == manifest['source_hashes'], 'source changed since the run')
    require(sha(root/AUTHORIZATION_PATH) == manifest['authorization_sha256'], 'authorization differs')
    seal = check_seal(output)
    require(seal['sha256'] == manifest['prediction_seal_sha256'], 'seal differs from the manifest')
    auth = read(root/AUTHORIZATION_PATH)
    state = preflight(root, auth)
    fresh = test_predictions(state, root)
    sealed = read_wide(output/'test_predictions.csv.gz', state['test'], COLUMNS)
    require(all([p['scores'] for p in fresh[c]] == [p['scores'] for p in sealed[c]] for c in COLUMNS),
            'label-free re-prediction differs from the sealed predictions')
    context, config = state['context'], state['context']['learned_config']
    qrels = open_sealed_qrels(root/auth['held_out']['sealed_qrels'], auth['held_out']['sealed_qrels_sha256'],
                              context['splits']['test'])
    labeled = build_records(state['rows'], state['queries'], qrels, context['splits'], ('test',),
                            positive_threshold=config['data']['positive_threshold'],
                            max_candidates=config['data']['max_candidates'])['test']
    result = score(output, labeled, lambda: None)
    for name, value in (('metrics_table.json', result['table']), ('paired_per_seed.json', result['paired'])):
        require(read(output/name) == json.loads(json.dumps(value)), f'{name} does not replay')
    return {'status': 'PASS', 'run_id': manifest['run_id'], 'prediction_seal_sha256': seal['sha256'],
            'summary': manifest['summary']}
