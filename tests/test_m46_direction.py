"""M4.6 direction record: prerequisites, gate-driven status, pins, create-once and replay."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m46 import direction  # noqa: E402

GATE = {'loss': 'v2_loss', 'spearman': 0.36, 'min_loss_weights': [0.6, 0.0, 0.4], 'min_loss': 0.43,
        'min_loss_ndcg': 0.79, 'max_ndcg': 0.86, 'G_A': 'FAIL', 'G_B': 'FAIL', 'status': 'REVISION_GATE_FAILED'}


def fixture(root, **overrides):
    """Minimal files behind every pin; `overrides` maps pin name -> replacement JSON."""
    files = {
        'g2_decision': {'decision': 'GO', 'm4_branch': 'continue_qpaf'},
        'g2_confirmation': {'decision': 'CONFIRMED'},
        'm43_freeze': {'branch_disposition': {'m4_branch': 'continue_qpaf'}},
        'm43_confirmation': {'decision': 'CONFIRMED'},
        'm44_mth_manifest': {}, 'm44_orc_manifest': {},
        'm45_verification': {'selection': {'validation_ndcg_at_10': {
            'train_fitted_static': 0.871, 'qpaf': 0.866, 'learned_qarf': 0.752}},
            'uncertainty': {'qpaf_minus_baseline_ndcg_at_10': {'train_fitted_static': {
                'mean_delta': -0.005, 'ci95': [-0.013, 0.003], 'wtl': {'wins': 3, 'ties': 161, 'losses': 7}}}}},
        'm45_acceptance': {'decision': 'ACCEPTED'},
        'probe': {'gate_v1': {**GATE, 'loss': 'v1_loss'}, 'gate_v2': GATE},
        'owner_confirmation': {'decision': 'CONFIRMED', 'm4_branch': 'revise_once'},
    }
    files.update(overrides)
    for name, (relative, _) in direction.PINS.items():
        path = Path(root)/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if name in files:
            path.write_text(json.dumps(files[name]), encoding='utf8')
        else:
            path.write_text(f'# {name}\n', encoding='utf8')
    return {name: (relative, None) for name, (relative, _) in direction.PINS.items()}


class PrerequisiteTests(unittest.TestCase):
    def test_prerequisites_require_confirmed_go_freeze_and_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            direction.prerequisites(folder, fixture(folder))
        bad = {'g2_decision': {'decision': 'NO-GO–PIVOT', 'm4_branch': 'negative_qpaf_result'},
               'g2_confirmation': {'decision': 'PENDING'},
               'm43_confirmation': {'decision': 'PENDING'},
               'm45_acceptance': {'decision': 'PENDING'},
               'owner_confirmation': {'decision': 'CONFIRMED', 'm4_branch': 'continue_qpaf'}}
        for name, value in bad.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as folder:
                pins = fixture(folder, **{name: value})
                with self.assertRaisesRegex(direction.DirectionError, Path(pins[name][0]).name):
                    direction.prerequisites(folder, pins)


class StatusTests(unittest.TestCase):
    def test_record_branch_and_status_follow_the_gate(self):
        self.assertEqual(direction.direction_status('PASS'), 'REVISE_ONCE_GATE_PASSED_AWAITING_A004_APPROVAL')
        self.assertEqual(direction.direction_status('REVISION_GATE_FAILED'),
                         'REVISION_GATE_FAILED_RETURN_TO_RESEARCH_LEAD')
        with self.assertRaises(direction.DirectionError):
            direction.direction_status('MAYBE')
        with tempfile.TemporaryDirectory() as folder:
            record = direction.collect(folder, fixture(folder))
        self.assertEqual((record['m4_branch'], record['status']),
                         ('revise_once', 'REVISION_GATE_FAILED_RETURN_TO_RESEARCH_LEAD'))
        self.assertEqual(record['amendment']['state'], 'NOT_ADOPTED_GATE_FAILED')
        self.assertFalse(record['authorizes_execution'])
        self.assertEqual(record['evidence']['qpaf_minus_train_fitted_static']['mean_delta'], -0.005)


class PinTests(unittest.TestCase):
    def test_pin_drift_refuses(self):
        with tempfile.TemporaryDirectory() as folder:
            pins = fixture(folder)
            relative = pins['m44_mth_manifest'][0]
            pins['m44_mth_manifest'] = (relative, '0'*64)
            with self.assertRaisesRegex(ValueError, Path(relative).name):
                direction.collect(folder, pins)


class RecordTests(unittest.TestCase):
    def test_create_once_and_verify_equality(self):
        def fake_git(root, *args):
            return '' if args[0] == 'status' else 'abc123'
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(direction, 'git', fake_git), \
                mock.patch.object(direction, 'is_ancestor', lambda root, commit: True):
            pins = fixture(folder)
            out = Path(folder)/'out'
            out.mkdir()
            direction.create(folder, out, pins)
            with self.assertRaises(direction.DirectionError):
                direction.create(folder, out, pins)
            self.assertEqual(direction.verify(folder, out, pins)['status'], 'PASS')
            path = out/'decision.json'
            path.write_bytes(path.read_bytes().replace(b'revise_once', b'revise_twice', 1))
            with self.assertRaises(direction.DirectionError):
                direction.verify(folder, out, pins)


if __name__ == '__main__':
    unittest.main()
