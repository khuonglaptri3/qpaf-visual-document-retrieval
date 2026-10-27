"""Large restricted-function results travel through verified stdout chunks."""
import copy
import importlib
import json
from pathlib import Path
import pickle
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ResultTransportTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('scripts.m55_gpu_transport')
        except ModuleNotFoundError:
            self.fail('restricted result transport is missing')

    def test_full_payload_round_trips_with_small_metadata_and_bounded_log_lines(self):
        result = {'status': 'COMPLETED', 'methods': ['QARF', 'QPAF'],
                  'timings': [{'q': i, 'ms': i/13.} for i in range(10000)]}
        meta, lines = self.api.encode_result(result)
        self.assertLess(len(pickle.dumps(meta)), 8192)
        self.assertTrue(all(len(line.encode('utf-8')) <= 3100 for line in lines))
        self.assertEqual(self.api.decode_result(meta, ['unrelated progress', *lines]), result)
        self.assertGreater(meta['uncompressed_bytes'], 8192)

    def test_missing_conflicting_corrupt_or_wrong_hash_chunks_are_refused(self):
        meta, lines = self.api.encode_result({'status': 'COMPLETED', 'rows': list(range(10000))})
        bad_meta = copy.deepcopy(meta)
        bad_meta['sha256'] = '0'*64
        for header, rows in ((meta, lines[:-1]), (bad_meta, lines),
                             (meta, [*lines, lines[0][:-1]+'!']),
                             (meta, [lines[0][:-1]+'!', *lines[1:]])):
            with self.subTest(size=len(rows)), self.assertRaises(ValueError):
                self.api.decode_result(header, rows)
        with self.assertRaises(ValueError):
            self.api.encode_result({'bad': float('nan')})


if __name__ == '__main__':
    unittest.main()
