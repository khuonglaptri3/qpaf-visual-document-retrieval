"""M4.6 v2 config and matched trainer: only the loss differs from the M4.2 contract."""
import copy
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import torch  # noqa: E402

from qpaf.m24 import trainer as m24_trainer  # noqa: E402
from qpaf.m24.config import load_config as load_v1  # noqa: E402
from qpaf.m24.dataset import build_records  # noqa: E402
from qpaf.m24.synthetic import make_fixture  # noqa: E402
from qpaf.m46 import config as m46_config, losses as m46_losses, trainer as m46_trainer  # noqa: E402

V1 = ROOT/'results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/inputs/shared_base.toml'
V2 = ROOT/'configs/m4.6/shared_base_v2.toml'


def toml(path):
    with path.open('rb') as stream:
        return tomllib.load(stream)


def records():
    rows, queries, qrels, splits = make_fixture()
    return build_records(rows, queries, qrels, splits, ('train', 'validation'))


def short(config, epochs):
    config = copy.deepcopy(config)
    config['training']['epochs'] = epochs
    return config


class ConfigTests(unittest.TestCase):
    def test_v2_toml_differs_from_m42_base_only_in_loss(self):
        v1, v2 = toml(V1), toml(V2)
        self.assertEqual(v2.pop('loss'), m46_config.LOSS)
        v1.pop('loss')
        self.assertEqual(v1, v2)
        self.assertEqual(m46_config.load_config(V2)['loss'], m46_config.LOSS)

    def test_validate_refuses_v1_loss_and_bad_other_fields(self):
        good = m46_config.load_config(V2)
        bad = {
            'v1 loss': ('loss', {'name': 'pairwise_logistic', 'reduction': 'query_mean'}),
            'extra loss key': ('loss', {**m46_config.LOSS, 'sigma': 1.0}),
            'other cutoff': ('loss', {**m46_config.LOSS, 'metric_cutoff': 5}),
        }
        for name, (section, value) in bad.items():
            config = copy.deepcopy(good)
            config[section] = value
            with self.subTest(name), self.assertRaises(ValueError):
                m46_config.validate(config)
        config = copy.deepcopy(good)
        config['training']['epochs'] = 0
        with self.assertRaises(ValueError):
            m46_config.validate(config)


class TrainerTests(unittest.TestCase):
    def test_initial_parameters_match_m24(self):
        v1, v2 = load_v1(V1), m46_config.load_config(V2)
        for method in ('QARF', 'QPAF'):
            a = m24_trainer.build_model(v1, method).state_dict()
            b = m46_trainer.build_model(v2, method).state_dict()
            with self.subTest(method):
                self.assertEqual(a.keys(), b.keys())
                self.assertTrue(all((a[k] == b[k]).all() for k in a))

    def test_synthetic_training_is_deterministic_and_uses_v2_loss(self):
        data, config = records(), short(m46_config.load_config(V2), 3)
        spy = mock.Mock(wraps=m46_losses.lambda_pairwise_logistic_loss)
        results = []
        with mock.patch.object(m46_trainer, 'lambda_pairwise_logistic_loss', spy):
            for _ in range(2):
                with tempfile.TemporaryDirectory() as folder:
                    out = m46_trainer.train(config, 'QPAF', data['train'], data['validation'], folder, log=lambda _: None)
                    # Checkpoint bytes hold wall-clock seconds, so compare the saved parameters.
                    state = torch.load(Path(folder)/'best.pt', map_location='cpu', weights_only=True)['model_state']
                    results.append((out['history'], state))
        self.assertTrue(spy.called)
        strip = [[{k: v for k, v in row.items() if k != 'seconds'} for row in h] for h, _ in results]
        self.assertEqual(strip[0], strip[1])
        self.assertTrue(all(torch.equal(results[0][1][k], results[1][1][k]) for k in results[0][1]))
        self.assertEqual(len(strip[0]), 3)

    def test_resume_matches_uninterrupted_run(self):
        data, config = records(), short(m46_config.load_config(V2), 3)
        quiet = {'log': lambda _: None}
        with tempfile.TemporaryDirectory() as straight, tempfile.TemporaryDirectory() as split:
            full = m46_trainer.train(config, 'QARF', data['train'], data['validation'], straight, **quiet)
            m46_trainer.train(config, 'QARF', data['train'], data['validation'], split, stop_after_epoch=2, **quiet)
            resumed = m46_trainer.train(config, 'QARF', data['train'], data['validation'], split,
                                        resume=Path(split)/'last.pt', **quiet)
            drop = lambda h: [{k: v for k, v in row.items() if k != 'seconds'} for row in h]  # noqa: E731
            self.assertEqual(drop(full['history']), drop(resumed['history']))


if __name__ == '__main__':
    unittest.main()
