"""M2.7 matched QARF/QPAF config freeze and fail-closed parity checks."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
HAS_TORCH = importlib.util.find_spec('torch') is not None

from qpaf.m24.config import validate
from qpaf.m27.matched import ParityError, load_base, load_manifest, resolve, semantic_diff

MANIFEST = ROOT/'configs/m2.7/matched.json'


def write_manifest(directory, data):
    """Write a manifest variant (dict or raw JSON text) into a temp directory."""
    path = Path(directory)/'matched.json'
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')
    return path


class TempDirTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)


class ManifestTests(TempDirTest):
    def test_committed_manifest_loads(self):
        m = load_manifest(MANIFEST)
        self.assertEqual(m['methods'], {'QARF': {'gate_granularity': 'query'},
                                        'QPAF': {'gate_granularity': 'page'}})
        self.assertEqual(m['allowed_semantic_diff'], ['gate_granularity'])
        self.assertEqual(m['seeds']['robustness'], [20260820, 20260821, 20260822])
        self.assertEqual(m['budget']['wall_time_minutes_per_run'], 60)
        self.assertEqual(m['status'], 'FROZEN_CONFIG_PENDING_M2.8_INPUTS')

    def test_config_files_are_lf_only(self):
        for name in ('shared_base.toml', 'matched.json'):
            self.assertNotIn(b'\r', (ROOT/'configs/m2.7'/name).read_bytes(), name)

    def test_rejects_invalid_manifests(self):
        cases = [
            ('unknown top-level key', lambda m: m.update(extra=1)),
            ('missing top-level key', lambda m: m.pop('budget')),
            ('unknown nested key', lambda m: m['runtime'].update(gpu='a100')),
            ('allowed diff widened', lambda m: m.update(
                allowed_semantic_diff=['gate_granularity', 'training.learning_rate'])),
            ('method set changed', lambda m: m['methods'].pop('QPAF')),
            ('bad granularity', lambda m: m['methods']['QARF'].update(gate_granularity='doc')),
            ('bool seed', lambda m: m['seeds']['robustness'].__setitem__(1, True)),
            ('negative seed', lambda m: m['seeds']['robustness'].__setitem__(1, -1)),
            ('seed too large', lambda m: m['seeds']['robustness'].__setitem__(1, 2**32)),
            ('dev seed outside robustness', lambda m: m['seeds'].update(development_gate=1)),
            ('pending replaced by fake hash', lambda m: m['shared_inputs'].update(qrels='0'*64)),
            ('pending input missing', lambda m: m['shared_inputs'].pop('score_cache')),
            ('bad sha format', lambda m: m['base_config'].update(sha256='ABC')),
        ]
        for label, mutate in cases:
            with self.subTest(label):
                data = json.loads(MANIFEST.read_text(encoding='utf-8'))
                mutate(data)
                with self.assertRaises(ParityError):
                    load_manifest(write_manifest(self.tmp, data))

    def test_rejects_duplicate_keys(self):
        text = MANIFEST.read_text(encoding='utf-8').replace(
            '"QPAF": {', '"QPAF": {"gate_granularity": "query"}, "QPAF": {', 1)
        with self.assertRaises(ParityError):
            load_manifest(write_manifest(self.tmp, text))


class DiffAndResolveTests(unittest.TestCase):
    def test_semantic_diff(self):
        self.assertEqual(semantic_diff({'a': {'b': 1}}, {'a': {'b': 1}}), {})
        self.assertEqual(semantic_diff({'a': {'b': 1}}, {'a': {'b': 2}}), {'a.b': [1, 2]})
        self.assertEqual(semantic_diff({'a': 1}, {'a': 1, 'c': 3}), {'c': [None, 3]})
        self.assertEqual(semantic_diff({'x': {'y': {'z': 'q'}}}, {'x': {'y': {'z': 'p'}}}),
                         {'x.y.z': ['q', 'p']})

    def test_resolve_applies_seed_and_granularity_only(self):
        m = load_manifest(MANIFEST)
        resolved = resolve(m, 'QARF', 20260821, ROOT)
        self.assertEqual(resolved['training']['seed'], 20260821)
        self.assertEqual(resolved['gate_granularity'], 'query')
        validate(load_base(m, ROOT, 20260821))  # still M2.4-valid
        with self.assertRaises(ParityError):
            resolve(m, 'CARF', 20260820, ROOT)


if __name__ == '__main__':
    unittest.main()
