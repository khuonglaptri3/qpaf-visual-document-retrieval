"""F3 ranking losses and document pooling (docs/feature_lab/F3)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch.utils._python_dispatch import TorchDispatchMode  # noqa: E402
from torch.utils._pytree import tree_leaves  # noqa: E402

from qpaf.lab.model import listwise_loss, max_pool, unit_ndcg  # noqa: E402
from qpaf.lab.train import run_experiment  # noqa: E402
from qpaf.lab.variants import load_variant  # noqa: E402
from qpaf.lab.variants.f3_approxndcg import approx_ndcg_loss  # noqa: E402
from qpaf.lab.variants.f3_lse_pool import lse_pool  # noqa: E402
from qpaf.lab.variants.f3_topk_hard import topk_hard_loss  # noqa: E402
from test_lab import synthetic  # noqa: E402


def batch(seed=0, rows=4, units=30):
    generator = torch.Generator().manual_seed(seed)
    scores = torch.randperm(rows*units, generator=generator).view(rows, units).to(torch.float64)/(rows*units)
    mask = torch.ones(rows, units, dtype=torch.bool)
    mask[1, 20:] = False
    positive = torch.rand(rows, units, generator=generator) < 0.15
    positive[:, 0] = True
    return scores, mask, positive & mask


def dense_approx_reference(scores, mask, positive, alpha=0.01, width=0.5):
    """Frozen original dense formula, independent of the positive-rank implementation."""
    positive = positive & mask
    valid = positive.any(1) & (mask & ~positive).any(1)
    values, present = scores[valid], mask[valid]
    relevance = positive[valid].to(values.dtype)
    values = torch.where(present, values, values.detach().min()-1)
    pairwise = torch.sigmoid((values[:, None, :]-values[:, :, None])/alpha)
    ranks = 0.5+(pairwise*present[:, None, :]).sum(-1)
    dcg = (relevance*torch.sigmoid((10.5-ranks)/width)/torch.log2(1+ranks)).sum(1)
    idcg = (1/torch.log2(torch.arange(2, 12, dtype=values.dtype))).cumsum(0)
    counts = relevance.sum(1).clamp(max=10).long()
    return (1-dcg/idcg[counts-1]).mean(), int(valid.sum())


class LargestTensor(TorchDispatchMode):
    """Observe real intermediate allocations without replacing any operation."""
    def __init__(self):
        super().__init__()
        self.elements = 0

    def __torch_dispatch__(self, func, types, args=(), kwargs=None):
        result = func(*args, **(kwargs or {}))
        for value in tree_leaves(result):
            if isinstance(value, torch.Tensor):
                self.elements = max(self.elements, value.numel())
        return result


class LossTests(unittest.TestCase):
    def test_approx_ndcg_loss_and_gradients_match_dense_with_padding_and_many_positives(self):
        scores, mask, positive = batch(7)
        positive[0, :15] = True  # IDCG clamps at ten while all positive gains still contribute
        positive[1, 20:] = True  # padding labels must have no effect
        positive[2] = False     # invalid: no positive
        positive[3] = mask[3]   # invalid: no negative
        for alpha, width in ((0.01, 0.5), (0.003, 0.02)):
            with self.subTest(alpha=alpha, width=width):
                actual_scores = scores.clone().requires_grad_(True)
                expected_scores = scores.clone().requires_grad_(True)
                actual, valid = approx_ndcg_loss(actual_scores, mask, positive, torch.zeros(()), None,
                                                 alpha=alpha, width=width)
                expected, reference_valid = dense_approx_reference(expected_scores, mask, positive, alpha, width)
                actual.backward()
                expected.backward()
                self.assertEqual((valid, reference_valid), (2, 2))
                torch.testing.assert_close(actual, expected, rtol=1e-12, atol=1e-12)
                torch.testing.assert_close(actual_scores.grad, expected_scores.grad, rtol=1e-10, atol=1e-12)
                self.assertTrue(torch.isfinite(actual_scores.grad).all())
                self.assertEqual(int(torch.count_nonzero(actual_scores.grad[~mask])), 0)

    def test_approx_ndcg_sparse_labels_do_not_allocate_all_unit_pairs(self):
        # Regression: reintroducing [B,U,U] rank tensors exceeds this linear working-set bound.
        scores = torch.linspace(0, 1, 512, dtype=torch.float64).reshape(2, 256).requires_grad_(True)
        mask = torch.ones_like(scores, dtype=torch.bool)
        positive = torch.zeros_like(mask)
        positive[:, :2] = True
        with LargestTensor() as allocations:
            loss, valid = approx_ndcg_loss(scores, mask, positive, torch.zeros(()), None)
            loss.backward()
        self.assertEqual(valid, 2)
        self.assertLessEqual(allocations.elements, 8192)

    def test_approx_ndcg_skips_queries_without_both_label_classes(self):
        scores = torch.tensor([[0.1, 0.2], [0.3, 0.4]], dtype=torch.float64)
        mask = torch.ones_like(scores, dtype=torch.bool)
        positive = torch.tensor([[False, False], [True, True]])
        loss, valid = approx_ndcg_loss(scores, mask, positive, torch.zeros(()), None)
        self.assertEqual(valid, 0)
        self.assertEqual(loss.item(), 0.)

    def test_approx_ndcg_matches_exact_ndcg_when_sharp(self):
        scores, mask, positive = batch()
        log_tau = torch.zeros((), dtype=torch.float64)
        loss, valid = approx_ndcg_loss(scores, mask, positive, log_tau, None, alpha=1e-4, width=0.02)
        exact = np.mean([unit_ndcg(scores[r][mask[r]].numpy(), positive[r][mask[r]].numpy(),
                                   int(positive[r].sum())) for r in range(4)])
        self.assertEqual(valid, 4)
        self.assertLess(abs(1-loss.item()-exact), 1e-3)

    def test_approx_ndcg_gradient_is_finite_with_padding(self):
        scores, mask, positive = batch(1)
        scores.requires_grad_(True)
        loss, _ = approx_ndcg_loss(scores, mask, positive, torch.zeros((), dtype=torch.float64), None)
        loss.backward()
        self.assertTrue(torch.isfinite(scores.grad).all())

    def test_topk_hard_equals_listwise_when_k_covers_all_and_queries_are_easy(self):
        scores, mask, positive = batch(2)
        anchor = scores+positive.to(torch.float64)*10  # anchor puts a positive at top-1 everywhere → no hard queries
        log_tau = torch.tensor(-1., dtype=torch.float64)
        ours, n = topk_hard_loss(scores, mask, positive, log_tau, anchor, k=1000)
        reference, m = listwise_loss(scores, mask, positive, log_tau)
        self.assertEqual(n, m)
        self.assertAlmostEqual(ours.item(), reference.item(), places=12)


class PoolTests(unittest.TestCase):
    def test_lse_pool_limits(self):
        page = torch.tensor([[0.3, 0.7, 0.7, 0.2, 0.]], dtype=torch.float64)
        units = torch.tensor([[0, 1, 1, 2, 3]])
        self.assertTrue(torch.allclose(lse_pool(page, units, 4, tau=1e-6)[:, :3], max_pool(page, units, 4)[:, :3]))
        pooled = lse_pool(page, units, 4)
        self.assertAlmostEqual(pooled[0, 1].item(), 0.7+0.02*np.log(2), places=12)
        self.assertAlmostEqual(pooled[0, 0].item(), 0.3, places=12)


class F3ExperimentTests(unittest.TestCase):
    def test_all_variants_run_cross_validation(self):
        queries = synthetic(count=12)
        for name in ('f3_approxndcg', 'f3_topk_hard', 'f3_lse_pool'):
            result = run_experiment(queries, load_variant(name), folds=2, recipe={'epochs': 2, 'average_from': 1},
                                    log=lambda *_: None)
            self.assertEqual(set(result['per_query']['qpaf']), {q.query_id for q in queries})


if __name__ == '__main__':
    unittest.main()
