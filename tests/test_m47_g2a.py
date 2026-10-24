"""M4.7 G2A record: prerequisites, pins, replay contract, frozen items, create-once and verify."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m47 import g2a  # noqa: E402

PASS = lambda root, argv: {'status': 'PASS', 'argv': argv}  # noqa: E731
JSON_PINS = {
    'g2_decision': {'decision': 'GO', 'm4_branch': 'continue_qpaf'},
    'g2_confirmation': {'decision': 'CONFIRMED'},
    'm43_confirmation': {'decision': 'CONFIRMED'},
    'm45_acceptance': {'decision': 'ACCEPTED'},
    'm46_final_confirmation': {'decision': 'CONFIRMED', 'm4_branch_final': 'continue_qpaf'},
    'm42_shared_inputs': {'sealed_test_qrels_sha256': 'f'*64},
}


def fixture(root, **overrides):
    contents = {**JSON_PINS, **overrides}
    for name, (relative, _) in g2a.PINS.items():
        path = Path(root)/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if name in contents:
            path.write_text(json.dumps(contents[name]), encoding='utf8')
        else:
            path.write_text(f'{name}\n', encoding='utf8')
    return {name: (relative, None) for name, (relative, _) in g2a.PINS.items()}


class PrerequisiteTests(unittest.TestCase):
    def test_prerequisites_refuse_with_the_file_named(self):
        with tempfile.TemporaryDirectory() as folder:
            g2a.prerequisites(folder, fixture(folder))
        bad = {'g2_decision': {'decision': 'NO-GO–PIVOT', 'm4_branch': 'negative_qpaf_result'},
               'g2_confirmation': {'decision': 'PENDING'},
               'm43_confirmation': {'decision': 'PENDING'},
               'm45_acceptance': {'decision': 'PENDING'},
               'm46_final_confirmation': {'decision': 'CONFIRMED', 'm4_branch_final': 'negative_qpaf_result'}}
        bad_decision = {'m46_final_confirmation': {'decision': 'PENDING', 'm4_branch_final': 'continue_qpaf'}}
        for name, value in [*bad.items(), *bad_decision.items()]:
            with self.subTest(name), tempfile.TemporaryDirectory() as folder:
                pins = fixture(folder, **{name: value})
                with self.assertRaisesRegex(g2a.G2AError, Path(pins[name][0]).name):
                    g2a.prerequisites(folder, pins)


class PinTests(unittest.TestCase):
    def test_missing_or_drifted_pin_names_the_path(self):
        with tempfile.TemporaryDirectory() as folder:
            pins = fixture(folder)
            relative = pins['oracle'][0]
            (Path(folder)/relative).unlink()
            with self.assertRaisesRegex(g2a.G2AError, Path(relative).name):
                g2a.collect(folder, pins, replay=PASS)
        with tempfile.TemporaryDirectory() as folder:
            pins = fixture(folder)
            relative = pins['m42_test_ids'][0]
            pins['m42_test_ids'] = (relative, '0'*64)
            with self.assertRaisesRegex(g2a.G2AError, Path(relative).name):
                g2a.collect(folder, pins, replay=PASS)


class ReplayTests(unittest.TestCase):
    def test_replay_must_print_pass(self):
        bodies = {'fail': 'print(\'{"status": "FAIL"}\')', 'silent': 'pass',
                  'exit': 'import sys; print(\'{"status": "PASS"}\'); sys.exit(2)', 'text': 'print("ok")'}
        with tempfile.TemporaryDirectory() as folder:
            for name, body in bodies.items():
                (Path(folder)/f'{name}.py').write_text(body, encoding='utf8')
                with self.subTest(name), self.assertRaises(g2a.G2AError):
                    g2a.run_replay(folder, [f'{name}.py'])
            (Path(folder)/'ok.py').write_text('print(\'{"status": "PASS", "x": 1}\')', encoding='utf8')
            self.assertEqual(g2a.run_replay(folder, ['ok.py']), {'status': 'PASS', 'x': 1})


class RecordTests(unittest.TestCase):
    def test_record_freezes_the_spec_items(self):
        with tempfile.TemporaryDirectory() as folder:
            pins = fixture(folder)
            record, verification = g2a.collect(folder, pins, replay=PASS)
            ids_sha = hashlib.sha256((Path(folder)/pins['m42_test_ids'][0]).read_bytes()).hexdigest()
        self.assertEqual(record['status'], 'G2A_FROZEN_TECHNICAL_PASS_PENDING_OWNER_CONFIRMATION')
        self.assertEqual(record['held_out'], {'dataset': 'Qiuchen-Wang/ViDoSeek', 'split': 'test', 'query_count': 172,
                                              'ids_sha256': ids_sha, 'sealed_qrels_sha256': 'f'*64,
                                              'labels_opened': False})
        self.assertEqual(record['vimdoc']['status'], 'NOT_RUN_DEFERRED')
        self.assertEqual([r['id'] for r in record['roster']], [f'R{i}' for i in range(1, 11)])
        self.assertEqual(record['baselines']['co_strongest'], ['train_fitted_static'])
        self.assertEqual(record['main_method']['selected_epoch'], 19)
        self.assertEqual(len(record['limitations']), 3)
        self.assertIs(record['authorizes_execution'], False)
        self.assertEqual(set(verification['replays']), {'m43', 'm46'})

    def test_create_once_refuses_before_replaying(self):
        replay = mock.Mock(side_effect=PASS)
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(g2a, 'git', lambda root, *args: '' if args[0] == 'status' else 'abc123'):
            pins, out = fixture(folder), Path(folder)/'out'
            g2a.create(folder, out, pins, replay=replay)
            calls = replay.call_count
            with self.assertRaises(g2a.G2AError):
                g2a.create(folder, out, pins, replay=replay)
            self.assertEqual(replay.call_count, calls)

    def test_verify_equality_ancestry_and_tamper(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(g2a, 'git', lambda root, *args: '' if args[0] == 'status' else 'abc123'):
            pins, out = fixture(folder), Path(folder)/'out'
            g2a.create(folder, out, pins, replay=PASS)
            with mock.patch.object(g2a, 'is_ancestor', lambda root, commit: True):
                self.assertEqual(g2a.verify(folder, out, pins, replay=PASS)['status'], 'PASS')
            with mock.patch.object(g2a, 'is_ancestor', lambda root, commit: False), \
                    self.assertRaises(g2a.G2AError):
                g2a.verify(folder, out, pins, replay=PASS)
            path = out/'g2a_freeze.json'
            path.write_bytes(path.read_bytes().replace(b'NOT_RUN_DEFERRED', b'RUN', 1))
            with mock.patch.object(g2a, 'is_ancestor', lambda root, commit: True), \
                    self.assertRaises(g2a.G2AError):
                g2a.verify(folder, out, pins, replay=PASS)


if __name__ == '__main__':
    unittest.main()
