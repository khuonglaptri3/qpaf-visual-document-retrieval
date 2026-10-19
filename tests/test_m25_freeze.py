"""Contract checks for frozen M2.5 baselines, statistics and leakage barriers."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m24.dataset import QueryRecord, build_records
from qpaf.m24.evaluator import evaluate
from qpaf.m24.synthetic import make_fixture
from qpaf.m25.baselines import ROSTER, fit_static_on_train, predictions, score_record, select_co_strongest
from qpaf.m25.leakage import assert_matched_candidates, audit_score_rows, verify_frozen_splits
from qpaf.m25.statistics import SEEDS, paired_report

CONFIG = json.loads((ROOT/'configs/m2.5/freeze.json').read_text(encoding='utf-8'))


class BaselineTests(unittest.TestCase):
    def test_hand_ranked_channels_and_label_blind_scoring(self):
        record = QueryRecord('q', 'text', ('b', 'a', 'c'),
                             ((10., 0., 1.), (0., 10., 1.), (5., 5., 1.)),
                             (1, 0, 0), 1)
        self.assertEqual(score_record(record, 'bm25'), [1., 0., .5])
        self.assertEqual(score_record(record, 'uniform_combsum'), [1/3, 1/3, 1/3])
        # The constant visual channel still contributes deterministic RRF ranks.
        rrf = score_record(record, 'rrf_k60')
        self.assertGreater(rrf[1], rrf[0])  # ascending page ID wins visual tie
        changed = QueryRecord(record.query_id, record.text, record.page_ids,
                              record.raw_scores, (0, 1, 1), 2)
        for method in ROSTER[:-1]:
            weights = (1., 0., 0.) if method == 'train_fitted_static' else None
            self.assertEqual(score_record(record, method, weights=weights),
                             score_record(changed, method, weights=weights))

    def test_static_fitting_and_selection_guards(self):
        rows, queries, qrels, splits = make_fixture(queries_per_role=(4, 2, 1), candidates=4)
        records = build_records(rows, queries, qrels, splits, ('train', 'validation'))
        fitted = fit_static_on_train(records['train'], splits['train'])
        self.assertEqual(fitted['candidates'], 66)
        self.assertAlmostEqual(sum(fitted['weights']), 1.)
        self.assertEqual(fitted, fit_static_on_train(records['train'], splits['train']))
        with self.assertRaises(ValueError):
            fit_static_on_train(records['train']+records['validation'], splits['train'])
        metrics = {method: .2 for method in ROSTER}
        metrics['bm25'] = .5
        metrics['bge_m3'] = .5+5e-13
        self.assertEqual(select_co_strongest(metrics), ['bm25', 'bge_m3'])
        del metrics['learned_qarf']
        with self.assertRaises(ValueError):
            select_co_strongest(metrics)


class StatisticsTests(unittest.TestCase):
    def test_three_seed_query_pairing_wtl_ci_and_concentration(self):
        qpaf = {s: {'a': .7, 'b': .5, 'c': .4, 'd': .6} for s in SEEDS}
        qarf = {s: {'a': .5, 'b': .5, 'c': .5, 'd': .5} for s in SEEDS}
        report = paired_report(qpaf, qarf)
        self.assertEqual(report['query_count'], 4)
        self.assertAlmostEqual(report['mean_delta'], .05)
        self.assertEqual(report['wtl']['wins'], 2)
        self.assertEqual(report['wtl']['ties'], 1)
        self.assertEqual(report['wtl']['losses'], 1)
        self.assertAlmostEqual(report['top_5pct_positive_gain_share'], 2/3)
        self.assertEqual(report['ci95'], paired_report(qpaf, qarf)['ci95'])
        self.assertLessEqual(report['ci95'][0], report['mean_delta'])
        self.assertGreaterEqual(report['ci95'][1], report['mean_delta'])
        qarf[SEEDS[1]].pop('d')
        with self.assertRaises(ValueError):
            paired_report(qpaf, qarf)

    def test_seed_averaging_precedes_bootstrap(self):
        qarf = {s: {'a': .5, 'b': .5} for s in SEEDS}
        qpaf = {SEEDS[0]: {'a': .8, 'b': .5}, SEEDS[1]: {'a': .5, 'b': .2},
                SEEDS[2]: {'a': .5, 'b': .5}}
        report = paired_report(qpaf, qarf, resamples=100)
        self.assertAlmostEqual(report['mean_delta'], 0.)
        self.assertAlmostEqual(report['per_query'][0]['seed_averaged_delta'], .1)
        self.assertAlmostEqual(report['per_query'][1]['seed_averaged_delta'], -.1)


class LeakageTests(unittest.TestCase):
    def test_actual_frozen_splits(self):
        result = verify_frozen_splits(ROOT, CONFIG)
        self.assertEqual(result['role_counts'], {'train': 799, 'validation': 171, 'test': 172})
        self.assertEqual(result['status'], 'PASS')

    def test_labels_duplicates_and_coverage_fail_closed(self):
        rows, _, _, splits = make_fixture(queries_per_role=(2, 1, 1), candidates=3)
        self.assertEqual(audit_score_rows(rows, splits)['query_count'], 3)
        dirty = copy.deepcopy(rows)
        dirty[0]['relevance'] = 1
        with self.assertRaises(ValueError):
            audit_score_rows(dirty, splits)
        with self.assertRaises(ValueError):
            audit_score_rows(rows+[rows[0]], splits)
        with self.assertRaises(ValueError):
            audit_score_rows([r for r in rows if r['query_id'] != splits['train'][0]], splits)
        self.assertTrue(assert_matched_candidates([('q', 'p')], [('q', 'p')]))
        with self.assertRaises(ValueError):
            assert_matched_candidates([('q', 'p')], [('q', 'other')])


if __name__ == '__main__':
    unittest.main()
