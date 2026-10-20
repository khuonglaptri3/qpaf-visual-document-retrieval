"""M2.7 matched QARF/QPAF config freeze and fail-closed parity checks."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
HAS_TORCH = importlib.util.find_spec('torch') is not None

from qpaf.m24.config import validate
from qpaf.m27 import matched
from qpaf.m27.matched import ParityError, check_parity, load_base, load_manifest, resolve, semantic_diff

MANIFEST = ROOT/'configs/m2.7/matched.json'
SEEDS = (20260820, 20260821, 20260822)
ROOT_FILES = ('configs/m2.7/shared_base.toml', 'configs/m2.7/matched.json', 'configs/m2.4/pipeline.toml',
              'configs/m2.5/freeze.json', 'evidence/revisions/m2.1-002/data_split_manifest.json')


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
            ('robustness seeds changed', lambda m: m['seeds'].update(robustness=[1, 2, 3], development_gate=1)),
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


def make_root(directory):
    """Byte copies of every file check_parity reads, so tampering never touches the repo."""
    root = Path(directory)/'repo'
    for name in ROOT_FILES:
        (root/name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, root/name)
    return root


def rehash(root):
    """Re-pin the base hash after an intentional base edit."""
    path = root/'configs/m2.7/matched.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['base_config']['sha256'] = hashlib.sha256((root/data['base_config']['path']).read_bytes()).hexdigest()
    path.write_text(json.dumps(data), encoding='utf-8')


class ParityChecksTests(TempDirTest):
    def setUp(self):
        super().setUp()
        self.root = make_root(self.tmp)

    def manifest(self):
        return load_manifest(self.root/'configs/m2.7/matched.json')

    def edit_base(self, old, new):
        path = self.root/'configs/m2.7/shared_base.toml'
        path.write_bytes(path.read_bytes().replace(old, new))

    @unittest.skipUnless(HAS_TORCH, 'install requirements-learned-local.txt for parity checks')
    def test_committed_configs_pass(self):
        report = check_parity(load_manifest(MANIFEST), ROOT)
        self.assertEqual(report['m24_drift'],
                         {'experiment_id': ['QPAF-M2_4-PIPELINE-001', 'QPAF-M2_7-MTH-001']})
        self.assertEqual(report['pairs'], {str(s): {'gate_granularity': ['query', 'page']} for s in SEEDS})
        self.assertTrue(report['methods_match_runner'])
        self.assertEqual(set(report['initialization']), {str(s) for s in SEEDS})
        for seed, item in report['initialization'].items():
            self.assertEqual(item, {'identical': True, 'parameter_count': 42}, seed)
        # 24 synthetic train queries in batches of 16 -> 2 batches per epoch, over 2 epochs.
        self.assertEqual(report['data_order'], {'identical': True, 'epochs': 2, 'batches': 4,
                                                'fixture': 'qpaf.m24.synthetic:20260820'})
        self.assertEqual(report['pending_inputs'], ['candidate_set', 'qrels', 'score_cache'])
        self.assertTrue(all(item['verified'] for item in report['shared_inputs'].values()))
        self.assertEqual(report['base_config_sha256'],
                         hashlib.sha256((ROOT/'configs/m2.7/shared_base.toml').read_bytes()).hexdigest())

    def test_edited_base_fails_hash(self):
        self.edit_base(b'epochs = 20', b'epochs = 20 # edited')
        with self.assertRaisesRegex(ParityError, 'sha256'):
            check_parity(self.manifest(), self.root)

    def test_base_drift_from_m24_fails(self):
        self.edit_base(b'learning_rate = 0.01', b'learning_rate = 0.02')
        rehash(self.root)
        with self.assertRaisesRegex(ParityError, 'M2.4'):
            check_parity(self.manifest(), self.root)

    def test_base_experiment_id_mismatch_fails(self):
        self.edit_base(b'QPAF-M2_7-MTH-001', b'QPAF-M2_7-MTH-999')
        rehash(self.root)
        with self.assertRaisesRegex(ParityError, 'experiment_id'):
            check_parity(self.manifest(), self.root)

    def test_swapped_granularity_fails(self):
        manifest = self.manifest()
        manifest['methods'] = {'QARF': {'gate_granularity': 'page'}, 'QPAF': {'gate_granularity': 'query'}}
        with self.assertRaisesRegex(ParityError, 'METHODS'):
            check_parity(manifest, self.root)

    def test_split_manifest_hash_mismatch_fails(self):
        with (self.root/'evidence/revisions/m2.1-002/data_split_manifest.json').open('ab') as stream:
            stream.write(b' ')
        with self.assertRaisesRegex(ParityError, 'split_manifest'):
            check_parity(self.manifest(), self.root)

    def test_second_differing_field_fails(self):
        real = matched.resolve

        def tampered(manifest, method, seed, root):
            config = real(manifest, method, seed, root)
            if method == 'QPAF':
                config['training']['learning_rate'] = 0.02
            return config
        with mock.patch.object(matched, 'resolve', tampered):
            with self.assertRaisesRegex(ParityError, 'gate_granularity'):
                check_parity(self.manifest(), self.root)

    @unittest.skipUnless(HAS_TORCH, 'install requirements-learned-local.txt for parity checks')
    def test_initialization_mismatch_fails(self):
        from qpaf.m24 import trainer
        real = trainer.build_model

        def shifted(config, method):
            if method == 'QPAF':
                config = copy.deepcopy(config)
                config['training']['seed'] += 1
            return real(config, method)
        with mock.patch.object(trainer, 'build_model', shifted):
            with self.assertRaisesRegex(ParityError, 'initialization'):
                check_parity(self.manifest(), self.root)

    @unittest.skipUnless(HAS_TORCH, 'install requirements-learned-local.txt for parity checks')
    def test_data_order_mismatch_fails(self):
        # A different batch seed permutes the synthetic queries while every batch
        # keeps the same size and pair count, so only query-ID order reveals it.
        from qpaf.m24 import trainer
        real = trainer.train

        def reseeded(config, method, *args, **kwargs):
            if method == 'QPAF':
                config = copy.deepcopy(config)
                config['training']['seed'] += 1
            return real(config, method, *args, **kwargs)
        with mock.patch.object(trainer, 'train', reseeded):
            with self.assertRaisesRegex(ParityError, 'data order'):
                check_parity(self.manifest(), self.root)

    def test_missing_torch_fails_closed(self):
        with mock.patch.dict(sys.modules, {'torch': None}):
            with self.assertRaisesRegex(ParityError, 'torch is required'):
                check_parity(self.manifest(), self.root)


@unittest.skipUnless(HAS_TORCH, 'install requirements-learned-local.txt for the verifier CLI')
class ScriptTests(TempDirTest):
    def run_script(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(ROOT/'scripts/verify_m27_matched.py'), *args],
                              capture_output=True, text=True, encoding='utf-8', cwd=cwd)

    def test_prints_report_from_any_cwd(self):
        result = self.run_script(cwd=self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['independent_review'], 'PENDING')
        self.assertEqual(report['wall_time_cap_minutes'], 60)
        self.assertEqual(report['status'], 'FROZEN_CONFIG_PENDING_M2.8_INPUTS')
        self.assertEqual(report['task_id'], 'M2.7')
        self.assertEqual(report['experiment_id'], 'QPAF-M2_7-MTH-001')
        self.assertEqual(report['manifest_sha256'], hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
        self.assertEqual(set(report['source_sha256']),
                         {'src/qpaf/m27/matched.py', 'src/qpaf/m24/config.py', 'src/qpaf/m24/dataset.py',
                          'src/qpaf/m24/trainer.py', 'src/qpaf/m24/evaluator.py', 'src/qpaf/m24/checkpoint.py',
                          'src/qpaf/m12/model.py', 'src/qpaf/m12/features.py', 'src/qpaf/m12/losses.py',
                          'scripts/run_m24_pipeline.py', 'scripts/verify_m27_matched.py'})
        self.assertEqual(report['pairs'], {str(s): {'gate_granularity': ['query', 'page']} for s in SEEDS})

    def test_output_is_create_once(self):
        target = self.tmp/'verification.json'
        first_run = self.run_script('--output', str(target))
        self.assertEqual(first_run.returncode, 0, first_run.stderr)
        first = target.read_bytes()
        self.assertNotIn(b'\r', first)
        again = self.run_script('--output', str(target))
        self.assertEqual(again.returncode, 2)
        self.assertIn('Error:', again.stderr)
        self.assertEqual(target.read_bytes(), first)

    def test_parity_error_exits_2(self):
        data = json.loads(MANIFEST.read_text(encoding='utf-8'))
        data['extra'] = 1
        result = self.run_script('--manifest', str(write_manifest(self.tmp, data)))
        self.assertEqual(result.returncode, 2)
        self.assertIn('Error:', result.stderr)


if __name__ == '__main__':
    unittest.main()
