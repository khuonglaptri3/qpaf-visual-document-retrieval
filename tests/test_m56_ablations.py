"""M5.6 masked-feature diagnostics on the synthetic fixture; no real data, GPU or network."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

import torch

from qpaf.m12.features import FEATURE_NAMES
from qpaf.m24.config import load_config
from qpaf.m24.dataset import build_records
from qpaf.m24.evaluator import evaluate, predict
from qpaf.m24.synthetic import make_fixture
from qpaf.m24.trainer import train as pilot_train
from qpaf.m56 import ablation, conditioning, runner
from qpaf.m56.ablation import ABLATIONS, AblationError

CONFIG = ROOT/'configs/m2.7/shared_base.toml'


def small_config(epochs=4):
    config = load_config(CONFIG)
    config['training'].update(epochs=epochs, batch_size=8, learning_rate=0.05)
    return config


def records():
    rows, queries, qrels, splits = make_fixture()
    return build_records(rows, queries, qrels, splits, ('train', 'validation'))


def deterministic():
    torch.manual_seed(0)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


class ContractTests(unittest.TestCase):
    def test_preregistered_groups_are_disjoint_and_one_group_per_run(self):
        self.assertEqual(list(ABLATIONS), ['R6-00', 'R6-01', 'R6-02', 'R6-03', 'R6-04'])
        self.assertEqual(ABLATIONS['R6-00'][1], ())
        removed = [name for _, omitted in list(ABLATIONS.values())[1:] for name in omitted]
        self.assertEqual(len(removed), len(set(removed)))
        self.assertEqual(set(removed), set(FEATURE_NAMES)-{'score_bm25', 'score_dense', 'score_visual'})

    def test_unknown_feature_is_refused(self):
        with self.assertRaises(AblationError):
            ablation.keep_vector(('not_a_feature',))

    def test_masked_model_starts_from_the_pilot_initialisation(self):
        from qpaf.m24.trainer import build_model
        config = small_config()
        pilot = build_model(config, 'QPAF').state_dict()
        masked = ablation.build_model(config, ABLATIONS['R6-01'][1]).state_dict()
        self.assertEqual(set(masked), {'gate.gate.weight', 'gate.gate.bias'})
        self.assertTrue(torch.equal(masked['gate.gate.weight'], pilot['gate.weight']))


class TrainingTests(unittest.TestCase):
    def setUp(self):
        deterministic()
        self.config, self.records = small_config(), records()

    def test_control_reproduces_the_m24_qpaf_trainer_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            pilot = pilot_train(self.config, 'QPAF', self.records['train'], self.records['validation'],
                                Path(directory)/'pilot', log=lambda _: None)
            control = ablation.train(self.config, (), self.records['train'], self.records['validation'],
                                     Path(directory)/'control', log=lambda _: None)
        drop = ('seconds',)
        self.assertEqual([{k: v for k, v in r.items() if k not in drop} for r in pilot['history']],
                         [{k: v for k, v in r.items() if k not in drop} for r in control['history']])
        self.assertEqual(pilot['steps'], control['steps'])
        self.assertEqual(pilot['best'], control['best'])
        cap = self.config['features']['query_length_cap']
        self.assertEqual(predict(pilot['model'], self.records['validation'], 8, cap),
                         predict(control['model'], self.records['validation'], 8, cap))

    def test_omitted_weights_never_move_and_checkpoint_round_trips(self):
        omitted = ABLATIONS['R6-03'][1]
        with tempfile.TemporaryDirectory() as directory:
            checkpoints = Path(directory)/'checkpoints'
            result = ablation.train(self.config, omitted, self.records['train'], self.records['validation'],
                                    checkpoints, log=lambda _: None)
            payload = ablation.load_checkpoint(checkpoints/'best.pt', config=self.config, omitted=omitted,
                                               expected_sha256=result['checkpoint_sha256']['best'])
            with self.assertRaises(AblationError):
                ablation.load_checkpoint(checkpoints/'best.pt', config=self.config, omitted=())
        self.assertTrue(ablation.masked_weights_unchanged(self.config, omitted, payload['model_state']))
        self.assertFalse(ablation.masked_weights_unchanged(self.config, ABLATIONS['R6-01'][1],
                                                           payload['model_state']))
        model = ablation.build_model(self.config, omitted)
        model.load_state_dict(payload['model_state'])
        metrics, _ = evaluate(predict(model, self.records['validation'], 8, 64), self.records['validation'])
        self.assertEqual(metrics[result['best']['metric']], result['best']['value'])

    def test_masked_features_do_not_change_the_output(self):
        from qpaf.m12.features import build_features
        model = ablation.build_model(self.config, ABLATIONS['R6-04'][1])
        record = self.records['validation'][0]
        raw = torch.tensor([record.raw_scores], dtype=torch.float64)
        outputs = [model(build_features(raw, [text], [list(record.page_ids)])).scores
                   for text in ('a', 'a much longer query with many more words in it')]
        self.assertTrue(torch.equal(*outputs))


class StatisticsTests(unittest.TestCase):
    def test_paired_statistics_counts_ties_and_is_seeded(self):
        deltas = {m: [0.1, -0.2, 0.0, 5e-13, 0.3] for m in ablation.METRICS}
        first, second = ablation.paired_statistics(deltas), ablation.paired_statistics(deltas)
        self.assertEqual(first, second)
        self.assertEqual(first['ndcg_at_10']['wtl'], {'wins': 2, 'ties': 2, 'losses': 1})
        self.assertAlmostEqual(first['ndcg_at_10']['mean_delta'], 0.04)
        self.assertLessEqual(first['ndcg_at_10']['ci95'][0], first['ndcg_at_10']['ci95'][1])

    def test_nonfinite_or_unpaired_input_is_refused(self):
        with self.assertRaises(AblationError):
            ablation.paired_statistics({m: [float('nan')] for m in ablation.METRICS})
        with self.assertRaises(AblationError):
            ablation.per_query_deltas([{'query_id': 'a'}], [{'query_id': 'b'}])

    def test_prediction_archive_is_byte_deterministic(self):
        data = [{'query_id': 'q', 'page_ids': ['a'], 'scores': [0.5], 'weights': [[1., 0., 0.]]}]
        with tempfile.TemporaryDirectory() as directory:
            for name in ('a.gz', 'b.gz'):
                runner.write_predictions(Path(directory)/name, data)
            self.assertEqual((Path(directory)/'a.gz').read_bytes(), (Path(directory)/'b.gz').read_bytes())
            self.assertEqual(runner.read_predictions(Path(directory)/'a.gz'), data)
        moved = copy.deepcopy(data)
        moved[0]['weights'][0][0] = 0.75
        self.assertEqual(runner.prediction_difference(data, moved), 0.25)


class ConditioningTests(unittest.TestCase):
    def test_six_accepted_runs_cover_three_seeds_and_both_granularities(self):
        self.assertEqual(set(conditioning.RUNS), {(s, m) for s in conditioning.SEEDS for m in ('QARF', 'QPAF')})

    def test_acceptance_must_be_a_single_pass_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'events.jsonl'
            path.write_text(json.dumps({'registry_event_id': 'E1', 'event_type': 'ACCEPTANCE_RECORDED',
                                        'registry_status': 'PASS'})+'\n', encoding='utf8')
            self.assertTrue(conditioning.accepted(Path(directory), 'events.jsonl', 'E1'))
            self.assertFalse(conditioning.accepted(Path(directory), 'events.jsonl', 'E2'))


class ApprovalTests(unittest.TestCase):
    def authorization(self):
        return {'status': 'APPROVED', 'task_id': 'M5.6', 'run_id': 'RUN-QPAF-M5_6-ABL-001-20261027T000000Z-A01',
                'scope': list(runner.SCOPE), 'permissions': dict(runner.PERMISSIONS),
                'approval': {'approver': 'Tấn Phát', 'approval_text': 'approved', 'approved_utc': '2026-10-27T00:00:00Z'},
                'source_commit': 'a'*40, 'source_files_sha256': {'x': '1'}, 'authority_pins': {'y': '2'},
                'runtime': {'python': '3'}, 'limits': dict(runner.LIMITS)}

    def check(self, auth, **overrides):
        arguments = dict(run_id=auth['run_id'], clean=True, source_hashes={'x': '1'}, authority_pins={'y': '2'},
                         runtime={'python': '3'})
        arguments.update(overrides)
        runner.check_approval(auth, **arguments)

    def test_complete_authorization_passes(self):
        self.check(self.authorization())

    def test_each_violation_is_refused(self):
        cases = [('approval', {'approver': 'Tấn Phát', 'approval_text': 'PENDING', 'approved_utc': 'PENDING'}),
                 ('scope', runner.SCOPE[:3]), ('status', 'DRAFT'),
                 ('permissions', {**runner.PERMISSIONS, 'test_labels': True}),
                 ('limits', {**runner.LIMITS, 'automatic_retries': 1})]
        for key, value in cases:
            with self.subTest(key=key), self.assertRaises(AblationError):
                self.check({**self.authorization(), key: value})
        for override in ({'clean': False}, {'source_hashes': {'x': 'other'}}, {'runtime': {'python': '4'}},
                         {'run_id': 'RUN-QPAF-M5_6-ABL-001-20261027T000000Z-A02'}):
            with self.subTest(override=override), self.assertRaises(AblationError):
                self.check(self.authorization(), **override)


if __name__ == '__main__':
    unittest.main()
