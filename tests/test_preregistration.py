import unittest
from pathlib import Path

import yaml

from oracle_study.constants import PREREGISTERED_THRESHOLDS, SEED


class PreregistrationTest(unittest.TestCase):
    def test_config_and_runtime_thresholds_match(self):
        root = Path(__file__).resolve().parents[1]
        config = yaml.safe_load((root / "configs" / "preregistered.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["seed"], SEED)
        qpaf = PREREGISTERED_THRESHOLDS["qpaf"]
        self.assertEqual(config["qpaf"]["discovery_mean_gain"], qpaf["discovery_mean_delta_ndcg10_min"])
        self.assertEqual(config["qpaf"]["confirmation_mean_gain"], qpaf["confirmation_mean_delta_ndcg10_min"])
        self.assertEqual(config["qpaf"]["confirmation_fraction_gain_ge_005"], qpaf["confirmation_fraction_gain_ge_005_min"])
        budget = PREREGISTERED_THRESHOLDS["budget_aware"]
        self.assertEqual(config["budget_aware"]["quality_absolute_tolerance"], budget["quality_absolute_tolerance"])
        self.assertEqual(config["budget_aware"]["beneficial_gain"], budget["beneficial_gain_exclusive"])
        self.assertEqual(config["budget_aware"]["maximum_b_star_go_percent"], budget["b_star_percent_max"])
        self.assertEqual(config["budget_aware"]["minimum_retention"], budget["retention_ci95_lower_min"])


if __name__ == "__main__":
    unittest.main()
