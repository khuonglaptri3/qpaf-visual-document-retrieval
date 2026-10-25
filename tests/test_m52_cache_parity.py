"""M5.2 rejects drift and replays batching/features without real label access."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from qpaf.m52 import cache_parity as api


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CacheParityTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        import pyarrow as pa
        import pyarrow.parquet as pq
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        self.config = copy.deepcopy(api.read_base_config(ROOT))
        self.config['training'].update(epochs=2, batch_size=2)
        self.splits = {'train': ['q2', 'q0', 'q1'], 'validation': ['q4', 'q3'], 'test': ['q5']}
        rows, normalized, candidates, queries = [], [], [], {}
        for qi in range(6):
            query = f'q{qi}'
            queries[query] = f'two words {qi}'
            values = np.asarray([[1., 3., 2.], [4., 1., 2.], [2., 2., 2.]])[:2 + qi % 2]
            norm = (values - values.min(0)) / np.where(np.ptp(values, axis=0) == 0, 1., np.ptp(values, axis=0))
            for pi, (raw, unit) in enumerate(zip(values, norm)):
                keys = {'query_id': query, 'page_id': f'p{pi}'}
                candidates.append(keys)
                rows.append(dict(keys, **dict(zip(api.CHANNELS, raw))))
                normalized.append(dict(keys, **dict(zip(api.CHANNELS, unit))))
        for name, data in [('raw_scores.parquet', rows), ('normalized_scores.parquet', normalized),
                           ('candidate_set.parquet', candidates)]:
            pq.write_table(pa.Table.from_pylist(data), self.inputs / name)
        (self.inputs / 'queries.json').write_text(json.dumps(queries), encoding='utf-8')
        (self.inputs / 'splits').mkdir()
        for role, name in api.SPLIT_FILES.items():
            (self.inputs / 'splits' / name).write_text('\n'.join(self.splits[role]) + '\n', encoding='utf-8')
        for name in ['shared_base.toml', 'matched.json']:
            shutil.copyfile(ROOT / 'configs/m2.7' / name, self.inputs / name)
        path = self.inputs / 'shared_base.toml'
        path.write_text(path.read_text(encoding='utf-8').replace('epochs = 20', 'epochs = 2')
                        .replace('batch_size = 16', 'batch_size = 2'), encoding='utf-8')
        (self.inputs / 'candidate_freeze.json').write_text('{}\n', encoding='utf-8')
        self.contract = {name: {'sha256': digest(self.inputs / name),
                               'size_bytes': (self.inputs / name).stat().st_size,
                               'm42_path': 'inputs/' + name}
                         for name in api.INPUT_FILES}
        self.records, self.audit = api.load_label_free_inputs(self.inputs, self.contract, 600)

    def test_records_have_no_label_fields_and_match_frozen_batch_path(self):
        import torch
        from qpaf.m24.dataset import QueryRecord
        from qpaf.m31.parity import fingerprint_view
        # Synthetic labels are used only by this independent legacy reference.
        reference = {role: [QueryRecord(r.query_id, r.text, r.page_ids, r.raw_scores,
                                        tuple(0 for _ in r.page_ids), 0) for r in records]
                     for role, records in self.records.items()}
        self.assertFalse(hasattr(self.records['train'][0], 'labels'))
        self.assertFalse(hasattr(self.records['train'][0], 'relevant_total'))
        before = torch.random.get_rng_state().clone()
        actual = api.fingerprint_view(self.records, self.config)
        historical = fingerprint_view(reference, self.config)
        api.check_historical(actual, historical)
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        self.assertNotIn('labels', actual['train']['components'])

    def test_seed_changes_training_shuffle_but_not_validation(self):
        first = api.fingerprint_view(self.records, self.config)
        second_config = copy.deepcopy(self.config)
        second_config['training']['seed'] += 1
        second = api.fingerprint_view(self.records, second_config)
        self.assertNotEqual(first['train']['batch_order_sha256'], second['train']['batch_order_sha256'])
        self.assertEqual(first['validation'], second['validation'])

    def test_rejects_changed_raw_cache_hash_before_loading(self):
        with (self.inputs / 'raw_scores.parquet').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(api.CacheParityError, 'hash'):
            api.load_label_free_inputs(self.inputs, self.contract, 600)

    def test_rejects_extra_label_column_before_reading_table_data(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        path = self.inputs / 'raw_scores.parquet'
        table = pq.read_table(path).append_column('relevance', pa.array([0] * self.audit['candidate_rows']))
        pq.write_table(table, path)
        with patch.object(pq.ParquetFile, 'read', side_effect=AssertionError('Data must not be read')):
            with self.assertRaisesRegex(api.CacheParityError, 'schema'):
                api.read_label_free_table(path, api.SCORE_COLUMNS)

    def test_rejects_changed_candidate_order_and_wrong_normalization(self):
        raw = api.read_label_free_table(self.inputs / 'raw_scores.parquet', api.SCORE_COLUMNS)
        norm = api.read_label_free_table(self.inputs / 'normalized_scores.parquet', api.SCORE_COLUMNS)
        candidates = api.read_label_free_table(self.inputs / 'candidate_set.parquet', ('query_id', 'page_id'))
        queries = json.loads((self.inputs / 'queries.json').read_text(encoding='utf-8'))
        reversed_candidates = candidates.take(list(reversed(range(candidates.num_rows))))
        with self.assertRaisesRegex(api.CacheParityError, 'order'):
            api.audit_tables(raw, norm, reversed_candidates, self.splits, queries, 600)
        changed = norm.to_pylist()
        changed[0]['bm25_score'] += .2
        import pyarrow as pa
        with self.assertRaisesRegex(api.CacheParityError, 'normalization'):
            api.audit_tables(raw, pa.Table.from_pylist(changed), candidates, self.splits, queries, 600)

    def test_rejects_nonfinite_scores_overlapping_splits_and_missing_query(self):
        import pyarrow as pa
        raw = api.read_label_free_table(self.inputs / 'raw_scores.parquet', api.SCORE_COLUMNS)
        norm = api.read_label_free_table(self.inputs / 'normalized_scores.parquet', api.SCORE_COLUMNS)
        candidates = api.read_label_free_table(self.inputs / 'candidate_set.parquet', ('query_id', 'page_id'))
        queries = json.loads((self.inputs / 'queries.json').read_text(encoding='utf-8'))
        changed = raw.to_pylist()
        changed[0]['bm25_score'] = float('nan')
        with self.assertRaisesRegex(api.CacheParityError, 'finite'):
            api.audit_tables(pa.Table.from_pylist(changed), norm, candidates, self.splits, queries, 600)
        splits = copy.deepcopy(self.splits)
        splits['test'].append('q0')
        with self.assertRaisesRegex(api.CacheParityError, 'split'):
            api.audit_tables(raw, norm, candidates, splits, queries, 600)
        del queries['q0']
        with self.assertRaisesRegex(api.CacheParityError, 'query text'):
            api.audit_tables(raw, norm, candidates, self.splits, queries, 600)

    def test_method_and_historical_drift_are_detected(self):
        first = api.fingerprint_view(self.records, self.config)
        second = copy.deepcopy(first)
        second['train']['components']['features'] = '0' * 64
        with self.assertRaisesRegex(api.CacheParityError, 'parity'):
            api.compare_methods({'QARF': first, 'QPAF': second})
        with self.assertRaisesRegex(api.CacheParityError, 'historical'):
            api.check_historical(first, second)

    def test_matrix_rejects_seed_substitution_and_nonseed_config_change(self):
        matrix = api.resolve_matrix(self.config)
        api.validate_matrix(matrix, self.config)
        altered = copy.deepcopy(matrix)
        altered[2]['seed'] = 20260823
        with self.assertRaisesRegex(api.CacheParityError, 'matrix'):
            api.validate_matrix(altered, self.config)
        altered = copy.deepcopy(matrix)
        altered[-1]['config']['training']['learning_rate'] *= 2
        with self.assertRaisesRegex(api.CacheParityError, 'matrix'):
            api.validate_matrix(altered, self.config)

    def test_wrong_numerical_runtime_is_rejected_before_payload_loading(self):
        expected = api.runtime_versions()
        changed = dict(expected, torch='unexpected-version')
        with patch.object(api, 'load_authority', return_value={'runtime': expected}), \
                patch.object(api, 'runtime_versions', return_value=changed), \
                patch.object(api, 'load_label_free_inputs', side_effect=AssertionError('Must not load')):
            with self.assertRaisesRegex(api.CacheParityError, 'runtime'):
                api.collect(self.root, self.inputs, '2026-10-25T00:00:00+00:00', 'a' * 40)

    def test_restore_reads_only_allowlisted_members_and_never_overwrites(self):
        archive = self.root / 'bundle.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for name in api.INPUT_FILES:
                z.write(self.inputs / name, api.ARCHIVE_ROOT + '/inputs/' + name)
            z.writestr(api.ARCHIVE_ROOT + '/inputs/qrels_development.json', 'MUST NOT READ')
            z.writestr('../outside.txt', 'MUST NOT EXTRACT')
        original_open = zipfile.ZipFile.open
        opened = []
        def guarded_open(z, member, *args, **kwargs):
            name = member.filename if isinstance(member, zipfile.ZipInfo) else member
            self.assertNotIn('qrels', name)
            self.assertNotIn('..', name)
            opened.append(name)
            return original_open(z, member, *args, **kwargs)
        output = self.root / 'restored'
        with patch.object(zipfile.ZipFile, 'open', guarded_open):
            result = api.restore_inputs(archive, output, self.contract, digest(archive))
        self.assertEqual(len(opened), len(api.INPUT_FILES))
        self.assertFalse(result['label_files_deserialized'])
        self.assertFalse((self.root / 'outside.txt').exists())
        self.assertEqual(digest(output / 'raw_scores.parquet'), self.contract['raw_scores.parquet']['sha256'])
        with self.assertRaisesRegex(api.CacheParityError, 'exists'):
            api.restore_inputs(archive, output, self.contract, digest(archive))

    def test_restore_rejects_bad_archive_or_member_bytes(self):
        archive = self.root / 'bad.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for name in api.INPUT_FILES:
                z.writestr(api.ARCHIVE_ROOT + '/inputs/' + name, b'changed')
        with self.assertRaisesRegex(api.CacheParityError, 'archive hash'):
            api.restore_inputs(archive, self.root / 'bad-output', self.contract, '0' * 64)
        with self.assertRaisesRegex(api.CacheParityError, 'member'):
            api.restore_inputs(archive, self.root / 'bad-output', self.contract, digest(archive))
        self.assertFalse((self.root / 'bad-output').exists())

    def test_production_authority_detects_pinned_record_drift(self):
        authority = api.load_authority(ROOT)
        self.assertEqual(authority['split_counts'], {'train': 799, 'validation': 171, 'test': 172})
        source = self.root / 'authority'
        for name, (relative, _) in api.PINS.items():
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        path = source / api.PINS['g2a'][0]
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(api.CacheParityError, 'g2a.*hash'):
            api.load_authority(source)

    def test_create_verify_is_read_only_and_rejects_receipt_or_input_tampering(self):
        historical = api.fingerprint_view(self.records, self.config)
        for relative in api.SOURCE_FILES:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        authority = {'pins': {}, 'contract': self.contract, 'config': self.config,
                     'runtime': api.runtime_versions(), 'historical': {'QARF': historical, 'QPAF': historical},
                     'split_counts': {k: len(v) for k, v in self.splits.items()},
                     'expected_candidate_rows': self.audit['candidate_rows'], 'external_seal': {'status': 'SEALED'},
                     'method_sources': {}}
        output = self.root / 'evidence'
        with patch.object(api, 'load_authority', return_value=authority), \
                patch.object(api, 'source_commit', return_value='a' * 40):
            receipt = api.create(self.root, self.inputs, output)
            receipt_hash = digest(output / 'cache_identity.json')
            before = {str(p.relative_to(self.root)): digest(p) for p in self.root.rglob('*') if p.is_file()}
            self.assertEqual(api.verify(self.root, self.inputs, output, receipt_hash)['status'], 'PASS')
            after = {str(p.relative_to(self.root)): digest(p) for p in self.root.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(len(receipt['matrix']), 6)
            self.assertFalse(receipt['boundaries']['labels_deserialized'])
            self.assertEqual(receipt['independent_human_review'], 'PENDING_USER_REVIEW')
            with self.assertRaisesRegex(api.CacheParityError, 'exists'):
                api.create(self.root, self.inputs, output)
            with self.assertRaisesRegex(api.CacheParityError, 'receipt hash'):
                api.verify(self.root, self.inputs, output, '0' * 64)
            path = self.inputs / 'raw_scores.parquet'
            path.write_bytes(path.read_bytes() + b'changed')
            with self.assertRaisesRegex(api.CacheParityError, 'hash'):
                api.verify(self.root, self.inputs, output, receipt_hash)


if __name__ == '__main__':
    unittest.main()
