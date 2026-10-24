"""M4.3 frozen QPAF: branch rule, pins, source drift, replay thresholds, record replay."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m43 import freeze  # noqa: E402

PASSING_WORKER = {'method': 'QPAF', 'status': 'PASS_FRESH_PROCESS', 'query_count': 171,
                  'candidate_count': 82000, 'score_max_abs_difference': 0.0,
                  'weight_max_abs_difference': 0.0, 'tolerance': 1e-7, 'ranking_disagreements': 0,
                  'metric_max_abs_difference': 0.0, 'worker_pid': 7, 'parent_pid': 6}


class BranchTests(unittest.TestCase):
    def test_only_go_continue_qpaf_freezes(self):
        result = freeze.branch_disposition({'decision': 'GO', 'm4_branch': 'continue_qpaf'})
        self.assertEqual(result, {'g2_decision': 'GO', 'm4_branch': 'continue_qpaf',
                                  'frozen_qpaf': 'FROZEN', 'revise_once': 'NOT_TRIGGERED',
                                  'negative_qpaf_result': 'NOT_TRIGGERED'})
        for decision, branch in [('PARTIAL–INVESTIGATE', 'revise_once'),
                                 ('NO-GO–PIVOT', 'negative_qpaf_result'),
                                 ('BLOCKED', None), ('GO', 'revise_once')]:
            with self.subTest(decision=decision), self.assertRaises(freeze.FreezeError):
                freeze.branch_disposition({'decision': decision, 'm4_branch': branch})


class PinTests(unittest.TestCase):
    def test_pin_drift_names_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'a.json').write_bytes(b'{}\n')
            good = hashlib.sha256(b'{}\n').hexdigest()
            self.assertEqual(freeze.check_pins(root, {'a': ('a.json', good)}), {'a': good})
            with self.assertRaisesRegex(freeze.FreezeError, 'a.json'):
                freeze.check_pins(root, {'a': ('a.json', '0'*64)})
            with self.assertRaisesRegex(freeze.FreezeError, 'missing.json'):
                freeze.check_pins(root, {'b': ('missing.json', good)})

    def test_source_drift_refuses(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'m.py').write_bytes(b'x = 1\n')
            digest = hashlib.sha256(b'x = 1\n').hexdigest()
            provenance = {'source': {'files': [{'path': 'm.py', 'sha256': digest}]}}
            self.assertEqual(freeze.check_sources(root, provenance, ('m.py',)), {'m.py': digest})
            provenance['source']['files'][0]['sha256'] = '0'*64
            with self.assertRaisesRegex(freeze.FreezeError, 'm.py'):
                freeze.check_sources(root, provenance, ('m.py',))
            with self.assertRaisesRegex(freeze.FreezeError, 'n.py'):
                freeze.check_sources(root, {'source': {'files': []}}, ('n.py',))


class ReplayTests(unittest.TestCase):
    def test_replay_thresholds(self):
        kept = freeze.check_replay(PASSING_WORKER)
        self.assertEqual(set(kept), {'query_count', 'candidate_count', 'score_max_abs_difference',
                                     'weight_max_abs_difference', 'ranking_disagreements',
                                     'metric_max_abs_difference', 'tolerance'})
        for key, value in [('score_max_abs_difference', 2e-7), ('weight_max_abs_difference', 2e-7),
                           ('ranking_disagreements', 1), ('metric_max_abs_difference', 1e-11),
                           ('status', 'FAILED'), ('query_count', 170)]:
            worker = dict(PASSING_WORKER, **{key: value})
            with self.subTest(key=key), self.assertRaises(freeze.FreezeError):
                freeze.check_replay(worker)


class CompareTests(unittest.TestCase):
    def test_compare_freeze(self):
        stored = {'source_commit': 'old', 'frozen_method': {'selected_epoch': 19}}
        freeze.compare_freeze(stored, copy.deepcopy(stored), is_ancestor=lambda commit: False)
        changed = {'source_commit': 'old', 'frozen_method': {'selected_epoch': 20}}
        with self.assertRaises(freeze.FreezeError):
            freeze.compare_freeze(stored, changed, is_ancestor=lambda commit: True)
        later = dict(stored, source_commit='new')
        freeze.compare_freeze(stored, later, is_ancestor=lambda commit: commit == 'old')
        with self.assertRaises(freeze.FreezeError):
            freeze.compare_freeze(stored, later, is_ancestor=lambda commit: False)


class CreateTests(unittest.TestCase):
    def test_create_refuses_existing_output_before_replay(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(freeze, 'collect', side_effect=AssertionError('replayed')) as collect:
            with self.assertRaisesRegex(freeze.FreezeError, 'exists'):
                freeze.create(ROOT, Path(folder))
            collect.assert_not_called()


SEAL_SCORES = ROOT/'results/m3.1/RUN-QPAF-M3_1-SEAL-001-20261021T142631Z-A01/inputs/score_cache.parquet'


@unittest.skipUnless(SEAL_SCORES.is_file(), 'sealed M3.1 score cache is not restored')
class RealFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record, cls.verification = freeze.collect(ROOT)

    def test_real_freeze_record(self):
        record = self.record
        self.assertEqual(record['branch_disposition']['m4_branch'], 'continue_qpaf')
        method = record['frozen_method']
        self.assertEqual(method['checkpoint']['sha256'],
                         'e4b00ab49e186fffe8b369e26491873304b61177c11fd2ce0f455158e30e5c8e')
        self.assertEqual(method['checkpoint']['selected_epoch'], 19)
        self.assertEqual(method['seed'], 20260820)
        self.assertEqual(record['matched_comparator']['checkpoint']['sha256'],
                         'e44ac1a4f3887700a70914fdba8a3e7b35330244e746253d1cd828508be30914')
        for name in ('QPAF', 'QARF'):
            self.assertLessEqual(record['replay'][name]['score_max_abs_difference'], 1e-7)
        self.assertIs(record['test_labels_opened'], False)
        self.assertEqual(self.verification['freeze_sha256'], freeze.record_sha256(record))

    def test_verify_refuses_tampered_record(self):
        tampered = copy.deepcopy(self.record)
        tampered['frozen_method']['checkpoint']['selected_epoch'] = 20
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'m4.3-test'
            output.mkdir()
            freeze.write_json(output/'method_freeze.json', tampered)
            freeze.write_json(output/'verification.json',
                              dict(self.verification, freeze_sha256=freeze.sha(output/'method_freeze.json')))
            with mock.patch.object(freeze, 'collect', return_value=(self.record, self.verification)), \
                    self.assertRaisesRegex(freeze.FreezeError, 'differs'):
                freeze.verify(ROOT, output)


if __name__ == '__main__':
    unittest.main()
