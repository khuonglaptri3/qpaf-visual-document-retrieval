"""F1 content features on a hand-made OCR corpus (docs/feature_lab/F1)."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from qpaf.lab.train import run_experiment  # noqa: E402
from qpaf.lab.variants import load_variant  # noqa: E402
from qpaf.lab.variants.f1_content import content_features  # noqa: E402
from test_lab import synthetic  # noqa: E402

PAGES = {'a': 'Revenue grew 12.5 percent\nin 2020', 'b': '', 'c': 'revenue grew slowly'}


def write_corpus(directory, pages):
    path = Path(directory)/'page_text.jsonl'
    path.write_text(''.join(json.dumps({'page_id': k, 'text': v})+'\n' for k, v in pages.items()), encoding='utf-8')
    return path


def idf(df, n=3):
    return math.log((n-df+0.5)/(df+0.5)+1)


class ContentFeatureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = write_corpus(self.directory.name, PAGES)
        self.features = content_features(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_values_match_hand_computation(self):
        x = self.features('q', 'How much did revenue grow in 2020 xyz', ('a', 'b', 'c'), np.zeros((3, 3)))
        self.assertEqual(x.shape, (3, 13))
        # page side: a has 7 tokens (revenue grew 12 5 percent in 2020), 3 with digits, 2 lines; b is empty
        self.assertAlmostEqual(x[0, 0], math.log1p(7))
        self.assertEqual(x[1, 1], 1.)
        self.assertAlmostEqual(x[0, 2], 3/7)
        self.assertAlmostEqual(x[0, 3], math.log1p(2))
        self.assertEqual(x[1, 3], 0.)
        # query side: has a number, numeric intent, known tokens revenue (df 2), in/2020 (df 1); 'how', 'much', 'did',
        # 'grow', 'xyz' unknown → 3 known of 8 unique
        self.assertTrue((x[:, 4] == 1).all() and (x[:, 5] == 1).all())
        self.assertAlmostEqual(x[0, 6], idf(1))
        self.assertAlmostEqual(x[0, 7], (idf(2)+2*idf(1))/3)
        self.assertAlmostEqual(x[0, 8], 1-3/8)
        # interaction: page a holds all three known tokens and the number 2020; c only 'revenue'
        self.assertEqual(x[0, 9], 1.)
        self.assertAlmostEqual(x[2, 9], 1/3)
        self.assertAlmostEqual(x[2, 10], idf(2)/(idf(2)+2*idf(1)))
        self.assertEqual(x[0, 11], 1.)
        self.assertEqual(x[2, 11], 0.)
        self.assertEqual(x[1, 9:].tolist(), [0., 0., 0., 0.])

    def test_bigram_coverage(self):
        x = self.features('q', 'revenue grew', ('a', 'b', 'c'), np.zeros((3, 3)))
        self.assertEqual(x[:, 12].tolist(), [1., 0., 1.])
        y = self.features('q', 'grew revenue', ('a',), np.zeros((1, 3)))
        self.assertEqual(y[0, 12], 0.)

    def test_order_independent_finite_and_page_only_prefix(self):
        first = self.features('q1', 'revenue 2020', ('a', 'c'), np.zeros((2, 3)))
        self.features('q2', 'something else', ('b',), np.zeros((1, 3)))
        self.assertTrue(np.array_equal(first, self.features('q1', 'revenue 2020', ('a', 'c'), np.zeros((2, 3)))))
        self.assertTrue(np.isfinite(self.features('q3', '', ('a', 'b'), np.zeros((2, 3)))).all())
        page_only = content_features(self.path, columns=4)('q1', 'revenue 2020', ('a', 'c'), np.zeros((2, 3)))
        self.assertTrue(np.array_equal(page_only, first[:, :4]))

    def test_missing_page_is_a_clear_error(self):
        with self.assertRaisesRegex(KeyError, 'no OCR row for page zz'):
            self.features('q', 'revenue', ('zz',), np.zeros((1, 3)))


class F1ExperimentTests(unittest.TestCase):
    def test_all_f1_variants_run_cross_validation(self):
        queries = synthetic(count=12)
        pages = {pid: f'text {pid} {i}' for q in queries for i, pid in enumerate(q.page_ids)}
        with tempfile.TemporaryDirectory() as directory:
            assets = {'page_text': str(write_corpus(directory, pages))}
            for name, width in (('f1_content', 13), ('f1_content_mlp', 13), ('f1_page_only', 4)):
                result = run_experiment(queries, load_variant(name, assets), folds=2,
                                        recipe={'epochs': 2, 'average_from': 1}, log=lambda *_: None)
                self.assertEqual(result['feature_dim'], 13+width)
                self.assertEqual(set(result['per_query']['qpaf']), {q.query_id for q in queries})


if __name__ == '__main__':
    unittest.main()
