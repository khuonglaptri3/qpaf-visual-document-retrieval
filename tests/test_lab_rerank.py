"""F5 reranker fusion on synthetic inputs only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np  # noqa: E402

from qpaf.lab.rerank import fold_anchors, fuse, minmax, top_pages, unit_score  # noqa: E402
from tests.test_lab import ANCHOR, synthetic  # noqa: E402


class RerankFusionTests(unittest.TestCase):
    def test_lambda_zero_reproduces_static(self):
        for q in synthetic(12):
            static = unit_score(q, minmax(q.raw)@np.asarray(ANCHOR))
            rerank = {i: float(-i) for i in range(len(q.page_ids))}
            self.assertEqual(unit_score(q, fuse(q, ANCHOR, rerank, 0., k=5)), static)

    def test_top_pages_stay_above_the_rest(self):
        q = synthetic(1)[0]
        top = top_pages(q, ANCHOR, k=4)
        scores = fuse(q, ANCHOR, {i: float(i) for i in range(len(q.page_ids))}, 1., k=4)
        rest = np.setdiff1d(np.arange(len(q.page_ids)), top)
        self.assertGreater(scores[top].min(), scores[rest].max())
        self.assertEqual(int(np.argmax(scores)), int(max(top)))  # λ = 1 orders the top by the reranker alone

    def test_fold_anchors_are_grid_points(self):
        anchors = fold_anchors(synthetic(30), folds=3)
        self.assertEqual(len(anchors), 3)
        for anchor in anchors:
            self.assertAlmostEqual(sum(anchor), 1.)


class GateStackTests(unittest.TestCase):
    RECIPE = {'epochs': 4, 'average_from': 2}

    def setUp(self):
        from qpaf.lab.rerank_stack import gate_page_scores
        self.queries = synthetic(30, documents=8, pages=3)
        self.scores, self.anchors = gate_page_scores(self.queries, 20260820, folds=3, recipe=self.RECIPE,
                                                     log=lambda *_: None)

    def test_page_scores_reproduce_the_lab_rows(self):
        from qpaf.lab.train import run_experiment
        from qpaf.lab.variants import load_variant
        result = run_experiment(self.queries, load_variant('baseline'), folds=3, recipe=self.RECIPE,
                                log=lambda *_: None)
        self.assertEqual(self.anchors, result['fold_anchors'])
        for method in ('qarf', 'qpaf'):
            for q, page_scores in zip(self.queries, self.scores[method]):
                self.assertEqual(unit_score(q, page_scores), result['per_query'][method][q.query_id])

    def test_lambda_zero_keeps_the_gate_ranking(self):
        from qpaf.lab.rerank import fuse_scores, top_of
        for q, page_scores in zip(self.queries, self.scores['qpaf']):
            rerank = {i: float(-i) for i in top_of(page_scores)}
            self.assertEqual(unit_score(q, fuse_scores(page_scores, rerank, 0.)), unit_score(q, page_scores))


class LambdaGateTests(unittest.TestCase):
    def setUp(self):
        from qpaf.lab.rerank_gate import query_tensors
        self.queries = synthetic(20, documents=8, pages=3)  # 24 pages, above the top-20 cut
        rng = np.random.default_rng(1)
        self.rerank = {q.query_id: {p: float(rng.normal()) for p in q.page_ids} for q in self.queries}
        self.text = {p: '' if p.endswith('_0') else 'page text' for q in self.queries for p in q.page_ids}
        self.items = [query_tensors(q, ANCHOR, self.rerank, self.text) for q in self.queries]

    def test_untrained_gate_matches_constant_lambda(self):
        from qpaf.lab.rerank_gate import LambdaGate, page_lambdas, columns_for
        for granularity in ('query', 'page'):
            columns = columns_for(granularity)
            gate = LambdaGate(0.6, len(columns))
            lam = page_lambdas(gate, columns, np.zeros(len(columns)), np.ones(len(columns)), self.items[0])
            np.testing.assert_allclose(lam, 0.6)

    def test_training_keeps_lambda_in_range(self):
        from qpaf.lab.rerank_gate import page_lambdas, train_gate
        recipe = {'epochs': 4, 'average_from': 2, 'learning_rate': 0.01, 'weight_decay': 0., 'batch_size': 8,
                  'max_grad_norm': 5.}
        model, columns, mean, std = train_gate(self.items, 0.6, 'page', 20260820, recipe)
        lam = page_lambdas(model, columns, mean, std, self.items[0])
        self.assertTrue(np.isfinite(lam).all() and ((lam > 0) & (lam < 1)).all())


if __name__ == '__main__':
    unittest.main()
