"""R8: frozen three-seed paired TEST-172 analysis from the sealed R7 output."""
import argparse
import csv
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m44.common import sha  # noqa: E402

SEEDS = (20260820, 20260821, 20260822)
METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')
TOLERANCE = 1e-12
RESAMPLES = 10_000
RNG_SEED = 20260820


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load_rows(path):
    with path.open(encoding='utf8', newline='') as stream:
        raw = list(csv.DictReader(stream))
    groups = {}
    for row in raw:
        method, query_id = row['method'], row['query_id']
        require(query_id not in groups.setdefault(method, {}), 'duplicate query row')
        parsed = {'query_id': query_id}
        for key in ('candidates', 'relevant_total', 'relevant_in_candidates'):
            parsed[key] = int(row[key])
        for metric in METRICS:
            parsed[metric] = float(row[metric])
            require(math.isfinite(parsed[metric]), 'nonfinite metric')
        groups[method][query_id] = parsed
    return groups


def statistics(deltas, samples):
    values = np.asarray(deltas, dtype=np.float64)
    require(values.size == 172 and np.isfinite(values).all(), 'delta query count or finiteness differs')
    ci = np.percentile(values[samples].mean(axis=1), [2.5, 97.5], method='linear')
    wins = int(np.count_nonzero(values > TOLERANCE))
    ties = int(np.count_nonzero(np.abs(values) <= TOLERANCE))
    losses = int(np.count_nonzero(values < -TOLERANCE))
    positives = np.maximum(values, 0)
    top = max(1, math.ceil(.05 * len(values)))
    return {'mean_delta': float(values.mean()), 'median_delta': float(np.median(values)),
            'std_delta': float(values.std(ddof=1)), 'ci95': [float(ci[0]), float(ci[1])],
            'wtl': {'wins': wins, 'ties': ties, 'losses': losses},
            'top_5pct_positive_gain_query_count': top,
            'top_5pct_positive_gain_share': (float(np.sort(positives)[-top:].sum()/positives.sum())
                                               if positives.sum() else 0.0)}


