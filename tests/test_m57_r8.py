"""Checks for the frozen R8 query bootstrap calculations."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analyze_m57_r8', ROOT/'scripts/analyze_m57_r8.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class R8StatisticsTests(unittest.TestCase):
    def test_constant_paired_gain_has_fixed_ci_and_wins(self):
        samples = np.random.default_rng(20260820).integers(0, 172, size=(10_000, 172))
        result = module.statistics([0.125]*172, samples)
        self.assertAlmostEqual(result['mean_delta'], 0.125)
        self.assertAlmostEqual(result['ci95'][0], 0.125)
        self.assertAlmostEqual(result['ci95'][1], 0.125)
        self.assertEqual(result['wtl'], {'wins': 172, 'ties': 0, 'losses': 0})
        self.assertEqual(result['top_5pct_positive_gain_query_count'], 9)
        self.assertAlmostEqual(result['top_5pct_positive_gain_share'], 9/172)

    def test_nonfinite_delta_fails_closed(self):
        samples = np.zeros((1, 172), dtype=int)
        with self.assertRaisesRegex(ValueError, 'finiteness'):
            module.statistics([float('nan')]+[0.0]*171, samples)


if __name__ == '__main__':
    unittest.main()
