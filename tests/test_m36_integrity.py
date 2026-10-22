"""The independent reviewer must reject corruption and keep unmeasured gates open."""
import copy
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('scripts.audit_m36_integrity')
        except ModuleNotFoundError:
            self.fail('M3.6 independent auditor is not implemented')
        self.predictions = [{'query_id': 'q1', 'page_ids': ['a', 'b'],
                             'scores': [0.8, 0.3],
                             'weights': [[0.5, 0.25, 0.25], [0.5, 0.25, 0.25]]}]

    def test_small_replay_difference_is_reported_against_the_frozen_tolerance(self):
        replay = copy.deepcopy(self.predictions)
        replay[0]['scores'][0] += 1e-8
        result = self.api.compare_predictions(self.predictions, replay, 1e-7)
        self.assertEqual(result['query_count'], 1)
        self.assertEqual(result['candidate_count'], 2)
        self.assertAlmostEqual(result['score_max_abs_difference'], 1e-8)
        self.assertEqual(result['ranking_disagreements'], 0)

    def test_nan_and_infinity_cannot_hide_inside_a_maximum_difference(self):
        for field, value in [('scores', float('nan')), ('scores', float('inf')),
                             ('weights', float('nan'))]:
            with self.subTest(field=field, value=value):
                replay = copy.deepcopy(self.predictions)
                if field == 'scores':
                    replay[0][field][0] = value
                else:
                    replay[0][field][0][0] = value
                with self.assertRaises(self.api.AuditError):
                    self.api.compare_predictions(self.predictions, replay, 1e-7)

    def test_reordered_missing_or_drifted_predictions_are_rejected(self):
        for change in ('pages', 'scores', 'weights', 'missing'):
            with self.subTest(change=change):
                replay = copy.deepcopy(self.predictions)
                if change == 'pages':
                    replay[0]['page_ids'].reverse()
                elif change == 'scores':
                    replay[0]['scores'][0] += 0.001
                elif change == 'weights':
                    replay[0]['weights'][0] = [0.25, 0.5, 0.25]
                else:
                    replay = []
                with self.assertRaises(self.api.AuditError):
                    self.api.compare_predictions(self.predictions, replay, 1e-7)

    def test_cpu_zero_cuda_allocation_cannot_pass_the_gpu_gate(self):
        auth = {'runtime': {'device': 'cpu', 'dtype': 'float64', 'threads': 1},
                'limits': {'wall_time_seconds': 3600},
                'sealed_inputs': {'split': {'counts': {'train': 799, 'validation': 171, 'test': 172}}}}
        telemetry = {'device': 'cpu', 'dtype': 'float64', 'threads': 1,
                     'peak_rss_mb': 754.0, 'phases': [
                         {'phase': 'train', 'seconds': 61.0, 'peak_cuda_allocated_mb': 0.0}]}
        result = self.api.review_resources(auth, {'wall_seconds': 76.0}, telemetry)
        self.assertEqual(result['verdict'], 'BLOCKED')
        self.assertEqual(result['cuda_gate'], 'NOT_MEASURED')
        self.assertEqual(result['latency_gate'], 'NOT_MEASURED')
        self.assertEqual(result['development_unique_queries'], 970)

    def test_nonfinite_checkpoint_state_is_rejected(self):
        import torch
        for value in ({'state': torch.tensor([1., float('nan')])},
                      {'history': [{'loss': float('inf')}] }):
            with self.subTest(value=value):
                with self.assertRaises(self.api.AuditError):
                    self.api.check_finite_tree(value)
        self.assertEqual(self.api.check_finite_tree({'state': torch.tensor([1., 2.]), 'epoch': 1}), 3)

    def test_existing_review_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'review.json'
            path.write_bytes(b'preserve me')
            with self.assertRaises(self.api.AuditError):
                self.api.main(['--output', str(path)])
            self.assertEqual(path.read_bytes(), b'preserve me')

    def test_fresh_worker_accepts_a_windows_venv_launcher_but_not_an_unrelated_process(self):
        self.assertTrue(hasattr(self.api, 'check_fresh_process'), 'launcher ancestry is not checked')
        self.api.check_fresh_process({'worker_pid': 40, 'parent_pid': 10, 'ancestor_pids': [10, 2]}, 10)
        self.api.check_fresh_process({'worker_pid': 40, 'parent_pid': 30, 'ancestor_pids': [30, 10, 2]}, 10)
        for worker in ({'worker_pid': 10, 'parent_pid': 2, 'ancestor_pids': [2]},
                       {'worker_pid': 40, 'parent_pid': 30, 'ancestor_pids': [30, 2]}):
            with self.assertRaises(self.api.AuditError):
                self.api.check_fresh_process(worker, 10)

    def test_persisted_step_losses_norms_and_coverage_are_verified(self):
        self.assertTrue(hasattr(self.api, 'check_step_telemetry'), 'step telemetry is not audited')
        epochs = [{'epoch': '1', 'train_steps': '2'}]
        steps = [{'epoch': '1', 'step': str(i), 'loss': '0.5', 'grad_norm': '0.1',
                  'valid_queries': '2', 'skipped_queries': '0', 'pairs': '2'} for i in range(2)]
        self.assertEqual(self.api.check_step_telemetry(epochs, steps)['step_count'], 2)
        for change in ('loss', 'grad_norm', 'missing', 'duplicate', 'jump'):
            with self.subTest(change=change):
                broken = copy.deepcopy(steps)
                if change in ('loss', 'grad_norm'):
                    broken[0][change] = 'nan'
                elif change == 'missing':
                    broken.pop()
                elif change == 'jump':
                    broken[1]['step'] = '999'
                else:
                    broken[1]['step'] = '0'
                with self.assertRaises(self.api.AuditError):
                    self.api.check_step_telemetry(epochs, broken)

    def test_m35_acceptance_must_belong_to_the_reviewed_pair_and_report(self):
        self.assertTrue(hasattr(self.api, 'check_comparison_acceptance'), 'comparison identities are not audited')
        run_ids = {'QARF': 'qarfrun', 'QPAF': 'qpafrun'}
        pins = {'qpaf_authorization': 'a'*64, 'qarf_authorization': 'b'*64}
        event = {'run_id': 'qpafrun', 'comparator_run_id': 'qarfrun',
                 'authorization_manifest_sha256': 'a'*64, 'verification_ref': 'comparison.json',
                 'verification_sha256': 'c'*64, 'independent_reviewer': 'Thanh'}
        comparison = {'task_id': 'M3.5', 'technical_verdict': 'PASS', 'run_ids': run_ids,
                      'pins_sha256': pins}
        signoff = {'task_id': 'M3.5', 'decision': 'ACCEPTED', 'reviewer': 'Thanh',
                   'technical_report_ref': 'comparison.json', 'technical_report_sha256': 'c'*64}
        self.api.check_comparison_acceptance(event, comparison, signoff, run_ids, pins)
        missing_event, missing_signoff = copy.deepcopy(event), copy.deepcopy(signoff)
        del missing_event['independent_reviewer']
        del missing_signoff['reviewer']
        with self.assertRaises(self.api.AuditError):
            self.api.check_comparison_acceptance(missing_event, comparison, missing_signoff, run_ids, pins)
        for target, key, value in [('event', 'run_id', 'other-run'),
                                   ('event', 'authorization_manifest_sha256', 'd'*64),
                                   ('report', 'technical_verdict', 'FAIL'),
                                   ('signoff', 'technical_report_sha256', 'd'*64)]:
            with self.subTest(target=target, key=key):
                values = {'event': copy.deepcopy(event), 'report': copy.deepcopy(comparison),
                          'signoff': copy.deepcopy(signoff)}
                values[target][key] = value
                with self.assertRaises(self.api.AuditError):
                    self.api.check_comparison_acceptance(values['event'], values['report'], values['signoff'],
                                                         run_ids, pins)


if __name__ == '__main__':
    unittest.main()
