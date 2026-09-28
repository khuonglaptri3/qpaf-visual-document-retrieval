"""Regression coverage for false PASS, partial qrels and real PDF audit."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from qpaf.m16.detector import verify_qrel_consistency
from qpaf.m16.manifest import build_page_manifest, resolve_aliases


class RealAuditTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, 'scripts/audit_collisions.py', *map(str, args)],
                              capture_output=True, text=True, encoding='utf-8',
                              env={**os.environ, 'PYTHONUTF8': '1'})

    def test_missing_input_never_falls_back_to_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'output'
            result = self.cli('--output-dir', output)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('PASS_AUDIT', result.stdout)

    def test_empty_corpus_is_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            annotations = root/'annotations.json'
            annotations.write_text(json.dumps({'examples': [{'uid':'q1','query':'test',
                'meta_info':{'file_name':'missing.pdf','reference_page':[999]}}]}))
            result = self.cli('--annotations', annotations, '--corpus-dir', root,
                              '--output-dir', root/'out', '--fail-on-leakage')
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('PASS_AUDIT', result.stdout)

    def test_every_positive_qrel_must_resolve(self):
        result = verify_qrel_consistency({'q1':{'exists':1,'missing':1}}, {'exists'})
        self.assertEqual(result['valid_queries'], 0)
        self.assertEqual(result['missing_target_count'], 1)

    def test_duplicate_page_ids_rejected(self):
        row = {'document_id':'doc', 'page_number':1, 'content':b'hello'}
        with self.assertRaises(ValueError):
            build_page_manifest([row, {**row, 'content':b'changed'}])

    def test_unknown_alias_has_unresolved_record(self):
        mapping, records = resolve_aliases([('missing_p1','query:q1')], {'doc_page_0001'})
        self.assertEqual(mapping, {})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].review_status, 'unresolved')

    def test_fixture_output_is_create_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'out'
            first = self.cli('--fixture', '--output-dir', output)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = {p.name:p.read_bytes() for p in output.iterdir()}
            second = self.cli('--fixture', '--output-dir', output)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(before, {p.name:p.read_bytes() for p in output.iterdir()})

    def test_real_pdf_cli_uses_m13_splits_and_measures_shared_documents(self):
        from qpaf.m13.corpus import generate_synthetic_vidoseek_fixture
        from qpaf.m11.dataset import extract_zip
        from qpaf.m13.splits import write_split_bundle
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = generate_synthetic_vidoseek_fixture(root/'fixture')
            extract_zip(fixture['zip_path'], root/'pdfs')
            annotations = json.loads(fixture['json_path'].read_text())
            write_split_bundle(root/'splits', [row['uid'] for row in annotations['examples']])
            result = self.cli('--annotations', fixture['json_path'], '--corpus-dir', root/'pdfs',
                              '--splits-dir', root/'splits', '--output-dir', root/'out')
            self.assertIn(result.returncode, (0, 1), result.stderr)
            summary = json.loads((root/'out/collision_summary.json').read_text())
            self.assertEqual(summary['total_queries'], 10)
            self.assertEqual(summary['total_documents'], 3)
            self.assertEqual(summary['total_pages'], 6)
            self.assertEqual(summary['missing_target_count'], 0)
            self.assertEqual(summary['independent_review'], 'PENDING')
            self.assertGreater(summary['document_overlap_count'], 0)
            self.assertEqual(summary['status'], 'REVIEW_REQUIRED_OVERLAP')


if __name__ == '__main__':
    unittest.main()
