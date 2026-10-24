"""M4.6 train-only alignment probe: grid, rank correlation, preregistered gate, train-only reads."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m24.synthetic import make_fixture  # noqa: E402
from qpaf.m46 import probe  # noqa: E402


class GridTests(unittest.TestCase):
    def test_grid_has_66_simplex_points(self):
        grid = probe.grid_points()
        self.assertEqual(len(grid), 66)
        self.assertTrue(all(abs(sum(w)-1) <= 1e-12 and min(w) >= 0 for w in grid))
        self.assertEqual(grid[0], [0.0, 0.0, 1.0])
        self.assertEqual(grid[-1], [1.0, 0.0, 0.0])
        self.assertIn([0.0, 0.1, 0.9], grid)

    def test_spearman_with_ties(self):
        self.assertAlmostEqual(probe.spearman([1, 2, 2, 3], [1, 3, 2, 4]), 0.9486832980505139, places=12)
        self.assertAlmostEqual(probe.spearman([1, 2, 3], [3, 2, 1]), -1.0, places=12)


class GateTests(unittest.TestCase):
    def test_gate_thresholds(self):
        top = 0.86
        cases = [((-0.5, top-0.01, top), ('PASS', 'PASS', 'PASS')),
                 ((-0.49, top, top), ('FAIL', 'PASS', 'REVISION_GATE_FAILED')),
                 ((-0.9, top-0.0101, top), ('PASS', 'FAIL', 'REVISION_GATE_FAILED')),
                 ((0.5, 0.7, top), ('FAIL', 'FAIL', 'REVISION_GATE_FAILED'))]
        for args, (a, b, status) in cases:
            with self.subTest(args):
                result = probe.evaluate_gate(*args)
                self.assertEqual((result['G_A'], result['G_B'], result['status']), (a, b, status))

    def test_gate_from_rows_uses_the_named_loss(self):
        rows = [{'weights': [1.0, 0.0, 0.0], 'v1_loss': 0.1, 'v2_loss': 0.9, 'ndcg_at_10': 0.70},
                {'weights': [0.5, 0.0, 0.5], 'v1_loss': 0.2, 'v2_loss': 0.5, 'ndcg_at_10': 0.80},
                {'weights': [0.0, 0.0, 1.0], 'v1_loss': 0.3, 'v2_loss': 0.1, 'ndcg_at_10': 0.86}]
        v1, v2 = probe.gate(rows, 'v1_loss'), probe.gate(rows, 'v2_loss')
        self.assertEqual((v1['min_loss_weights'], v1['status']), ([1.0, 0.0, 0.0], 'REVISION_GATE_FAILED'))
        self.assertEqual((v2['min_loss_weights'], v2['status']), ([0.0, 0.0, 1.0], 'PASS'))
        self.assertAlmostEqual(v2['spearman'], -1.0, places=12)


class TrainOnlyTests(unittest.TestCase):
    def bundle(self, folder, *, leak_test=False):
        rows, queries, qrels, splits = make_fixture()
        root = Path(folder)
        (root/'inputs/splits').mkdir(parents=True)
        for role, name in (('train', 'train_ids.txt'), ('validation', 'val_ids.txt'), ('test', 'test_ids.txt')):
            (root/'inputs/splits'/name).write_text('\n'.join(splits[role])+'\n', encoding='utf8')
        keep = splits['train']+splits['validation']+(splits['test'] if leak_test else [])
        (root/'inputs/qrels_development.json').write_text(json.dumps({q: qrels[q] for q in keep}), encoding='utf8')
        (root/'inputs/queries.json').write_text(json.dumps(queries), encoding='utf8')
        return root, rows, splits

    def test_probe_reads_train_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root, rows, splits = self.bundle(folder)
            spy = mock.Mock(wraps=probe.build_records)
            with mock.patch.object(probe, 'read_score_rows', return_value=rows), \
                    mock.patch.object(probe, 'build_records', spy):
                records = probe.load_train(root)
            (args, kwargs), = spy.call_args_list
            self.assertEqual(args[4], ('train',))
            self.assertLessEqual(set(args[2]), set(splits['train']))
            self.assertEqual([r.query_id for r in records], splits['train'])

    def test_development_qrels_with_test_ids_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root, rows, _ = self.bundle(folder, leak_test=True)
            with mock.patch.object(probe, 'read_score_rows', return_value=rows), \
                    self.assertRaisesRegex(ValueError, 'test'):
                probe.load_train(root)


if __name__ == '__main__':
    unittest.main()
