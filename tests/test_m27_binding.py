"""M2.7 real-input binding: hashes, accepted M2.8 handover and no-training batch parity."""
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class BindingTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('qpaf.m27.binding')
        except ModuleNotFoundError:
            self.fail('M2.7 real-input binding is not implemented')
        import pandas as pd
        from qpaf.m24.synthetic import make_fixture
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for rel in ('configs/m2.7/matched.json', 'configs/m2.7/shared_base.toml',
                    'configs/m2.4/pipeline.toml', 'evidence/revisions/m2.1-002/data_split_manifest.json',
                    'configs/m2.5/freeze.json'):
            (self.root/rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/rel, self.root/rel)
        bundle = self.root/'bundle'
        (bundle/'splits').mkdir(parents=True)
        rows, queries, qrels, splits = make_fixture(20260820)
        pd.DataFrame(rows).to_parquet(bundle/'raw_scores.parquet')
        (bundle/'candidate_set.parquet').write_bytes(b'candidates')
        (bundle/'candidate_freeze.json').write_text('{}\n', encoding='utf-8')
        dev = {q: qrels[q] for role in ('train', 'validation') for q in splits[role]}
        (bundle/'qrels_development.json').write_text(json.dumps(dev), encoding='utf-8')
        (bundle/'qrels_test_sealed.json').write_text(json.dumps({q: qrels[q] for q in splits['test']}),
                                                     encoding='utf-8')
        (bundle/'queries.json').write_text(json.dumps(queries), encoding='utf-8')
        names = {'train': 'train_ids.txt', 'validation': 'val_ids.txt', 'test': 'test_ids.txt'}
        for role, name in names.items():
            (bundle/'splits'/name).write_text(''.join(q+'\n' for q in splits[role]), encoding='utf-8')
        refs = {'score_cache': 'raw_scores.parquet', 'candidate_set': 'candidate_set.parquet',
                'candidate_freeze': 'candidate_freeze.json', 'qrels_development': 'qrels_development.json',
                'qrels_test_sealed': 'qrels_test_sealed.json', 'query_texts': 'queries.json'}
        handover = {'status': 'PASS', 'policy_id': 'qpaf_m28_top_document_expansion_v1',
                    'uncovered_query_ids': [], 'macro_candidate_recall': 1.0,
                    'max_candidates_per_query': 12,
                    'score_cache_sha256': _sha(bundle/'raw_scores.parquet'),
                    'candidate_freeze_sha256': _sha(bundle/'candidate_freeze.json'),
                    'qrels_development_sha256': _sha(bundle/'qrels_development.json'),
                    'qrels_test_sha256': _sha(bundle/'qrels_test_sealed.json'),
                    'query_texts_sha256': _sha(bundle/'queries.json'),
                    'split_role_sha256': {role: _sha(bundle/'splits'/name) for role, name in names.items()}}
        (bundle/'handover.json').write_text(json.dumps(handover), encoding='utf-8')
        self.binding = {
            'schema_version': 1, 'task_id': 'M2.7', 'binding_id': 'QPAF-M2_7-INPUTS-001',
            'status': 'BOUND_REAL_INPUTS_PENDING_INDEPENDENT_REVIEW',
            'matched_manifest': {'path': 'configs/m2.7/matched.json',
                                 'sha256': _sha(self.root/'configs/m2.7/matched.json')},
            'policy_id': 'qpaf_m28_top_document_expansion_v1',
            'source_run_id': 'RUN-FIXTURE',
            'handover': {'path': 'bundle/handover.json', 'sha256': _sha(bundle/'handover.json')},
            'inputs': {name: {'path': f'bundle/{rel}', 'sha256': _sha(bundle/rel)} for name, rel in refs.items()},
            'splits': {role: {'path': f'bundle/splits/{name}', 'sha256': _sha(bundle/'splits'/name)}
                       for role, name in names.items()},
        }
        self.path = self.root/'binding.json'
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.path.write_text(json.dumps(self.binding, indent=2), encoding='utf-8')

    def test_binding_verifies_hashes_handover_and_real_row_batch_order(self):
        report = self.api.verify_binding(self.api.load_binding(self.path), self.root)
        self.assertEqual(report['status'], 'PASS')
        order = report['real_row_parity']
        self.assertTrue(order['identical'])
        self.assertEqual(order['training_executed'], False)
        self.assertGreater(order['batches'], 0)
        self.assertEqual(set(order['record_counts']), {'train', 'validation'})
        self.assertEqual(report['synthetic_parity']['pairs']['20260820'],
                         {'gate_granularity': ['query', 'page']})

    def test_changed_bound_file_fails_closed(self):
        (self.root/'bundle/qrels_test_sealed.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'qrels_test_sealed'):
            self.api.verify_binding(self.api.load_binding(self.path), self.root)

    def test_blocked_or_mismatched_handover_is_rejected(self):
        handover_path = self.root/'bundle/handover.json'
        handover = json.loads(handover_path.read_text(encoding='utf-8'))
        handover['status'] = 'BLOCKED_COVERAGE'
        handover_path.write_text(json.dumps(handover), encoding='utf-8')
        self.binding['handover']['sha256'] = _sha(handover_path)
        self.write()
        with self.assertRaisesRegex(ValueError, 'handover'):
            self.api.verify_binding(self.api.load_binding(self.path), self.root)

    def test_edited_matched_manifest_is_rejected(self):
        self.binding['matched_manifest']['sha256'] = '0'*64
        self.write()
        with self.assertRaisesRegex(ValueError, 'matched'):
            self.api.verify_binding(self.api.load_binding(self.path), self.root)

    def test_unknown_or_missing_binding_keys_are_rejected(self):
        self.binding['extra'] = True
        self.write()
        with self.assertRaises(ValueError):
            self.api.load_binding(self.path)


if __name__ == '__main__':
    unittest.main()
