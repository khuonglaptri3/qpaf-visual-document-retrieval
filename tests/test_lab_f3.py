"""F3 ranking losses and document pooling (docs/feature_lab/F3)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import torch  # noqa: E402

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


class LossTests(unittest.TestCase):
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
