"""Runtime regressions; generated blank PDFs are software fixtures, not calibration."""
from datetime import datetime, timedelta, timezone
import csv
import importlib.util
import logging
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m11.artifacts import read_json, write_json
from qpaf.m11.config import load_config
from qpaf.m11.dataset import prepare
from qpaf.m11.pipeline import execute_stage
from qpaf.m18.namespace import create_run_namespace, format_canonical_run_id, parse_canonical_run_id
from qpaf.m18.ocr_policy import evaluate_page_text


class PolicyRuntimeTests(unittest.TestCase):
    def test_empty_native_routes_to_ocr_but_empty_ocr_fails(self):
        self.assertEqual(evaluate_page_text('').route, 'OCR_FALLBACK_TRIGGERED')
        self.assertEqual(evaluate_page_text('', confidence=90).route, 'EXTRACTION_FAILED')

    def test_long_ocr_text_does_not_override_low_or_invalid_confidence(self):
        for confidence in (20, float('nan'), -1, 101):
            with self.subTest(confidence=confidence):
                self.assertEqual(evaluate_page_text('word ' * 30, confidence=confidence).route,
                                 'EXTRACTION_FAILED')

    def test_confident_ocr_has_distinct_qualified_route(self):
        self.assertEqual(evaluate_page_text('word ' * 30, confidence=90).route, 'OCR_TEXT_QUALIFIED')

    def test_run_ids_validate_dates_attempts_and_timezone(self):
        for value in ('RUN-exp-20260230T120000Z-A01', 'RUN-exp-20260928T250000Z-A01',
                      'RUN-exp-20260928T120000Z-A00'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_canonical_run_id(value)
        ts = datetime(2026, 9, 28, 19, tzinfo=timezone(timedelta(hours=7)))
        self.assertEqual(format_canonical_run_id('exp', ts), 'RUN-exp-20260928T120000Z-A01')
        for attempt in (0, 100, 1.5, True):
            with self.subTest(attempt=attempt), self.assertRaises(ValueError):
                format_canonical_run_id('exp', ts, attempt)
        with self.assertRaises(ValueError):
            format_canonical_run_id('exp', datetime(2026, 9, 28))

    def test_namespace_rejects_mismatch_and_traversal_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for experiment in ('other', '../escape', 'bad/name'):
                with self.subTest(experiment=experiment), self.assertRaises(ValueError):
                    create_run_namespace(tmp, experiment, 'RUN-exp-20260928T120000Z-A01')
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_real_stages_block_before_preparation_or_output_creation(self):
        cfg = load_config(ROOT/'configs/m1.1/vidoseek.toml')
        with tempfile.TemporaryDirectory() as tmp:
            for stage in ('prepare', 'bm25', 'dense', 'visual', 'oracle'):
                with self.subTest(stage=stage), patch('qpaf.m11.pipeline.prepare', side_effect=AssertionError('preparation reached')), self.assertRaises(PermissionError):
                    execute_stage(stage, cfg, tmp, 'real', {'digest': 'real'})
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_launcher_guard_precedes_app_construction(self):
        spec = importlib.util.spec_from_file_location('launcher_guard_test', ROOT/'scripts/run_m11_modal.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch('qpaf.m11.modal_app.build_app', side_effect=AssertionError('cloud construction reached')):
            with self.assertRaises(PermissionError):
                module.main(['--config', str(ROOT/'configs/m1.1/vidoseek.toml')])

    def test_run_metadata_is_immutable_but_allows_stage_resume(self):
        from qpaf.m18 import namespace
        self.assertTrue(hasattr(namespace, 'ensure_run_metadata'), 'run metadata is not integrated')
        cfg = load_config(ROOT/'configs/m1.1/vidoseek.toml')
        run_id = 'RUN-QPAF-M1_1-ORACLE-001-20260928T120000Z-A01'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/run_id
            namespace.ensure_run_metadata(root, run_id, cfg, {'digest': 'abc', 'command': ['test']})
            initial = (root/'run_metadata.json').read_bytes()
            (root/'prepare').mkdir()
            namespace.ensure_run_metadata(root, run_id, cfg, {'digest': 'abc', 'command': ['resume']})
            self.assertEqual((root/'run_metadata.json').read_bytes(), initial)
            with self.assertRaises(ValueError):
                namespace.ensure_run_metadata(root, run_id, cfg, {'digest': 'changed'})
            cfg['text']['dpi'] = 300
            with self.assertRaises(ValueError):
                namespace.ensure_run_metadata(root, run_id, cfg, {'digest': 'abc'})

    def test_retry_run_requires_matching_prior_attempt(self):
        from qpaf.m18 import namespace
        self.assertTrue(hasattr(namespace, 'ensure_run_metadata'), 'retry lineage is not integrated')
        cfg = load_config(ROOT/'configs/m1.1/vidoseek.toml')
        run_id = 'RUN-QPAF-M1_1-ORACLE-001-20260928T120000Z-A02'
        with tempfile.TemporaryDirectory() as tmp:
            for prior in ('', 'RUN-other-20260928T110000Z-A01', 'RUN-QPAF-M1_1-ORACLE-001-20260928T130000Z-A01'):
                cfg['execution']['retry_of'] = prior
                with self.subTest(prior=prior), self.assertRaises(ValueError):
                    namespace.ensure_run_metadata(Path(tmp)/run_id, run_id, cfg, {'digest': 'a'})

    def test_remote_worker_blocks_before_volume_access_even_with_fixture_marker(self):
        from qpaf.m11.modal_app import _execute_remote
        cfg = load_config(ROOT/'configs/m1.1/vidoseek.toml')
        with self.assertRaises(PermissionError):
            _execute_remote('prepare', cfg, 'test', {'kind': 'synthetic_software_test'})


class PrepareOCRRuntimeTests(unittest.TestCase):
    def run_prepare(self, root, result, max_failure=0.01, corrupt=False, engine_version='5.3.0'):
        import pypdfium2 as pdfium
        cfg = load_config(ROOT/'configs/m1.1/vidoseek.toml')
        cfg['text']['max_failure_fraction'] = max_failure
        doc = pdfium.PdfDocument.new()
        for _ in range(2):
            doc.new_page(72, 72).close()
        doc.save(root/'doc.pdf')
        doc.close()
        if corrupt:
            (root/'doc.pdf').write_bytes(b'broken PDF')
        with zipfile.ZipFile(root/'corpus.zip', 'w') as archive:
            archive.write(root/'doc.pdf', 'doc.pdf')
        write_json(root/'annotations.json', {'examples': [{'uid': 'q', 'query': 'question',
            'meta_info': {'file_name': 'doc.pdf', 'reference_page': [2]}}]})
        output = root/'prepared'
        output.mkdir()
        def download(repo, filename, **kwargs):
            return str(root/('annotations.json' if filename == cfg['dataset']['annotation_file'] else 'corpus.zip'))
        def ocr(image, **kwargs):
            self.assertEqual(kwargs['lang'], 'eng')
            self.assertEqual(kwargs['timeout'], 120)
            if isinstance(result, Exception):
                raise result
            return result
        with patch('huggingface_hub.hf_hub_download', side_effect=download), \
             patch('pytesseract.get_tesseract_version', return_value=engine_version), \
             patch('pytesseract.image_to_data', side_effect=ocr), \
             patch('pytesseract.image_to_string', side_effect=AssertionError('confidence discarded')):
            prepare(cfg, output, logging.getLogger('ocr-runtime-test'), root/'cache')
        return output

    def test_scan_fallback_uses_word_confidence_and_canonical_page_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self.run_prepare(Path(tmp), {'text': ['', 'Quality text ' * 6, 'ending'], 'conf': [-1, 80, 100]})
            pages = read_json(output/'pages.json')
            self.assertEqual([p['page_id'] for p in pages], ['doc_page_0001', 'doc_page_0002'])
            self.assertEqual(pages[0]['ocr_confidence'], 90)
            self.assertEqual(pages[0]['extraction_status'], 'OCR_TEXT_QUALIFIED')
            self.assertEqual(read_json(output/'qrels.json'), {'q': {'doc_page_0002': 1}})
            self.assertEqual(list(csv.DictReader((output/'failures.csv').read_text().splitlines())), [])

    def test_failures_persist_pages_and_images_before_fraction_stops_run(self):
        for result in (RuntimeError('Tesseract process timeout'),
                       {'text': ['long text ' * 20], 'conf': [20]}):
            with self.subTest(result=result), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with self.assertRaisesRegex(ValueError, 'failure fraction'):
                    self.run_prepare(root, result)
                pages = read_json(root/'prepared/pages.json')
                self.assertEqual(len(pages), 2)
                self.assertTrue(all(p['extraction_status'] == 'EXTRACTION_FAILED' for p in pages))
                self.assertTrue(all((root/'prepared'/p['image']).is_file() for p in pages))
                failures = list(csv.DictReader((root/'prepared/failures.csv').read_text().splitlines()))
                self.assertEqual(len(failures), 2)
                self.assertEqual(read_json(root/'prepared/extraction_summary.json')['failure_fraction'], 1)
                from qpaf.m11.artifacts import verify_manifest
                verify_manifest(root/'prepared', read_json(root/'prepared/extraction_hashes.json'))

    def test_engine_version_mismatch_is_logged_and_stops_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'failure fraction'):
                self.run_prepare(root, {'text': ['Quality ' * 20], 'conf': [90]}, engine_version='4.1.0')
            failures = list(csv.DictReader((root/'prepared/failures.csv').read_text().splitlines()))
            self.assertIn('version', failures[0]['error'])

    def test_corrupt_pdf_leaves_failure_evidence_and_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                self.run_prepare(root, {}, corrupt=True)
            failures = list(csv.DictReader((root/'prepared/failures.csv').read_text().splitlines()))
            self.assertEqual(failures[0]['document'], 'doc.pdf')
            self.assertEqual(failures[0]['reason'], 'pdf_open_failed')
