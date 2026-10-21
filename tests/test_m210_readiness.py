"""M2.10 checks must reject tampered evidence and invalid coverage claims."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))

from scripts.audit_m210_readiness import audit_coverage, audit_matched_config, audit_revision_bytes
from qpaf.m25.leakage import verify_frozen_splits


class AuditTests(unittest.TestCase):
    def test_recompute_real_coverage_and_reject_false_pass(self):
        freeze = json.loads((ROOT/'configs/m2.5/freeze.json').read_text(encoding='utf-8'))
        splits = verify_frozen_splits(ROOT, freeze)['roles']
        coverage = json.loads((ROOT/'evidence/revisions/m2.8-001/coverage_report.json').read_text(encoding='utf-8'))
        replay = audit_coverage(coverage, splits)
        self.assertEqual(replay['overall']['status'], 'BLOCKED')
        self.assertEqual(len(replay['overall']['uncovered_query_ids']), 1)
        self.assertEqual(replay['by_split']['train']['status'], 'BLOCKED')
        self.assertEqual(replay['by_split']['validation']['status'], 'PASS')
        tampered = copy.deepcopy(coverage)
        tampered['status'] = 'PASS'
        with self.assertRaisesRegex(ValueError, 'Global coverage mismatch'):
            audit_coverage(tampered, splits)
        tampered = copy.deepcopy(coverage)
        tampered['per_query'][0]['captured_relevant'] = 0
        with self.assertRaises(ValueError):
            audit_coverage(tampered, splits)

    def test_hash_manifest_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder/'source.json').write_bytes(b'original')
            manifest = [{'path': 'source.json', 'size_bytes': 8,
                         'sha256': hashlib.sha256(b'original').hexdigest()}]
            (folder/'hashes.json').write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(audit_revision_bytes(folder)['files_rehashed'], 1)
            (folder/'source.json').write_bytes(b'changed!')
            with self.assertRaisesRegex(ValueError, 'byte/hash drift'):
                audit_revision_bytes(folder)

    def test_m27_structural_config_is_still_frozen(self):
        result = audit_matched_config(ROOT)
        self.assertEqual(result['status'], 'PASS_STRUCTURAL_AND_SYNTHETIC_PARITY')
        self.assertEqual(result['source_files_rehashed'], 11)
        self.assertTrue(result['synthetic_parity_replay']['data_order']['identical'])
        self.assertEqual(result['real_cache_binding'], 'PENDING_M2.8_IN_FROZEN_MANIFEST')


if __name__ == '__main__':
    unittest.main()
