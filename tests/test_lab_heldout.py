"""F9 held-out pieces that run before the sealed opening, on synthetic records only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np  # noqa: E402

from qpaf.lab.data import make_query  # noqa: E402
from qpaf.lab.heldout import ROWS, label_free_query, predictions_bytes, read_predictions, recall_at  # noqa: E402
from qpaf.m24.dataset import QueryRecord  # noqa: E402

PAGES = ('doc_page_0010', 'Đoc_page_0001', 'doc_page_0002', 'abc_page_0001')


def record(query_id='q1'):
    raw = tuple((float(i), float(-i), i/10) for i in range(len(PAGES)))
    return QueryRecord(query_id, 'what is it?', PAGES, raw, (0,)*len(PAGES), 0)


class LabelFreeQueryTests(unittest.TestCase):
    def test_matches_the_labeled_query_except_labels(self):
        free = label_free_query(record())
        labeled = make_query('q1', 'what is it?', list(PAGES), record().raw_scores, {p: p for p in PAGES},
                             {'doc_page_0002'}, 1)
        self.assertEqual(free.page_ids, labeled.page_ids)
        np.testing.assert_array_equal(free.raw, labeled.raw)
        np.testing.assert_array_equal(free.units, labeled.units)
        self.assertEqual(free.unit_ids, labeled.unit_ids)
        self.assertFalse(free.positive.any())

    def test_recall_counts_relevant_units_in_the_top_k(self):
        q = make_query('q1', 'what is it?', list(PAGES), record().raw_scores, {p: p for p in PAGES},
                       {'doc_page_0002', 'abc_page_0001'}, 3)
        scores = np.zeros(len(q.page_ids))
        scores[q.page_ids.index('doc_page_0002')] = 1.
        self.assertAlmostEqual(recall_at(q, scores, 1), 1/3)
        self.assertAlmostEqual(recall_at(q, scores, 3), 2/3)  # ties go to the smaller index: abc_page_0001 first


class PredictionFileTests(unittest.TestCase):
    def test_bytes_are_deterministic_and_round_trip_exactly(self):
        queries = [label_free_query(record('q1')), label_free_query(record('q2'))]
        rng = np.random.default_rng(0)
        rows = {name: [rng.normal(size=len(q.page_ids)) for q in queries] for name in ROWS}
        data = predictions_bytes(queries, rows)
        self.assertEqual(data, predictions_bytes(queries, rows))
        back = read_predictions(data, queries)
        for name in ROWS:
            for a, b in zip(rows[name], back[name]):
                np.testing.assert_array_equal(a, b)

    def test_reading_refuses_other_queries(self):
        queries = [label_free_query(record('q1'))]
        data = predictions_bytes(queries, {name: [np.zeros(len(PAGES))] for name in ROWS})
        with self.assertRaises(ValueError):
            read_predictions(data, [label_free_query(record('q2'))])


if __name__ == '__main__':
    unittest.main()
