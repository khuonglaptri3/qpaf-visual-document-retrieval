"""A005 Stage 2 ViMDoc alignment gate and its authorization guard, on a synthetic cache only."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from qpaf.a005.stage2 import AUTHORIZATION, CACHE_FILES, SOURCES, SPLITS, Stage2Error, check_authorization, run  # noqa: E402
from qpaf.m43.freeze import sha  # noqa: E402

sys.path.insert(0, str(ROOT/'tests'))
from test_a005_vimdoc import cache as synthetic_cache  # noqa: E402


class Stage2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.cache = Path(self.tmp.name)/'repo', Path(self.tmp.name)/'cache'
        self.cache.mkdir()
        frame, qrels = synthetic_cache(queries=16)
        train = sorted(qrels)[:12]
        validation = {q: qrels[q] for q in sorted(qrels)[12:]}
        (self.root/SPLITS).mkdir(parents=True)
        (self.root/SPLITS/'train_ids.txt').write_text('\n'.join(train)+'\n', encoding='utf-8')
        pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), self.cache/'candidate_scores.parquet')
        (self.cache/'queries.jsonl').write_text(
            ''.join(json.dumps({'query_id': q, 'text': 'synthetic query'})+'\n' for q in qrels), encoding='utf-8')
        (self.cache/'dev_qrels.json').write_text(
            json.dumps({'train': {q: qrels[q] for q in train}, 'validation': validation}), encoding='utf-8')
        self.train = train

    def tearDown(self):
        self.tmp.cleanup()

    def test_gate_uses_train_queries_only_and_passes_on_an_aligned_cache(self):
        record = run(self.root, self.cache)
        self.assertEqual(record['query_count'], len(self.train))
        self.assertEqual(len(record['grid']), 66)
        self.assertEqual(record['grid_best_weights'], [0.0, 0.0, 1.0])
        self.assertEqual(record['gate']['status'], 'PASS')
        self.assertFalse(record['validation_labels_used'])

    def test_train_qrels_must_match_the_sealed_train_ids(self):
        (self.root/SPLITS/'train_ids.txt').write_text('\n'.join(self.train[:-1])+'\n', encoding='utf-8')
        with self.assertRaisesRegex(Stage2Error, 'M4.1 train IDs'):
            run(self.root, self.cache)

    def test_authorization_guard(self):
        with self.assertRaisesRegex(Stage2Error, 'authorization missing'):
            check_authorization(self.root, self.cache)
        for relative in SOURCES:
            (self.root/relative).parent.mkdir(parents=True, exist_ok=True)
            (self.root/relative).write_text(relative, encoding='utf-8')
        record = {'status': 'APPROVED', 'source_files_sha256': {r: sha(self.root/r) for r in SOURCES},
                  'cache_sha256': {n: sha(self.cache/n) for n in CACHE_FILES}}
        (self.root/AUTHORIZATION).parent.mkdir(parents=True, exist_ok=True)
        (self.root/AUTHORIZATION).write_text(json.dumps(record), encoding='utf-8')
        self.assertEqual(check_authorization(self.root, self.cache), sha(self.root/AUTHORIZATION))
        (self.cache/'queries.jsonl').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(Stage2Error, 'cache file differs'):
            check_authorization(self.root, self.cache)


if __name__ == '__main__':
    unittest.main()
