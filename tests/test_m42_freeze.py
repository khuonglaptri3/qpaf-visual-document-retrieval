"""Real sealed-ID replay, tamper rejection, and create-once CLI behavior."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FreezeTests(unittest.TestCase):
    def setUp(self):
        script = ROOT / 'scripts/freeze_m42_baselines.py'
        self.assertTrue(script.exists(), 'M4.2 freeze verifier is not implemented')
        spec = importlib.util.spec_from_file_location('m42_freeze', script)
        self.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.api)

    def copy_inputs(self, target):
        for name in self.api.INPUTS:
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)

    def test_replays_actual_sealed_ids_without_claiming_real_inputs_ready(self):
        manifest = self.api.build_manifest(ROOT)
        self.assertEqual(manifest['splits']['counts'], {'train': 1600, 'validation': 400,
                                                       'confirmation': 8904})
        self.assertEqual(manifest['splits']['query_overlap'], 0)
        self.assertEqual(manifest['settings_check'], 'PASS')
        self.assertEqual(manifest['real_input_readiness'], 'BLOCKED')
        self.assertFalse(manifest['m42_accepted'])
        self.assertIsNone(manifest['real_fitted_weights'])
        self.assertGreater(len(manifest['missing_real_inputs']), 5)

    def test_rejects_split_tampering_before_any_fit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copy_inputs(root)
            (root / 'evidence/revisions/m4.1-001/train_ids.txt').write_text('other\n')
            with self.assertRaisesRegex(ValueError, 'split hash'):
                self.api.build_manifest(root)

    def test_rejects_m41_manifest_and_policy_tampering(self):
        for name in ['evidence/revisions/m4.1-001/manifest.json',
                     'evidence/M1_FINAL/02_protocol/candidate_policy.md']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.copy_inputs(root)
                (root / name).write_bytes((root / name).read_bytes()+b'\n')
                with self.assertRaisesRegex(ValueError, 'hash'):
                    self.api.build_manifest(root)

    def test_rejects_grid_change_and_claimed_real_fit(self):
        for key in ['grid', 'fit']:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.copy_inputs(root)
                path = root / 'configs/m4.2/freeze.json'
                config = json.loads(path.read_text(encoding='utf8'))
                if key == 'grid':
                    config['static_fit']['grid_denominator'] = 20
                else:
                    config['access']['real_static_fit_executed'] = True
                path.write_text(json.dumps(config), encoding='utf8')
                with self.assertRaises(ValueError):
                    self.api.build_manifest(root)

    def test_creation_rejects_contradictory_or_omitted_frozen_settings(self):
        for change in ['contradictory', 'missing']:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.copy_inputs(root)
                path = root / 'configs/m4.2/freeze.json'
                config = json.loads(path.read_text(encoding='utf8'))
                if change == 'contradictory':
                    config['static_fit']['tie_tolerance'] = .5
                    config['rrf']['rank_start'] = 0
                    config['normalization']['method'] = 'raw_scores'
                    config['shared_candidates']['rescore_all_three_channels'] = False
                else:
                    config['evaluation'] = {}
                    config['real_inputs'] = {}
                    config['access'] = {'owner_acceptance': 'PENDING'}
                path.write_text(json.dumps(config), encoding='utf8')
                with self.assertRaises(ValueError):
                    self.api.build_manifest(root)

    def test_fixture_cannot_validate_a_different_implementation_than_it_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copy_inputs(root)
            (root/'src/qpaf/m42/baselines.py').write_text('raise RuntimeError("broken")\n')
            with self.assertRaisesRegex(ValueError, 'implementation'):
                self.api.build_manifest(root)

    def test_verification_rejects_removed_inventory_entry_and_changed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copy_inputs(root)
            output = root / 'output'
            self.api.create(root, output)
            manifest_path = output / 'manifest.json'
            original = manifest_path.read_bytes()
            manifest = json.loads(original)
            manifest['files'].pop()
            manifest_path.write_text(json.dumps(manifest), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'manifest|implementation'):
                self.api.verify(root, output)
            manifest_path.write_bytes(original)
            (root / 'src/qpaf/m42/baselines.py').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'manifest|implementation'):
                self.api.verify(root, output)

    def test_create_once_and_verification_leave_input_and_output_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copy_inputs(root)
            output = root / 'output'
            self.api.create(root, output)
            before = {p.relative_to(root).as_posix(): p.read_bytes()
                      for p in root.rglob('*') if p.is_file()}
            result = self.api.verify(root, output)
            self.assertEqual(result['status'], 'PASS')
            with self.assertRaises(ValueError):
                self.api.create(root, output)
            self.assertEqual(before, {p.relative_to(root).as_posix(): p.read_bytes()
                                     for p in root.rglob('*') if p.is_file()})

    def test_cli_checks_readiness_and_never_overwrites_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copy_inputs(root)
            command = [sys.executable, str(ROOT/'scripts/freeze_m42_baselines.py'),
                       '--root', str(root), '--output-dir', str(root/'output')]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn('real-input readiness: BLOCKED', first.stdout)
            replay = subprocess.run(command+['--verify'], capture_output=True, text=True)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            duplicate = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn('already exists', duplicate.stderr)


if __name__ == '__main__':
    unittest.main()
