"""Run the public verification CLI and validate its portable evidence."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m11.artifacts import digest, read_json, verify_manifest


@unittest.skipUnless(importlib.util.find_spec('torch'), 'install requirements/m12-cpu.txt')
class VerificationTests(unittest.TestCase):
    def test_cli_exports_verified_evidence_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'new-run'
            command = [sys.executable, str(ROOT/'scripts/verify_m12.py'), '--config',
                       str(ROOT/'configs/m1.2/core.toml'), '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            pointer = read_json(output/'verification/complete.json')
            run = output/'verification'/pointer['attempt']
            self.assertEqual(digest(run/'receipt.json'), pointer['receipt_sha256'])
            verify_manifest(run, read_json(run/'receipt.json')['outputs'])
            summary = read_json(run/'summary.json')
            self.assertEqual(summary['kind'], 'synthetic_software_verification')
            self.assertEqual(summary['independent_review'], 'pending')
            self.assertGreater(summary['unit_tests']['run'], 0)
            self.assertEqual(summary['unit_tests']['skipped'], 0)
            self.assertEqual(set(summary['methods']), {'QARF', 'QPAF'})
            self.assertEqual(summary['methods']['QARF']['parameter_count'],
                             summary['methods']['QPAF']['parameter_count'])
            for method in summary['methods'].values():
                self.assertGreater(method['gradient_l1_initial'], 0.)
                self.assertLess(method['loss_final'], method['loss_initial'])
                self.assertTrue(method['retriever_frozen'])
            self.assertTrue((run/'verification.md').is_file())
            before = digest(run/'receipt.json')
            repeated = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(digest(run/'receipt.json'), before)

    def test_bad_config_fails_without_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)/'invalid.toml'
            config.write_text((ROOT/'configs/m1.2/core.toml').read_text(encoding='utf-8')
                              .replace('temperature = 1.0', 'temperature = 0.0'), encoding='utf-8')
            output = Path(tmp)/'must-not-exist'
            result = subprocess.run([sys.executable, str(ROOT/'scripts/verify_m12.py'),
                '--config', str(config), '--output', str(output)], capture_output=True,
                text=True, encoding='utf-8', cwd=ROOT)
            self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
            self.assertIn('temperature', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
