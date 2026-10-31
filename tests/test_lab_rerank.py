"""F5 reranker fusion on synthetic inputs only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np  # noqa: E402

from qpaf.lab.rerank import fold_anchors, fuse, minmax, top_pages, unit_score  # noqa: E402
from tests.test_lab import ANCHOR, synthetic  # noqa: E402


class RerankFusionTests(unittest.TestCase):
    def test_lambda_zero_reproduces_static(self):
        for q in synthetic(12):
            static = unit_score(q, minmax(q.raw)@np.asarray(ANCHOR))
            rerank = {i: float(-i) for i in range(len(q.page_ids))}
            self.assertEqual(unit_score(q, fuse(q, ANCHOR, rerank, 0., k=5)), static)

    def test_top_pages_stay_above_the_rest(self):
        q = synthetic(1)[0]
        top = top_pages(q, ANCHOR, k=4)
        scores = fuse(q, ANCHOR, {i: float(i) for i in range(len(q.page_ids))}, 1., k=4)
        rest = np.setdiff1d(np.arange(len(q.page_ids)), top)
        self.assertGreater(scores[top].min(), scores[rest].max())
        self.assertEqual(int(np.argmax(scores)), int(max(top)))  # λ = 1 orders the top by the reranker alone

    def test_fold_anchors_are_grid_points(self):
        anchors = fold_anchors(synthetic(30), folds=3)
        self.assertEqual(len(anchors), 3)
        for anchor in anchors:
            self.assertAlmostEqual(sum(anchor), 1.)


if __name__ == '__main__':
    unittest.main()
