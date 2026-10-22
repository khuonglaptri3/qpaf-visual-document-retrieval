"""Hard-limit enforcement controls must fail closed unless an attributed OOM is observed."""
import importlib
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class MemoryProbeTests(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module('scripts.m36_memory_probe')
        self.ok = {'status': 'COMPLETED', 'target_mib': 2048, 'error_type': None, 'error_text': None,
                   'in_sandbox': {}}
        self.oom = {'status': 'FAILED', 'target_mib': 4608, 'error_type': 'FunctionError',
                    'error_text': 'Container ran out of memory (OOM)', 'in_sandbox': None}
        self.stats = {'input_success_count': 1, 'input_failure_count': 1,
                      'container_total_count': 2, 'container_error_count': 1}

    def test_constants_match_reviewed_design(self):
        self.assertEqual((self.api.PROBE_LIMIT_MIB, self.api.BELOW_TARGET_MIB, self.api.ABOVE_TARGET_MIB),
                         (4096, 2048, 4608))

    def test_touch_allocation_commits_requested_bytes(self):
        result = self.api.touch_allocation(8)
        self.assertEqual(result['allocated_bytes'], 8 * 2**20)
        if os.name != 'nt':  # resource.getrusage is Linux-only; the probe always runs on Linux
            self.assertGreater(result['ru_maxrss_bytes'], 0)

    def test_demonstrated_requires_below_success_and_attributed_above_oom(self):
        self.assertEqual(self.api.classify_controls(self.ok, self.oom, self.stats), 'ENFORCEMENT_DEMONSTRATED')

    def test_above_limit_completion_on_retry_is_not_demonstrated(self):
        stats = {**self.stats, 'input_success_count': 2, 'container_total_count': 3}
        self.assertEqual(self.api.classify_controls(self.ok, self.oom, stats), 'ENFORCEMENT_NOT_DEMONSTRATED')
        self.assertEqual(self.api.classify_controls(self.ok, {**self.ok, 'target_mib': 4608}, self.stats),
                         'ENFORCEMENT_NOT_DEMONSTRATED')

    def test_failure_without_oom_attribution_is_inconclusive(self):
        timeout = {**self.oom, 'error_type': 'TimeoutError', 'error_text': 'watchdog stopped app'}
        self.assertEqual(self.api.classify_controls(self.ok, timeout, {**self.stats, 'container_error_count': 0}),
                         'INCONCLUSIVE')
        self.assertEqual(self.api.classify_controls({**self.oom, 'target_mib': 2048}, self.oom, self.stats),
                         'INCONCLUSIVE')

    def test_oom_attribution_reads_error_text_or_provider_reason(self):
        self.assertTrue(self.api.oom_attributed('Killed: exit code 137', None))
        self.assertTrue(self.api.oom_attributed('', {'exit_reasons': ['OOM']}))
        self.assertFalse(self.api.oom_attributed('ImportError', {'exit_reasons': []}))

    def test_bound_verdict_only_when_demonstrated(self):
        runs = {'A02': {'limit_mib': 4096, 'success_marker': True, 'failed_calls': 0},
                'A03': {'limit_mib': 5120, 'success_marker': True, 'failed_calls': 0}}
        good = self.api.memory_bound_verdict('ENFORCEMENT_DEMONSTRATED', runs)
        self.assertEqual(good['issue_status'], 'RESOLVED_BY_ENFORCED_BOUND')
        self.assertEqual(good['runs']['A02'], {'bound': 'BELOW_LIMIT', 'limit_mib': 4096})
        self.assertFalse(good['exact_peak_available'])
        bad = self.api.memory_bound_verdict('INCONCLUSIVE', runs)
        self.assertEqual(bad['issue_status'], 'OPEN')
        failed = self.api.memory_bound_verdict('ENFORCEMENT_DEMONSTRATED',
                                               {**runs, 'A02': {**runs['A02'], 'failed_calls': 1}})
        self.assertEqual(failed['runs']['A02']['bound'], 'UNBOUNDED')


if __name__ == '__main__':
    unittest.main()
