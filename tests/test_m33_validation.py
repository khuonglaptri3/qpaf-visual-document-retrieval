"""Independent M3.3 metric and run-integrity checks."""
import math
import tempfile
import unittest
from pathlib import Path

from scripts.audit_m33_qarf import AuditError, calculate_validation, check_supervisor_markers


class IndependentMetricTests(unittest.TestCase):
    def setUp(self):
        self.ids = ['q1', 'q2']
        self.pages = {'q1': ['a', 'b', 'c'], 'q2': ['x', 'y']}
        self.qrels = {'q1': {'b': 1}, 'q2': {'x': 1, 'outside': 1}}
        self.predictions = [
            {'query_id': 'q1', 'page_ids': ['a', 'b', 'c'], 'scores': [0.5, 0.5, 0.1]},
            {'query_id': 'q2', 'page_ids': ['x', 'y'], 'scores': [2.0, 1.0]},
        ]

    def test_ties_use_page_id_and_recall_uses_all_qrels_positives(self):
        aggregate, rows = calculate_validation(
            self.predictions, self.qrels, self.ids, self.pages)
        self.assertAlmostEqual(rows[0]['ndcg_at_10'], 1 / math.log2(3))
        self.assertEqual(rows[0]['recall_at_1'], 0)
        self.assertEqual(rows[0]['mrr_at_10'], 0.5)
        self.assertEqual(rows[1]['relevant_total'], 2)
        self.assertEqual(rows[1]['recall_at_1'], 0.5)
        self.assertEqual(rows[1]['recall_at_3'], 0.5)
        self.assertAlmostEqual(
            aggregate['ndcg_at_10'],
            (1 / math.log2(3) + 1 / (1 + 1 / math.log2(3))) / 2)

    def test_tampered_or_incomplete_predictions_are_rejected(self):
        for bad in (
            self.predictions[:1],
            [self.predictions[0], self.predictions[0]],
            [{**self.predictions[0], 'page_ids': ['b', 'a', 'c']}, self.predictions[1]],
            [{**self.predictions[0], 'scores': [float('nan'), 0.5, 0.1]}, self.predictions[1]],
        ):
            with self.subTest(bad=bad), self.assertRaises(AuditError):
                calculate_validation(bad, self.qrels, self.ids, self.pages)


class SupervisorMarkerTests(unittest.TestCase):
    def test_missing_or_conflicting_markers_reject_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / '_ATTEMPTED.json').write_text('{"authorization_sha256":"pin"}')
            (run / '_SUCCESS.json').write_text('{"authorization_sha256":"pin","exit_code":0}')
            (run / 'supervisor.log').write_text('supervised')
            check_supervisor_markers(run, 'pin')
            (run / '_FAILED.json').write_text('{}')
            with self.assertRaises(AuditError):
                check_supervisor_markers(run, 'pin')
            (run / '_FAILED.json').unlink()
            (run / 'supervisor.log').unlink()
            with self.assertRaises(AuditError):
                check_supervisor_markers(run, 'pin')


if __name__ == '__main__':
    unittest.main()
