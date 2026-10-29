"""A005-R1 refined trainer: cosine LR, small epsilon, weight averaging and the create-once run record."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import torch  # noqa: E402

from qpaf.a005.refine import (CONFIG, VARIANTS, RefineError, build_model, cosine_lr, create_run, run_dir,  # noqa: E402
                              train_refined, variant_config)
from qpaf.a005.stage2 import SPLITS  # noqa: E402
from qpaf.a005.stage4 import STAGE3  # noqa: E402
from qpaf.m12.features import build_features  # noqa: E402
from qpaf.m24.dataset import collate  # noqa: E402
from qpaf.m43.freeze import read  # noqa: E402

sys.path.insert(0, str(ROOT/'tests'))
from test_a005_trainer import ANCHOR, quiet, records  # noqa: E402
from test_a005_vimdoc import cache as synthetic_cache  # noqa: E402


def relevant_documents(rows):
    return {r.query_id: {r.page_ids[r.labels.index(1)].rpartition('_')[0]} for r in rows}


def git(root, *args):
    subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=root, check=True,
                   capture_output=True)


class TrainerTests(unittest.TestCase):
    def setUp(self):
        self.train_rows, self.validation_rows = records(24, 5, 0, doc_ids=True), records(12, 6, 0, doc_ids=True)
        self.kwargs = dict(query_length_cap=64, log=quiet, train_relevant_documents=relevant_documents(self.train_rows),
                           validation_relevant_documents=relevant_documents(self.validation_rows))

    def test_cosine_lr_endpoints(self):
        self.assertEqual(cosine_lr(1), 0.01)
        self.assertTrue(0 < cosine_lr(40) < 1e-4)
        values = [cosine_lr(e) for e in range(1, 41)]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertAlmostEqual(cosine_lr(21), 0.005, places=12)

    def test_epoch0_equals_anchor_with_small_epsilon(self):
        self.assertEqual(CONFIG['epsilon'], 1e-6)
        batch = collate(self.train_rows[:4])
        features = build_features(batch.raw_scores, batch.texts, batch.page_ids, batch.mask, query_length_cap=64)
        for granularity in ('query', 'page'):
            weights = build_model(ANCHOR, granularity, 20260820, CONFIG['epsilon'])(features).weights
            deviation = (weights[batch.mask]-torch.tensor(ANCHOR, dtype=torch.float64)).abs().max().item()
            self.assertLess(deviation, 1e-5)

    def test_average_is_mean_of_epoch_states(self):
        states = {}
        result = train_refined(ANCHOR, 'page', 20260820, self.train_rows, self.validation_rows, epochs=3,
                               average_from=2, on_epoch=lambda e, m: states.update({e: m.state_dict()}),
                               **self.kwargs)
        self.assertEqual(set(states), {2, 3})
        averaged = result['averaged_model'].state_dict()
        for name, value in averaged.items():
            expected = (states[2][name]+states[3][name])/2
            self.assertLess((value-expected).abs().max().item(), 1e-12, name)
        self.assertIn('log_tau', averaged)
        self.assertEqual([row['epoch'] for row in result['history']], [0, 1, 2, 3])
        self.assertEqual([row['lr'] for row in result['history'][1:]], [cosine_lr(e, 3) for e in (1, 2, 3)])
        self.assertTrue(0 <= result['best_epoch'] <= 3)

    def test_deterministic(self):
        runs = [train_refined(ANCHOR, 'query', 20260821, self.train_rows, self.validation_rows, epochs=2,
                              average_from=1, **self.kwargs) for _ in range(2)]
        for name, value in runs[0]['averaged_model'].state_dict().items():
            self.assertTrue(torch.equal(value, runs[1]['averaged_model'].state_dict()[name]), name)

    def test_variants_differ_only_in_declared_field(self):
        self.assertEqual(VARIANTS, ('full', 'eps1e3', 'constlr'))
        self.assertEqual(variant_config('full'), CONFIG)
        for variant, field, value in (('eps1e3', 'epsilon', 1e-3), ('constlr', 'lr_schedule', 'constant')):
            config = variant_config(variant)
            self.assertEqual({k for k in CONFIG if config[k] != CONFIG[k]}, {field})
            self.assertEqual(config[field], value)
        with self.assertRaises(RefineError):
            variant_config('other')


class RunTests(unittest.TestCase):
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
        (self.root/STAGE3).parent.mkdir(parents=True)
        (self.root/STAGE3).write_text(json.dumps({'stage4_anchor_weights': ANCHOR}), encoding='utf-8')
        git(self.root, 'init', '-q')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'fixture')
        self.small = dict(epochs=3, average_from=2)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_run_records_and_is_create_once(self):
        record = create_run(self.root, self.cache, 'full', 'page', 20260820, log=quiet, **self.small)
        directory = run_dir(self.root, 'full', 'page', 20260820)
        self.assertEqual(directory.name, 'full-qpaf-sa-r1-20260820')
        stored = read(directory/'result.json')
        self.assertEqual(stored['source_commit'], record['source_commit'])
        self.assertEqual((stored['variant'], stored['granularity'], stored['seed']), ('full', 'page', 20260820))
        self.assertEqual(len(stored['history']), 4)
        for key in ('averaged', 'best_epoch_model'):
            entry = stored['validation'][key]
            self.assertAlmostEqual(entry['ndcg_at_10'], sum(entry['per_query'].values())/len(entry['per_query']))
        self.assertTrue((directory/'averaged.pt').is_file() and (directory/'best_epoch.pt').is_file())
        self.assertEqual(set(stored['checkpoint_sha256']), {'averaged.pt', 'best_epoch.pt'})
        with self.assertRaisesRegex(RefineError, 'already recorded'):
            create_run(self.root, self.cache, 'full', 'page', 20260820, log=quiet, **self.small)

    def test_create_run_requires_clean_tree(self):
        (self.root/STAGE3).write_text(json.dumps({'stage4_anchor_weights': ANCHOR, 'x': 1}), encoding='utf-8')
        with self.assertRaisesRegex(RefineError, 'clean tracked tree'):
            create_run(self.root, self.cache, 'full', 'page', 20260820, log=quiet, **self.small)
        self.assertFalse(run_dir(self.root, 'full', 'page', 20260820).exists())

    def test_create_run_refuses_unknown_run(self):
        with self.assertRaisesRegex(RefineError, 'unknown'):
            create_run(self.root, self.cache, 'full', 'page', 1, log=quiet, **self.small)
        with self.assertRaisesRegex(RefineError, 'unknown'):
            create_run(self.root, self.cache, 'nope', 'page', 20260820, log=quiet, **self.small)


if __name__ == '__main__':
    unittest.main()
