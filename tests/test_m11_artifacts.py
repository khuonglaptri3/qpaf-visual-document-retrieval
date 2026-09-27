import json
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from qpaf.m11.artifacts import StageRun, completed_stage, read_json, write_json
from qpaf.m11.dataset import annotations, select_queries, extract_zip
from unittest.mock import patch


class DatasetTests(unittest.TestCase):
    def example(self, page=1):
        return {'uid': 'q', 'query': 'where?', 'reference_answer': 'do not use',
                'meta_info': {'file_name': 'doc.pdf', 'reference_page': [page]}}

    def test_original_wrapper_and_one_based_page(self):
        queries, qrels = annotations({'examples': [self.example()]}, 'examples',
                                    {'doc.pdf': ['doc_1', 'doc_2']})
        self.assertEqual(queries, [{'query_id': 'q', 'text': 'where?'}])
        self.assertEqual(qrels, {'q': {'doc_1': 1}})

    def test_missing_zero_page_and_duplicate_queries_fail(self):
        for examples in [[self.example(0)], [self.example(3)],
                         [self.example(), self.example()]]:
            with self.subTest(examples=examples), self.assertRaises(ValueError):
                annotations({'examples': examples}, 'examples', {'doc.pdf': ['doc_1']})

    def test_selection_is_id_only_and_order_independent(self):
        queries = [{'query_id': str(i), 'text': 'text'} for i in range(20)]
        selected = select_queries(queries, 5, 19)
        self.assertEqual([x['query_id'] for x in selected],
                         [x['query_id'] for x in select_queries(list(reversed(queries)), 5, 19)])
        self.assertEqual(len(selected), 5)
        with self.assertRaises(ValueError):
            select_queries(queries, 21, 19)

    def test_zip_traversal_does_not_write_outside_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/'input.zip'
            with zipfile.ZipFile(archive, 'w') as out:
                out.writestr('../escaped.pdf', b'bad')
            with self.assertRaises(ValueError):
                extract_zip(archive, root/'payload')
            self.assertFalse((root/'escaped.pdf').exists())

    @unittest.skipUnless(all(importlib.util.find_spec(name) for name in
        ('pypdfium2', 'PIL', 'pytesseract', 'huggingface_hub')), 'optional PDF verification dependencies')
    def test_real_pdf_rendering_preserves_empty_pages_and_one_based_labels(self):
        import pypdfium2 as pdfium
        import logging
        from qpaf.m11.config import load_config
        from qpaf.m11.dataset import prepare
        from qpaf.m11.artifacts import read_json, write_json
        root_repo = Path(__file__).resolve().parents[1]
        cfg = load_config(root_repo/'configs/m1.1/vidoseek.toml', ['text.mode=native'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            document = pdfium.PdfDocument.new()
            for _ in range(2):
                page = document.new_page(72, 72)
                page.close()
            document.save(root/'doc.pdf')
            document.close()
            with zipfile.ZipFile(root/'corpus.zip', 'w') as archive:
                archive.write(root/'doc.pdf', 'pdf/doc.pdf')
            write_json(root/'annotations.json', {'examples': [self.example(2)]})
            output = root/'prepared'
            output.mkdir()
            def download(repo, filename, **kwargs):
                return str(root/('annotations.json' if filename == cfg['dataset']['annotation_file'] else 'corpus.zip'))
            with patch('huggingface_hub.hf_hub_download', side_effect=download):
                prepare(cfg, output, logging.getLogger('pdf-test'), root/'cache')
            self.assertEqual(read_json(output/'qrels.json'), {'q': {'doc_2': 1}})
            self.assertEqual(read_json(output/'dataset.json')['text_extraction_counts']['empty'], 2)
            self.assertEqual([x['page_id'] for x in read_json(output/'pages.json')], ['doc_1', 'doc_2'])
            self.assertTrue((output/'images/doc_1.png').is_file())


class ArtifactTests(unittest.TestCase):
    def test_atomic_write_recovers_from_temporary_windows_file_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'status.json'
            write_json(path, {'status': 'running'})
            replace = os.replace
            failures_left = 2

            def transient_lock(source, destination):
                nonlocal failures_left
                if failures_left:
                    failures_left -= 1
                    self.assertEqual(read_json(path), {'status': 'running'})
                    error = PermissionError('simulated temporary Windows file lock')
                    error.winerror = 5
                    raise error
                return replace(source, destination)

            with patch('qpaf.m11.artifacts.os.replace', side_effect=transient_lock):
                write_json(path, {'status': 'completed'})
            self.assertEqual(read_json(path), {'status': 'completed'})
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

    def test_atomic_write_preserves_original_after_persistent_windows_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'status.json'
            write_json(path, {'status': 'running'})
            error = PermissionError('simulated persistent Windows file lock')
            error.winerror = 5
            with patch('qpaf.m11.artifacts.os.replace', side_effect=error):
                with self.assertRaises(PermissionError):
                    write_json(path, {'status': 'completed'})
            self.assertEqual(read_json(path), {'status': 'running'})

    def test_success_receipt_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with StageRun(root, 'prepare', {'x': 1}, {}, {'digest': 'abc'}) as run:
                (run.path/'data.txt').write_text('original', encoding='utf-8')
            result = completed_stage(root, 'prepare', {'x': 1}, {}, {'digest': 'abc'})
            self.assertEqual(result, run.path)
            (result/'data.txt').write_text('modified', encoding='utf-8')
            with self.assertRaises(ValueError):
                completed_stage(root, 'prepare', {'x': 1}, {}, {'digest': 'abc'})

    def test_failure_keeps_log_but_cannot_be_used_as_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, 'expected'):
                with StageRun(root, 'visual', {}, {}, {}) as run:
                    raise RuntimeError('expected')
            self.assertIn('expected', (run.path/'run.log').read_text(encoding='utf-8'))
            self.assertIsNone(completed_stage(root, 'visual', {}, {}, {}))
            self.assertEqual(json.loads((run.path/'status.json').read_text())['status'], 'failed')
            with StageRun(root, 'visual', {}, {}, {}) as retry:
                self.assertNotEqual(run.path, retry.path)

    def test_changed_config_cannot_reuse_completed_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with StageRun(root, 'prepare', {'seed': 1}, {}, {}):
                pass
            with self.assertRaises(ValueError):
                completed_stage(root, 'prepare', {'seed': 2}, {}, {})

    def test_changing_local_download_path_does_not_invalidate_cloud_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with StageRun(root, 'prepare', {'seed': 1, 'output': {'local_dir': 'first'}}, {}, {}) as run:
                pass
            self.assertEqual(completed_stage(root, 'prepare',
                {'seed': 1, 'output': {'local_dir': 'second'}}, {}, {}), run.path)


if __name__ == '__main__':
    unittest.main()
