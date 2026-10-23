"""Hand-derived ViMDoc document baseline and leakage checks."""
import copy
import importlib
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def row(page, scores, query='train'):
    return dict(query_id=query, page_id=page, bm25_score=scores[0],
                dense_score=scores[1], visual_score=scores[2])


class BaselineTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('qpaf.m42.baselines')
        except ModuleNotFoundError:
            self.fail('M4.2 document baselines are not implemented')
        self.rows = [row('a_0', (10., 0., 1.)), row('b_0', (0., 10., 1.)),
                     row('c_0', (5., 5., 1.))]

    def test_single_channels_and_uniform_normalize_the_same_union(self):
        self.assertEqual(self.api.score_pages(self.rows, 'bm25'), [1., 0., .5])
        self.assertEqual(self.api.score_pages(self.rows, 'bge_m3'), [0., 1., .5])
        self.assertEqual(self.api.score_pages(self.rows, 'colqwen25'), [0., 0., 0.])
        self.assertEqual(self.api.score_pages(self.rows, 'uniform_combsum'), [1/3]*3)

    def test_rrf_uses_one_based_raw_ranks_and_page_id_ties(self):
        scores = self.api.score_pages(self.rows, 'rrf_k60')
        expected = [1/61+1/63+1/61, 1/63+1/61+1/62, 1/62+1/62+1/63]
        for actual, want in zip(scores, expected):
            self.assertAlmostEqual(actual, want, places=15)

    def test_near_constant_channel_uses_frozen_epsilon(self):
        rows = [row('a_0', (0., 2., 0.)), row('b_0', (5e-16, 2., 0.))]
        self.assertEqual(self.api.score_pages(rows, 'bm25'), [0., 0.])

    def test_document_max_and_last_underscore_mapping(self):
        ranked = self.api.document_ranking(
            ['a_long_doc_0', 'a_long_doc_1', 'b_0'], [.2, .8, .8])
        self.assertEqual(ranked, [('a_long_doc', .8), ('b', .8)])

    def test_idcg_uses_all_relevant_documents_and_deduplicates_pages(self):
        metric = self.api.document_ndcg_at_10(
            ['a_0', 'a_1', 'b_0'], [.9, .8, .1], ['a', 'absent'])
        self.assertAlmostEqual(metric, 1/(1+1/math.log2(3)))
        self.assertEqual(self.api.document_ndcg_at_10(['a_0'], [1.], ['absent']), 0.)

    def test_document_ranking_rejects_bad_alignment_duplicates_and_ids(self):
        for pages, scores in [(['a_0'], []), (['a_0', 'a_0'], [1., 2.]),
                              (['no-suffix'], [1.]), (['_0'], [1.]),
                              (['a_'], [1.]), (['a_0'], [float('nan')])]:
            with self.subTest(pages=pages, scores=scores), self.assertRaises(ValueError):
                self.api.document_ranking(pages, scores)

    def test_invalid_document_qrels_are_rejected(self):
        for qrels in [[], ['a', 'a'], [''], [True], ['a\nb']]:
            with self.subTest(qrels=qrels), self.assertRaises(ValueError):
                self.api.document_ndcg_at_10(['a_0'], [1.], qrels)

    def test_scalar_or_unordered_qrels_cannot_silently_change_metrics_or_fit(self):
        rows = [row('doc_0', (1., 1., 1.))]
        for qrels in ['doc', {'doc'}, {'doc': 1}]:
            with self.subTest(qrels=qrels), self.assertRaises(ValueError):
                self.api.document_ndcg_at_10(['doc_0'], [1.], qrels)
            with self.subTest(fit_qrels=qrels), self.assertRaises(ValueError):
                self.api.fit_static_on_train(rows, {'train': qrels}, ['train'])

    def test_static_fit_uses_exact_train_only_ids_and_document_objective(self):
        rows = [row('a_0', (10., 0., 0.)), row('b_0', (0., 10., 10.))]
        result = self.api.fit_static_on_train(rows, {'train': ['b']}, ['train'])
        self.assertEqual(result['weights'], (0., 0., 1.))
        self.assertEqual(result['train_document_ndcg_at_10'], 1.)
        self.assertEqual(result['grid_candidates'], 66)
        self.assertEqual(result, self.api.fit_static_on_train(rows, {'train': ['b']}, ['train']))

    def test_extra_validation_scores_or_qrels_are_rejected_before_fitting(self):
        for rows, qrels, ids in [
            (self.rows+[row('z_0', (1., 1., 1.), 'validation')], {'train': ['a']}, ['train']),
            (self.rows, {'train': ['a'], 'validation': ['z']}, ['train']),
            (self.rows, {'train': ['a']}, ['train', 'missing']),
            (self.rows, {'train': ['a']}, ['train', 'train']),
        ]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.api.fit_static_on_train(rows, qrels, ids)

    def test_label_columns_nonfinite_scores_duplicates_and_bad_order_rejected(self):
        cases = []
        dirty = copy.deepcopy(self.rows)
        dirty[0]['relevance'] = 1
        cases.append(dirty)
        cases.extend([self.rows+self.rows[:1], list(reversed(self.rows))])
        for bad in [True, '1', float('nan'), float('inf')]:
            dirty = copy.deepcopy(self.rows)
            dirty[0]['dense_score'] = bad
            cases.append(dirty)
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.api.score_pages(rows, 'uniform_combsum')

    def test_score_overflow_empty_rows_and_candidate_cap_fail_closed(self):
        cases = [[], [row('a_0', (-1e308, 0., 0.)), row('b_0', (1e308, 0., 0.))],
                 [row(f'd_{i:04}', (1., 1., 1.)) for i in range(601)]]
        for rows in cases:
            with self.subTest(count=len(rows)), self.assertRaises(ValueError):
                self.api.score_pages(rows, 'uniform_combsum')

    def test_invalid_simplex_and_learned_or_oracle_substitutions_are_rejected(self):
        for weights in [None, (1., 1., 0.), (-.1, .1, 1.), (True, 0., 0.),
                        (float('nan'), 0., 1.)]:
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                self.api.score_pages(self.rows, 'train_fitted_static', weights=weights)
        for method in ['learned_qarf', 'oracle_qarf', 'dse']:
            with self.subTest(method=method), self.assertRaises(ValueError):
                self.api.score_pages(self.rows, method)


if __name__ == '__main__':
    unittest.main()
