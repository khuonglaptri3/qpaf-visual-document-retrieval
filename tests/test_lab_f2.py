"""F2 monotone calibrators (docs/feature_lab/F2)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import torch  # noqa: E402

from qpaf.lab.train import run_experiment  # noqa: E402
from qpaf.lab.variants import load_variant  # noqa: E402
from qpaf.lab.variants.f2_pwl import MonotonePWL  # noqa: E402
from qpaf.lab.variants.f2_pwl_rrf import PWLRankBlend, rrf_channel  # noqa: E402
from test_lab import synthetic  # noqa: E402


class CalibratorTests(unittest.TestCase):
    def setUp(self):
        generator = torch.Generator().manual_seed(0)
        self.scores = torch.rand(4, 7, 3, generator=generator, dtype=torch.float64)
        self.mask = torch.ones(4, 7, dtype=torch.bool)
        self.mask[2, 5:] = False

    def test_identity_at_initialization(self):
        for module in (MonotonePWL(), PWLRankBlend()):
            self.assertLess((module(self.scores, self.mask)-self.scores).abs().max().item(), 1e-12)

    def test_random_logits_stay_monotone_with_fixed_ends(self):
        module = MonotonePWL()
        with torch.no_grad():
            module.logits.copy_(torch.randn(3, 8, generator=torch.Generator().manual_seed(1), dtype=torch.float64)*2)
        grid = torch.linspace(0, 1, 201, dtype=torch.float64).view(1, -1, 1).expand(1, 201, 3)
        g = module(grid, torch.ones(1, 201, dtype=torch.bool))[0]
        self.assertTrue((g[1:]-g[:-1] >= -1e-15).all())
        self.assertLess(g[0].abs().max().item(), 1e-15)
        self.assertLess((g[-1]-1).abs().max().item(), 1e-12)

    def test_rrf_channel_by_hand(self):
        scores = torch.tensor([[[0.2, 0.9, 0.5], [0.8, 0.9, 0.1], [0.5, 0.1, 0.7], [9., 9., 9.]]], dtype=torch.float64)
        mask = torch.tensor([[True, True, True, False]])
        u = rrf_channel(scores, mask)
        rank = torch.tensor([[3, 1, 2], [1, 2, 3], [2, 3, 1]], dtype=torch.float64)  # channel-1 tie → smaller index
        self.assertTrue(torch.allclose(u[0, :3], 61/(60+rank)))
        self.assertEqual(u[0, 3].tolist(), [0., 0., 0.])
        self.assertEqual(u[0, :3].max().item(), 1.)


class F2ExperimentTests(unittest.TestCase):
    def test_both_variants_run_cross_validation(self):
        queries = synthetic(count=12)
        for name in ('f2_pwl', 'f2_pwl_rrf'):
            result = run_experiment(queries, load_variant(name), folds=2, recipe={'epochs': 2, 'average_from': 1},
                                    log=lambda *_: None)
            self.assertEqual(set(result['per_query']['qarf']), {q.query_id for q in queries})


if __name__ == '__main__':
    unittest.main()
