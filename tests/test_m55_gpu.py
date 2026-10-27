"""R5-04 counts repeated validation events honestly and refuses unsafe evidence."""
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ValidationGPUContractTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('scripts.m55_gpu_worker')
        except ModuleNotFoundError:
            self.fail('M5.5 validation GPU worker is missing')
        self.ids = [f'val-{i:03d}' for i in range(171)]

    def records(self):
        return [{'query_id': q, 'text': 'query', 'page_ids': ['a'],
                 'raw_scores': [[1., 2., 3.]]} for q in self.ids]

    def timings(self):
        return [{'query_id': q, 'pass_index': p, 'candidate_count': 1,
                 'online_wall_ms': float(p+1), 'cpu_features_ms': .1,
                 'h2d_wall_ms': .1, 'gate_wall_ms': .1, 'gate_cuda_ms': .09,
                 'd2h_wall_ms': .1, 'ranking_wall_ms': .1}
                for p in range(6) for q in self.ids]

    def test_workload_is_171_unique_ids_and_1026_events_with_20_warmups(self):
        result = self.api.make_workload(self.ids)
        self.assertEqual(result['warmup'], self.ids[:20])
        self.assertEqual(result['measured'], self.ids)
        self.assertEqual((result['passes'], result['distinct_measured_queries'],
                          result['measurement_events']), (6, 171, 1026))
        self.assertTrue(result['warmup_overlaps_measured_ids'])
        for bad in (self.ids[:-1], self.ids+[self.ids[0]], ['']+self.ids[1:],
                    [self.ids[0]]+self.ids[:-1]):
            with self.subTest(ids=bad[:2]), self.assertRaises(ValueError):
                self.api.make_workload(bad)

    def test_payload_rejects_labels_non_validation_ids_and_invalid_scores(self):
        workload = self.api.make_workload(self.ids)
        self.api.validate_payload(workload, self.records())
        for mutate in (lambda rows: rows[0].update(labels=[1]),
                       lambda rows: rows[0].update(query_id='test-query'),
                       lambda rows: rows.reverse(),
                       lambda rows: rows[0].update(raw_scores=[[float('nan'), 2., 3.]]),
                       lambda rows: rows[0].update(raw_scores=[[True, 2., 3.]]),
                       lambda rows: rows[0].update(page_ids=['a', 'a']),
                       lambda rows: rows[0].update(text='')):
            rows = self.records()
            mutate(rows)
            with self.assertRaises(ValueError):
                self.api.validate_payload(workload, rows)
        bad = copy.deepcopy(workload)
        bad['passes'] = 5
        with self.assertRaises(ValueError):
            self.api.validate_payload(bad, self.records())

    def test_summary_reports_events_separately_and_medians_across_six_passes(self):
        result = self.api.summarize(self.timings(), self.ids, 1.49*2**30)
        self.assertEqual((result['distinct_measured_queries'], result['measurement_rows'],
                          result['passes']), (171, 1026, 6))
        self.assertEqual(result['online_wall_ms']['median_of_query_medians'], 3.5)
        self.assertEqual(result['online_wall_ms']['event_p50'], 3.5)
        self.assertEqual(result['online_wall_ms']['event_p95'], 6.)
        self.assertEqual(len(result['online_wall_ms']['per_pass']), 6)
        self.assertEqual(result['resource_verdict'], 'PASS')
        self.assertFalse(result['meets_m36_1000_distinct_id_protocol'])

    def test_missing_reordered_duplicate_and_nonfinite_events_are_refused(self):
        valid = self.timings()
        variants = [valid[:-1], valid+[valid[0]], [valid[1], valid[0], *valid[2:]],
                    [{**r, 'online_wall_ms': float('nan')} for r in valid],
                    [{**r, 'online_wall_ms': .4} for r in valid]]
        for rows in variants:
            with self.assertRaises(ValueError):
                self.api.summarize(rows, self.ids, 1.)
        with self.assertRaises(ValueError):
            self.api.summarize(valid, self.ids, 0)

    def test_resource_boundaries_are_inclusive_latency_and_exclusive_allocation(self):
        for latency, peak, verdict in ((10., 1.49*2**30, 'PASS'),
                                       (10.00001, 1., 'FAIL'), (1., 1.5*2**30, 'FAIL')):
            rows = [{**r, 'online_wall_ms': latency} for r in self.timings()]
            self.assertEqual(self.api.summarize(rows, self.ids, peak)['resource_verdict'], verdict)

    def test_invalid_candidate_counts_and_cuda_time_exceeding_wall_are_refused(self):
        for fields in ({'candidate_count': 0}, {'candidate_count': True}, {'candidate_count': 601},
                       {'candidate_count': 1.5}, {'gate_cuda_ms': 999999.}):
            rows = [{**r, **fields} for r in self.timings()]
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.api.summarize(rows, self.ids, 1.)
        rows = self.timings()
        rows[171]['candidate_count'] = 2
        with self.assertRaises(ValueError):
            self.api.summarize(rows, self.ids, 1.)

    def test_bundle_rejects_a_label_file_even_if_it_has_a_manifest_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'input').mkdir()
            label = root/'input/qrels_development.json'
            label.write_text('{}')
            (root/'bundle_manifest.json').write_text(json.dumps({'files': {
                'input/qrels_development.json': self.api.sha(label)}}))
            with self.assertRaises(ValueError):
                self.api.verify_bundle(root)


class GPUAuthorizationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('scripts.run_m55_gpu')
        except ModuleNotFoundError:
            self.fail('M5.5 GPU launcher is missing')
        self.auth = {'status': 'AUTHORIZED_BY_KHUONG_WORKING_SESSION', 'task_id': 'M5.5',
                     'source_commit': 'a'*40, 'scope': 'validation',
                     'bundle_manifest_sha256': 'b'*64, 'workload_sha256': 'c'*64,
                     'query_count': 171, 'measurement_events_per_method': 1026,
                     'warmup_events': 20, 'passes': 6, 'invocations': 1, 'automatic_retries': 0,
                     'memory_limit_mib': 5120, 'function_timeout_seconds': 900,
                     'whole_app_watchdog_seconds': 900, 'gpu': 'A10', 'gpu_count': 1,
                     'startup_timeout_seconds': 120, 'worker_timeout_seconds': 410,
                     'cpu_limit_cores': 2, 'budget_usd': .5,
                     'runtime': {'python': '3.13.7', 'torch': '2.11.0+cu126',
                                 'numpy': '2.5.4', 'pandas': '3.0.6', 'pyarrow': '26.0.0',
                                 'modal': '1.5.5', 'dtype': 'float64', 'threads': 1},
                     'base_oci_image': 'python:3.13.7-slim-bookworm@sha256:'
                                       'adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d',
                     'permissions': {'validation_only': True, 'training': False, 'test_labels': False},
                     'output_path': 'results/m5.5/RUN-QPAF-M5_5-SYS-001-20261027T140000Z-A01',
                     'approval': {'text': 'Cho phép chạy Modal/GPU để hoàn tất số đo M5.5',
                                  'delegation': 'Tự quyết chi tiết và triển khai trong phạm vi validation'}}

    def check(self, auth=None, **changes):
        context = {'head': 'a'*40, 'clean': True, 'bundle_sha': 'b'*64, 'workload_sha': 'c'*64,
                   'output_rel': self.auth['output_path']}
        context.update(changes)
        return self.api.validate_authorization(auth or self.auth, **context)

    def test_exact_owner_scope_and_single_invocation_are_accepted(self):
        self.check()

    def test_dirty_source_pin_scope_budget_or_event_drift_is_refused(self):
        for change in ({'clean': False}, {'head': 'd'*40}, {'bundle_sha': 'd'*64},
                       {'workload_sha': 'd'*64}, {'output_rel': 'results/m3.6/old'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check(**change)
        for change in ({'task_id': 'M3.6'}, {'scope': 'test'}, {'invocations': 2},
                       {'automatic_retries': 1}, {'query_count': 1000}, {'passes': 3},
                       {'memory_limit_mib': 4096}, {'budget_usd': 5}, {'gpu': 'H100'},
                       {'runtime': {'torch': 'other'}}, {'base_oci_image': 'python:latest'},
                       {'startup_timeout_seconds': 999}, {'worker_timeout_seconds': 999},
                       {'approval': {}}, {'permissions': {'test_labels': True}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check({**self.auth, **change})
        for field in ('runtime', 'base_oci_image', 'startup_timeout_seconds', 'worker_timeout_seconds'):
            missing = dict(self.auth)
            del missing[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                self.check(missing)

    def test_existing_namespace_is_untouched_before_any_cloud_access(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'old'
            output.mkdir()
            marker = output/'keep.txt'
            marker.write_text('keep')
            with self.assertRaises(FileExistsError):
                self.api.execute(Path(folder)/'no-bundle', Path(folder)/'no-auth', '0'*64, output)
            self.assertEqual(marker.read_text(), 'keep')
            self.assertEqual([p.name for p in output.iterdir()], ['keep.txt'])

    def test_call_id_is_saved_before_waiting_and_only_one_input_is_submitted(self):
        api = self.api
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            class Call:
                object_id = 'fc-durable-fixture'
                def get(self, timeout):
                    saved = json.loads((output/'function_call.json').read_text())
                    if saved['function_call_id'] != self.object_id or timeout != 900:
                        raise AssertionError('call identity must be persisted before the result wait')
                    return {'status': 'COMPLETED'}
            class Function:
                submitted = 0
                def spawn(self):
                    self.submitted += 1
                    return Call()
            fn = Function()
            self.assertTrue(callable(getattr(api, 'invoke_once', None)), 'durable invocation helper missing')
            self.assertEqual(api.invoke_once(fn, output), {'status': 'COMPLETED'})
            self.assertEqual(fn.submitted, 1)

    def test_a_result_wait_failure_retains_call_identity_without_resubmitting(self):
        api = self.api
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            class Call:
                object_id = 'fc-interrupted-fixture'
                def get(self, timeout):
                    raise ConnectionError('result transport interrupted')
            class Function:
                submitted = 0
                def spawn(self):
                    self.submitted += 1
                    return Call()
            fn = Function()
            self.assertTrue(callable(getattr(api, 'invoke_once', None)), 'durable invocation helper missing')
            with self.assertRaises(ConnectionError):
                api.invoke_once(fn, output)
            self.assertEqual(fn.submitted, 1)
            self.assertEqual(json.loads((output/'function_call.json').read_text())['function_call_id'],
                             'fc-interrupted-fixture')


if __name__ == '__main__':
    unittest.main()
