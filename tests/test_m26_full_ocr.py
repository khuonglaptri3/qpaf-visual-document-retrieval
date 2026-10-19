"""Full OCR contracts: real saved artifacts, routing replay and failed-page accounting."""
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m11.artifacts import digest, write_json
from qpaf.m23.policy import load_frozen_policy

POLICY_SHA = 'c0fcf0b3b13b27070716179d75545ba33ae406cc99a74902737bcf2dad19c4b8'


class FullOCRTests(unittest.TestCase):
    def module(self, name):
        self.assertIsNotNone(importlib.util.find_spec('qpaf.m26'), 'M2.6 package is not implemented')
        self.assertIsNotNone(importlib.util.find_spec('qpaf.m26.' + name), 'M2.6 ' + name + ' is not implemented')
        return importlib.import_module('qpaf.m26.' + name)

    def fixture(self, folder, *, empty=False, failed=False):
        from PIL import Image
        text = '' if empty else 'alpha'
        policy = load_frozen_policy(ROOT / 'configs/m2.3/ocr_policy_frozen.toml', POLICY_SHA)
        scheduled = [{'page_id': 'doc_page_0001', 'document_id': 'doc', 'page_number': 1,
                      'pdf_sha256': 'a' * 64, 'source_content_sha256': 'b' * 64}]
        page = folder / 'pages/doc_page_0001'
        page.mkdir(parents=True)
        (page / 'native.txt').write_text(text, encoding='utf-8')
        (page / 'text.txt').write_text(text, encoding='utf-8')
        artifacts = {}
        row = {**scheduled[0], 'native_text': text, 'text': text,
               'native_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
               'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
               'raw_ocr_text_sha256': None, 'policy_sha256': POLICY_SHA,
               'text_source': 'native', 'technical_failure': failed,
               'extraction_status': 'RENDER_ERROR' if failed else 'NATIVE_TEXT_USED',
               'reason': 'render failed' if failed else 'native_preserved', 'warnings': [],
               'render_status': 'ERROR' if failed else 'OK', 'artifacts': artifacts,
               'ocr': {'status': 'NOT_RUN' if failed else 'NO_TEXT_DETECTED' if empty else 'OK',
                       'text': None if failed else text,
                       'mean_word_confidence': None if empty or failed else 90.}}
        paths = {'native_text': page / 'native.txt', 'text': page / 'text.txt'}
        if not failed:
            Image.new('RGB', (10, 10), 'white').save(page / 'image.png')
            geometry = {'width': 10, 'height': 10, 'rotation': 0,
                        'native_rectangles': [] if empty else [[0, 0, 10, 10]],
                        'native_text_sha256': row['native_text_sha256']}
            write_json(page / 'geometry.json', geometry)
            (page / 'ocr.txt').write_text(text + '\n', encoding='utf-8', newline='\n')
            header = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
            (page / 'ocr.tsv').write_text(header + ('' if empty else '5\t1\t1\t1\t1\t1\t1\t1\t3\t3\t90\talpha\n'), encoding='utf-8')
            (page / 'ocr.stderr.txt').write_text('', encoding='utf-8')
            row['raw_ocr_text_sha256'] = hashlib.sha256(text.encode()).hexdigest()
            row['image_size'] = [10, 10]
            row['image_sha256'] = digest(page / 'image.png')
            paths.update(image=page / 'image.png', geometry=page / 'geometry.json',
                         raw_ocr_txt=page / 'ocr.txt', raw_ocr_tsv=page / 'ocr.tsv',
                         raw_ocr_stderr=page / 'ocr.stderr.txt')
            if empty:
                row.update(text_source='ocr', extraction_status='NO_TEXT_DETECTED',
                           reason='ocr_found_no_words_not_proof_of_blank_page',
                           warnings=['no_text_requires_visual_channel'])
        for key, path in paths.items():
            artifacts[key] = {'path': path.relative_to(folder).as_posix(),
                              'sha256': digest(path), 'size_bytes': path.stat().st_size}
        return [row], scheduled, policy

    def verify(self, folder, rows, scheduled, policy, maximum=.01):
        return self.module('bundle').validate_records(rows, scheduled, folder, policy, POLICY_SHA,
                                                       maximum_fraction=maximum)

    def test_frozen_config_has_full_scope_and_production_timeout(self):
        config = self.module('config').load_config(ROOT / 'configs/m2.6/full_ocr.toml')
        self.assertEqual(config['corpus']['page_count'], 5385)
        self.assertEqual(config['corpus']['document_count'], 292)
        self.assertEqual(config['policy']['sha256'], POLICY_SHA)
        self.assertEqual(config['execution']['workers'], 2)
        self.assertEqual(config['execution']['ocr_timeout_seconds'], 15)

    def test_config_rejects_changed_frozen_resources_and_unsafe_paths(self):
        module = self.module('config')
        original = module.load_config(ROOT / 'configs/m2.6/full_ocr.toml')
        for section, key, value in [('execution', 'workers', 3), ('execution', 'ocr_timeout_seconds', 120),
                                    ('policy', 'sha256', '0' * 64), ('output', 'directory', '../escape')]:
            config = copy.deepcopy(original)
            config[section][key] = value
            with self.assertRaises(ValueError):
                module.validate(config)

    def test_real_files_verify_and_raw_file_hash_differs_from_stripped_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            self.assertNotEqual(rows[0]['artifacts']['raw_ocr_txt']['sha256'], rows[0]['raw_ocr_text_sha256'])
            result = self.verify(folder, rows, scheduled, policy)
            self.assertEqual(result['pages'], 1)
            self.assertEqual(result['technical_failures'], 0)
            self.assertEqual(result['policy_replayed_pages'], 1)

    def test_no_text_page_keeps_visual_and_is_not_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder, empty=True)
            result = self.verify(folder, rows, scheduled, policy)
            self.assertEqual(result['technical_failures'], 0)
            self.assertEqual(result['extraction_statuses']['NO_TEXT_DETECTED'], 1)
            self.assertTrue((folder / rows[0]['artifacts']['image']['path']).is_file())

    def test_hash_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            (folder / rows[0]['artifacts']['image']['path']).write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum|hash'):
                self.verify(folder, rows, scheduled, policy)

    def test_rehashed_wrong_final_text_fails_policy_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            row = rows[0]
            path = folder / row['artifacts']['text']['path']
            path.write_text('fabricated', encoding='utf-8')
            row.update(text='fabricated', text_sha256=digest(path))
            row['artifacts']['text'].update(sha256=digest(path), size_bytes=path.stat().st_size)
            with self.assertRaisesRegex(ValueError, 'policy|resolved'):
                self.verify(folder, rows, scheduled, policy)

    def test_missing_duplicate_and_wrong_document_pages_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            wrong = copy.deepcopy(rows)
            wrong[0]['document_id'] = 'other'
            for invalid in [[], rows + rows, wrong]:
                with self.assertRaises(ValueError):
                    self.verify(folder, invalid, scheduled, policy)

    def test_render_failure_is_retained_and_counts_against_all_scheduled_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder, failed=True)
            with self.assertRaisesRegex(ValueError, 'failure cap'):
                self.verify(folder, rows, scheduled, policy)
            result = self.verify(folder, rows, scheduled, policy, maximum=1.)
            self.assertEqual(result['pages'], 1)
            self.assertEqual(result['technical_failures'], 1)
            self.assertEqual(result['failure_fraction'], 1.)

    def test_success_missing_raw_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            del rows[0]['artifacts']['raw_ocr_tsv']
            with self.assertRaises(ValueError):
                self.verify(folder, rows, scheduled, policy)

    def test_artifact_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            rows[0]['artifacts']['text']['path'] = '../outside.txt'
            with self.assertRaises(ValueError):
                self.verify(folder, rows, scheduled, policy)

    def test_mixed_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            rows[0]['policy_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'policy'):
                self.verify(folder, rows, scheduled, policy)

    def test_corrupt_pdf_yields_terminal_failure_and_keeps_both_text_files(self):
        engine = self.module('engine')
        config = self.module('config').load_config(ROOT / 'configs/m2.6/full_ocr.toml')
        policy = load_frozen_policy(ROOT / 'configs/m2.3/ocr_policy_frozen.toml', POLICY_SHA)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            pdf = folder / 'bad.pdf'
            pdf.write_bytes(b'%PDF-this is corrupt')
            scheduled = {'page_id': 'doc_page_0001', 'document_id': 'doc', 'page_number': 1,
                         'pdf_sha256': digest(pdf), 'source_content_sha256': 'b' * 64}
            row = engine.prepare_page(scheduled, pdf, folder, policy, config)
            result = engine.finish_page(row, folder, policy, 60.)
            self.assertTrue(result['technical_failure'])
            self.assertEqual(result['extraction_status'], 'RENDER_ERROR')
            self.assertEqual(result['ocr']['status'], 'NOT_RUN')
            self.assertEqual(set(result['artifacts']), {'native_text', 'text'})
            self.assertTrue((folder / 'pages/doc_page_0001/record.json').is_file())

    def test_interrupted_page_recovery_preserves_existing_native_text_and_image(self):
        engine = self.module('engine')
        self.assertTrue(hasattr(engine, 'recover_page'), 'Interrupted page recovery is not implemented')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            result = engine.recover_page(scheduled[0], folder, policy, POLICY_SHA)
            self.assertTrue(result['technical_failure'])
            self.assertEqual(result['native_text'], 'alpha')
            self.assertEqual(result['text'], 'alpha')
            self.assertEqual(result['image_sha256'], rows[0]['image_sha256'])
            self.assertEqual(result['ocr']['status'], 'NOT_RUN')
            self.verify(folder, [result], scheduled, policy, maximum=1.)

    def test_partial_failed_image_is_preserved_without_claiming_valid_visual_input(self):
        engine = self.module('engine')
        config = self.module('config').load_config(ROOT / 'configs/m2.6/full_ocr.toml')
        policy = load_frozen_policy(ROOT / 'configs/m2.3/ocr_policy_frozen.toml', POLICY_SHA)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            pdf = folder / 'bad.pdf'
            pdf.write_bytes(b'%PDF-corrupt')
            scheduled = {'page_id': 'doc_page_0001', 'document_id': 'doc', 'page_number': 1,
                         'pdf_sha256': digest(pdf), 'source_content_sha256': 'b' * 64}
            row = engine.prepare_page(scheduled, pdf, folder, policy, config)
            (folder / 'pages/doc_page_0001/image.png').write_bytes(b'partial PNG')
            result = engine.finish_page(row, folder, policy, 60.)
            self.assertIn('partial_image', result['artifacts'])
            self.assertNotIn('image', result['artifacts'])
            self.verify(folder, [result], [scheduled], policy, maximum=1.)

    def test_rehashed_fabricated_failure_text_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder, failed=True)
            row = rows[0]
            path = folder / row['artifacts']['text']['path']
            path.write_bytes(b'fabricated')
            row.update(text='fabricated', text_sha256=digest(path))
            row['artifacts']['text'].update(sha256=digest(path), size_bytes=path.stat().st_size)
            with self.assertRaisesRegex(ValueError, 'fallback|policy'):
                self.verify(folder, rows, scheduled, policy, maximum=1.)

    def test_schedule_validates_actual_counts_ids_hash_and_document_sequences(self):
        bundle = self.module('bundle')
        self.assertTrue(hasattr(bundle, 'validate_schedule'), 'Schedule validation is missing')
        from qpaf.m11.artifacts import object_hash
        scheduled = [{'page_id': 'doc_page_0001', 'document_id': 'doc', 'page_number': 1,
                      'pdf_sha256': 'a' * 64, 'source_content_sha256': 'b' * 64}]
        inputs = {'page_count': 1, 'document_count': 1, 'scheduled_pages': scheduled,
                  'documents': [{'document_id': 'doc', 'sha256': 'a' * 64, 'page_count': 1}],
                  'page_ids_sha256': object_hash(['doc_page_0001'])}
        bundle.validate_schedule(inputs, {'page_count': 1, 'document_count': 1})
        invalid = []
        item = copy.deepcopy(inputs); item['page_count'] = 5385; item['document_count'] = 292; invalid.append(item)
        item = copy.deepcopy(inputs); item['page_ids_sha256'] = 'invented'; invalid.append(item)
        item = copy.deepcopy(inputs); item['documents'][0]['page_count'] = 2; invalid.append(item)
        item = copy.deepcopy(inputs); item['documents'][0]['sha256'] = 'c' * 64; invalid.append(item)
        for item in invalid:
            with self.assertRaises(ValueError):
                bundle.validate_schedule(item, {'page_count': item['page_count'], 'document_count': item['document_count']})

    def test_csv_environment_and_resources_are_checked_semantically(self):
        bundle = self.module('bundle')
        self.assertTrue(hasattr(bundle, 'validate_metadata'), 'Metadata validation is missing')
        from qpaf.m11.artifacts import write_csv
        config = self.module('config').load_config(ROOT / 'configs/m2.6/full_ocr.toml')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            csv_rows = [{key: row.get(key) for key in bundle.PAGE_HASH_FIELDS} for row in rows]
            write_csv(folder / 'page_hashes.csv', csv_rows, bundle.PAGE_HASH_FIELDS)
            environment = {'packages': {'pypdfium2': '4.30.0', 'Pillow': '11.3.0', 'psutil': '7.0.0'},
                           'tesseract_version': 'tesseract 5.3.0\n',
                           'traineddata_sha256': policy['engine']['traineddata_sha256'],
                           'gpu_requested': False, 'cpu_requested': 4, 'omp_thread_limit': '1'}
            resources = {'wall_seconds': 10., 'peak_python_and_children_rss_mib': 100.,
                         'workers': 2, 'cpu': 4, 'gpu_requested': False, 'ocr_timeout_seconds': 15}
            write_json(folder / 'environment.json', environment)
            write_json(folder / 'resources.json', resources)
            expected = {'wall': True, 'ram': True, 'failure_cap': True}
            self.assertEqual(bundle.validate_metadata(folder, rows, policy, config), expected)
            (folder / 'page_hashes.csv').write_text('invented CSV', encoding='utf-8')
            with self.assertRaises(ValueError):
                bundle.validate_metadata(folder, rows, policy, config)
            write_csv(folder / 'page_hashes.csv', csv_rows, bundle.PAGE_HASH_FIELDS)
            environment['tesseract_version'] = 'wrong'
            write_json(folder / 'environment.json', environment)
            with self.assertRaises(ValueError):
                bundle.validate_metadata(folder, rows, policy, config)
            environment['tesseract_version'] = 'tesseract 5.3.0\n'
            write_json(folder / 'environment.json', environment)
            resources['wall_seconds'] = 99999999
            write_json(folder / 'resources.json', resources)
            with self.assertRaises(ValueError):
                bundle.validate_metadata(folder, rows, policy, config)

    def test_partial_utf8_native_is_retained_as_failed_raw_evidence(self):
        engine = self.module('engine')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows, scheduled, policy = self.fixture(folder)
            (folder / 'pages/doc_page_0001/native.txt').write_bytes(b'partial \xe1')
            result = engine.recover_page(scheduled[0], folder, policy, POLICY_SHA)
            self.assertTrue(result['technical_failure'])
            self.assertIn('partial_native_text', result['artifacts'])
            artifact = folder / result['artifacts']['partial_native_text']['path']
            self.assertEqual(artifact.read_bytes(), b'partial \xe1')
            self.verify(folder, [result], scheduled, policy, maximum=1.)

    def test_atomic_extraction_resumes_after_interrupted_temporary_write(self):
        collection = self.module('collection')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'image.png'
            original = Path.write_bytes
            def interrupted(target, payload):
                original(target, payload[:2])
                raise OSError('simulated interruption')
            with patch.object(Path, 'write_bytes', interrupted):
                with self.assertRaises(OSError):
                    collection.atomic_payload(path, b'complete image')
            self.assertFalse(path.exists())
            collection.atomic_payload(path, b'complete image')
            self.assertEqual(path.read_bytes(), b'complete image')

    def test_hard_termination_collects_committed_records_without_final_manifest(self):
        collection = self.module('collection')
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'run'
            folder.mkdir()
            remote = root / 'remote'
            output = remote / 'runs/run/output'
            output.mkdir(parents=True)
            rows, scheduled, policy = self.fixture(output)
            write_json(output / 'pages/doc_page_0001/record.json', rows[0])
            missing = {**scheduled[0], 'page_id': 'doc_page_0002', 'page_number': 2}
            write_json(folder / 'input_manifest.json', {'scheduled_pages': scheduled + [missing]})
            write_json(folder / 'resolved_config.json', self.module('config').load_config(ROOT / 'configs/m2.6/full_ocr.toml'))
            (folder / 'ocr_policy_frozen.toml').write_bytes((ROOT / 'configs/m2.3/ocr_policy_frozen.toml').read_bytes())
            class Volume:
                def read_file(self, name):
                    yield (remote / name.lstrip('/')).read_bytes()
                def iterdir(self, name, recursive=True):
                    return iter(SimpleNamespace(path=p.relative_to(remote).as_posix())
                                for p in (remote / name.lstrip('/')).rglob('*') if p.is_file())
            receipt = collection.collect_partial(folder, Volume())
            self.assertEqual(receipt['status'], 'PARTIAL_NOT_COMPLETE')
            self.assertEqual(receipt['completed_records_verified'], 1)
            self.assertEqual(receipt['incomplete_page_ids'], ['doc_page_0002'])
            self.assertTrue((folder / 'partial-output/pages/doc_page_0001/image.png').is_file())
            self.assertFalse((folder / 'verification.json').exists())


if __name__ == '__main__':
    unittest.main()
