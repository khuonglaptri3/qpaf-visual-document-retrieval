"""A005 ViMDoc Stage 2-3 helpers on a synthetic score cache."""
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from qpaf.a005.losses import LOG_TAU_BOUNDS, golden_minimum  # noqa: E402
from qpaf.a005.model import document_metrics  # noqa: E402
from qpaf.a005.vimdoc import baselines, doc_profile_loss, load_records, normalized, rrf, static_grid  # noqa: E402


def cache(queries=12, pages=30, seed=0, good_channel=2):
    """Relevant document's pages score high on `good_channel`; documents have three pages."""
    rng, rows, qrels = np.random.default_rng(seed), [], {}
    for q in range(queries):
        target = int(rng.integers(pages // 3))
        qrels[f'q{q}'] = [f'd{target}']
        for p in range(pages):
            score = rng.random(3)*0.7
            if p // 3 == target:
                score[good_channel] = 0.9+0.1*rng.random()
            rows.append({'query_id': f'q{q}', 'page_id': f'd{p // 3}_{p % 3}.png', 'document_id': f'd{p // 3}',
                         'bm25': score[0]*10, 'dense': score[1], 'visual': score[2]*20})
    return pd.DataFrame(rows), qrels


class VimdocTests(unittest.TestCase):
    def setUp(self):
        self.frame, self.qrels = cache()
        self.texts = {q: 'synthetic query' for q in self.qrels}
        self.records = load_records(self.frame, self.texts, self.qrels, list(self.qrels))

    def test_records_hold_no_page_labels_and_sorted_pages(self):
        record = self.records[0]
        self.assertEqual(set(record.labels), {0})
        self.assertEqual(list(record.page_ids), sorted(record.page_ids))
        self.assertEqual(record.relevant_total, 1)
        with self.assertRaises(ValueError):
            load_records(self.frame, self.texts, self.qrels, ['missing'])

    def test_normalization_and_rrf(self):
        norm = normalized(self.records[0])
        self.assertTrue(np.allclose(norm.min(axis=0), 0) and np.allclose(norm.max(axis=0), 1))
        self.assertLessEqual(rrf(self.records[0]).max(), 3/61)
        self.assertEqual(len(rrf(self.records[0])), len(self.records[0].page_ids))

    def test_static_grid_finds_the_informative_channel(self):
        rows, best = static_grid(self.records, self.qrels)
        self.assertEqual(len(rows), 66)
        self.assertEqual(best, [0.0, 0.0, 1.0])
        roster = baselines(self.records, self.qrels, best)
        self.assertEqual(roster['train_fitted_static']['ndcg_at_10'], roster['colqwen25']['ndcg_at_10'])
        self.assertGreater(roster['colqwen25']['ndcg_at_10'], roster['bm25']['ndcg_at_10'])

    def test_profile_loss_prefers_the_informative_channel(self):
        golden = lambda f: golden_minimum(f, *LOG_TAU_BOUNDS)  # noqa: E731
        (good, _), n = doc_profile_loss(self.records, self.qrels, [0., 0., 1.], golden)
        (bad, _), _ = doc_profile_loss(self.records, self.qrels, [1., 0., 0.], golden)
        self.assertEqual(n, len(self.records))
        self.assertLess(good, bad)

    def test_document_metric_matches_hand_value(self):
        m = document_metrics(['a_0.png', 'a_1.jpg', 'b_0.png'], [0.2, 0.9, 0.5], ['b'])
        self.assertAlmostEqual(m['ndcg_at_10'], 1/math.log2(3), places=12)


if __name__ == '__main__':
    unittest.main()
