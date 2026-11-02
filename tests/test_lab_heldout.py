"""F9 held-out pieces that run before the sealed opening, on synthetic records only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np  # noqa: E402

from qpaf.lab.data import make_query  # noqa: E402
from qpaf.lab.heldout import (ROWS, label_free_query, label_free_units_query, predictions_bytes,  # noqa: E402
                              ranking_metrics, rankings_bytes, read_predictions, read_rankings, recall_at, top_units)
from qpaf.lab.model import unit_max, unit_ndcg  # noqa: E402
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


class DocumentRankingTests(unittest.TestCase):
    """ViMDoc seals top-10 document lists; they must score exactly like the lab on the full page scores."""

    def setUp(self):
        rng = np.random.default_rng(3)
        self.cases = []
        for n in range(40):
            documents = [f'd{n}x{j}' for j in range(int(rng.integers(3, 25)))]
            pages = [f'{d}_{k}' for d in documents for k in range(int(rng.integers(1, 5)))]
            doc_of = {p: p.rsplit('_', 1)[0] for p in pages}
            raw = rng.normal(size=(len(pages), 3))
            relevant = set(rng.choice(documents, size=int(rng.integers(1, 3)), replace=False)) | \
                ({'outside'} if n % 3 == 0 else set())
            labeled = make_query(f'q{n}', 'text', pages, raw, doc_of, relevant, len(relevant))
            free = label_free_units_query(f'q{n}', 'text', pages, raw, doc_of)
            scores = np.round(rng.random(len(pages)), 1)  # coarse values force ties between documents
            self.cases.append((labeled, free, scores, relevant))

    def test_label_free_query_matches_the_labeled_one(self):
        for labeled, free, _, _ in self.cases:
            self.assertEqual((free.page_ids, free.unit_ids), (labeled.page_ids, labeled.unit_ids))
            np.testing.assert_array_equal(free.units, labeled.units)
            np.testing.assert_array_equal(free.raw, labeled.raw)
            self.assertFalse(free.positive.any())

    def test_top_ten_lists_give_the_lab_metrics(self):
        for labeled, free, scores, relevant in self.cases:
            got = ranking_metrics([u for u, _ in top_units(free, scores)], relevant, len(relevant))
            unit = unit_max(scores, labeled.units, len(labeled.unit_ids))
            self.assertEqual(got['ndcg10'], unit_ndcg(unit, labeled.positive, labeled.relevant_total))
            self.assertEqual(got['recall1'], recall_at(labeled, scores, 1))
            self.assertEqual(got['recall3'], recall_at(labeled, scores, 3))

    def test_ranking_file_round_trips_and_is_deterministic(self):
        queries = [free for _, free, _, _ in self.cases]
        rankings = {name: [top_units(q, s+i) for q, (_, _, s, _) in zip(queries, self.cases)]
                    for i, name in enumerate(ROWS)}
        data = rankings_bytes(queries, rankings)
        self.assertEqual(data, rankings_bytes(queries, rankings))
        back = read_rankings(data, queries)
        for name in ROWS:
            self.assertEqual(back[name], [[u for u, _ in r] for r in rankings[name]])
        with self.assertRaises(ValueError):
            read_rankings(data, queries[::-1])


if __name__ == '__main__':
    unittest.main()
