"""A005-R1 evaluation: ensembles, the validation ablation table, and the one-time post-hoc confirmation.

The configuration was fixed before any of this ran. The confirmation split was already opened once by A005
Stage 5, so the record below is post-hoc; it is create-once and is the only R1 code that reads the sealed qrels,
and only through `stage5.confirmation_inputs` (which hashes the file first).
"""
from pathlib import Path

from qpaf.m25.statistics import paired_report
from qpaf.m43.freeze import git, read, sha, write_json

from . import stage5
from .refine import NAME, ROOT_DIR, RefineError, load_model, require, run_dir, variant_config
from .stage2 import CACHE_FILES, split_inputs
from .stage4 import GRANULARITIES, METHOD, SEEDS, STAGE3, per_query_ndcg, validation_scores
from .stage4 import run_dir as s4_run_dir

VALIDATION_OUTPUT = ROOT_DIR+'/validation.json'
CONFIRMATION_OUTPUT = ROOT_DIR+'/confirmation.json'
R1 = {'query': 'QARF-SA-R1', 'page': 'QPAF-SA-R1'}
NOTE = 'configuration fixed before evaluation; confirmation split already opened once by A005 Stage 5'


def mean_scores(score_sets):
    """Per query, the mean over models of the fused page scores."""
    return {q: [sum(values)/len(score_sets) for values in zip(*(scores[q] for scores in score_sets))]
            for q in score_sets[0]}


def ensemble_scores(models, records):
    """Fused page scores averaged over models; the document max is taken afterwards, as for one model."""
    return mean_scores([validation_scores(model, records) for model in models])


def recorded_run(root, variant, granularity, seed):
    """A recorded R1 run whose checkpoints still match their result.json."""
    directory = run_dir(root, variant, granularity, seed)
    require((directory/'result.json').is_file(), f'R1 run missing: {directory.name}')
    result = read(directory/'result.json')
    require((result['variant'], result['granularity'], result['seed']) == (variant, granularity, seed),
            'R1 result is for another run')
    for file, digest in result['checkpoint_sha256'].items():
        require((directory/file).is_file() and sha(directory/file) == digest, f'R1 checkpoint differs: {file}')
    return result


def load_models(root, variant, granularity, seeds, file):
    anchor = read(Path(root)/STAGE3)['stage4_anchor_weights']
    epsilon = variant_config(variant)['epsilon']
    return [load_model(run_dir(root, variant, granularity, seed)/file, anchor, granularity, epsilon)
            for seed in seeds]


def mean(values):
    values = list(values)
    return sum(values)/len(values)


def validation_table(root, cache):
    """Create-once validation.json: seven rows per granularity, each with its delta to train_fitted_static."""
    root = Path(root).resolve()
    require(not (root/VALIDATION_OUTPUT).exists(), f'output already exists: {VALIDATION_OUTPUT}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'), 'table requires a clean tracked tree')
    stage3 = read(root/STAGE3)
    static = stage3['roster']['train_fitted_static']['ndcg_at_10']
    records, qrels = split_inputs(root, cache, 'validation')
    first = SEEDS[:1]
    rows, shas = {}, {}
    for granularity in GRANULARITIES:
        results = {(v, s): recorded_run(root, v, granularity, s)
                   for v, seeds in (('full', SEEDS), ('eps1e3', first), ('constlr', first)) for s in seeds}
        original = [read(s4_run_dir(root, granularity, s)/'result.json') for s in SEEDS]
        ensemble = lambda file: mean(per_query_ndcg(  # noqa: E731
            ensemble_scores(load_models(root, 'full', granularity, SEEDS, file), records),
            records, qrels).values())
        averaged = lambda variant, seed: results[(variant, seed)]['validation']['averaged']['ndcg_at_10']  # noqa: E731
        values = [
            ('a005_original', 'A005 original, mean of 3 seeds (epoch chosen on validation, 20 epochs)',
             mean(r['validation_ndcg_at_10'] for r in original)),
            ('full_ensemble', 'R1 full, ensemble of 3 weight-averaged models', ensemble('averaged.pt')),
            ('full_seed_mean', 'R1 full, mean of 3 weight-averaged models (no ensemble)',
             mean(averaged('full', s) for s in SEEDS)),
            ('full_best_epoch_ensemble', 'R1 full, ensemble of 3 best-epoch models (epoch picked on validation)',
             ensemble('best_epoch.pt')),
            ('eps1e3_seed1', 'ablation: epsilon 1e-3, weight-averaged, seed 20260820', averaged('eps1e3', first[0])),
            ('constlr_seed1', 'ablation: constant LR, weight-averaged, seed 20260820', averaged('constlr', first[0])),
            ('full_seed1', 'R1 full, weight-averaged, seed 20260820', averaged('full', first[0]))]
        rows[granularity] = [{'id': name, 'description': text, 'ndcg_at_10': value, 'delta_vs_static': value-static}
                             for name, text, value in values]
        shas[granularity] = {f'{v}-{s}': sha(run_dir(root, v, granularity, s)/'result.json') for v, s in results}
    record = {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': 'R1-validation',
              'experiment_id': 'QPAF-A005-R1-VAL', 'dataset': 'ViMDoc', 'split': 'validation', 'unit': 'document',
              'methods': R1, 'train_fitted_static': static, 'rows': rows, 'run_result_sha256': shas,
              'inputs_sha256': {name: sha(Path(cache)/name) for name in CACHE_FILES}, 'stage3_sha256': sha(root/STAGE3),
              'source_commit': git(root, 'rev-parse', 'HEAD'), 'post_hoc': True,
              'confirmation_labels_opened': False, 'vidoseek_test_accessed': False}
    write_json(root/VALIDATION_OUTPUT, record)
    return record


