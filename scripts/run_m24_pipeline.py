"""Train one learned method (QARF or QPAF), select on validation and retain evidence.

Inputs are either a real score cache (--scores/--queries/--qrels/--splits) or the
deterministic synthetic fixture. Test labels are never opened: test IDs are read
only to prove split disjointness.
"""
import argparse
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m11.artifacts import StageRun, digest, object_hash, source_provenance, write_csv, write_json
from qpaf.m24.config import METHODS, METRICS, load_config, validate


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--method', required=True, choices=sorted(METHODS))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--epochs', type=int, help='override training.epochs (recorded in resolved config)')
    parser.add_argument('--resume', type=Path, help='continue from a last.pt of the same config/method')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--synthetic-fixture', action='store_true')
    source.add_argument('--scores', type=Path, help='parquet/csv with qpaf_score_rows_v1 columns')
    parser.add_argument('--queries', type=Path, help='JSON {query_id: text}')
    parser.add_argument('--qrels', type=Path, help='JSON {query_id: {page_id: relevance}}')
    parser.add_argument('--splits', type=Path, help='directory with train/val/test_ids.txt')
    args = parser.parse_args(argv)
    if args.scores and not (args.queries and args.qrels and args.splits):
        parser.error('--scores requires --queries, --qrels and --splits')
    return args


def load_inputs(args, config):
    from qpaf.m24.dataset import build_records, read_score_rows, read_split_ids
    from qpaf.m24.synthetic import make_fixture
    if args.synthetic_fixture:
        rows, queries, qrels, splits = make_fixture(config['training']['seed'])
    else:
        rows = read_score_rows(args.scores)
        queries = json.loads(args.queries.read_text(encoding='utf-8'))
        qrels = json.loads(args.qrels.read_text(encoding='utf-8'))
        splits = read_split_ids(args.splits)
    return build_records(rows, queries, qrels, splits, ('train', 'validation'),
                         positive_threshold=config['data']['positive_threshold'],
                         max_candidates=config['data']['max_candidates']), splits


def data_manifest(records, splits):
    roles = {}
    for role, items in records.items():
        in_union = sum(sum(r.labels) for r in items)
        total = sum(r.relevant_total for r in items)
        roles[role] = {'queries': len(items), 'candidates': sum(len(r.page_ids) for r in items),
                       'max_candidates': max(len(r.page_ids) for r in items),
                       'relevant_in_candidates': in_union, 'relevant_total': total,
                       'candidate_recall': in_union/total,
                       'query_ids_sha256': object_hash([r.query_id for r in items])}
    roles['test'] = {'queries': len(splits['test']), 'state': 'not_opened'}
    return roles


