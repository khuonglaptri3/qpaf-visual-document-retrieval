"""Feature-lab harness on synthetic inputs only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch import nn  # noqa: E402

from qpaf.lab.compare import paired, summary  # noqa: E402
from qpaf.lab.data import LabDataError, fold_of, make_query  # noqa: E402
from qpaf.lab.model import LabGate, listwise_loss, max_pool, unit_max, unit_ndcg  # noqa: E402
from qpaf.lab.train import collate, gate_inputs, prepare, run_experiment, standardizer  # noqa: E402
from qpaf.lab.variants import Variant, load_variant  # noqa: E402
from qpaf.m24.evaluator import query_metrics  # noqa: E402

ANCHOR = [0.1, 0.2, 0.7]


def synthetic(count=24, seed=0, documents=6, pages=3):
    """ViMDoc-like queries: relevant documents score higher on the visual channel, plus noise."""
    rng = np.random.default_rng(seed)
    queries = []
    for q in range(count):
        page_ids = [f'd{d}_{p}' for d in range(documents) for p in range(pages)]
        relevant = {f'd{rng.integers(documents)}'}
        raw = rng.random((len(page_ids), 3))
        raw[:, 2] += np.array([0.6*(pid.split('_')[0] in relevant) for pid in page_ids])
        queries.append(make_query(f'q{q:03d}', f'query {q} text', page_ids, raw,
                                  {pid: pid.split('_')[0] for pid in page_ids}, relevant, len(relevant)))
    return queries


class Identity(nn.Module):
    def __init__(self):
        super().__init__()
        self.gamma = nn.Parameter(torch.zeros((), dtype=torch.float64))

    def forward(self, scores, mask):
        return scores.clamp_min(0)**torch.exp(self.gamma)


class DataTests(unittest.TestCase):
    def test_make_query_sorts_pages_and_indexes_units(self):
        q = make_query('q', 'text', ['b_1', 'a_2', 'a_1'], [[1, 1, 1], [2, 2, 2], [3, 3, 3]],
                       {'b_1': 'b', 'a_2': 'a', 'a_1': 'a'}, {'b', 'zz'}, 2)
        self.assertEqual(q.page_ids, ('a_1', 'a_2', 'b_1'))
        self.assertEqual(q.raw[:, 0].tolist(), [3, 2, 1])
        self.assertEqual(q.unit_ids, ('a', 'b'))
        self.assertEqual(q.units.tolist(), [0, 0, 1])
        self.assertEqual(q.positive.tolist(), [False, True])
        with self.assertRaises(LabDataError):
            make_query('q', 'text', ['a'], [[np.nan, 0, 0]], {'a': 'a'}, {'a'}, 1)

    def test_folds_are_deterministic_and_in_range(self):
        folds = [fold_of(f'q{i}') for i in range(500)]
        self.assertEqual(folds, [fold_of(f'q{i}') for i in range(500)])
        self.assertEqual(set(folds), set(range(5)))


class ModelTests(unittest.TestCase):
    def test_unit_ndcg_matches_the_m24_metric_with_ties(self):
        rng = np.random.default_rng(1)
        for _ in range(200):
            scores = rng.integers(0, 4, 15).astype(float)
            positive = rng.random(15) < 0.2
            total = int(positive.sum())+int(rng.integers(0, 2))
            if total == 0:
                continue
            order = sorted(range(15), key=lambda i: (-scores[i], i))
            expected = query_metrics([int(positive[i]) for i in order], total)['ndcg_at_10']
            self.assertAlmostEqual(unit_ndcg(scores, positive, total), expected, places=12)

    def test_every_gate_starts_at_the_anchor(self):
        generator = torch.Generator().manual_seed(0)
        features = torch.rand(2, 5, 15, generator=generator, dtype=torch.float64)
        scores = torch.rand(2, 5, 3, generator=generator, dtype=torch.float64)
        mask = torch.ones(2, 5, dtype=torch.bool)
        mask[1, 3:] = False
        expected = torch.where(mask, scores@torch.tensor(ANCHOR, dtype=torch.float64), 0.)
        for granularity in ('query', 'page'):
            for hidden, calibrator in ((0, None), (8, None), (0, Identity())):
                fused, _ = LabGate(ANCHOR, granularity, 15, hidden=hidden, calibrator=calibrator)(features, scores, mask)
                self.assertTrue(torch.allclose(fused, expected, atol=1e-5), (granularity, hidden))

    def test_max_pool_matches_numpy_and_ignores_padding(self):
        page_scores = torch.tensor([[0.2, 0.9, 0.4, 0.], [0.5, 0.1, 0., 0.]], dtype=torch.float64)
        units = torch.tensor([[0, 0, 1, 2], [1, 0, 2, 2]])
        pooled = max_pool(page_scores, units, 3)
        self.assertEqual(pooled[0, :2].tolist(), unit_max([0.2, 0.9, 0.4], [0, 0, 1], 2).tolist())
        self.assertEqual(pooled[1, :2].tolist(), [0.1, 0.5])

    def test_listwise_loss_has_finite_gradients_with_padding(self):
        scores = torch.tensor([[0.9, 0.2, 0.5, 0.], [0.3, 0.8, 0., 0.]], dtype=torch.float64, requires_grad=True)
        unit_mask = torch.tensor([[True, True, True, False], [True, True, False, False]])
        positive = torch.tensor([[False, True, False, False], [True, True, False, False]])
        log_tau = torch.tensor(-1., dtype=torch.float64, requires_grad=True)
        loss, valid = listwise_loss(scores, unit_mask, positive, log_tau)
        loss.backward()
        self.assertEqual(valid, 1)  # the second query has no negative
        expected = torch.logsumexp(scores[0, :3]/np.exp(-1), 0)-scores[0, 1]/np.exp(-1)
        self.assertAlmostEqual(loss.item(), expected.item(), places=12)
        self.assertTrue(torch.isfinite(scores.grad).all() and torch.isfinite(log_tau.grad))


class HarnessTests(unittest.TestCase):
    def test_baseline_cross_validation_scores_every_query_once(self):
        queries = synthetic()
        result = run_experiment(queries, load_variant('baseline'), folds=3, recipe={'epochs': 4, 'average_from': 2},
                                log=lambda *_: None)
        ids = {q.query_id for q in queries}
        for method in ('static', 'qarf', 'qpaf'):
            self.assertEqual(set(result['per_query'][method]), ids)
            self.assertTrue(all(0 <= v <= 1 for v in result['per_query'][method].values()))
        self.assertEqual(sum(result['fold_sizes']), len(queries))
        self.assertEqual(result['feature_dim'], 13)

    def test_extra_features_are_label_free_and_standardized(self):
        seen = []

        def page_features(query_id, text, page_ids, raw):
            seen.append(query_id)
            return np.stack([raw[:, 2]*100, np.full(len(page_ids), len(text))], axis=1)
        variant = Variant('probe', page_features=page_features, hidden=4)
        queries = synthetic(count=12)
        items = prepare(queries, variant)
        self.assertEqual(seen, [q.query_id for q in queries])
        inputs = gate_inputs(items, *standardizer(items))
        stacked = torch.cat(inputs)[:, 13:]
        self.assertTrue(torch.allclose(stacked[:, 0].mean(), torch.zeros((), dtype=torch.float64), atol=1e-9))
        batch = collate(items[:3], inputs[:3])
        self.assertEqual(tuple(batch['features'].shape[1:]), (18, 15))
        result = run_experiment(queries, variant, granularities=('page',), folds=2,
                                recipe={'epochs': 2, 'average_from': 1}, log=lambda *_: None)
        self.assertEqual(result['feature_dim'], 15)

    def test_bad_feature_width_is_rejected(self):
        variant = Variant('bad', page_features=lambda q, t, p, r: np.zeros((len(p)+1, 2)))
        with self.assertRaises(RuntimeError):
            prepare(synthetic(count=2), variant)

    def test_load_variant_rejects_bad_names(self):
        self.assertEqual(load_variant('baseline').name, 'baseline')
        for name in ('../x', 'Baseline', ''):
            with self.assertRaises(ValueError):
                load_variant(name)


class CompareTests(unittest.TestCase):
    def test_paired_bootstrap(self):
        a = {f'q{i}': i/100 for i in range(50)}
        same = paired(a, dict(a))
        self.assertEqual((same['delta'], same['ci95'], same['ties']), (0., [0., 0.], 50))
        shifted = paired({k: v+0.01 for k, v in a.items()}, a)
        self.assertAlmostEqual(shifted['delta'], 0.01, places=12)
        self.assertEqual(shifted['wins'], 50)
        with self.assertRaises(ValueError):
            paired(a, {'q0': 0.})

    def test_summary_renders_without_a_verdict_rule(self):
        per_query = {m: {'q1': 0.5, 'q2': 1.} for m in ('static', 'qarf', 'qpaf')}
        record = {'queries': 2, 'mean': {m: 0.75 for m in per_query}, 'per_query': per_query}
        text = summary({('vimdoc', 'baseline'): record, ('vimdoc', 'f1_content'): record})
        self.assertIn('| vimdoc | f1_content | QPAF |', text)


if __name__ == '__main__':
    unittest.main()
