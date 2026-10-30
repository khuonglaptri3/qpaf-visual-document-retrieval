"""F4 query-embedding PCA features (docs/feature_lab/F4)."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from qpaf.lab.train import run_experiment  # noqa: E402
from qpaf.lab.variants import load_variant  # noqa: E402
from qpaf.lab.variants.f4_qemb16 import query_features, query_table  # noqa: E402
from test_lab import synthetic  # noqa: E402


def write_embeddings(directory, ids, seed=0):
    rng = np.random.default_rng(seed)
    vectors = rng.normal(size=(len(ids), 1024))*np.linspace(3, 0.1, 1024)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    path = Path(directory)/'qemb.npz'
    np.savez(path, ids=np.array(ids), vectors=vectors.astype(np.float32))
    return path


class QueryTableTests(unittest.TestCase):
    def test_pca_has_16_dims_in_decreasing_variance(self):
        with tempfile.TemporaryDirectory() as directory:
            table = query_table(write_embeddings(directory, [f'q{i}' for i in range(20)]))
        matrix = np.stack(list(table.values()))
        self.assertEqual(matrix.shape, (20, 16))
        variance = matrix.var(axis=0)
        self.assertEqual(int(variance.argmax()), 0)
        self.assertTrue((np.diff(variance) <= 1e-12).all())

    def test_same_row_on_every_page_and_clear_missing_error(self):
        with tempfile.TemporaryDirectory() as directory:
            features = query_features(write_embeddings(directory, [f'q{i}' for i in range(20)]))
        x = features('q3', 'text', ('a', 'b', 'c'), np.zeros((3, 3)))
        self.assertEqual(x.shape, (3, 16))
        self.assertTrue((x == x[0]).all())
        with self.assertRaisesRegex(KeyError, 'no vector for query nope'):
            features('nope', 'text', ('a',), np.zeros((1, 3)))


class F4ExperimentTests(unittest.TestCase):
    def test_both_variants_run_cross_validation(self):
        queries = synthetic(count=24)
        with tempfile.TemporaryDirectory() as directory:
            assets = {'query_embeddings': str(write_embeddings(directory, [q.query_id for q in queries]))}
            for name in ('f4_qemb16', 'f4_qemb16_mlp'):
                result = run_experiment(queries, load_variant(name, assets), folds=2,
                                        recipe={'epochs': 2, 'average_from': 1}, log=lambda *_: None)
                self.assertEqual(result['feature_dim'], 29)


if __name__ == '__main__':
    unittest.main()
