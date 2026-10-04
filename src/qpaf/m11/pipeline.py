"""Stage orchestration shared by local cache evaluation and Modal workers."""
import json
from pathlib import Path
import re

from .artifacts import StageRun, completed_stage, digest, read_json, verify_manifest, write_csv, write_json
from .dataset import prepare
from .oracle import evaluate
from .retrieval import bm25_scores, dense_scores, visual_scores, load_score_cache, save_score_cache

STAGES = ('prepare', 'bm25', 'dense', 'visual', 'oracle')


def verify_generation_config(path, stage, requested):
    receipt = read_json(path/'receipt.json')
    verify_manifest(path, receipt['outputs'])
    recorded = read_json(path/'resolved_config.json')
    sections = ['dataset', 'selection', 'text']
    if stage != 'prepare':
        sections.extend([stage, 'execution'])
    for section in sections:
        if recorded[section] != requested[section]:
            raise ValueError(f'{stage} cache was generated with a different {section} configuration')


def run_directory(workspace, run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', run_id):
        raise ValueError('Run ID must be 1-100 ASCII letters/digits/dot/underscore/hyphen')
    return Path(workspace)/'runs'/run_id


def resolve_stage(root, stage, config, source, memo=None):
    memo = {} if memo is None else memo
    if stage in memo:
        return memo[stage]
    inputs = {}
    if stage != 'prepare':
        prepared = resolve_stage(root, 'prepare', config, source, memo)
        if prepared is None:
            raise ValueError('Run prepare successfully before scoring/evaluation')
        inputs['prepare'] = digest(prepared/'receipt.json')
    if stage == 'oracle':
        for channel in ('bm25', 'dense', 'visual'):
            cached = resolve_stage(root, channel, config, source, memo)
            if cached is None:
                raise ValueError(f'Missing completed {channel} score cache')
            inputs[channel] = digest(cached/'receipt.json')
    memo[stage] = completed_stage(root, stage, config, inputs, source)
    return memo[stage]


def write_reports(output, queries, pages, qrels, scores, config, dataset, logger):
    query_ids = [row['query_id'] for row in queries]
    page_ids = [row['page_id'] for row in pages]
    rows, summary, decisions = evaluate(scores, query_ids, page_ids, qrels, config)
    summary['dataset'] = dataset
    write_csv(output/'query_ids.csv', [{'query_id': query, 'scope': 'new_oracle_study'} for query in query_ids])
    write_csv(output/'per_query_metrics.csv', rows)
    write_json(output/'summary.json', summary)
    with (output/'oracle_decisions.jsonl').open('w', encoding='utf-8') as stream:
        for row in decisions:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
    lines = ['# New M1.1 Oracle run', '',
             'This is a new study with recorded inputs, not a reproduction of the historical Exploratory-24.',
             f'Queries: {len(queries)}. Corpus pages: {len(pages)}. Metric: {summary["metric"]}.', '',
             '| Weight set | Global | QARF | QPAF | Delta | CI95 | W/T/L |',
             '| --- | --- | --- | --- | --- | --- | --- |']
    for name, stats in summary['weight_sets'].items():
        lines.append(f'| {name} | {stats["global_mean"]:.6f} | {stats["qarf_mean"]:.6f} | '
                     f'{stats["qpaf_mean"]:.6f} | {stats["mean_delta"]:.6f} | {stats["ci95"]} | '
                     f'{stats["wins"]}/{stats["ties"]}/{stats["losses"]} |')
    lines.extend(['', 'Binary per-page Oracle maximizes relevant scores and minimizes nonrelevant scores.',
                  'Weight sets containing all three simplex vertices have the same QPAF optimum.',
                  'The historical report has different W7/W66 QPAF values; its exact solver and inputs',
                  'were not supplied. That difference remains unresolved and is not a reproduction target.',
                  'Global selects weights using all study labels and is also an Oracle, not a deployable baseline.',
                  'No learned QPAF performance is measured. Historical study scopes are not pooled here.',
                  'Independent review by another team member: PENDING.', ''])
    (output/'review.md').write_text('\n'.join(lines), encoding='utf-8')
    logger.info('evaluated %d queries; independent QA remains pending', len(queries))


def execute_stage(stage, config, workspace, run_id, source):
    if stage not in STAGES:
        raise ValueError(f'Unknown pipeline stage: {stage}')
    root = run_directory(workspace, run_id)
    memo = {}
    existing = resolve_stage(root, stage, config, source, memo)
    if existing is not None:
        return existing
    inputs = {}
    prepared = None
    caches = {}
    if stage != 'prepare':
        prepared = resolve_stage(root, 'prepare', config, source, memo)
        inputs['prepare'] = digest(prepared/'receipt.json')
    if stage == 'oracle':
        for channel in ('bm25', 'dense', 'visual'):
            caches[channel] = resolve_stage(root, channel, config, source, memo)
            inputs[channel] = digest(caches[channel]/'receipt.json')
    with StageRun(root, stage, config, inputs, source) as run:
        cache_dir = Path(workspace)/'hf-cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        if stage == 'prepare':
            prepare(config, run.path, run.logger, cache_dir)
        else:
            queries = read_json(prepared/'queries.json')
            pages = read_json(prepared/'pages.json')
            query_ids = [row['query_id'] for row in queries]
            page_ids = [row['page_id'] for row in pages]
            texts = [row['text'] for row in pages]
            question_texts = [row['text'] for row in queries]
            if stage == 'oracle':
                import numpy as np
                scores = np.stack([load_score_cache(caches[channel], query_ids, page_ids, channel)
                                   for channel in ('bm25', 'dense', 'visual')], axis=-1)
                write_reports(run.path, queries, pages, read_json(prepared/'qrels.json'), scores,
                              config, read_json(prepared/'dataset.json'), run.logger)
            else:
                if stage == 'bm25':
                    scores = bm25_scores(question_texts, texts, config['bm25']['k1'], config['bm25']['b'])
                else:
                    import torch
                    torch.manual_seed(config['execution']['seed'])
                    write_json(run.path/'compute.json', {'torch': torch.__version__,
                               'cuda': torch.version.cuda, 'seed': config['execution']['seed'],
                               'gpu': torch.cuda.get_device_name() if torch.cuda.is_available() else None})
                    if stage == 'dense':
                        scores = dense_scores(question_texts, texts, config['dense'], run.path, run.logger, cache_dir)
                    else:
                        scores = visual_scores(question_texts, pages, prepared, config['visual'], run.path, run.logger, cache_dir)
                save_score_cache(run.path, scores, query_ids, page_ids, stage)
                run.logger.info('saved %s scores: %s', stage, scores.shape)
    return run.path