def analyze(run, pin, audit, audit_sha256):
    require(sha(run/'manifest.json') == pin, 'R7 manifest pin differs')
    manifest = json.loads((run/'manifest.json').read_text(encoding='utf8'))
    files = {entry['path']: entry['sha256'] for entry in manifest['files']}
    require(sha(run/'per_query_metrics.csv') == files['per_query_metrics.csv'], 'R7 per-query hash differs')
    require(audit['status'] == 'PASS_WITH_NUMERICAL_PARITY_NOTE' and
            audit['manifest_sha256'] == pin, 'independent R7 audit missing')
    prereg_path = ROOT/'evidence/revisions/m5.1-001/preregistration.json'
    prereg = json.loads(prereg_path.read_text(encoding='utf8'))
    stats_policy = prereg['statistics']
    require(stats_policy['resamples'] == RESAMPLES and stats_policy['rng_seed'] == RNG_SEED and
            stats_policy['per_query_seed_mean_before_bootstrap'] is True and
            stats_policy['wtl_tolerance'] == TOLERANCE, 'R1 statistics policy differs')
    selection_path = ROOT/'results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01/selection.json'
    selected = json.loads(selection_path.read_text(encoding='utf8'))
    require(selected['co_strongest'] == ['train_fitted_static'], 'validation-selected baseline differs')
    bundle = ROOT/'results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01'
    bundle_manifest = json.loads((bundle/'manifest.json').read_text(encoding='utf8'))
    bundle_files = {entry['path']: entry['sha256'] for entry in bundle_manifest['files']}
    query_path = bundle/'inputs/queries.json'
    require(sha(query_path) == bundle_files['inputs/queries.json'], 'pinned query texts differ')
    query_texts = json.loads(query_path.read_text(encoding='utf8'))
    groups = load_rows(run/'per_query_metrics.csv')
    required = {f'{method}_{seed}' for method in ('qarf', 'qpaf') for seed in SEEDS}
    required.add('train_fitted_static')
    require(required <= set(groups), 'missing method or seed')
    query_ids = sorted(groups['train_fitted_static'])
    require(len(query_ids) == 172 and all(set(groups[m]) == set(query_ids) for m in required),
            'query set differs by method or seed')
    require(all(q in query_texts for q in query_ids), 'query texts do not cover test IDs')
    for q in query_ids:
        reference = groups['train_fitted_static'][q]
        for method in required:
            row = groups[method][q]
            require(all(row[k] == reference[k] for k in
                        ('candidates', 'relevant_total', 'relevant_in_candidates')),
                    'candidate or relevance counts differ')
    rng = np.random.default_rng(RNG_SEED)
    samples = rng.integers(0, len(query_ids), size=(RESAMPLES, len(query_ids)))
    contrasts = {}
    per_query = []
    for comparison in ('qarf', 'train_fitted_static'):
        name = 'QPAF_minus_' + ('matched_QARF' if comparison == 'qarf' else comparison)
        means_by_metric = {m: [] for m in METRICS}
        per_seed = []
        for seed in SEEDS:
            left = groups[f'qpaf_{seed}']
            right = groups[f'qarf_{seed}'] if comparison == 'qarf' else groups['train_fitted_static']
            per_seed.append({'seed': seed, **{m: float(np.mean([left[q][m]-right[q][m] for q in query_ids]))
                                                 for m in METRICS}})
        for q in query_ids:
            row = {'comparison': name, 'query_id': q,
                   'candidates': groups['train_fitted_static'][q]['candidates'],
                   'relevant_total': groups['train_fitted_static'][q]['relevant_total']}
            for metric in METRICS:
                values = [groups[f'qpaf_{seed}'][q][metric] -
                          groups[f'qarf_{seed}'][q][metric] if comparison == 'qarf'
                          else groups[f'qpaf_{seed}'][q][metric] - groups['train_fitted_static'][q][metric]
                          for seed in SEEDS]
                row['delta_'+metric] = float(np.mean(values))
                means_by_metric[metric].append(row['delta_'+metric])
            per_query.append(row)
        metrics = {metric: statistics(means_by_metric[metric], samples) for metric in METRICS}
        ndcg = means_by_metric['ndcg_at_10']
        losses = sorted((r for r in per_query if r['comparison'] == name),
                        key=lambda r: (r['delta_ndcg_at_10'], r['query_id']))[:10]
        counts = [groups['train_fitted_static'][q]['relevant_total'] for q in query_ids]
        candidates = [groups['train_fitted_static'][q]['candidates'] for q in query_ids]
        lengths = [len(query_texts[q].split()) for q in query_ids]
        candidate_median = float(np.median(candidates))
        length_median = float(np.median(lengths))
        subgroup = {}
        for label, positions in (('one_relevant_page', [i for i, n in enumerate(counts) if n == 1]),
                                 ('multiple_relevant_pages', [i for i, n in enumerate(counts) if n > 1]),
                                 ('candidate_count_leq_median', [i for i, n in enumerate(candidates)
                                                                if n <= candidate_median]),
                                 ('candidate_count_gt_median', [i for i, n in enumerate(candidates)
                                                               if n > candidate_median]),
                                 ('query_words_leq_median', [i for i, n in enumerate(lengths)
                                                            if n <= length_median]),
                                 ('query_words_gt_median', [i for i, n in enumerate(lengths)
                                                           if n > length_median])):
            subgroup[label] = {'query_count': len(positions),
                               'mean_delta_ndcg_at_10': (float(np.mean([ndcg[i] for i in positions]))
                                                         if positions else None)}
        contrasts[name] = {'metrics': metrics, 'per_seed_mean_delta': per_seed,
                           'per_seed_ndcg_mean_std': float(np.std([r['ndcg_at_10'] for r in per_seed], ddof=1)),
                           'descriptive_subgroups': subgroup,
                           'descriptive_subgroup_medians': {'candidate_count': candidate_median,
                                                            'query_words': length_median},
                           'worst_10_queries': [
                               {'query_id': r['query_id'],
                                'delta_ndcg_at_10': r['delta_ndcg_at_10'],
                                'qpaf_seed_mean_ndcg_at_10': float(np.mean([
                                    groups[f'qpaf_{seed}'][r['query_id']]['ndcg_at_10'] for seed in SEEDS])),
                                'comparator_seed_mean_ndcg_at_10': float(np.mean([
                                    (groups[f'qarf_{seed}'] if comparison == 'qarf'
                                     else groups['train_fitted_static'])[r['query_id']]['ndcg_at_10']
                                    for seed in SEEDS]))}
                               for r in losses]}
    by_seed = {method: {str(seed): {metric: float(np.mean([groups[f'{method}_{seed}'][q][metric]
                                                         for q in query_ids])) for metric in METRICS}
                        for seed in SEEDS} for method in ('qpaf', 'qarf')}
    primary = contrasts['QPAF_minus_matched_QARF']['metrics']['ndcg_at_10']
    baseline = contrasts['QPAF_minus_train_fitted_static']['metrics']['ndcg_at_10']
    return {'summary': {'schema_version': 1, 'task_id': 'M5.7', 'roster_id': 'R8',
                        'status': 'TECHNICAL_ANALYSIS_COMPLETE',
                        'r7_run_id': manifest['run_id'], 'r7_manifest_sha256': pin,
                        'r7_per_query_sha256': files['per_query_metrics.csv'],
                        'r7_independent_audit_sha256': audit_sha256,
                        'preregistration_sha256': sha(prereg_path),
                        'validation_selection_sha256': sha(selection_path),
                        'query_texts_sha256': sha(query_path),
                        'query_count': len(query_ids), 'seeds': list(SEEDS),
                        'statistics_policy': {'unit': 'paired query after seed averaging',
                                              'bootstrap_resamples': RESAMPLES, 'rng_seed': RNG_SEED,
                                              'ci': 'linear percentile 2.5/97.5', 'wtl_tolerance': TOLERANCE},
                        'method_mean_by_seed': by_seed, 'contrasts': contrasts,
                        'quality_signals': {'delta_qarf_at_least_0_01': primary['mean_delta'] >= .01,
                                            'ci_qarf_lower_above_zero': primary['ci95'][0] > 0,
                                            'above_validation_selected_baseline': baseline['mean_delta'] > 0,
                                            'overall_quality_gate': primary['mean_delta'] >= .01 and
                                            primary['ci95'][0] > 0 and baseline['mean_delta'] > 0},
                        'limitations': ['R7 is one held-out test split; seed averaging does not create new queries.',
                                        'Subgroups and worst cases are descriptive, not additional primary gates.',
                                        'Operational latency/memory acceptance is separate.',
                                        'No method, seed, checkpoint or baseline was selected on test.']},
            'per_query': per_query}


def csv_bytes(rows):
    import io
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode('utf8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--expected-manifest-sha256', required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding='utf8'))
    report = analyze(args.run, args.expected_manifest_sha256, audit, sha(args.audit))
    payloads = {'summary.json': (json.dumps(report['summary'], indent=2, ensure_ascii=False)+'\n').encode('utf8'),
                'per_query_deltas.csv': csv_bytes(report['per_query'])}
    if args.verify:
        require(all((args.output/name).read_bytes() == content for name, content in payloads.items()),
                'R8 saved outputs differ from replay')
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        for name, content in payloads.items():
            with (args.output/name).open('xb') as stream:
                stream.write(content)
    print(json.dumps({'status': 'PASS', 'verify_only': args.verify,
                      'quality_signals': report['summary']['quality_signals']}))
