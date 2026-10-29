"""A005 Stage 3 baselines and co-strongest selection, on a synthetic cache only."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from qpaf.a005.stage2 import SPLITS  # noqa: E402
from qpaf.a005.stage3 import STAGE2, Stage3Error, check_authorization, co_strongest, run  # noqa: E402

sys.path.insert(0, str(ROOT/'tests'))
from test_a005_vimdoc import cache as synthetic_cache  # noqa: E402


class Stage3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.cache = Path(self.tmp.name)/'repo', Path(self.tmp.name)/'cache'
        self.cache.mkdir()
        frame, qrels = synthetic_cache(queries=20)
        ids = sorted(qrels)
        roles = {'train': ids[:14], 'validation': ids[14:]}
        (self.root/SPLITS).mkdir(parents=True)
        for role, members in roles.items():
            (self.root/SPLITS/f'{role}_ids.txt').write_text('\n'.join(members)+'\n', encoding='utf-8')
        pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), self.cache/'candidate_scores.parquet')
        (self.cache/'queries.jsonl').write_text(
            ''.join(json.dumps({'query_id': q, 'text': 'synthetic query'})+'\n' for q in qrels), encoding='utf-8')
        (self.cache/'dev_qrels.json').write_text(
            json.dumps({role: {q: qrels[q] for q in members} for role, members in roles.items()}), encoding='utf-8')
        (self.root/STAGE2).parent.mkdir(parents=True)
        (self.root/STAGE2).write_text(json.dumps({'gate': {'status': 'PASS'}}), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_static_refit_on_train_and_validation_roster(self):
        record = run(self.root, self.cache)
        self.assertEqual(record['train_fitted_static_weights'], [0.0, 0.0, 1.0])
        self.assertEqual(record['validation_query_count'], 6)
        self.assertEqual(set(record['roster']), {'bm25', 'bge_m3', 'colqwen25', 'uniform_combsum', 'rrf_k60',
                                                 'train_fitted_static'})
        self.assertIn('train_fitted_static', record['co_strongest'])
        self.assertIn('colqwen25', record['co_strongest'])
        self.assertEqual(len(record['roster']['bm25']['per_query']), 6)

    def test_co_strongest_tolerance(self):
        roster = {'a': {'ndcg_at_10': 0.5}, 'b': {'ndcg_at_10': 0.5-5e-13}, 'c': {'ndcg_at_10': 0.5-2e-12}}
        self.assertEqual(co_strongest(roster), ['a', 'b'])

    def test_needs_a_passing_stage2_gate(self):
        (self.root/STAGE2).write_text(json.dumps({'gate': {'status': 'REVISION_GATE_FAILED'}}), encoding='utf-8')
        with self.assertRaisesRegex(Stage3Error, 'passing Stage 2'):
            check_authorization(self.root, self.cache)


if __name__ == '__main__':
    unittest.main()
