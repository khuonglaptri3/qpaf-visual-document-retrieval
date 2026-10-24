"""M4.6 A004 loss: ΔnDCG@10 pair weights, metric tie rule, masking and refusals."""
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import torch  # noqa: E402

from qpaf.m46.losses import discounts, lambda_pairwise_logistic_loss  # noqa: E402

D = [1/math.log2(p+2) for p in range(4)]  # positions 0..3


def softplus(x):
    return math.log1p(math.exp(x))


def single(scores, labels, page_ids=None):
    s = torch.tensor([scores], dtype=torch.float64)
    y = torch.tensor([labels], dtype=torch.float64)
    ids = page_ids or [f'p{i:02d}' for i in range(len(scores))]
    return lambda_pairwise_logistic_loss(s, y, torch.ones_like(s, dtype=torch.bool), [ids])


class WeightTests(unittest.TestCase):
    def test_hand_computed_loss(self):
        s = [0.9, 0.8, 0.1, 0.0]
        w = {(1, 0): abs(D[1]-D[0]), (1, 3): abs(D[1]-D[3]),
             (2, 0): abs(D[2]-D[0]), (2, 3): abs(D[2]-D[3])}
        expected = sum(v*softplus(s[j]-s[i]) for (i, j), v in w.items())/sum(w.values())
        out = single(s, [0., 1., 1., 0.], ['a', 'b', 'c', 'd'])
        self.assertAlmostEqual(out.loss.item(), expected, places=12)
        self.assertEqual((out.valid_queries, out.skipped_queries, out.pairs), (1, 0, 4))

    def test_ties_follow_rank(self):
        self.assertEqual(discounts(['b', 'a', 'c'], [0.5, 0.5, 0.1]), [D[1], D[0], D[2]])

    def test_positions_past_cutoff_have_zero_discount(self):
        values = discounts([f'p{i:02d}' for i in range(12)], [1-i/12 for i in range(12)])
        self.assertEqual(values[10:], [0.0, 0.0])
        self.assertEqual(values[0], 1.0)

    def test_cutoff_drops_pairs_past_position_10(self):
        # Positives at positions 0 and 11; the (11, 10) pair must get weight 0.
        labels = [1.]+[0.]*10+[1.]
        s = [1-i/12 for i in range(12)]

        def expected(cutoff):
            d = [1/math.log2(p+2) if p < cutoff else 0. for p in range(12)]
            pairs = [(i, j) for i in (0, 11) for j in range(1, 11)]
            w = [abs(d[i]-d[j]) for i, j in pairs]
            return sum(v*softplus(s[j]-s[i]) for v, (i, j) in zip(w, pairs))/sum(w)
        loss = single(s, labels).loss.item()
        self.assertAlmostEqual(loss, expected(10), places=12)
        self.assertNotAlmostEqual(loss, expected(12), places=6)


class MaskTests(unittest.TestCase):
    def test_padding_gets_no_weight_or_gradient(self):
        a = ([0.9, 0.2, 0.5], [1., 0., 0.])
        b = ([0.1, 0.7, 0.3, 0.8, 0.4], [0., 1., 0., 0., 1.])
        s = torch.tensor([a[0]+[0.6, 0.6], b[0]], dtype=torch.float64, requires_grad=True)
        y = torch.tensor([a[1]+[1., 0.], b[1]], dtype=torch.float64)
        mask = torch.tensor([[True]*3+[False]*2, [True]*5])
        ids = [['x0', 'x1', 'x2', '', ''], [f'y{i}' for i in range(5)]]
        out = lambda_pairwise_logistic_loss(s, y, mask, ids)
        out.loss.backward()
        self.assertTrue(torch.equal(s.grad[0, 3:], torch.zeros(2, dtype=torch.float64)))
        expected = (single(*a).loss.item()+single(*b).loss.item())/2
        self.assertAlmostEqual(out.loss.item(), expected, places=12)
        self.assertEqual(out.valid_queries, 2)

    def test_short_query_has_finite_loss(self):
        out = single([0.3, 0.6], [1., 0.])
        self.assertTrue(math.isfinite(out.loss.item()))
        self.assertAlmostEqual(out.loss.item(), softplus(0.6-0.3), places=12)

    def test_query_without_both_classes_is_skipped(self):
        s = torch.tensor([[0.9, 0.1], [0.4, 0.2]], dtype=torch.float64)
        y = torch.tensor([[1., 0.], [1., 1.]], dtype=torch.float64)
        out = lambda_pairwise_logistic_loss(s, y, torch.ones_like(s, dtype=torch.bool),
                                            [['a', 'b'], ['c', 'd']])
        self.assertEqual((out.valid_queries, out.skipped_queries), (1, 1))

    def test_gradcheck(self):
        s = torch.tensor([[0.91, 0.52, 0.33, 0.14, 0.75]], dtype=torch.float64, requires_grad=True)
        y = torch.tensor([[0., 1., 1., 0., 0.]], dtype=torch.float64)
        mask = torch.ones_like(y, dtype=torch.bool)
        ids = [[f'p{i}' for i in range(5)]]
        self.assertTrue(torch.autograd.gradcheck(
            lambda x: lambda_pairwise_logistic_loss(x, y, mask, ids).loss, (s,), eps=1e-6, atol=1e-8))


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.s = torch.tensor([[0.9, 0.1]], dtype=torch.float64)
        self.y = torch.tensor([[1., 0.]], dtype=torch.float64)
        self.m = torch.ones_like(self.s, dtype=torch.bool)
        self.ids = [['a', 'b']]

    def test_refusals(self):
        cases = {
            'shape mismatch': (self.s, self.y[:, :1], self.m, self.ids, 10),
            'non-binary labels': (self.s, torch.tensor([[2., 0.]], dtype=torch.float64), self.m, self.ids, 10),
            'non-finite score': (torch.tensor([[math.nan, 0.1]], dtype=torch.float64), self.y, self.m, self.ids, 10),
            'page ids not aligned': (self.s, self.y, self.m, [['a']], 10),
            'cutoff below 1': (self.s, self.y, self.m, self.ids, 0),
            'no learnable query': (self.s, torch.tensor([[1., 1.]], dtype=torch.float64), self.m, self.ids, 10),
        }
        for name, (s, y, m, ids, cutoff) in cases.items():
            with self.subTest(name), self.assertRaises(ValueError):
                lambda_pairwise_logistic_loss(s, y, m, ids, cutoff=cutoff)


if __name__ == '__main__':
    unittest.main()
