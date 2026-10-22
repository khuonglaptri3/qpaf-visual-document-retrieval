"""Independent M3.5 paired development comparison of the sealed QPAF/QARF pilots.

Restore M3.1 development qrels and validation IDs at the sealed paths first.
Without --output-dir this audit only prints its summary. It never reads test qrels.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_m33_qarf import calculate_validation, compare_reported_metrics  # noqa: E402

METRICS = ('ndcg_at_10', 'recall_at_1', 'recall_at_3', 'mrr_at_10')
QARF = ROOT / 'results/m3.2/RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01/QARF/20261022T040759-ff3934df'
QPAF = ROOT / 'results/m3.4/RUN-QPAF-M3_4-MTH-001-20261022T112102Z-A01/QPAF/20261022T112355-77b54aa0'
PINS = {
    'qarf_authorization': ('evidence/revisions/m3.2-001/authorization.json', 'ae51a3a5601d43b0a758d5feb69b74b4ba24b0413965e5fee96ed7015ede9b4b'),
    'qpaf_authorization': ('evidence/revisions/m3.4-001/authorization.json', '4be026b852574e7687fdc4b9337f716aa96a64ac39556ae288193bdba99e5365'),
    'qarf_predictions': (QARF.relative_to(ROOT).as_posix() + '/validation_predictions.json', '658c8162b690bff751609298aa8e77bf80cdf035cdbb45711ca5f1050407ab1e'),
    'qpaf_predictions': (QPAF.relative_to(ROOT).as_posix() + '/validation_predictions.json', '95ba3ed8e4a395bf0f888866a0e33abec43375d381f37dfa66195e65b7d9db5b'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def paired_statistics(rows, *, resamples=10000, seed=20260820):
    """Single-seed query-paired exploratory statistics; no three-seed claim."""
    require(rows and len({r['query_id'] for r in rows}) == len(rows), 'empty/duplicate query rows')
    require(type(resamples) is int and resamples > 0, 'invalid bootstrap budget')
    result = {}
    rng = np.random.default_rng(seed)
    # Reuse the same query draws for all metrics, preserving their pairing.
    samples = rng.integers(0, len(rows), size=(resamples, len(rows)))
    for metric in METRICS:
        delta = np.array([r['delta_' + metric] for r in rows], dtype=np.float64)
        require(np.isfinite(delta).all(), f'{metric}: nonfinite paired delta')
        boot = delta[samples].mean(axis=1)
        ci = np.percentile(boot, [2.5, 97.5], method='linear')
        wins = int(np.count_nonzero(delta > 1e-12))
        ties = int(np.count_nonzero(np.abs(delta) <= 1e-12))
        losses = int(np.count_nonzero(delta < -1e-12))
        require(wins + ties + losses == len(rows), 'W/T/L count mismatch')
        positive = np.maximum(delta, 0)
        top_n = max(1, math.ceil(.05 * len(rows)))
        positive_sum = float(positive.sum())
        std = float(delta.std(ddof=1)) if len(rows) > 1 else 0.0
        result[metric] = {
            'mean_delta': float(delta.mean()),
            'median_delta': float(np.median(delta)),
            'ci95': [float(ci[0]), float(ci[1])],
            'wtl': {'wins': wins, 'ties': ties, 'losses': losses},
            'sample_std_delta': std,
            'paired_standardized_effect': float(delta.mean() / std) if std else None,
            'top_5pct_positive_gain_query_count': top_n,
            'top_5pct_positive_gain_share': (
                float(np.sort(positive)[-top_n:].sum() / positive_sum) if positive_sum else 0.0),
        }
    return result


def check_first_pass(script, expected):
    completed = subprocess.run([sys.executable, str(script)], cwd=ROOT,
                               capture_output=True, text=True, encoding='utf-8')
    require(completed.returncode == 0 and
            f"'PASS': {expected}, 'FAIL': 0, 'SKIPPED': 0" in completed.stdout,
            f'{script.name}: first-pass replay failed: {completed.stderr[-500:]}')


def rank_diagnostics(prediction, judged):
    positives = {page for page, relevance in judged.items() if relevance >= 1}
    ranked = sorted(zip(prediction['scores'], prediction['page_ids']),
                    key=lambda item: (-item[0], item[1]))
    first = next((index for index, (_, page) in enumerate(ranked[:10], start=1)
                  if page in positives), None)
    return {'top1_page_id': ranked[0][1], 'top1_relevant': ranked[0][1] in positives,
            'first_relevant_rank_at_10': first}


def audit():
    for label, (relative, expected) in PINS.items():
        require(sha(ROOT / relative) == expected, f'{label}: SHA-256 differs')
    qarf_auth = read(ROOT / PINS['qarf_authorization'][0])
    qpaf_auth = read(ROOT / PINS['qpaf_authorization'][0])
    require(qarf_auth['method']['name'] == 'QARF' and qpaf_auth['method']['name'] == 'QPAF',
            'unexpected method authorization')
    require(qarf_auth['sealed_inputs'] == qpaf_auth['sealed_inputs'] and
            qarf_auth['config'] == qpaf_auth['config'] and
            qarf_auth['runtime'] == qpaf_auth['runtime'] and
            qarf_auth['method']['seed'] == qpaf_auth['method']['seed'] == 20260820,
            'methods are not matched on seal/config/runtime/seed')
    seal = ROOT / qarf_auth['sealed_inputs']['run_path']
    files = qarf_auth['sealed_inputs']['files_relative_to_run_path']
    for relative in ('inputs/qrels_development.json', 'inputs/splits/val_ids.txt'):
        require(sha(seal / relative) == files[relative], f'{relative}: sealed input differs')
    ids = (seal / 'inputs/splits/val_ids.txt').read_text(encoding='utf-8').splitlines()
    require(len(ids) == 171 and len(set(ids)) == 171, 'validation split differs')
    qrels = read(seal / 'inputs/qrels_development.json')
    require(sha(QARF / 'resolved_config.json') == sha(QPAF / 'resolved_config.json') and
            sha(QARF / 'data_manifest.json') == sha(QPAF / 'data_manifest.json'),
            'resolved config or data manifest differs')
    require(read(QARF / 'provenance.json')['inputs'] == read(QPAF / 'provenance.json')['inputs'],
            'source inputs differ')
    check_first_pass(ROOT / 'evidence/revisions/m3.2-001/post_run_check.py', 30)
    check_first_pass(ROOT / 'evidence/revisions/m3.4-001/post_run_check.py', 39)
    events = [json.loads(line) for line in (ROOT / 'evidence/revisions/m3.2-001/governance_events.jsonl').read_text(encoding='utf-8').splitlines()]
    require(any(e.get('registry_event_id') == 'QPAF-REG-20261022-0022' and
                e.get('registry_status') == 'PASS' and e.get('run_id') == qarf_auth['run_id']
                for e in events), 'M3.3 QARF acceptance missing')
    prediction = {method: read(path / 'validation_predictions.json') for method, path in
                  (('QARF', QARF), ('QPAF', QPAF))}
    require(len(prediction['QARF']) == len(prediction['QPAF']) == 171,
            'prediction query count differs')
    require([(p['query_id'], p['page_ids']) for p in prediction['QARF']] ==
            [(p['query_id'], p['page_ids']) for p in prediction['QPAF']],
            'query or candidate page/order differs')
    calculated = {}
    metric_diff_max = 0.0
    for method, path in (('QARF', QARF), ('QPAF', QPAF)):
        pages = {p['query_id']: p['page_ids'] for p in prediction[method]}
        aggregate, rows = calculate_validation(prediction[method], qrels, ids, pages)
        metric_diff_max = max(metric_diff_max, compare_reported_metrics(aggregate, rows, path))
        calculated[method] = (aggregate, rows)
    left, right = calculated['QPAF'][1], calculated['QARF'][1]
    paired = []
    for a, b in zip(left, right):
        require(a['query_id'] == b['query_id'] and a['candidates'] == b['candidates'] and
                a['relevant_total'] == b['relevant_total'] and
                a['relevant_in_candidates'] == b['relevant_in_candidates'],
                'per-query pairing/relevance differs')
        paired.append({'query_id': a['query_id'], 'candidates': a['candidates'],
                       'relevant_total': a['relevant_total'],
                       **{f'qpaf_{key}': value for key, value in
                          rank_diagnostics(prediction['QPAF'][len(paired)], qrels[a['query_id']]).items()},
                       **{f'qarf_{key}': value for key, value in
                          rank_diagnostics(prediction['QARF'][len(paired)], qrels[a['query_id']]).items()},
                       **{f'qpaf_{m}': a[m] for m in METRICS},
                       **{f'qarf_{m}': b[m] for m in METRICS},
                       **{f'delta_{m}': a[m] - b[m] for m in METRICS}})
    stats = paired_statistics(paired)
    worst = sorted(paired, key=lambda r: (r['delta_ndcg_at_10'], r['query_id']))[:10]
    return {
        'schema_version': 1, 'task_id': 'M3.5', 'owner': 'Thanh',
        'executed_by': "Codex at Thanh's request", 'checked_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'technical_verdict': 'PASS', 'owner_acceptance': 'PENDING_THANH_CONFIRMATION',
        'scope': 'single-seed development validation paired comparison; G2 and M3.6 pending',
        'run_ids': {'QARF': qarf_auth['run_id'], 'QPAF': qpaf_auth['run_id']},
        'pins_sha256': {label: expected for label, (_, expected) in PINS.items()},
        'sealed_qrels_sha256': files['inputs/qrels_development.json'],
        'validation_ids_sha256': files['inputs/splits/val_ids.txt'],
        'validation_query_count': len(ids), 'candidate_rows': sum(r['candidates'] for r in paired),
        'metric_replay_max_abs_difference': metric_diff_max,
        'bootstrap': {'unit': 'paired query', 'resamples': 10000, 'seed': 20260820,
                      'ci': 'linear percentile 2.5/97.5', 'wtl_tolerance': 1e-12},
        'metrics': stats,
        'ndcg_loss_queries': stats['ndcg_at_10']['wtl']['losses'],
        'worst_ndcg_queries': [{'query_id': r['query_id'], 'delta_ndcg_at_10': r['delta_ndcg_at_10'],
                                'qpaf_ndcg_at_10': r['qpaf_ndcg_at_10'],
                                'qarf_ndcg_at_10': r['qarf_ndcg_at_10'],
                                'qpaf_first_relevant_rank_at_10': r['qpaf_first_relevant_rank_at_10'],
                                'qarf_first_relevant_rank_at_10': r['qarf_first_relevant_rank_at_10']}
                               for r in worst],
        'test_labels_opened': False, 'training_executed_by_audit': False,
        'multi_seed_claim': False, 'baseline_comparison_done': False,
        'm3_6_integrity_review_complete': False, 'g2_decision_made': False,
    }, paired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, help='new create-once evidence directory')
    args = parser.parse_args()
    if args.output_dir is not None:
        require(not args.output_dir.exists(), 'output directory already exists')
    report, rows = audit()
    if args.output_dir is None:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        with (args.output_dir / 'comparison.json').open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        with (args.output_dir / 'per_query.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f'M3.5 paired comparison PASS: {args.output_dir}')


if __name__ == '__main__':
    try:
        main()
    except ValueError as exc:
        print(f'M3.5 refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
