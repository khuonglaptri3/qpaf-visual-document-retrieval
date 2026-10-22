"""Hard-limit enforcement controls must fail closed unless an attributed OOM is observed."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
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

    def test_provider_retry_of_above_control_is_demonstrated_only_if_every_retry_errored(self):
        retried = {**self.stats, 'container_total_count': 3, 'container_error_count': 2}
        self.assertEqual(self.api.classify_controls(self.ok, self.oom, retried), 'ENFORCEMENT_DEMONSTRATED')
        below_errored = {**self.stats, 'container_total_count': 3, 'container_error_count': 1}
        self.assertEqual(self.api.classify_controls(self.ok, self.oom, below_errored), 'INCONCLUSIVE')

    def test_missing_or_wrong_provider_counts_are_inconclusive(self):
        for stats in ({}, {**self.stats, 'input_failure_count': 0}, {**self.stats, 'input_success_count': '1'},
                      {k: v for k, v in self.stats.items() if k != 'container_total_count'}):
            self.assertEqual(self.api.classify_controls(self.ok, self.oom, stats), 'INCONCLUSIVE')

    def test_oom_markers_match_words_not_substrings(self):
        self.assertFalse(self.api.oom_attributed('No room left on device', None))
        self.assertFalse(self.api.oom_attributed('container ta-01ZOOMx failed', None))
        self.assertTrue(self.api.oom_attributed('worker OOM-killed', None))
        self.assertTrue(self.api.oom_attributed('process exited: exit code: 137', None))

    def test_provider_reason_attributes_only_when_errored_containers_are_above_controls(self):
        generic = {**self.oom, 'error_text': 'Function failed'}
        stats = {**self.stats, 'exit_reasons': ['OOMKilled']}
        self.assertEqual(self.api.classify_controls(self.ok, generic, stats), 'ENFORCEMENT_DEMONSTRATED')
        self.assertEqual(self.api.classify_controls(self.ok, generic, {**self.stats, 'exit_reasons': []}),
                         'INCONCLUSIVE')

    def test_bound_verdict_requires_both_reference_runs_with_strict_types(self):
        good = {'A02': {'limit_mib': 4096, 'success_marker': True, 'failed_calls': 0},
                'A03': {'limit_mib': 5120, 'success_marker': True, 'failed_calls': 0}}
        for runs in ({}, {'A03': good['A03']},
                     {**good, 'A02': {**good['A02'], 'success_marker': 'false'}},
                     {**good, 'A02': {**good['A02'], 'limit_mib': 5120}}):
            self.assertEqual(self.api.memory_bound_verdict('ENFORCEMENT_DEMONSTRATED', runs)['issue_status'], 'OPEN')

    def test_below_failure_stops_before_the_above_call(self):
        calls, written = [], {}

        def call(target):
            calls.append(target)
            raise RuntimeError('CUDA init failed')
        with self.assertRaises(RuntimeError):
            self.api.run_controls(call, lambda name, record: written.update({name: record}))
        self.assertEqual(calls, [2048])
        self.assertEqual(written['below']['status'], 'FAILED')
        self.assertNotIn('above', written)

    def test_above_failure_is_recorded_not_raised(self):
        written = {}

        def call(target):
            if target == 4608:
                raise RuntimeError('out of memory')
            return dict(self.ok)
        self.api.run_controls(call, lambda name, record: written.update({name: record}))
        self.assertEqual((written['below']['status'], written['above']['status']), ('COMPLETED', 'FAILED'))

    def test_missing_records_or_watchdog_load_as_failed_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / 'below.json').write_text(json.dumps(self.ok), encoding='utf-8')
            (out / '_WATCHDOG.json').write_text('{}', encoding='utf-8')
            below, above = self.api.load_controls(out)
            self.assertEqual(below['status'], 'COMPLETED')
            self.assertEqual((above['status'], above['error_type']), ('FAILED', 'MISSING_RECORD'))
            self.assertEqual(self.api.classify_controls(below, above, self.stats), 'INCONCLUSIVE')

    def test_watchdog_covers_two_worst_case_calls(self):
        self.assertGreaterEqual(self.api.WATCHDOG_SECONDS, 900)


if __name__ == '__main__':
    unittest.main()