def confirmation_record(root, cache, sealed_path):
    """Create-once confirmation.json for the `full` configuration. Every check precedes opening the seal."""
    import torch
    root = Path(root).resolve()
    require(not (root/CONFIRMATION_OUTPUT).exists(), f'output already exists: {CONFIRMATION_OUTPUT}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'),
            'confirmation requires a clean tracked tree')
    pins = {name: sha(Path(cache)/name) for name in CACHE_FILES}
    results = {}
    for granularity in GRANULARITIES:
        for seed in SEEDS:
            results[(granularity, seed)] = recorded_run(root, 'full', granularity, seed)
            require(results[(granularity, seed)]['inputs_sha256'] == pins, 'R1 run used another cache')
    require((root/stage5.OUTPUT).is_file(), 'Stage 5 confirmation record missing')
    stage5_record = read(root/stage5.OUTPUT)
    records, qrels = stage5.confirmation_inputs(root, cache, sealed_path)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    order = {r.query_id for r in records}
    static = stage5_record['baselines']['train_fitted_static']['per_query']
    require(set(static) == order, 'Stage 5 static baseline covers other queries')
    original = {seed: stage5_record['methods'][METHOD['page']][str(seed)] for seed in SEEDS}
    require(all(set(entry['per_query']) == order for entry in original.values()), 'Stage 5 methods cover other queries')
    per_seed, ensembles = {}, {}
    for granularity in GRANULARITIES:
        models = load_models(root, 'full', granularity, SEEDS, 'averaged.pt')
        score_sets = [validation_scores(model, records) for model in models]
        per_seed[R1[granularity]] = {}
        for seed, scores in zip(SEEDS, score_sets):
            values = per_query_ndcg(scores, records, qrels)
            per_seed[R1[granularity]][str(seed)] = {'ndcg_at_10': mean(values.values()), 'per_query': values}
        values = per_query_ndcg(mean_scores(score_sets), records, qrels)
        ensembles[R1[granularity]] = {'ndcg_at_10': mean(values.values()), 'per_query': values}
    qpaf, qarf = ensembles[R1['page']]['per_query'], ensembles[R1['query']]['per_query']
    same = lambda values: {seed: values for seed in SEEDS}  # noqa: E731
    comparisons = {
        'a_qpaf_r1_vs_static': paired_report(same(qpaf), same(static)),
        'b_qpaf_r1_vs_qarf_r1': paired_report(same(qpaf), same(qarf)),
        'c_qpaf_r1_vs_qpaf_sa_v2': paired_report(same(qpaf), {s: e['per_query'] for s, e in original.items()})}
    record = {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': 'R1-confirmation',
              'experiment_id': 'QPAF-A005-R1-CNF', 'dataset': 'ViMDoc', 'split': 'confirmation', 'unit': 'document',
              'post_hoc': True, 'note': NOTE, 'variant': 'full', 'confirmation_query_count': len(records),
              'ndcg_at_10': {'train_fitted_static': stage5_record['baselines']['train_fitted_static']['ndcg_at_10'],
                             'QPAF-SA-v2 (A005, mean of 3 seeds)': mean(e['ndcg_at_10'] for e in original.values()),
                             **{f'{name} ensemble': entry['ndcg_at_10'] for name, entry in ensembles.items()}},
              'ensembles': ensembles, 'per_seed_averaged': per_seed, 'comparisons': comparisons,
              'primary_comparisons': ['a_qpaf_r1_vs_static', 'b_qpaf_r1_vs_qarf_r1'],
              'run_result_sha256': {f'full-{NAME[g]}-{s}': sha(run_dir(root, 'full', g, s)/'result.json')
                                    for g, s in results},
              'stage5_confirmation_sha256': sha(root/stage5.OUTPUT),
              'inputs_sha256': {**pins, stage5.SEALED_NAME: sha(sealed_path)}, 'stage3_sha256': sha(root/STAGE3),
              'confirmation_labels_opened': True, 'vidoseek_test_accessed': False,
              'source_commit': git(root, 'rev-parse', 'HEAD')}
    write_json(root/CONFIRMATION_OUTPUT, record)
    return record
