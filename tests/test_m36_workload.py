"""A performance workload must count distinct IDs and disclose held-out access."""
import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class WorkloadTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('scripts.prepare_m36_gpu_review')
        except ModuleNotFoundError:
            self.fail('M3.6 workload preparation is not implemented')
        self.splits = {'train': [f't{i}' for i in range(799)],
                       'validation': [f'v{i}' for i in range(171)],
                       'test': [f'h{i}' for i in range(172)]}

    def test_warmup_and_measured_queries_are_disjoint_and_counts_are_honest(self):
        result = self.api.make_workload(self.splits)
        warmup = {r['query_id'] for r in result['warmup']}
        measured = {r['query_id'] for r in result['measured']}
        self.assertEqual(len(warmup), 20)
        self.assertEqual(len(measured), 1122)
        self.assertFalse(warmup & measured)
        self.assertEqual(len(warmup | measured), 1142)
        self.assertEqual(result['held_out_query_ids_included'], 172)
        self.assertFalse(result['test_label_access_permitted'])
        self.assertEqual(result['status'], 'PROPOSED_REQUIRES_REVIEW')

    def test_selection_ignores_input_order_and_uses_no_labels(self):
        reverse = {role: list(reversed(ids)) for role, ids in self.splits.items()}
        self.assertEqual(self.api.make_workload(self.splits), self.api.make_workload(reverse))

    def test_development_only_is_insufficient_and_repeated_ids_cannot_inflate_it(self):
        insufficient = {**self.splits, 'test': []}
        with self.assertRaisesRegex(ValueError, '1000'):
            self.api.make_workload(insufficient)
        duplicated = {**self.splits, 'test': self.splits['train']}
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.api.make_workload(duplicated)


if __name__ == '__main__':
    unittest.main()
