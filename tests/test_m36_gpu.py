"""Resource evidence must reject leakage, fabricated counts and incomplete timing."""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class GPUContractTests(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module('scripts.m36_gpu_worker')

    def test_label_free_records_drop_every_non_score_column_and_sort_pages(self):
        rows = [{'query_id': 'q', 'page_id': page, 'bm25_score': 1.,
                 'dense_score': 2., 'visual_score': 3., 'relevance': 99}
                for page in ('b', 'a')]
        records = self.api.label_free_records(rows, {'q': 'query'}, ['q'], 600)
        self.assertEqual(records, [{'query_id': 'q', 'text': 'query',
                                   'page_ids': ['a', 'b'], 'raw_scores': [[1., 2., 3.], [1., 2., 3.]]}])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.api.label_free_records(rows+rows, {'q': 'query'}, ['q'], 600)
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.api.label_free_records(rows, {'q': 'query'}, ['q', 'absent'], 600)

    def test_reject_nonfinite_scores_before_export(self):
        for bad in (float('nan'), float('inf'), True):
            rows = [{'query_id': 'q', 'page_id': 'p', 'bm25_score': bad,
                     'dense_score': 2., 'visual_score': 3.}]
            with self.assertRaisesRegex(ValueError, 'finite'):
                self.api.label_free_records(rows, {'q': 'query'}, ['q'], 600)

    def timings(self):
        return [{'query_id': f'q{i}', 'pass_index': p, 'online_wall_ms': float(p+1),
                 'cpu_features_ms': .1, 'h2d_wall_ms': .1, 'gate_wall_ms': .1,
                 'gate_cuda_ms': .09, 'd2h_wall_ms': .1, 'ranking_wall_ms': .1}
                for p in range(3) for i in range(1000)]

    def test_summary_counts_unique_queries_and_median_per_query(self):
        result = self.api.summarize(self.timings(), [f'q{i}' for i in range(1000)], 1.49*2**30)
        self.assertEqual(result['distinct_measured_queries'], 1000)
        self.assertEqual(result['measurement_rows'], 3000)
        self.assertEqual(result['online_wall_ms']['median_of_query_medians'], 2.)
        self.assertEqual(result['resource_verdict'], 'PASS')
        self.assertEqual(self.api.summarize(self.timings(), [f'q{i}' for i in range(1000)],
                                            1.5*2**30)['resource_verdict'], 'FAIL')

    def test_missing_duplicate_or_nonfinite_timing_cannot_pass(self):
        ids = [f'q{i}' for i in range(1000)]
        for rows in (self.timings()[:-1], self.timings()+[self.timings()[0]],
                     [{**r, 'online_wall_ms': float('nan')} for r in self.timings()]):
            with self.assertRaises(ValueError):
                self.api.summarize(rows, ids, 1.)
        with self.assertRaisesRegex(ValueError, '1000'):
            self.api.summarize(self.timings(), ids[:999], 1.)

    def test_latency_gate_is_full_online_time_inclusive_at_ten(self):
        ids = [f'q{i}' for i in range(1000)]
        for value, verdict in ((10., 'PASS'), (10.00001, 'FAIL')):
            rows = [{**r, 'online_wall_ms': value} for r in self.timings()]
            self.assertEqual(self.api.summarize(rows, ids, 1.)['resource_verdict'], verdict)

    def test_unlisted_label_file_and_changed_source_refuse_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'source.py').write_text('frozen', encoding='utf-8')
            self.api.write_new(root/'bundle_manifest.json',
                               {'files': {'source.py': self.api.sha(root/'source.py')}})
            self.api.verify_bundle(root)
            (root/'qrels_test.json').write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'allowlist'):
                self.api.verify_bundle(root)
            (root/'qrels_test.json').unlink()
            (root/'source.py').write_text('drift', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash'):
                self.api.verify_bundle(root)

    def test_cpu_zero_cuda_and_impossible_stage_times_are_rejected(self):
        ids = [f'q{i}' for i in range(1000)]
        with self.assertRaisesRegex(ValueError, 'positive CUDA'):
            self.api.summarize(self.timings(), ids, 0)
        rows = [{**r, 'online_wall_ms': .4} for r in self.timings()]
        with self.assertRaisesRegex(ValueError, 'stage'):
            self.api.summarize(rows, ids, 1)

    def test_worker_timeout_keeps_partial_stdout_and_failure_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'scripts').mkdir()
            (root/'scripts/m36_gpu_worker.py').write_text(
                "import time\nprint('partial-pass', flush=True)\ntime.sleep(60)\n", encoding='utf-8')
            result = self.api.run_method('QARF', root, root/'result.json', timeout=1.)
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(result['reason'], 'WORKER_TIMEOUT')
            self.assertIn('partial-pass', result['log']['stdout'])
            self.assertIsNone(result['output'])

    def test_bytecode_named_directory_cannot_hide_unlisted_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.api.write_new(root/'bundle_manifest.json', {'files': {}})
            (root/'__pycache__').mkdir()
            (root/'__pycache__/qrels_test.json').write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'allowlist'):
                self.api.verify_bundle(root)

    def test_modal_log_symbols_work_with_legacy_windows_output_encoding(self):
        process = subprocess.run([sys.executable, '-c',
                                  'from scripts.run_m36_gpu import configure_console; '
                                  "configure_console(); print('\\u2713 Modal ready')"],
                                 cwd=Path(__file__).resolve().parents[1],
                                 env={**os.environ, 'PYTHONIOENCODING': 'cp1252'}, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn('\u2713 Modal ready'.encode('utf-8'), process.stdout)


if __name__ == '__main__':
    unittest.main()
