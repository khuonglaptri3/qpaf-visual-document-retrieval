"""M2.4 dataset, trainer, evaluator, checkpoint and failure-path checks."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
HAS_TORCH = importlib.util.find_spec('torch') is not None

from qpaf.m24.config import load_config, validate
from qpaf.m24.dataset import DatasetError, build_records, read_split_ids
from qpaf.m24.evaluator import evaluate, query_metrics, rank
from qpaf.m24.synthetic import make_fixture

if HAS_TORCH:
    import torch
    from qpaf.m24.checkpoint import CheckpointError, load_checkpoint
    from qpaf.m24.dataset import collate
    from qpaf.m24.evaluator import predict
    from qpaf.m24.trainer import TrainingError, build_model, train

CONFIG = ROOT/'configs/m2.4/pipeline.toml'


def small_config(epochs=3):
    config = load_config(CONFIG)
    config['training'].update(epochs=epochs, batch_size=8, learning_rate=0.05)
    return config


def fixture_records(roles=('train', 'validation')):
    rows, queries, qrels, splits = make_fixture()
    return build_records(rows, queries, qrels, splits, roles)


def setUpModule():
    global previous_threads
    if HAS_TORCH:
        previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)


def tearDownModule():
    if HAS_TORCH:
        torch.set_num_threads(previous_threads)


class ConfigTests(unittest.TestCase):
    def test_frozen_config_loads(self):
        config = load_config(CONFIG)
        self.assertEqual(config['training']['seed'], 20260820)
        self.assertEqual(config['evaluation']['selection_metric'], 'ndcg_at_10')

    def test_rejects_unknown_fields_and_bad_values(self):
        base = load_config(CONFIG)
        for section, key, value in [('training', 'optimizer', 'sgd'), ('training', 'epochs', 0),
                                    ('training', 'learning_rate', float('nan')),
                                    ('evaluation', 'selection_metric', 'ndcg_at_100'),
                                    ('loss', 'reduction', 'pair_mean'), ('data', 'schema', 'v0')]:
            config = copy.deepcopy(base)
            config[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                validate(config)
        config = copy.deepcopy(base)
        config['training']['extra'] = 1
        with self.assertRaises(ValueError):
            validate(config)


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.queries, self.qrels, self.splits = make_fixture(queries_per_role=(2, 1, 1), candidates=3)

    def build(self, roles=('train', 'validation')):
        return build_records(self.rows, self.queries, self.qrels, self.splits, roles)

    def test_records_are_sorted_and_count_outside_positives(self):
        record = self.build()['train'][0]
        self.assertEqual(list(record.page_ids), sorted(record.page_ids))
        self.assertEqual(sum(record.labels), 1)
        self.assertEqual(record.relevant_total, 2)  # includes the page outside the union

    def test_test_rows_are_not_materialized(self):
        self.rows.append({'query_id': self.splits['test'][0], 'page_id': 'bad', 'bm25_score': float('nan'),
                          'dense_score': 0., 'visual_score': 0.})
        records = self.build()
        self.assertEqual(set(records), {'train', 'validation'})

    def test_score_row_relevance_column_is_ignored(self):
        for row in self.rows:
            row['relevance'] = 1.
        record = self.build()['train'][0]
        self.assertEqual(sum(record.labels), 1)

    def test_failure_paths(self):
        cases = {
            'overlap': lambda: self.splits['validation'].append(self.splits['train'][0]),
            'unknown query': lambda: self.rows.append({**self.rows[0], 'query_id': 'ghost'}),
            'duplicate page': lambda: self.rows.append(dict(self.rows[0])),
            'nan score': lambda: self.rows[0].update(dense_score=float('nan')),
            'bool score': lambda: self.rows[0].update(dense_score=True),
            'missing text': lambda: self.queries.pop(self.splits['train'][0]),
            'no positive': lambda: self.qrels[self.splits['train'][0]].update(
                {page: 0 for page in self.qrels[self.splits['train'][0]]}),
            'uncovered': lambda: self.rows.__setitem__(
                slice(None), [r for r in self.rows if r['query_id'] != self.splits['train'][0]]),
        }
        for name, mutate in cases.items():
            self.setUp()
            mutate()
            with self.subTest(name), self.assertRaises(DatasetError):
                self.build()
        self.setUp()
        with self.assertRaises(DatasetError):
            build_records(self.rows, self.queries, self.qrels, self.splits, ('train',), max_candidates=2)

    def test_reads_m13_split_bundle(self):
        splits = read_split_ids(ROOT/'evidence/revisions/m1.3-001/splits')
        self.assertEqual([len(splits[r]) for r in ('train', 'validation', 'test')], [799, 171, 172])
        with tempfile.TemporaryDirectory() as directory:
            for name in ('train_ids.txt', 'val_ids.txt', 'test_ids.txt'):
                Path(directory, name).write_text('a\na\n', encoding='utf-8')
            with self.assertRaises(DatasetError):
                read_split_ids(directory)


class MetricTests(unittest.TestCase):
    def test_hand_computed_metrics(self):
        values = query_metrics([0, 1, 0, 1], relevant_total=3)
        ideal = 1+1/math.log2(3)+1/2
        self.assertAlmostEqual(values['ndcg_at_10'], (1/math.log2(3)+1/math.log2(5))/ideal, places=12)
        self.assertEqual(values['recall_at_1'], 0)
        self.assertAlmostEqual(values['recall_at_3'], 1/3, places=12)
        self.assertEqual(values['mrr_at_10'], .5)
        self.assertEqual(query_metrics([0]*12+[1], 1)['mrr_at_10'], 0.)

    def test_ties_break_by_page_id(self):
        self.assertEqual(rank(['b', 'a', 'c'], [1., 1., 2.]), [2, 1, 0])

    def test_evaluate_rejects_missing_or_mismatched_predictions(self):
        records = fixture_records()['validation']
        predictions = [{'query_id': r.query_id, 'page_ids': list(r.page_ids),
                        'scores': [0.]*len(r.page_ids)} for r in records]
        aggregate, per_query = evaluate(predictions, records)
        self.assertEqual(aggregate['query_count'], len(records))
        with self.assertRaises(ValueError):
            evaluate(predictions[1:], records)
        bad = copy.deepcopy(predictions)
        bad[0]['scores'][0] = float('inf')
        with self.assertRaises(ValueError):
            evaluate(bad, records)


@unittest.skipUnless(HAS_TORCH, 'install requirements-learned-local.txt for trainer checks')
class TrainerTests(unittest.TestCase):
    def setUp(self):
        torch.use_deterministic_algorithms(True)
        self.records = fixture_records()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def run_train(self, method, config, directory, **kwargs):
        return train(config, method, self.records['train'], self.records['validation'],
                     directory, log=lambda message: None, **kwargs)

    def test_matched_initialization(self):
        config = small_config()
        qarf, qpaf = build_model(config, 'QARF'), build_model(config, 'QPAF')
        self.assertEqual(qarf.granularity, 'query')
        self.assertEqual(qpaf.granularity, 'page')
        for (name, left), right in zip(qarf.state_dict().items(), qpaf.state_dict().values()):
            self.assertTrue(torch.equal(left, right), name)

    def test_training_reduces_loss_and_beats_initial_validation(self):
        config = small_config(epochs=8)
        for method in ('QARF', 'QPAF'):
            with self.subTest(method):
                result = self.run_train(method, config, self.dir/method)
                history = result['history']
                self.assertLess(history[-1]['train_loss'], history[0]['train_loss'])
                initial = evaluate(predict(build_model(config, method), self.records['validation'], 8, 64),
                                   self.records['validation'])[0]['ndcg_at_10']
                self.assertGreater(result['best']['value'], initial)
                self.assertTrue((self.dir/method/'best.pt').is_file())

    def test_checkpoint_reload_parity(self):
        config = small_config()
        result = self.run_train('QPAF', config, self.dir)
        payload = load_checkpoint(self.dir/'last.pt', config=config, method='QPAF',
                                  expected_sha256=result['checkpoint_sha256']['last'])
        fresh = build_model(config, 'QPAF')
        fresh.load_state_dict(payload['model_state'])
        before = predict(result['model'], self.records['validation'], 8, 64)
        after = predict(fresh, self.records['validation'], 8, 64)
        difference = max(abs(a-b) for x, y in zip(before, after) for a, b in zip(x['scores'], y['scores']))
        self.assertLessEqual(difference, config['evaluation']['reload_tolerance'])

    def test_resume_is_bit_identical(self):
        config = small_config(4)
        straight = self.run_train('QPAF', config, self.dir/'straight')
        self.run_train('QPAF', config, self.dir/'part', stop_after_epoch=2)
        resumed = self.run_train('QPAF', config, self.dir/'part', resume=self.dir/'part/last.pt')
        for left, right in zip(straight['model'].parameters(), resumed['model'].parameters()):
            self.assertTrue(torch.equal(left, right))
        self.assertEqual([h['epoch'] for h in resumed['history']], [1, 2, 3, 4])
        self.assertEqual(resumed['best'], straight['best'])

    def test_checkpoint_rejects_wrong_contract(self):
        config = small_config()
        result = self.run_train('QARF', config, self.dir)
        with self.assertRaises(CheckpointError):
            load_checkpoint(self.dir/'last.pt', config=config, method='QPAF')
        changed = small_config()
        changed['gate']['temperature'] = 2.
        with self.assertRaises(CheckpointError):
            load_checkpoint(self.dir/'last.pt', config=changed, method='QARF')
        with self.assertRaises(CheckpointError):
            load_checkpoint(self.dir/'last.pt', config=config, method='QARF', expected_sha256='0'*64)
        (self.dir/'broken.pt').write_bytes(b'not a checkpoint')
        with self.assertRaises(CheckpointError):
            load_checkpoint(self.dir/'broken.pt', config=config, method='QARF')
        self.assertIn('last', result['checkpoint_sha256'])

    def test_nonfinite_parameters_fail_loudly(self):
        config = small_config()
        model = build_model(config, 'QPAF')
        with torch.no_grad():
            next(model.parameters()).fill_(float('nan'))
        with mock.patch('qpaf.m24.trainer.build_model', return_value=model),                 self.assertRaises((TrainingError, ValueError)):
            self.run_train('QPAF', config, self.dir)
        self.assertFalse((self.dir/'last.pt').exists())

    def test_nothing_to_learn_fails(self):
        config = small_config()
        only_positive = [r.__class__(r.query_id, r.text, r.page_ids[:1], r.raw_scores[:1], (1,), 1)
                         for r in self.records['train']]
        with self.assertRaises(TrainingError):
            train(config, 'QPAF', only_positive, self.records['validation'], self.dir, log=lambda m: None)

    def test_padding_is_masked(self):
        records = self.records['train'][:2]
        shorter = records[1].__class__(records[1].query_id, records[1].text, records[1].page_ids[:5],
                                       records[1].raw_scores[:5], records[1].labels[:5], 1)
        batch = collate([records[0], shorter])
        self.assertEqual(batch.mask.sum(dim=1).tolist(), [12, 5])
        self.assertEqual(batch.page_ids[1][5:], ['']*7)


@unittest.skipUnless(HAS_TORCH, 'install requirements-learned-local.txt for the pipeline CLI')
class CliTests(unittest.TestCase):
    def test_synthetic_run_writes_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT/'scripts/run_m24_pipeline.py'),
                                     '--config', str(CONFIG), '--method', 'QPAF', '--synthetic-fixture',
                                     '--epochs', '3', '--output', directory], capture_output=True,
                                    text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            stage = Path(directory)/'QPAF'
            attempt = stage/json.loads((stage/'complete.json').read_text(encoding='utf-8'))['attempt']
            summary = json.loads((attempt/'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['kind'], 'synthetic_software_verification')
            self.assertEqual(summary['test_split'], 'not_opened')
            self.assertTrue(summary['reload_parity']['passed'])
            for name in ('checkpoints/best.pt', 'checkpoints/last.pt', 'epochs.csv', 'steps.csv',
                         'telemetry.json', 'validation_per_query.csv', 'validation_predictions.json'):
                self.assertTrue((attempt/name).is_file(), name)

    def test_failed_run_keeps_failure_record(self):
        with tempfile.TemporaryDirectory() as directory:
            scores = Path(directory)/'scores.csv'
            scores.write_text('query_id,page_id,bm25_score,dense_score,visual_score\nq,p,1,nan,1\n',
                              encoding='utf-8')
            (Path(directory)/'q.json').write_text('{"q": "text"}', encoding='utf-8')
            (Path(directory)/'r.json').write_text('{"q": {"p": 1}}', encoding='utf-8')
            splits = Path(directory)/'splits'
            splits.mkdir()
            for name, ids in [('train_ids.txt', 'q\n'), ('val_ids.txt', 'v\n'), ('test_ids.txt', 't\n')]:
                (splits/name).write_text(ids, encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT/'scripts/run_m24_pipeline.py'),
                                     '--config', str(CONFIG), '--method', 'QARF', '--scores', str(scores),
                                     '--queries', str(Path(directory)/'q.json'),
                                     '--qrels', str(Path(directory)/'r.json'), '--splits', str(splits),
                                     '--output', str(Path(directory)/'out')],
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 2)
            attempts = [p for p in (Path(directory)/'out/QARF').iterdir() if p.is_dir()]
            self.assertEqual(len(attempts), 1)
            status = json.loads((attempts[0]/'status.json').read_text(encoding='utf-8'))
            failure = json.loads((attempts[0]/'failure.json').read_text(encoding='utf-8'))
            self.assertEqual(status['status'], 'failed')
            self.assertEqual(failure['status'], 'FAIL')
            self.assertFalse((Path(directory)/'out/QARF/complete.json').exists())


if __name__ == '__main__':
    unittest.main()
