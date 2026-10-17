"""Regression tests for calibration boundaries, ID alignment and score correctness."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from qpaf.m11.artifacts import file_manifest, object_hash, write_json
from qpaf.m11.retrieval import bm25_scores, load_score_cache, save_score_cache
from qpaf.m22.checks import bm25_reference, compare, rankings
from qpaf.m22.config import load_config, validate
from qpaf.m22.sample import pack_folder, select_sample, validate_inputs
from qpaf.m22.telemetry import failure_record

ROOT = Path(__file__).resolve().parents[1]


def config():
    return load_config(ROOT/'configs/m2.2/retriever_smoke.toml')


class BoundaryTests(unittest.TestCase):
    def test_rejects_test_split_and_unbounded_or_mutable_settings(self):
        mutations = [('sample', 'split', 'test'), ('sample', 'query_count', 0),
            ('sample', 'page_count', 65), ('caps', 'timeout_seconds', 1801),
            ('caps', 'retries', 1), ('visual', 'revision', 'main'),
            ('visual', 'family', 'colqwen2'), ('visual', 'max_pixels', 900000),
            ('dense', 'tokenizer_revision', 'main'), ('parity', 'dense_atol', float('nan')),
            ('parity', 'visual_atol', 100), ('visual', 'processor_revision', 'main')]
        for section, key, value in mutations:
            c = config()
            c[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                validate(c)

    def test_deterministic_selection_is_independent_of_input_order_and_labels(self):
        c = config()
        queries = [{'query_id': f'q{i}', 'text': f'query {i}'} for i in range(12)]
        ids = [f'q{i}' for i in range(8)]
        pages = [{'page_id': f'p{i}'} for i in range(24)]
        a = select_sample(queries, ids, pages, c)
        b = select_sample(queries[::-1], ids[::-1], pages[::-1], c)
        self.assertEqual(a, b)
        self.assertTrue(set(q['query_id'] for q in a[0]) <= set(ids))
        self.assertEqual(len(a[1]), 16)

    def test_selection_rejects_duplicate_and_unknown_ids(self):
        c = config()
        queries = [{'query_id': f'q{i}', 'text': 'query'} for i in range(8)]
        pages = [{'page_id': f'p{i}'} for i in range(16)]
        for ids in (['q0']*4, ['missing', 'q0', 'q1', 'q2']):
            with self.assertRaises(ValueError):
                select_sample(queries, ids, pages, c)
        with self.assertRaises(ValueError):
            select_sample(queries, [q['query_id'] for q in queries], pages[:-1]+[pages[0]], c)

    def test_payload_cap_applies_to_uncompressed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/'compressible').write_bytes(b'0'*(1024**2+1))
            with self.assertRaisesRegex(ValueError, 'size exceeds cap'):
                pack_folder(folder, 1)


class ScoreTests(unittest.TestCase):
    def test_bm25_matches_hand_computed_repeated_term_and_scalar_reference(self):
        queries, texts = ['apple apple', 'không tồn tại', ''], ['apple apple pear', 'pear', '']
        actual = bm25_scores(queries, texts, 1.5, .75)
        expected = 2*np.log1p(2.5/1.5)*2*2.5/(2+1.5*(.25+.75*3/(4/3)))
        self.assertAlmostEqual(actual[0, 0], expected, places=12)
        self.assertTrue(compare(actual, bm25_reference(queries, texts, 1.5, .75), 1e-12)['passed'])
        self.assertTrue(np.array_equal(actual[1:], np.zeros((2, 3))))

    def test_bm25_zero_length_corpus(self):
        self.assertTrue(compare(bm25_scores(['x'], ['', ''], 1.5, .75), [[0, 0]], 0)['passed'])

    def test_cache_rejects_id_order_channel_nonfinite_and_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            save_score_cache(folder, [[1., 2.]], ['q'], ['a', 'b'], 'dense')
            for qids, pids, channel in [(['other'], ['a', 'b'], 'dense'),
                    (['q'], ['b', 'a'], 'dense'), (['q'], ['a', 'b'], 'visual')]:
                with self.assertRaises(ValueError):
                    load_score_cache(folder, qids, pids, channel)
            np.save(folder/'scores.npy', [[9., 2.]])
            with self.assertRaisesRegex(ValueError, 'checksum'):
                load_score_cache(folder, ['q'], ['a', 'b'], 'dense')
            with self.assertRaises(ValueError):
                save_score_cache(folder, [[np.nan, 2]], ['q'], ['a', 'b'], 'dense')

    def test_ties_use_page_id_and_compare_rejects_bad_shapes(self):
        self.assertEqual(rankings([[2, 2, 0]], ['z', 'a', 'b']), [['a', 'z', 'b']])
        for other in ([[1]], [[np.inf, 1]]):
            with self.assertRaises(ValueError):
                compare([[1, 2]], other, 1e-5)
        self.assertFalse(compare([[1, 2]], [[1, 3]], 1e-5)['passed'])


class FailureTests(unittest.TestCase):
    def test_error_classification_preserves_reason(self):
        for error, kind in [(MemoryError('allocation failed'), 'OOM'),
                (RuntimeError('CUDA out of memory'), 'OOM'),
                (TimeoutError('deadline'), 'TIMEOUT'), (ValueError('bad IDs'), 'ERROR')]:
            record = failure_record(error)
            self.assertEqual(record['failure_kind'], kind)
            self.assertEqual(record['status'], 'FAIL')
            self.assertIn(str(error), record['error'])

    def test_cpu_and_gpu_functions_have_distinct_registered_names(self):
        from types import SimpleNamespace
        from qpaf.m22.worker import build_app
        names = []
        class FakeApp:
            def __init__(self, name):
                pass
            def function(self, **kwargs):
                def register(fn):
                    if fn.__name__ in names:
                        raise ValueError('Duplicate Modal function name')
                    names.append(fn.__name__)
                    return fn
                return register
        fake = SimpleNamespace(Image=MagicMock(), Volume=MagicMock(), App=FakeApp)
        with patch.dict('sys.modules', {'modal': fake}):
            build_app(config(), ROOT)
        self.assertIn('cpu_stage', names)
        self.assertIn('gpu_stage', names)

    @unittest.skipUnless(__import__('os').name == 'posix', 'Modal worker runs on Linux')
    def test_oom_and_timeout_leave_durable_failed_stage_evidence(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        from qpaf.m11.artifacts import read_json, verify_manifest
        from qpaf.m22 import worker
        for exc in (MemoryError('fixture OOM'), TimeoutError('fixture deadline')):
            with self.subTest(error=type(exc).__name__), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                c = config()
                write_json(folder/'resolved_config.json', c)
                fake = SimpleNamespace(Volume=MagicMock())
                meter = SimpleNamespace(phases=[], peak_rss_mb=0, phase=lambda name: nullcontext())
                with patch.dict('sys.modules', {'modal': fake}), \
                     patch.object(worker, 'root_for', return_value=folder), \
                     patch.object(worker, 'runtime_info', return_value={}), \
                     patch.object(worker, 'Telemetry', return_value=meter), \
                     patch.object(worker, 'resolve_text', side_effect=exc):
                    result = worker.execute('prepare', c, 'fixture')
                self.assertEqual(result['status'], 'FAIL')
                self.assertIn(result['failure_kind'], ('OOM', 'TIMEOUT'))
                self.assertEqual(read_json(folder/'prepare/status.json')['status'], 'FAIL')
                verify_manifest(folder/'prepare', read_json(folder/'prepare/hashes.json'))


class InputIntegrityTests(unittest.TestCase):
    def fixture(self, folder):
        c = config()
        c['sample'].update(query_count=1, page_count=1)
        image = folder/'image.png'
        image.write_bytes(b'image fixture bytes')
        write_json(folder/'queries.json', [{'query_id': 'q', 'text': 'question'}])
        write_json(folder/'pages.json', [{'page_id': 'p', 'text': 'page text', 'image': 'image.png',
            'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
            'native_text_sha256': hashlib.sha256(b'page text').hexdigest()}])
        write_json(folder/'sample_manifest.json', {'query_ids': ['q'], 'page_ids': ['p'],
            'config_sha256': object_hash(c), 'test_query_overlap': 0})
        write_json(folder/'hashes.json', file_manifest(folder))
        return c

    def test_valid_inputs_then_modified_image_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            c = self.fixture(folder)
            self.assertEqual(validate_inputs(folder, c)[2]['page_ids'], ['p'])
            (folder/'image.png').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                validate_inputs(folder, c)


    def test_reordered_ids_rejected_even_with_new_file_hashes(self):
        from qpaf.m11.artifacts import read_json
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            c = self.fixture(folder)
            meta = read_json(folder/'sample_manifest.json')
            meta['page_ids'] = ['wrong']
            write_json(folder/'sample_manifest.json', meta)
            write_json(folder/'hashes.json', file_manifest(folder, exclude=('hashes.json',)))
            with self.assertRaisesRegex(ValueError, 'ID mismatch'):
                validate_inputs(folder, c)

    def test_config_drift_rejected_before_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            c = self.fixture(folder)
            c['seed'] += 1
            with self.assertRaisesRegex(ValueError, 'provenance'):
                validate_inputs(folder, c)


class ExtractionTests(unittest.TestCase):
    def run_extraction(self, response):
        from PIL import Image
        from qpaf.m11.artifacts import read_json
        from qpaf.m22.worker import resolve_text
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/'inputs').mkdir()
            (folder/'prepare').mkdir()
            Image.new('RGB', (8, 8), 'white').save(folder/'inputs/image.png')
            pages = [{'page_id': 'p', 'text': '', 'image': 'image.png'}]
            ocr = {'side_effect': response} if isinstance(response, Exception) else {'return_value': response}
            with patch('qpaf.m22.worker.validate_inputs', return_value=([], pages, {})), \
                 patch('pytesseract.get_tesseract_version', return_value='5.3.0'), \
                 patch('pytesseract.image_to_data', **ocr):
                try:
                    result = resolve_text(config(), folder, folder/'prepare')
                except ValueError:
                    result = {'status': 'FAIL'}
            return result, read_json(folder/'prepare/pages.json'), read_json(folder/'prepare/failures.json')

    def test_no_words_keeps_page_and_records_m23_review(self):
        result, pages, failures = self.run_extraction({'text': ['', ''], 'conf': [-1, -1]})
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['no_text_detected_pages'], 1)
        self.assertEqual(pages[0]['page_id'], 'p')
        self.assertEqual(pages[0]['extraction_status'], 'NO_TEXT_DETECTED')
        self.assertEqual(pages[0]['text'], '')
        self.assertEqual(failures, [])

    def test_low_confidence_and_engine_timeout_remain_failures(self):
        for response in ({'text': ['uncertain text '*20], 'conf': [10]}, RuntimeError('Tesseract process timeout')):
            result, pages, failures = self.run_extraction(response)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(len(pages), 1)
            self.assertEqual(len(failures), 1)

try:
    import torch
    HAS_TORCH = True
except (ImportError, OSError):
    HAS_TORCH = False


@unittest.skipUnless(HAS_TORCH, 'PyTorch import unavailable in this environment')
class MultiVectorTests(unittest.TestCase):
    def test_maxsim_reference_and_padding_alignment(self):
        from qpaf.m22.checks import compare_multivectors, maxsim_reference
        q = torch.tensor([[1., 0.], [0., 1.]])
        p = torch.tensor([[1., 0.], [0., .5]])
        self.assertAlmostEqual(float(maxsim_reference([q], [p])[0, 0]), 1.5)
        padded = torch.cat([torch.zeros(2, 2), q])
        self.assertTrue(compare_multivectors([padded], [q], 0, 0)['passed'])
        self.assertFalse(compare_multivectors([padded], [q+.1], .001, 0)['passed'])


if __name__ == '__main__':
    unittest.main()
