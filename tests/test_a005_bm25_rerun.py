"""BM25 re-run exchange: rebuilt rows give the same candidates as the full matrix, ties included."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import numpy as np  # noqa: E402

from qpaf.a005.bm25_rerun import channel_tops, rebuild_rows, union_scores  # noqa: E402
from qpaf.a005.candidates import query_candidates  # noqa: E402


class Bm25RerunTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(7)
        self.total = 900
        # Many exact zeros and repeated values, as BM25 rows have, to exercise the tie rule.
        self.bm25 = np.round(rng.random((6, self.total))*3, 1)*(rng.random((6, self.total)) > 0.6)
        self.dense = rng.random((6, self.total))
        self.visual = np.round(rng.random((6, self.total)), 2)

    def test_rebuilt_rows_reproduce_union_raw_and_normalized(self):
        tops = {name: channel_tops(m) for name, m in (('bm25', self.bm25), ('dense', self.dense),
                                                      ('visual', self.visual))}
        union, values = union_scores(self.bm25, tops['bm25'], tops['dense'], tops['visual'])
        rebuilt = rebuild_rows(self.total, tops['bm25'], union, values, tops['dense'], tops['visual'])
        for q in range(len(self.bm25)):
            original = query_candidates({'bm25': self.bm25[q], 'dense': self.dense[q], 'visual': self.visual[q]})
            again = query_candidates({'bm25': rebuilt[q], 'dense': self.dense[q], 'visual': self.visual[q]})
            for a, b in zip(original, again):
                self.assertTrue(np.array_equal(a, b))

    def test_a_union_from_other_tops_is_refused(self):
        tops = [channel_tops(m) for m in (self.bm25, self.dense, self.visual)]
        union, values = union_scores(self.bm25, *tops)
        shifted = tops[1].copy()
        shifted[0, 0] = (shifted[0, 0]+1) % self.total
        with self.assertRaisesRegex(ValueError, 'remote union differs'):
            rebuild_rows(self.total, tops[0], union, values, shifted, tops[2])


if __name__ == '__main__':
    unittest.main()
