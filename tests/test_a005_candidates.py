"""The vectorized candidate union matches the frozen ViMDoc reference helpers exactly, ties included."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from qpaf.a005.candidates import CHANNELS, document_recall, query_candidates, top_k_indices  # noqa: E402
from scripts.prepare_vimdoc_m3 import normalized_union  # noqa: E402


def universe(n, seed, ties=False):
    rng = np.random.default_rng(seed)
    ids = sorted(f'doc{i // 7}_{i % 7}' for i in range(n))
    scores = {c: rng.random(n) for c in CHANNELS}
    if ties:
        scores['bm25'] = np.round(scores['bm25']*5)/5
        scores['visual'][:] = 0.25
    return ids, scores


class CandidateTests(unittest.TestCase):
    def test_matches_reference_with_and_without_ties(self):
        for seed, ties, k in ((1, False, 20), (2, True, 20), (3, True, 50), (4, False, 400)):
            ids, scores = universe(300, seed, ties)
            union, raw, normalized = query_candidates(scores, top_k=k)
            reference = normalized_union({c: dict(zip(ids, scores[c].tolist())) for c in CHANNELS}, top_k=k)
            self.assertEqual([ids[i] for i in union], [row['page_id'] for row in reference])
            self.assertTrue(np.array_equal(normalized, np.array([row['scores'] for row in reference])))
            self.assertTrue(np.array_equal(raw[:, 0], scores['bm25'][union]))

    def test_cutoff_ties_take_the_smaller_index(self):
        self.assertEqual(top_k_indices([0.5, 0.9, 0.5, 0.5, 0.1], 3).tolist(), [0, 1, 2])

    def test_constant_channel_normalizes_to_zero_and_union_is_bounded(self):
        _, scores = universe(1000, 5, ties=True)
        union, _, normalized = query_candidates(scores)
        self.assertLessEqual(union.size, 600)
        self.assertTrue((normalized[:, 2] == 0).all())
        self.assertAlmostEqual(normalized[:, 0].max(), 1.)

    def test_rejects_bad_inputs(self):
        _, scores = universe(50, 6)
        with self.assertRaises(ValueError):
            query_candidates({'visual': scores['visual'], 'dense': scores['dense'], 'bm25': scores['bm25']})
        with self.assertRaises(ValueError):
            top_k_indices([0.1, float('nan')], 1)

    def test_document_recall(self):
        recall = document_recall(['a_1', 'b_2.png', 'b_3'], ['b', 'c'], lambda p: p.rpartition('_')[0])
        self.assertEqual(recall, 0.5)


if __name__ == '__main__':
    unittest.main()
