"""A005 listwise loss, temperature profile and Stage 0 authorization guard, on synthetic inputs only."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import torch  # noqa: E402

from qpaf.a005.losses import LOG_TAU_BOUNDS, golden_minimum, listwise_loss  # noqa: E402
from qpaf.a005.probe import AUTHORIZATION, ProbeError, SOURCES, check_authorization  # noqa: E402
from qpaf.m43.freeze import sha  # noqa: E402


def t(rows, dtype=torch.float64):
    return torch.tensor(rows, dtype=dtype)


class ListwiseLossTests(unittest.TestCase):
    def test_matches_hand_computation_with_padding_and_two_positives(self):
        scores = t([[0.9, 0.5, 0.1, 0.7]])
        labels = torch.tensor([[1, 0, 1, 0]])
        mask = torch.tensor([[True, True, True, False]])
        loss, valid = listwise_loss(scores, labels, mask, math.log(0.5))
        z = math.exp(1.8)+math.exp(1.0)+math.exp(0.2)
        self.assertEqual(valid, 1)
        self.assertAlmostEqual(loss.item(), -math.log((math.exp(1.8)+math.exp(0.2))/z), places=12)

    def test_queries_without_both_classes_are_skipped(self):
        scores = t([[0.9, 0.1], [0.4, 0.6], [0.2, 0.3]])
        labels = torch.tensor([[1, 0], [0, 0], [1, 1]])
        mask = torch.ones(3, 2, dtype=torch.bool)
        _, valid = listwise_loss(scores, labels, mask, 0.)
        self.assertEqual(valid, 1)

    def test_lower_temperature_rewards_a_correct_ranking(self):
        scores, labels, mask = t([[0.9, 0.1, 0.2]]), torch.tensor([[1, 0, 0]]), torch.ones(1, 3, dtype=torch.bool)
        sharp, _ = listwise_loss(scores, labels, mask, math.log(1e-2))
        flat, _ = listwise_loss(scores, labels, mask, 0.)
        self.assertLess(sharp.item(), flat.item())


class GoldenMinimumTests(unittest.TestCase):
    def test_interior_minimum(self):
        value, x = golden_minimum(lambda v: (v+2.)**2, *LOG_TAU_BOUNDS)
        self.assertAlmostEqual(x, -2., places=6)
        self.assertAlmostEqual(value, 0., places=10)

    def test_boundary_minimum_is_kept(self):
        value, x = golden_minimum(lambda v: v, *LOG_TAU_BOUNDS)
        self.assertEqual(x, LOG_TAU_BOUNDS[0])
        self.assertEqual(value, LOG_TAU_BOUNDS[0])

    def test_deterministic(self):
        f = lambda v: math.cos(v)+0.1*v*v  # noqa: E731
        self.assertEqual(golden_minimum(f, *LOG_TAU_BOUNDS), golden_minimum(f, *LOG_TAU_BOUNDS))


class AuthorizationGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for relative in SOURCES:
            (self.root/relative).parent.mkdir(parents=True, exist_ok=True)
            (self.root/relative).write_text(relative, encoding='utf-8')
        self.pins = {relative: sha(self.root/relative) for relative in SOURCES}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, **record):
        path = self.root/AUTHORIZATION
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record), encoding='utf-8')

    def test_missing_or_pending_authorization_refuses(self):
        with self.assertRaisesRegex(ProbeError, 'authorization missing'):
            check_authorization(self.root)
        self.write(status='PENDING_RESEARCH_LEAD_APPROVAL', source_files_sha256=self.pins)
        with self.assertRaisesRegex(ProbeError, 'not APPROVED'):
            check_authorization(self.root)

    def test_changed_source_refuses(self):
        self.write(status='APPROVED', source_files_sha256=self.pins)
        self.assertEqual(len(check_authorization(self.root)), 64)
        (self.root/SOURCES[2]).write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ProbeError, 'source differs'):
            check_authorization(self.root)

    def test_unpinned_source_refuses(self):
        partial = dict(list(self.pins.items())[:-1])
        self.write(status='APPROVED', source_files_sha256=partial)
        with self.assertRaisesRegex(ProbeError, 'does not pin every source'):
            check_authorization(self.root)


if __name__ == '__main__':
    unittest.main()