def main(argv=None):
    args = parse(argv)
    config = load_config(args.config)
    if args.epochs is not None:
        config['training']['epochs'] = args.epochs
        validate(config)
    import numpy
    import torch
    from qpaf.m22.telemetry import Telemetry, failure_record
    from qpaf.m24.checkpoint import load_checkpoint
    from qpaf.m24.evaluator import evaluate, predict
    from qpaf.m24.trainer import build_model, train

    seed = config['training']['seed']
    random.seed(seed)
    numpy.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    if args.synthetic_fixture:
        inputs = {'config': digest(args.config), 'synthetic_fixture': f'qpaf.m24.synthetic:{seed}'}
    else:
        inputs = {'config': digest(args.config), 'scores': digest(args.scores),
                  'queries': digest(args.queries), 'qrels': digest(args.qrels),
                  'splits': {name: digest(args.splits/name)
                             for name in ('train_ids.txt', 'val_ids.txt', 'test_ids.txt')}}
    if args.resume:
        inputs['resume'] = digest(args.resume)
    source = source_provenance(ROOT, 'requirements-learned-local.txt')
    cap, batch_size = config['features']['query_length_cap'], config['training']['batch_size']
    with StageRun(args.output, args.method, config, inputs, source) as run:
        telemetry = Telemetry()
        try:
            with telemetry.phase('load'):
                records, splits = load_inputs(args, config)
            write_json(run.path/'data_manifest.json', data_manifest(records, splits))
            with telemetry.phase('train'):
                result = train(config, args.method, records['train'], records['validation'],
                               run.path/'checkpoints', resume=args.resume, log=run.logger.info)
            write_csv(run.path/'epochs.csv', result['history'])
            write_csv(run.path/'steps.csv', result['steps'],
                      ['epoch', 'step', 'loss', 'grad_norm', 'valid_queries', 'skipped_queries', 'pairs'])
            best_path = run.path/'checkpoints/best.pt'
            with telemetry.phase('reload_and_evaluate'):
                payload = load_checkpoint(best_path, config=config, method=args.method)
                model = build_model(config, args.method)
                model.load_state_dict(payload['model_state'])
                predictions = predict(model, records['validation'], batch_size, cap)
                aggregate, per_query = evaluate(predictions, records['validation'])
                # Parity of a second fresh load guards against state leaking through the first model.
                again = build_model(config, args.method)
                again.load_state_dict(load_checkpoint(best_path, config=config, method=args.method)['model_state'])
                repeat = predict(again, records['validation'], batch_size, cap)
            difference = max(abs(a-b) for x, y in zip(predictions, repeat) for a, b in zip(x['scores'], y['scores']))
            tolerance = config['evaluation']['reload_tolerance']
            parity = {'max_abs_difference': difference, 'tolerance': tolerance, 'passed': difference <= tolerance,
                      'scope': 'in-process fresh model; fresh-environment parity is M6.1'}
            if not parity['passed']:
                raise RuntimeError(f'Reload parity failed: {difference} > {tolerance}')
            write_json(run.path/'validation_predictions.json', predictions)
            write_csv(run.path/'validation_per_query.csv', per_query)
            write_json(run.path/'validation_metrics.json', aggregate)
            write_json(run.path/'telemetry.json', {'phases': telemetry.phases, 'peak_rss_mb': telemetry.peak_rss_mb,
                                                   'device': 'cpu', 'dtype': 'float64', 'threads': 1})
            kind = 'synthetic_software_verification' if args.synthetic_fixture else 'real_data_development'
            summary = {'kind': kind, 'experiment_id': config['experiment_id'], 'method': args.method,
                       'granularity': METHODS[args.method], 'seed': seed, 'epochs': config['training']['epochs'],
                       'selected_epoch': result['best']['epoch'], 'selection_metric': result['best']['metric'],
                       'validation': aggregate, 'reload_parity': parity, 'test_split': 'not_opened',
                       'parameter_count': sum(p.numel() for p in model.parameters()),
                       'checkpoint_sha256': {'best': digest(best_path),
                                             'last': digest(run.path/'checkpoints/last.pt')},
                       'torch': torch.__version__, 'independent_review': 'pending'}
            write_json(run.path/'summary.json', summary)
            lines = [f'# M2.4 learned pipeline run — {args.method}', '',
                     f'**Kind: {kind}.** Seed {seed}; {config["training"]["epochs"]} epochs; '
                     f'selected epoch {result["best"]["epoch"]} by validation {result["best"]["metric"]}.', '',
                     '| Metric | Validation |', '| --- | --- |',
                     *[f'| {name} | {aggregate[name]:.6f} |' for name in METRICS], '',
                     f'Validation queries: {aggregate["query_count"]}. Test split: not opened.',
                     f'Reload parity: max |delta| {difference:.3e} (tolerance {tolerance}).', '']
            if args.synthetic_fixture:
                lines.append('Synthetic data proves the software path only; it is not a retrieval result.')
            (run.path/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        except Exception as exc:
            write_json(run.path/'failure.json', {**failure_record(exc), 'telemetry': telemetry.phases})
            raise
    print(f'M2.4 evidence: {run.path}')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (ValueError, FileExistsError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        raise SystemExit(2)
