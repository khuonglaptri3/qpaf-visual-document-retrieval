"""ID-only M4.1 seal boundaries; no qrels or query text are used."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.seal_m41_confirmation import build, hash_order, ids_bytes, split_ids


class ConfirmationSealTests(unittest.TestCase):
    def test_frozen_hash_split_and_complement(self):
        ids = [f'q{i:05d}' for i in range(10904)]
        sample = hash_order(ids, '20260820')[:2000]
        groups = split_ids(list(reversed(ids)), sample)
        self.assertEqual([len(groups[key]) for key in ('train', 'validation', 'confirmation')],
                         [1600, 400, 8904])
        self.assertEqual(groups['development'], sample)
        self.assertEqual(groups['confirmation'], hash_order(ids, '20260820')[2000:])
        self.assertEqual(groups['train'], hash_order(sample, 'vimdoc_m3_local_v1:dev_split:20260820')[:1600])
        self.assertEqual(len(set(groups['train'] + groups['validation'] + groups['confirmation'])), 10904)
        with self.assertRaises(ValueError):
            split_ids(ids, list(reversed(sample)))

    def test_serialization_and_duplicate_rejection(self):
        self.assertEqual(ids_bytes(['b', 'a']), b'b\na\n')
        for ids in (['a', 'a'], ['a\nb'], ['']):
            with self.assertRaises(ValueError):
                ids_bytes(ids)

    def test_wrong_source_hash_rejected_before_parquet_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fake.parquet'
            path.write_bytes(b'not the pinned ViMDoc source')
            self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                '7ccac6c8715cc338c041e9276583b9dbd79a818131a9b13a5abf4b9ced73bcc0')
            with self.assertRaisesRegex(ValueError, 'source Parquet SHA-256 differs'):
                build(path)


if __name__ == '__main__':
    unittest.main()
