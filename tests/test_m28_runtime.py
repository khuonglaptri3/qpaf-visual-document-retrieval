"""M2.8 guards: pinned text/query inputs, finite durable shards, CUDA required."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m28.runtime import require_cuda, save_array, load_array, bm25_probe
from qpaf.m28.preflight import validate_pages, read_query_texts


class RuntimeGuards(unittest.TestCase):
    def test_bm25_reference_uses_full_corpus_statistics(self):
        from qpaf.m11.retrieval import bm25_scores
        queries = ['a a', 'a b']
        texts = ['a b c', '', 'b', 'a a a a a', 'c d e f']
        expected = bm25_scores(queries, texts, 1.5, .75)[:, :2]
        np.testing.assert_allclose(bm25_probe(queries, texts, 1.5, .75, 2), expected,
                                   atol=1e-12, rtol=0)

    def test_requires_cuda_no_cpu_fallback(self):
        with self.assertRaisesRegex(RuntimeError, 'CUDA'):
            require_cuda(SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))

    def test_shard_roundtrip_rejects_identity_and_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'scores.npy'
            a = np.arange(6, dtype=np.float32).reshape(2, 3)
            save_array(p, a, {'run': 'one'})
            np.testing.assert_array_equal(load_array(p, {'run': 'one'}, (2, 3)), a)
            with self.assertRaisesRegex(ValueError, 'identity'):
                load_array(p, {'run': 'two'})
            p.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'hash|checksum'):
                load_array(p, {'run': 'one'})

    def test_reject_nonfinite_or_bool_before_writing(self):
        for a in (np.array([np.nan]), np.array([np.inf]), np.array([True])):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError):
                    save_array(Path(d) / 'bad.npy', a, {})

    def test_orphan_payload_is_not_reused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'scores.npy'
            np.save(p, np.ones((2, 2)))
            with self.assertRaises(ValueError):
                load_array(p, {})

    def test_query_reader_preserves_exact_ids_and_ignores_reference_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'queries.json'
            p.write_text(json.dumps({'examples': [{'uid': 'q', 'query': ' Question ',
                                                   'meta_info': {'reference_page': 'unreadable'}}]}))
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(read_query_texts(p, sha, ['q']), {'q': 'Question'})
            with self.assertRaises(ValueError):
                read_query_texts(p, sha, ['other'])
            with self.assertRaises(ValueError):
                read_query_texts(p, '0' * 64, ['q'])

    def test_text_hash_policy_and_namespace_must_match(self):
        row = {'page_id': 'doc_page_0001', 'document_id': 'doc', 'page_number': 1,
               'text': '', 'text_sha256': hashlib.sha256(b'').hexdigest(),
               'policy_sha256': 'a'*64, 'technical_failure': True,
               'extraction_status': 'OCR_TIMEOUT', 'image_sha256': 'b'*64,
               'artifacts': {'image': {'path': 'pages/doc_page_0001/image.png',
                                      'sha256': 'b'*64, 'size_bytes': 10}}}
        handover = {'page_count': 1, 'document_count': 1, 'policy_sha256': 'a'*64}
        self.assertEqual(validate_pages([row], handover)['page_count'], 1)
        for field, value in [('text', 'tampered'), ('policy_sha256', 'c'*64),
                             ('page_id', '../escape'), ('image_sha256', None)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_pages([{**row, field: value}], handover)
        with self.assertRaises(ValueError):
            validate_pages([row, row], {**handover, 'page_count': 2})


if __name__ == '__main__':
    unittest.main()
