"""Pilot sealing rejects drift and proves real input parity without training."""
import copy
from dataclasses import replace
import hashlib
import importlib
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return {'path': path.name, 'sha256': sha(path)}


class SealTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('qpaf.m31.seal')
        except ModuleNotFoundError:
            self.fail('M3.1 sealed pilot inputs are not implemented')
        import pyarrow as pa
        import pyarrow.parquet as pq
        from qpaf.m24.synthetic import make_fixture
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in (*self.api.SOURCE_FILES, 'configs/m2.7/matched.json',
                    'configs/m2.7/shared_base.toml', 'configs/m2.4/pipeline.toml',
                    'configs/m2.5/freeze.json',
                    'docs/GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx'):
            destination = self.root/rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/rel, destination)
        # The fixture pins the runtime available to this test job; the real config
        # continues to use the repository's matched CPU requirements.
        (self.root/'requirements-learned-local.txt').write_text('torch=='+version('torch')+'\n', encoding='utf-8')
        rows, queries, qrels, splits = make_fixture(queries_per_role=(2, 1, 1), candidates=3)
        rows.sort(key=lambda row: (row['query_id'], row['page_id']))
        # Use fully covered development qrels, matching the declared handover.
        available = {(row['query_id'], row['page_id']) for row in rows}
        qrels = {q: {p: v for p, v in judged.items() if (q, p) in available}
                 for q, judged in qrels.items()}
        bundle = self.root/'bundle'
        bundle.mkdir()
        pq.write_table(pa.Table.from_pylist(rows), bundle/'raw_scores.parquet')
        pq.write_table(pa.Table.from_pylist([{k: row[k] for k in ('query_id', 'page_id')}
                                           for row in rows]), bundle/'candidate_set.parquet')
        write(bundle/'candidate_freeze.json', {'status': 'FROZEN', 'policy': {'policy_id': 'fixture'}})
        write(bundle/'queries.json', queries)
        write(bundle/'qrels_development.json', {q: qrels[q] for role in ('train', 'validation') for q in splits[role]})
        # Any accidental JSON parsing of test labels must fail, even on the happy path.
        (bundle/'qrels_test_sealed.json').write_bytes(b'SEALED: DO NOT PARSE TEST LABELS')
        names = {'train': 'train_ids.txt', 'validation': 'val_ids.txt', 'test': 'test_ids.txt'}
        master = {'status': 'VERIFIED_ACTIVE_PRIMARY_SPLITS', 'roles': {}}
        for role, filename in names.items():
            p = bundle/'splits'/filename
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(''.join(q+'\n' for q in splits[role]).encode())
            master['roles'][role] = {'count': len(splits[role]), 'sha256': sha(p)}
        master_path = self.root/'split_manifest.json'
        write(master_path, master)
        matched_path = self.root/'configs/m2.7/matched.json'
        matched = json.loads(matched_path.read_text())
        matched['shared_inputs']['split_manifest'] = {'path': 'split_manifest.json', 'sha256': sha(master_path)}
        write(matched_path, matched)
        refs = {'score_cache': 'raw_scores.parquet', 'candidate_set': 'candidate_set.parquet',
                'candidate_freeze': 'candidate_freeze.json', 'qrels_development': 'qrels_development.json',
                'qrels_test_sealed': 'qrels_test_sealed.json', 'query_texts': 'queries.json'}
        binding = json.loads((ROOT/'configs/m2.7/input_binding.json').read_text())
        binding['matched_manifest']['sha256'] = sha(matched_path)
        binding['inputs'] = {k: {'path': 'bundle/'+v, 'sha256': sha(bundle/v)} for k, v in refs.items()}
        binding['splits'] = {role: {'path': 'bundle/splits/'+name, 'sha256': sha(bundle/'splits'/name)} for role, name in names.items()}
        handover = {'status': 'PASS', 'policy_id': binding['policy_id'], 'run_id': binding['source_run_id'],
                    'uncovered_query_ids': [], 'macro_candidate_recall': 1.0,
                    'candidate_count': len(rows), 'max_candidates_per_query': 3,
                    'split_role_sha256': {k: v['sha256'] for k,v in binding['splits'].items()}}
        for key, field in self.api.HANDOVER_HASHES.items():
            handover[field] = binding['inputs'][key]['sha256']
        write(bundle/'handover.json', handover)
        binding['handover'] = {'path': 'bundle/handover.json', 'sha256': sha(bundle/'handover.json')}
        write(self.root/'binding.json', binding)
        prior = {'status': 'PASS', 'binding_sha256': sha(self.root/'binding.json'),
                 'real_row_parity': {'identical': True, 'training_executed': False}}
        write(self.root/'prior.json', prior)
        d1 = {'task_id': 'M2.11', 'decision': 'PASS', 'pilot_input_package_ready': True,
              'decision_basis': {'m2_7': {'binding_sha256': sha(self.root/'binding.json'),
                                         'sha256': sha(self.root/'prior.json')},
                                 'm2_8': {'sha256': sha(bundle/'handover.json')}}}
        write(self.root/'d1.json', d1)
        self.config = {name: {'path': path, 'sha256': sha(self.root/path)} for name, path in {
            'authority': 'docs/GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx',
            'binding': 'binding.json', 'd1': 'd1.json', 'prior_binding_verification': 'prior.json'}.items()}
        self.output = self.root/'sealed'

    def seal(self):
        result = self.api.seal_inputs(self.root, self.root, self.output, self.config)
        self.pin = sha(self.output/'manifest.json')
        return result

    def test_seals_and_replays_inputs_without_opening_test_labels(self):
        result = self.seal()
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(result['training_executed'])
        self.assertFalse(result['test_labels_opened'])
        self.assertEqual(result['parity']['record_counts'], {'train': 2, 'validation': 1})
        self.assertEqual(result['parity']['candidate_rows'], {'train': 6, 'validation': 3})
        self.assertTrue((self.output/'_SUCCESS.json').is_file())
        replay = self.api.verify_seal(self.root, self.output, expected_manifest_sha256=self.pin)
        self.assertEqual(replay['parity'], result['parity'])

    def test_cannot_replace_an_existing_seal(self):
        self.output.mkdir()
        (self.output/'keep').write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            self.seal()
        self.assertEqual((self.output/'keep').read_bytes(), b'keep')

    def test_changed_source_payload_is_rejected_before_success(self):
        (self.root/'bundle/queries.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'query_texts|hash'):
            self.seal()
        self.assertFalse((self.output/'_SUCCESS.json').exists())

    def test_blocked_d1_cannot_seal(self):
        p = self.root/'d1.json'
        d1 = json.loads(p.read_text())
        d1['decision'] = 'BLOCKED'
        write(p, d1)
        self.config['d1']['sha256'] = sha(p)
        with self.assertRaisesRegex(ValueError, 'D1'):
            self.seal()

    def test_insufficient_development_coverage_cannot_pass_from_metadata_alone(self):
        p = self.root/'bundle/qrels_development.json'
        qrels = json.loads(p.read_text())
        for judged in qrels.values():
            judged['positive-outside-pool'] = 1
        write(p, qrels)
        binding_path = self.root/'binding.json'
        binding = json.loads(binding_path.read_text())
        binding['inputs']['qrels_development']['sha256'] = sha(p)
        handover_path = self.root/'bundle/handover.json'
        handover = json.loads(handover_path.read_text())
        handover['qrels_development_sha256'] = sha(p)
        write(handover_path, handover)
        binding['handover']['sha256'] = sha(handover_path)
        write(binding_path, binding)
        self.config['binding']['sha256'] = sha(binding_path)
        prior_path = self.root/'prior.json'
        prior = json.loads(prior_path.read_text())
        prior['binding_sha256'] = sha(binding_path)
        write(prior_path, prior)
        self.config['prior_binding_verification']['sha256'] = sha(prior_path)
        d1_path = self.root/'d1.json'
        d1 = json.loads(d1_path.read_text())
        d1['decision_basis']['m2_7'] = {'binding_sha256': sha(binding_path), 'sha256': sha(prior_path)}
        d1['decision_basis']['m2_8']['sha256'] = sha(handover_path)
        write(d1_path, d1)
        self.config['d1']['sha256'] = sha(d1_path)
        with self.assertRaisesRegex(ValueError, 'coverage|recall'):
            self.seal()

    def test_modified_sealed_payload_is_rejected_on_replay(self):
        self.seal()
        p = self.output/'inputs/query_texts.json'
        p.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'hash|query_texts'):
            self.api.verify_seal(self.root, self.output, expected_manifest_sha256=self.pin)

    def test_source_code_drift_is_rejected_on_replay(self):
        self.seal()
        p = self.root/'src/qpaf/m12/features.py'
        p.write_bytes(p.read_bytes()+b'\n# changed\n')
        with self.assertRaisesRegex(ValueError, 'source|features|hash'):
            self.api.verify_seal(self.root, self.output, expected_manifest_sha256=self.pin)

    def test_rewritten_local_manifest_cannot_replace_the_external_pin(self):
        self.seal()
        expected = sha(self.output/'manifest.json')
        manifest = json.loads((self.output/'manifest.json').read_text())
        manifest['source_commit'] = 'forged-local-metadata'
        write(self.output/'manifest.json', manifest)
        marker = json.loads((self.output/'_SUCCESS.json').read_text())
        marker['manifest_sha256'] = sha(self.output/'manifest.json')
        write(self.output/'_SUCCESS.json', marker)
        try:
            with self.assertRaisesRegex(ValueError, 'manifest|pin'):
                self.api.verify_seal(self.root, self.output, expected_manifest_sha256=expected)
        except TypeError:
            self.fail('External manifest pin verification is not implemented')

    def test_mismatched_runtime_requirements_cannot_seal(self):
        (self.root/'requirements-learned-local.txt').write_text('torch==0.0.0\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'runtime|torch'):
            self.seal()

    def test_label_column_in_score_cache_is_rejected(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        p = self.root/'bundle/raw_scores.parquet'
        table = pq.read_table(p)
        pq.write_table(table.append_column('relevance', pa.array([1]*table.num_rows)), p)
        # Exercise semantic validation after successful integrity verification.
        with self.assertRaisesRegex(ValueError, 'schema|label|columns'):
            self.api.audit_cache(p, self.root/'bundle/candidate_set.parquet',
                                 {'train': ['x'], 'validation': [], 'test': []}, 600)

    def test_different_candidates_are_rejected(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        p = self.root/'bundle/candidate_set.parquet'
        rows = pq.read_table(p).to_pylist()
        rows[0]['page_id'] = 'wrong-page'
        pq.write_table(pa.Table.from_pylist(rows), p)
        with self.assertRaisesRegex(ValueError, 'candidate'):
            self.api.audit_cache(self.root/'bundle/raw_scores.parquet', p,
                                 {'train': ['x'], 'validation': [], 'test': []}, 600)

    def test_parity_detects_row_order_and_labels_independently(self):
        from qpaf.m24.config import load_config
        from qpaf.m24.dataset import build_records
        from qpaf.m24.synthetic import make_fixture
        from qpaf.m31.parity import compare_views, fingerprint_view
        rows, queries, qrels, splits = make_fixture(queries_per_role=(2,1,1), candidates=3)
        left = build_records(rows, queries, qrels, splits, ('train','validation'))
        config = load_config(ROOT/'configs/m2.7/shared_base.toml')
        config['training']['epochs'] = 2
        for field in ('page_ids', 'labels'):
            right = copy.deepcopy(left)
            record = right['train'][0]
            changed = tuple(reversed(record.page_ids)) if field == 'page_ids' else tuple(1-x for x in record.labels)
            right['train'][0] = replace(record, **{field: changed})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'parity'):
                compare_views({'QARF': left, 'QPAF': right}, config)
        right = copy.deepcopy(left)
        right['train'][0] = replace(right['train'][0], labels=tuple(1-x for x in right['train'][0].labels))
        a, b = fingerprint_view(left, config), fingerprint_view(right, config)
        self.assertEqual(a['train']['components']['features'], b['train']['components']['features'])
        self.assertNotEqual(a['train']['components']['labels'], b['train']['components']['labels'])


if __name__ == '__main__':
    unittest.main()
