"""Independent arithmetic and exhaustive checks for the research core."""
import itertools
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from qpaf.m11.metrics import ndcg, paired_summary
from qpaf.m11.oracle import evaluate, weight_sets
from qpaf.m11.config import load_config


def small_config():
    return {
        'retrieval': {'candidate_k': 3, 'normalization': 'minmax'},
        'oracle': {'metric_k': 10, 'bootstrap_samples': 200, 'seed': 11,
                   'tie_tolerance': 1e-12},
        'weights': {'vertices': {'values': [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}},
    }


class MetricTests(unittest.TestCase):
    def test_idcg_includes_relevant_pages_outside_pool(self):
        self.assertAlmostEqual(ndcg(['miss', 'a'], {'a': 1, 'outside': 1}, 10),
                               (1/math.log2(3))/(1+1/math.log2(3)))

    def test_duplicate_ranking_and_graded_labels_are_rejected(self):
        with self.assertRaises(ValueError):
            ndcg(['a', 'a'], {'a': 1}, 10)
        with self.assertRaises(ValueError):
            ndcg(['a'], {'a': 2}, 10)

    def test_bootstrap_is_paired_and_deterministic(self):
        a = paired_summary([.1, .1, .1], 300, 19, 1e-12)
        self.assertEqual(a, paired_summary([.1, .1, .1], 300, 19, 1e-12))
        self.assertEqual(a['wins'], 3)
        self.assertEqual(a['ties'], 0)
        self.assertAlmostEqual(a['ci95'][0], .1)
        self.assertAlmostEqual(a['ci95'][1], .1)
        self.assertEqual(paired_summary([-.2, 0, .1], 50, 7, 1e-12)['losses'], 1)


class OracleTests(unittest.TestCase):
    def test_global_chooses_one_profile_for_the_entire_study(self):
        import numpy as np
        scores = np.array([[[1., 0., 0.], [0., 1., 0.]],
                           [[0., 1., 0.], [1., 0., 0.]]])
        rows, summary, _ = evaluate(scores, ['q1', 'q2'], ['a', 'b'],
            {'q1': {'b': 1}, 'q2': {'b': 1}}, small_config())
        self.assertAlmostEqual(summary['weight_sets']['vertices']['global_mean'], (1+1/math.log2(3))/2)
        self.assertEqual(summary['weight_sets']['vertices']['qarf_mean'], 1.)

    def test_binary_oracle_matches_exhaustive_weight_assignment(self):
        import numpy as np
        raw = np.array([[[.2, .8, .3], [.5, .1, .9], [.8, .4, .2]]])
        labels = {'q': {'a': 1, 'b': 1}}
        cfg = small_config()
        rows, summary, _ = evaluate(raw, ['q'], ['a', 'b', 'c'], labels, cfg)
        normalized = (raw[0]-raw[0].min(0))/(raw[0].max(0)-raw[0].min(0))
        exhaustive = []
        for choices in itertools.product(range(3), repeat=3):
            scores = [normalized[i, choice] for i, choice in enumerate(choices)]
            order = sorted(range(3), key=lambda i: (-scores[i], ['a', 'b', 'c'][i]))
            exhaustive.append(ndcg([['a', 'b', 'c'][i] for i in order], labels['q'], 10))
        self.assertAlmostEqual(rows[0]['qpaf_ndcg10'], max(exhaustive))
        self.assertGreaterEqual(rows[0]['qpaf_ndcg10'], rows[0]['qarf_ndcg10'])
        self.assertEqual(summary['n_queries'], 1)

    def test_candidate_pool_does_not_read_labels(self):
        import numpy as np
        cfg = small_config()
        cfg['retrieval']['candidate_k'] = 1
        scores = np.array([[[2., 2., 2.], [1., 1., 1.]]])
        rows, _, _ = evaluate(scores, ['q'], ['a', 'b'], {'q': {'b': 1}}, cfg)
        self.assertEqual(rows[0]['candidate_recall'], 0.)
        self.assertEqual(rows[0]['qpaf_ndcg10'], 0.)

    def test_vertex_containing_sets_have_same_exact_qpaf(self):
        import numpy as np
        cfg = small_config()
        cfg['weights']['grid'] = {'simplex_divisions': 10}
        scores = np.array([[[1., 0., .2], [.6, .4, .6], [0., 1., 1.]]])
        rows, _, _ = evaluate(scores, ['q'], ['z', 'a', 'b'], {'q': {'a': 1}}, cfg)
        self.assertEqual(len(weight_sets(cfg)['grid']), 66)
        self.assertEqual(rows[0]['qpaf_ndcg10'], rows[1]['qpaf_ndcg10'])

    def test_nonfinite_or_wrong_id_cache_fails(self):
        import numpy as np
        with self.assertRaises(ValueError):
            evaluate(np.array([[[float('nan'), 0., 0.]]]), ['q'], ['p'],
                     {'q': {'p': 1}}, small_config())
        with self.assertRaises(ValueError):
            evaluate(np.ones((1, 2, 3)), ['q'], ['p', 'p'],
                     {'q': {'p': 1}}, small_config())

    def test_constant_scores_use_id_ties(self):
        import numpy as np
        rows, _, _ = evaluate(np.ones((1, 2, 3)), ['q'], ['z', 'a'],
                              {'q': {'z': 1}}, small_config())
        self.assertAlmostEqual(rows[0]['qpaf_ndcg10'], 1/math.log2(3))


class ConfigTests(unittest.TestCase):
    def test_preset_and_cli_overrides(self):
        root = Path(__file__).resolve().parents[1]
        cfg = load_config(root/'configs/m1.1/vidoseek.toml',
                          ['modal.gpu=L4', 'selection.count=7'])
        self.assertEqual(cfg['modal']['gpu'], 'L4')
        self.assertEqual(cfg['selection']['count'], 7)

    def test_unknown_override_and_invalid_resource_fail(self):
        root = Path(__file__).resolve().parents[1]
        for override in ['modal.gpu_typo="L4"', 'modal.timeout=0',
                         'retrieval.candidate_k=-1', 'selection.count=true']:
            with self.subTest(override=override), self.assertRaises(ValueError):
                load_config(root/'configs/m1.1/vidoseek.toml', [override])


if __name__ == '__main__':
    unittest.main()
