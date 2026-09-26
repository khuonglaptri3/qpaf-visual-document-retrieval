"""Independent numeric and behavioral checks for the learned fusion core."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
HAS_TORCH = importlib.util.find_spec('torch') is not None
if HAS_TORCH:
    import torch
    from qpaf.m12.features import FeatureBatch, FEATURE_NAMES, build_features
    from qpaf.m12.model import FusionGate, fuse_scores, make_model
    from qpaf.m12.losses import pairwise_logistic_loss
    from qpaf.m12.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def setUpModule():
    global previous_threads
    if HAS_TORCH:
        previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)


def tearDownModule():
    if HAS_TORCH:
        torch.set_num_threads(previous_threads)


def fixture():
    return build_features(torch.tensor([[[4., 20., 7.], [2., 10., 7.], [0., 30., 7.]]],
                                      dtype=torch.float64), ['apple pear'], [['c', 'a', 'b']],
                          query_length_cap=4)


@unittest.skipUnless(HAS_TORCH, 'install requirements/m12-cpu.txt for method-core checks')
class FeatureTests(unittest.TestCase):
    def test_thirteen_features_match_hand_computation(self):
        batch = fixture()
        expected = torch.tensor([[
            [1., .5, 0., 1., .5, 1/3, .5, .5, 0., .5, 1., .5, .5],
            [.5, 0., 0., .5, 1/3, 1., .5, .5, 0., .5, .5, 0., .5],
            [0., 1., 0., 1/3, 1., .5, .5, .5, 0., 1., 0., 1., .5],
        ]], dtype=torch.float64)
        torch.testing.assert_close(batch.values, expected)
        self.assertEqual(FEATURE_NAMES, ('score_bm25', 'score_dense', 'score_visual',
            'rr_bm25', 'rr_dense', 'rr_visual', 'gap_bm25', 'gap_dense', 'gap_visual',
            'disagreement_bm25_dense', 'disagreement_bm25_visual',
            'disagreement_dense_visual', 'query_length'))

    def test_constant_channels_singleton_and_empty_query_are_defined(self):
        batch = build_features(torch.tensor([[[7., -3., 0.]]]), [''], [['p']])
        self.assertEqual(batch.values.tolist(), [[[0., 0., 0., 1., 1., 1.,
                                                 0., 0., 0., 0., 0., 0., 0.]]])

    def test_padding_and_permutation_preserve_page_features(self):
        baseline = fixture()
        raw = torch.tensor([[[0., 30., 7.], [float('nan')]*3, [4., 20., 7.], [2., 10., 7.]]],
                           dtype=torch.float64)
        batch = build_features(raw, ['apple pear'], [['b', '', 'c', 'a']],
                               torch.tensor([[True, False, True, True]]), query_length_cap=4)
        torch.testing.assert_close(batch.values[:, [2, 3, 0]], baseline.values)
        self.assertEqual(batch.values[0, 1].tolist(), [0.]*13)
        self.assertTrue(torch.isfinite(batch.scores).all())

    def test_query_length_is_capped_unicode_word_count(self):
        batch = build_features(torch.ones(1, 1, 3), ['bảng biểu tài chính'], [['p']],
                               query_length_cap=2)
        self.assertEqual(batch.values[0, 0, 12], 1.)

    def test_active_nonfinite_scores_and_invalid_identifiers_fail(self):
        for bad in (float('nan'), float('inf'), -float('inf')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build_features(torch.tensor([[[bad, 0., 0.]]]), ['q'], [['p']])
        for ids in ([['a', 'a']], [['a', '']], [['a']]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                build_features(torch.ones(1, 2, 3), ['q'], ids)

    def test_bad_shape_dtype_empty_query_pool_and_cap_fail(self):
        cases = [
            (torch.ones(1, 2, 2), None, 64),
            (torch.ones(1, 2, 3, dtype=torch.int64), None, 64),
            (torch.ones(1, 2, 3), torch.zeros(1, 2, dtype=torch.bool), 64),
            (torch.ones(1, 2, 3), torch.ones(1, 2), 64),
            (torch.ones(1, 2, 3), None, 0),
        ]
        for raw, mask, cap in cases:
            with self.subTest(shape=raw.shape, mask=mask, cap=cap), self.assertRaises(ValueError):
                build_features(raw, ['q'], [['a', 'b']], mask, query_length_cap=cap)

    def test_feature_construction_disconnects_retriever_autograd(self):
        raw = torch.tensor([[[1., 0., 2.], [0., 1., 1.]]], requires_grad=True)
        batch = build_features(raw, ['q'], [['a', 'b']])
        self.assertFalse(batch.values.requires_grad)
        self.assertFalse(batch.scores.requires_grad)
        self.assertIsNone(raw.grad)


@unittest.skipUnless(HAS_TORCH, 'install requirements/m12-cpu.txt for method-core checks')
class GateTests(unittest.TestCase):
    def test_matched_variants_share_initial_parameters_and_budget(self):
        cfg = load_config(ROOT/'configs/m1.2/core.toml')
        for kind in ('linear', 'mlp'):
            cfg['gate']['kind'] = kind
            qarf, qpaf = make_model(cfg, 'query'), make_model(cfg, 'page')
            self.assertEqual(sum(p.numel() for p in qarf.parameters()),
                             sum(p.numel() for p in qpaf.parameters()))
            for left, right in zip(qarf.parameters(), qpaf.parameters()):
                torch.testing.assert_close(left, right, rtol=0, atol=0)

    def test_granularity_matches_softmax_and_uniform_fusion_by_hand(self):
        batch = fixture()
        qarf = FusionGate('query').double()
        qpaf = FusionGate('page').double()
        with torch.no_grad():
            for model in (qarf, qpaf):
                for p in model.parameters():
                    p.zero_()
                model.gate.weight[0, 0] = 1.
        query = qarf(batch)
        page = qpaf(batch)
        expected = torch.tensor([math.exp(.5), 1., 1.], dtype=torch.float64)/(math.exp(.5)+2)
        torch.testing.assert_close(query.weights[0], expected.expand(3, 3))
        self.assertGreater(page.weights[0, 0, 0], page.weights[0, 1, 0])
        self.assertGreater(page.weights[0, 1, 0], page.weights[0, 2, 0])
        torch.testing.assert_close(page.weights.sum(-1), torch.ones(1, 3, dtype=torch.float64))
        self.assertTrue(torch.all(page.weights >= 0))
        with torch.no_grad():
            qpaf.gate.weight.zero_()
        torch.testing.assert_close(qpaf(batch).scores,
                                   torch.tensor([[.5, 1/6, 1/3]], dtype=torch.float64))

    def test_fusion_matches_known_weighted_scores(self):
        values = torch.tensor([[[.2, .6, 1.], [.8, .1, .4]]], dtype=torch.float64)
        weights = torch.tensor([[[.5, .25, .25], [.1, .2, .7]]], dtype=torch.float64)
        result = fuse_scores(values, weights, torch.tensor([[True, True]]))
        torch.testing.assert_close(result, torch.tensor([[.5, .38]], dtype=torch.float64))

    def test_fusion_rejects_non_simplex_weights(self):
        for weights in ([1., 1., 1.], [-.1, .6, .5], [float('nan'), 0., 1.]):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                fuse_scores(torch.ones(1, 1, 3), torch.tensor([[weights]]),
                            torch.tensor([[True]]))

    def test_mask_and_permutation_do_not_change_real_predictions(self):
        batch = fixture()
        padded = build_features(torch.tensor([[[0., 30., 7.], [4., 20., 7.],
                                               [float('nan')]*3, [2., 10., 7.]]], dtype=torch.float64),
                                ['apple pear'], [['b', 'c', '', 'a']],
                                torch.tensor([[True, True, False, True]]), query_length_cap=4)
        for granularity in ('query', 'page'):
            model = FusionGate(granularity, kind='mlp', hidden_dim=5).double()
            before, after = model(batch), model(padded)
            torch.testing.assert_close(after.scores[:, [1, 3, 0]], before.scores)
            torch.testing.assert_close(after.weights[:, [1, 3, 0]], before.weights)
            self.assertEqual(after.scores[0, 2], 0.)
            self.assertEqual(after.weights[0, 2].tolist(), [0., 0., 0.])

    def test_bad_gate_settings_are_rejected(self):
        for kwargs in ({'granularity': 'oracle'}, {'temperature': 0},
                       {'temperature': float('nan')}, {'kind': 'deep'}, {'hidden_dim': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                FusionGate(**kwargs)

    def test_backward_updates_only_gate_even_with_attached_input_tensors(self):
        for granularity in ('query', 'page'):
            raw = torch.tensor([[[3., 0., 1.], [0., 2., 1.], [1., 1., 0.]]],
                               dtype=torch.float64, requires_grad=True)
            original = raw.detach().clone()
            batch = build_features(raw, ['q'], [['a', 'b', 'c']])
            values = batch.values.clone().requires_grad_()
            scores = batch.scores.clone().requires_grad_()
            batch = FeatureBatch(values, scores, batch.mask)
            model = FusionGate(granularity).double()
            prediction = model(batch)
            loss = pairwise_logistic_loss(prediction.scores, torch.tensor([[1., 0., 0.]]), batch.mask)
            loss.loss.backward()
            grads = [p.grad for p in model.parameters()]
            self.assertTrue(all(g is not None and torch.isfinite(g).all() for g in grads))
            self.assertGreater(sum(g.abs().sum().item() for g in grads), 0.)
            before = [p.detach().clone() for p in model.parameters()]
            torch.optim.SGD(model.parameters(), lr=.2).step()
            self.assertTrue(any(not torch.equal(a, b) for a, b in zip(before, model.parameters())))
            self.assertIsNone(raw.grad)
            self.assertIsNone(values.grad)
            self.assertIsNone(scores.grad)
            torch.testing.assert_close(raw.detach(), original, rtol=0, atol=0)

    def test_gate_loss_autograd_matches_finite_differences(self):
        from torch.func import functional_call
        batch = fixture()
        labels = torch.tensor([[1., 0., 0.]], dtype=torch.float64)
        for granularity in ('query', 'page'):
            for kind in ('linear', 'mlp'):
                model = FusionGate(granularity, kind=kind, hidden_dim=2).double()
                names, parameters = zip(*model.named_parameters())
                def objective(*weights):
                    prediction = functional_call(model, dict(zip(names, weights)), (batch,))
                    return pairwise_logistic_loss(prediction.scores, labels, batch.mask).loss
                self.assertTrue(torch.autograd.gradcheck(objective, parameters, atol=1e-5, rtol=1e-3))

    def test_small_learning_run_reduces_loss_for_both_variants(self):
        cfg = load_config(ROOT/'configs/m1.2/core.toml')
        batch = fixture()
        labels = torch.tensor([[1., 0., 0.]], dtype=torch.float64)
        for granularity in ('query', 'page'):
            model = make_model(cfg, granularity).double()
            optimizer = torch.optim.SGD(model.parameters(), lr=.2)
            start = pairwise_logistic_loss(model(batch).scores, labels, batch.mask).loss.item()
            for _ in range(30):
                optimizer.zero_grad()
                pairwise_logistic_loss(model(batch).scores, labels, batch.mask).loss.backward()
                optimizer.step()
            end = pairwise_logistic_loss(model(batch).scores, labels, batch.mask).loss.item()
            self.assertLess(end, start-.01)


@unittest.skipUnless(HAS_TORCH, 'install requirements/m12-cpu.txt for method-core checks')
class LossTests(unittest.TestCase):
    def test_pairwise_loss_and_derivative_match_hand_calculation(self):
        scores = torch.tensor([[.8, .2]], dtype=torch.float64, requires_grad=True)
        result = pairwise_logistic_loss(scores, torch.tensor([[1., 0.]]), torch.tensor([[True, True]]))
        self.assertAlmostEqual(result.loss.item(), math.log1p(math.exp(-.6)))
        result.loss.backward()
        derivative = 1/(1+math.exp(.6))
        torch.testing.assert_close(scores.grad, torch.tensor([[-derivative, derivative]], dtype=torch.float64))
        self.assertEqual((result.valid_queries, result.skipped_queries, result.pairs), (1, 0, 1))

    def test_query_mean_does_not_overweight_queries_with_more_pairs(self):
        scores = torch.tensor([[0., 0., 0.], [1., 0., float('nan')], [0., 0., 0.]])
        labels = torch.tensor([[1., 0., 0.], [1., 0., float('nan')], [1., 1., 1.]])
        mask = torch.tensor([[True, True, True], [True, True, False], [True, True, True]])
        result = pairwise_logistic_loss(scores, labels, mask)
        self.assertAlmostEqual(result.loss.item(), (math.log(2)+math.log1p(math.exp(-1)))/2, places=6)
        self.assertEqual((result.valid_queries, result.skipped_queries, result.pairs), (2, 1, 3))

    def test_inactive_scores_have_zero_gradient(self):
        scores = torch.tensor([[.8, .2, float('nan')]], requires_grad=True)
        result = pairwise_logistic_loss(scores, torch.tensor([[1., 0., float('nan')]]),
                                        torch.tensor([[True, True, False]]))
        result.loss.backward()
        self.assertEqual(scores.grad[0, 2], 0.)
        self.assertTrue(torch.isfinite(scores.grad).all())

    def test_no_pairs_graded_labels_and_nonfinite_active_values_fail(self):
        for labels in ([[1., 1.]], [[0., 0.]], [[2., 0.]], [[float('nan'), 0.]]):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                pairwise_logistic_loss(torch.zeros(1, 2), torch.tensor(labels), torch.ones(1, 2, dtype=torch.bool))
        with self.assertRaises(ValueError):
            pairwise_logistic_loss(torch.tensor([[float('inf'), 0.]]), torch.tensor([[1., 0.]]),
                                   torch.ones(1, 2, dtype=torch.bool))

    def test_large_score_difference_is_numerically_stable(self):
        result = pairwise_logistic_loss(torch.tensor([[-1000., 1000.]], requires_grad=True),
                                        torch.tensor([[1., 0.]]), torch.tensor([[True, True]]))
        self.assertEqual(result.loss.item(), 2000.)


if __name__ == '__main__':
    unittest.main()
