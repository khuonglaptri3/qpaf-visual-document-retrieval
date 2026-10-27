"""R6-05: query-level (QARF) versus page-level (QPAF) conditioning on the accepted matched runs; no training.

The six runs were trained with the same sealed inputs, config and seed per pair; `gate_granularity` is the
only difference (M3.4/M5.3/M5.4 supervisors). Per-query metrics are recomputed from the saved validation
predictions and the development qrels, checked against each run's own CSV, then paired. Following the M5.1
statistics rule, the three per-seed deltas are averaged per query before the bootstrap.
"""
import csv
import json

from .ablation import METRICS, paired_statistics, per_query_deltas, require

SEEDS = (20260820, 20260821, 20260822)
# (seed, method) -> accepted attempt directory, its pinned files and the acceptance event that admits it.
RUNS = {
    (20260820, 'QARF'): ('results/m3.2/RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01/QARF/20261022T040759-ff3934df',
                         '658c8162b690bff751609298aa8e77bf80cdf035cdbb45711ca5f1050407ab1e',
                         'e7318a489f7fee80071ba56ed9477b94c21ff6cfc2f7bf7ed5600e67b881c777',
                         ('evidence/revisions/m3.2-001/governance_events.jsonl', 'QPAF-REG-20261022-0022')),
    (20260820, 'QPAF'): ('results/m3.4/RUN-QPAF-M3_4-MTH-001-20261022T112102Z-A01/QPAF/20261022T112355-77b54aa0',
                         '95ba3ed8e4a395bf0f888866a0e33abec43375d381f37dfa66195e65b7d9db5b',
                         '02abf2e14298d042b38f98671cad7f0a6ac7e2f9921237c428771a19a3d52b66',
                         ('evidence/revisions/m3.4-001/governance_events.jsonl', 'QPAF-REG-20261022-0026')),
    (20260821, 'QARF'): ('results/m5.3/RUN-QPAF-M5_3-MTH-001-20261025T135954Z-A01/QARF/20261025T140512-0de4dd1d',
                         '84bbff7fa7794afbd7029c5405869c658b62c3d3c890fd78ed955dc479ca7611',
                         'fe445556a0aa1f09de3d410c9eb85d3523cbdaf0843ccd9cb69c5564aa9866da',
                         ('evidence/revisions/m5.3-001/governance_events.jsonl', 'QPAF-REG-20261026-0001')),
    (20260821, 'QPAF'): ('results/m5.3/RUN-QPAF-M5_3-MTH-002-20261026T025155Z-A01/QPAF/20261026T025443-a29ae705',
                         '4d6fe2c6829214a09c35052cdd4580f16ae86654fe637879371060386294618f',
                         '04105bddc465f2b26e305953531261db0b39b544a37ca34f889565ec9e0ec579',
                         ('evidence/revisions/m5.3-002/governance_events.jsonl', 'QPAF-REG-20261026-0009')),
    (20260822, 'QARF'): ('results/m5.4/RUN-QPAF-M5_4-MTH-001-20261025T154818Z-A01/QARF/20261025T155859-f0aefa1c',
                         '43e05c4b12bf4bed1f45f72a940d94e3f09375f9774c7415d8b9ea0e8e6c1e9d',
                         '582c34e55ed45805bbc89acc0498771016857a5f52567d1da67e0fbd0b313598',
                         ('evidence/revisions/m5.4-001/governance_events.jsonl', 'QPAF-REG-20261026-0002')),
    (20260822, 'QPAF'): ('results/m5.4/RUN-QPAF-M5_4-MTH-002-20261026T025155Z-A01/QPAF/20261026T025834-242457dc',
                         '8667b6abc44c861180f8e506656ff8ab4a8223723e87df035eefc0d46a22874a',
                         '117dd7a4f216313e7cddcdc64694175355c5df6793cbaff1973a510acfebd4cd',
                         ('evidence/revisions/m5.4-002/governance_events.jsonl', 'QPAF-REG-20261026-0010')),
}
GRANULARITY = {'QARF': 'query', 'QPAF': 'page'}
CSV_TOLERANCE = 1e-12


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def accepted(root, events_path, event_id):
    events = [json.loads(line) for line in (root/events_path).read_text(encoding='utf8').splitlines() if line.strip()]
    found = [e for e in events if e.get('registry_event_id') == event_id]
    return len(found) == 1 and (found[0].get('event_type'), found[0].get('registry_status')) == (
        'ACCEPTANCE_RECORDED', 'PASS')


def load_run(root, seed, method, records, sha):
    """Recomputed per-query metrics of one accepted run, after its pins, summary and CSV agree."""
    from qpaf.m24.evaluator import evaluate
    directory, predictions_sha, csv_sha, (events, event_id) = RUNS[(seed, method)]
    directory = root/directory
    require(sha(directory/'validation_predictions.json') == predictions_sha, f'{method}/{seed}: predictions pin differs')
    require(sha(directory/'validation_per_query.csv') == csv_sha, f'{method}/{seed}: per-query CSV pin differs')
    require(accepted(root, events, event_id), f'{method}/{seed}: acceptance event {event_id} missing')
    summary = read(directory/'summary.json')
    require((summary['method'], summary['seed'], summary['granularity'], summary['test_split']) ==
            (method, seed, GRANULARITY[method], 'not_opened'), f'{method}/{seed}: summary identity differs')
    aggregate, per_query = evaluate(read(directory/'validation_predictions.json'), records)
    with (directory/'validation_per_query.csv').open(encoding='utf8', newline='') as stream:
        saved = list(csv.DictReader(stream))
    require([r['query_id'] for r in saved] == [r['query_id'] for r in per_query], f'{method}/{seed}: CSV order differs')
    worst = max(abs(float(s[m])-r[m]) for s, r in zip(saved, per_query) for m in METRICS)
    worst = max(worst, *(abs(summary['validation'][m]-aggregate[m]) for m in METRICS))
    require(worst <= CSV_TOLERANCE, f'{method}/{seed}: recomputed metrics differ from the run by {worst}')
    return aggregate, per_query, worst


def compare(root, records, sha):
    """Per-seed and three-seed-mean paired QPAF - QARF statistics on the validation queries."""
    seeds, means, rows = [], {m: [0.]*len(records) for m in METRICS}, []
    for seed in SEEDS:
        qarf, qarf_rows, qarf_worst = load_run(root, seed, 'QARF', records, sha)
        qpaf, qpaf_rows, qpaf_worst = load_run(root, seed, 'QPAF', records, sha)
        deltas = per_query_deltas(qpaf_rows, qarf_rows)
        for metric in METRICS:
            means[metric] = [a+b/len(SEEDS) for a, b in zip(means[metric], deltas[metric])]
        seeds.append({'seed': seed, 'qarf': qarf, 'qpaf': qpaf, 'paired': paired_statistics(deltas),
                      'recompute_max_abs_difference': max(qarf_worst, qpaf_worst)})
        rows.extend({'seed': seed, 'query_id': q['query_id'],
                     **{f'qarf_{m}': q[m] for m in METRICS}, **{f'qpaf_{m}': p[m] for m in METRICS},
                     **{f'delta_{m}': deltas[m][i] for m in METRICS}}
                    for i, (q, p) in enumerate(zip(qarf_rows, qpaf_rows)))
    return {'roster_id': 'R6-05', 'factor': 'query_vs_page_conditioning', 'contrast': 'QPAF (page) - QARF (query)',
            'seeds': seeds, 'three_seed_query_mean': paired_statistics(means),
            'aggregation': 'per-query mean of the three per-seed deltas, then bootstrap over 171 queries',
            'training_executed': False}, rows
