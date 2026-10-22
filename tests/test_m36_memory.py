"""Read-only process and cgroup accounting must preserve units, scope and gaps."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class MemoryTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module('scripts.m36_memory_telemetry')

    def test_process_kib_values_are_bytes_and_unrelated_fields_are_ignored(self):
        result = self.api.parse_kib_fields('Name:\tworker\nVmRSS:\t1024 kB\nVmHWM:\t2048 kB\n')
        self.assertEqual(result, {'VmRSS': 1048576, 'VmHWM': 2097152})
        with self.assertRaises(ValueError):
            self.api.parse_kib_fields('VmRSS: 1024 MB\n')

    def test_v2_mount_root_is_removed_from_process_membership(self):
        mounts = '30 21 0:27 /tenant /sys/fs/cgroup rw - cgroup2 cgroup rw\n'
        self.assertEqual(self.api.resolve_cgroups('0::/tenant/job\n', mounts),
                         [{'version': 2, 'path': '/sys/fs/cgroup/job', 'membership': '/tenant/job'}])
        self.assertEqual(self.api.resolve_cgroups('0::/other/job\n', mounts), [])

    def test_v1_selects_memory_controller_and_handles_mount_spaces(self):
        mounts = ('31 21 0:28 / /sys/fs/cgroup/cpu rw - cgroup cgroup rw,cpu\n'
                  '32 21 0:29 / /sys/fs/cgroup/memory\\040group rw - cgroup cgroup rw,memory\n')
        result = self.api.resolve_cgroups('3:cpu:/job\n4:memory:/job\n', mounts)
        self.assertEqual(result, [{'version': 1, 'path': '/sys/fs/cgroup/memory group/job',
                                   'membership': '/job'}])

    def test_current_usage_cannot_be_reported_as_cgroup_peak(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'memory.current').write_text('100\n')
            (root/'memory.max').write_text('5368709120\n')
            (root/'memory.events').write_text('oom 0\noom_kill 0\n')
            result = self.api.read_cgroup(root, 2)
            self.assertEqual(result['current_bytes'], 100)
            self.assertIsNone(result['peak_bytes'])
            self.assertEqual(result['limit_bytes'], 5*2**30)
            (root/'memory.max').write_text('max\n')
            self.assertIsNone(self.api.read_cgroup(root, 2)['limit_bytes'])

    def test_limit_verdict_distinguishes_process_only_from_cgroup_evidence(self):
        limit = 5*2**30
        process = {'ru_maxrss_bytes': 4.9*2**30, 'vmhwm_bytes': 4.8*2**30}
        result = self.api.assess_memory(process, [], limit)
        self.assertEqual(result['process_high_water_verdict'], 'PASS')
        self.assertEqual(result['container_peak_verdict'], 'UNAVAILABLE')
        self.assertFalse(result['physical_container_peak_verified'])
        cgroup = {'version': 2, 'path': '/sys/fs/cgroup/job', 'membership': '/job',
                  'limit_bytes': limit, 'peak_bytes': limit-1, 'current_bytes': 1,
                  'events': {'oom_kill': 0, 'oom': 0}}
        result = self.api.assess_memory(process, [cgroup], limit)
        self.assertEqual(result['container_peak_verdict'], 'PASS_REPORTED_CGROUP_PEAK')
        self.assertTrue(result['reported_container_peak_verified'])
        cgroup['peak_bytes'] = limit+1
        self.assertEqual(self.api.assess_memory(process, [cgroup], limit)['container_peak_verdict'], 'FAIL')
        cgroup['peak_bytes'] = 1
        cgroup['events']['oom_kill'] = 1
        self.assertEqual(self.api.assess_memory(process, [cgroup], limit)['container_peak_verdict'], 'FAIL')

    def test_wrong_scope_limit_or_missing_events_cannot_verify_container(self):
        limit = 5*2**30
        group = {'limit_bytes': 8*2**30, 'peak_bytes': 1, 'events': {'oom': 0}}
        self.assertEqual(self.api.assess_memory({}, [group], limit)['container_peak_verdict'], 'UNAVAILABLE')
        group.update(limit_bytes=limit, events=None)
        result = self.api.assess_memory({}, [group], limit)
        self.assertEqual(result['container_peak_verdict'], 'UNAVAILABLE')
        self.assertEqual(result['process_high_water_verdict'], 'UNAVAILABLE')

    def test_v1_peak_is_not_confused_with_current_or_unlimited_value(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'memory.usage_in_bytes').write_text('10\n')
            (root/'memory.max_usage_in_bytes').write_text('200\n')
            (root/'memory.limit_in_bytes').write_text('5368709120\n')
            (root/'memory.oom_control').write_text('oom_kill_disable 0\nunder_oom 0\noom_kill 0\n')
            result = self.api.read_cgroup(root, 1)
            self.assertEqual(result['peak_bytes'], 200)
            self.assertEqual(result['current_bytes'], 10)
            result.update(version=1)
            assessment = self.api.assess_memory({}, [result], 5*2**30)
            self.assertEqual(assessment['container_peak_verdict'], 'PASS_REPORTED_CGROUP_PEAK')
            self.assertFalse(assessment['physical_container_peak_verified'])


if __name__ == '__main__':
    unittest.main()
