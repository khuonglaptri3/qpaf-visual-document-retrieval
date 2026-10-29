"""A005 Stage 4 runner pieces on a synthetic cache: reload check, stop rule, per-run authorization."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import torch  # noqa: E402

from qpaf.a005.stage2 import SPLITS, split_inputs  # noqa: E402
from qpaf.a005.stage4 import (SEEDS, Stage4Error, check_authorization, no_deviation_rule, reload_check,  # noqa: E402
                              run_dir, validation_scores)
from qpaf.a005.trainer import train  # noqa: E402

sys.path.insert(0, str(ROOT/'tests'))
from test_a005_vimdoc import cache as synthetic_cache  # noqa: E402


class Stage4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.cache = Path(self.tmp.name)/'repo', Path(self.tmp.name)/'cache'
        self.cache.mkdir()
        frame, qrels = synthetic_cache(queries=20, good_channel=1)
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

    def tearDown(self):
        self.tmp.cleanup()

    def test_training_learns_off_the_anchor_and_reloads_in_a_fresh_process(self):
        train_records, train_qrels = split_inputs(self.root, self.cache, 'train')
        validation_records, validation_qrels = split_inputs(self.root, self.cache, 'validation')
        anchor = [0., 0.1, 0.9]
        result = train(anchor, 'page', SEEDS[0], train_records, validation_records, query_length_cap=64,
                       train_relevant_documents=train_qrels, validation_relevant_documents=validation_qrels,
                       epochs=3, log=lambda _: None)
        model = result['model'].eval()
        checkpoint = Path(self.tmp.name)/'checkpoint.pt'
        torch.save(model.state_dict(), checkpoint)
        scores = validation_scores(model, validation_records)
        self.assertLessEqual(reload_check(self.root, self.cache, checkpoint, anchor, 'page', scores), 1e-7)

    def test_no_deviation_rule(self):
        for seed, epoch in zip(SEEDS, (0, 0, 7)):
            directory = run_dir(self.root, 'page', seed)
            directory.mkdir(parents=True)
            (directory/'result.json').write_text(json.dumps({'best_epoch': epoch}), encoding='utf-8')
        self.assertEqual(no_deviation_rule(self.root)['status'], 'NO_LEARNED_DEVIATION')
        (run_dir(self.root, 'page', SEEDS[1])/'result.json').write_text(json.dumps({'best_epoch': 3}))
        self.assertEqual(no_deviation_rule(self.root)['status'], 'PROCEED')

    def test_authorization_is_per_run(self):
        with self.assertRaisesRegex(Stage4Error, 'authorization missing'):
            check_authorization(self.root, self.cache, 'query', SEEDS[0])
        directory = run_dir(self.root, 'query', SEEDS[0])
        directory.mkdir(parents=True)
        (directory/'authorization.json').write_text(json.dumps(
            {'status': 'APPROVED', 'granularity': 'query', 'seed': SEEDS[1]}), encoding='utf-8')
        with self.assertRaisesRegex(Stage4Error, 'another run'):
            check_authorization(self.root, self.cache, 'query', SEEDS[0])


if __name__ == '__main__':
    unittest.main()
