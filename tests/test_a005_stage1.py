"""A005 Stage 1 helpers on synthetic data: sharding round-trip, qrels split, coverage."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np  # noqa: E402

from qpaf.a005.stage1 import (assemble_channel, coverage, shard_pages, shard_positions,  # noqa: E402
                              split_qrels, stem_document)


class ShardTests(unittest.TestCase):
    def test_shards_partition_and_reassemble_exactly(self):
        total, shards = 23, 4
        pages = [f'p{i:02d}' for i in range(total)]
        parts = [shard_pages(pages, shards, s) for s in range(shards)]
        self.assertEqual(sorted(p for part in parts for p in part), pages)
        full = np.random.default_rng(0).random((5, total))
        blocks = [full[:, shard_positions(total, shards, s)] for s in range(shards)]
        self.assertTrue(np.array_equal(assemble_channel(total, shards, blocks), full))

    def test_bad_block_shape_or_nan_refuses(self):
        blocks = [np.zeros((2, 3)), np.zeros((2, 2))]
        with self.assertRaises(ValueError):
            assemble_channel(5, 2, [np.zeros((2, 2)), np.zeros((2, 2))])
        blocks[0][0, 0] = np.nan
        with self.assertRaises(ValueError):
            assemble_channel(5, 2, blocks)


class QrelsTests(unittest.TestCase):
    def test_split_maps_page_stems_to_documents(self):
        rows = [('1', ['docA_3', 'docA_7']), ('2', ['x_y_0', 'docB_1']), ('3', ['docC_0'])]
        out = split_qrels(rows, {'train': ['1'], 'validation': ['2'], 'confirmation': ['3']})
        self.assertEqual(out['train'], {'1': ['docA']})
        self.assertEqual(out['validation'], {'2': ['docB', 'x_y']})

    def test_unknown_query_or_missing_coverage_refuses(self):
        with self.assertRaises(ValueError):
            split_qrels([('9', ['a_0'])], {'train': ['1']})
        with self.assertRaises(ValueError):
            split_qrels([('1', ['a_0'])], {'train': ['1', '2']})
        with self.assertRaises(ValueError):
            stem_document('nounderscore')


class CoverageTests(unittest.TestCase):
    def test_macro_recall_and_missing_queries(self):
        page_ids = ['a_0.png', 'a_1.png', 'b_0.jpg', 'c_0.png']
        docs = {p: p.rpartition('_')[0] for p in page_ids}
        result = coverage({'q1': [0, 2], 'q2': [3]}, page_ids, docs, {'q1': ['a', 'b'], 'q2': ['a']})
        self.assertEqual(result['macro_document_recall'], 0.5)
        self.assertEqual(result['queries_without_positive'], 1)
        self.assertFalse(result['pass'])


if __name__ == '__main__':
    unittest.main()
