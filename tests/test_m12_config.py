import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from qpaf.m12.config import load_config, validate

ROOT = Path(__file__).resolve().parents[1]


class MethodConfigTests(unittest.TestCase):
    def test_shared_preset_loads(self):
        config = load_config(ROOT/'configs/m1.2/core.toml')
        self.assertEqual(config['features']['schema'], 'qpaf13_v1')
        self.assertEqual(config['loss']['reduction'], 'query_mean')

    def test_invalid_fields_are_rejected_before_model_construction(self):
        base = load_config(ROOT/'configs/m1.2/core.toml')
        for section, field, value in [
            ('gate', 'temperature', 0), ('gate', 'temperature', float('nan')),
            ('gate', 'temperature', True), ('gate', 'kind', 'oracle'),
            ('gate', 'hidden_dim', 0), ('features', 'schema', 'unknown'),
            ('features', 'query_length_cap', True), ('features', 'qrels_feature', True),
            ('loss', 'name', 'unknown'), ('loss', 'reduction', 'pair_mean'),
            ('verification', 'steps', 0), ('verification', 'seed', -1),
            ('verification', 'learning_rate', float('inf')),
        ]:
            config = copy.deepcopy(base)
            config[section][field] = value
            with self.subTest(section=section, field=field, value=value), self.assertRaises(ValueError):
                validate(config)


if __name__ == '__main__':
    unittest.main()
