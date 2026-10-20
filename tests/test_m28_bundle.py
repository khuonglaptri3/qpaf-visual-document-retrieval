"""Candidate construction and publication must stay independent of relevance."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


class CandidateConstructionTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('qpaf.m28.bundle')
        except ModuleNotFoundError:
            self.fail('M2.8 label-free candidate bundle is not implemented')
        self.qids = ['q2', 'q1']
        self.pids = ['p3', 'p1', 'p4', 'p2']
        self.scores = {
            'bm25': np.array([[8, 8, -100, 1], [4, 4, 4, 4]], dtype=np.float64),
            'dense': np.array([[0, 0, -30, 10], [5, 1, -50, 3]], dtype=np.float64),
            'visual': np.array([[11, 0, -5, 0], [9, 0, -5, 0]], dtype=np.float64),
        }

    def build(self, **kwargs):
        return self.api.build_candidates(
            kwargs.get('scores', self.scores), kwargs.get('query_ids', self.qids),
            kwargs.get('page_ids', self.pids), kwargs.get('top_k', 1))

    def test_ties_and_union_keep_all_channels_with_five_columns(self):
        bundle = self.build()
        self.assertEqual(bundle['candidates'], [
            {'query_id': 'q2', 'page_id': 'p1'},
            {'query_id': 'q2', 'page_id': 'p2'},
            {'query_id': 'q2', 'page_id': 'p3'},
            {'query_id': 'q1', 'page_id': 'p1'},
            {'query_id': 'q1', 'page_id': 'p3'},
        ])
        self.assertEqual(bundle['raw_rows'][0], {
            'query_id': 'q2', 'page_id': 'p1', 'bm25_score': 8.0,
            'dense_score': 0.0, 'visual_score': 0.0})
        self.assertEqual(bundle['top_lists'], [
            {'query_id': 'q2', 'page_id': 'p1', 'channel': 'bm25', 'rank': 1, 'raw_score': 8.0},
            {'query_id': 'q2', 'page_id': 'p2', 'channel': 'dense', 'rank': 1, 'raw_score': 10.0},
            {'query_id': 'q2', 'page_id': 'p3', 'channel': 'visual', 'rank': 1, 'raw_score': 11.0},
            {'query_id': 'q1', 'page_id': 'p1', 'channel': 'bm25', 'rank': 1, 'raw_score': 4.0},
            {'query_id': 'q1', 'page_id': 'p3', 'channel': 'dense', 'rank': 1, 'raw_score': 5.0},
            {'query_id': 'q1', 'page_id': 'p3', 'channel': 'visual', 'rank': 1, 'raw_score': 9.0},
        ])
        self.assertEqual(bundle['counts']['candidate_count'], 5)
        self.assertEqual(bundle['counts']['query_count'], 2)
        self.assertEqual(bundle['counts']['page_count'], 4)
        self.assertTrue(all(list(row) == ['query_id', 'page_id', 'bm25_score',
                                        'dense_score', 'visual_score']
                            for row in bundle['raw_rows']))

    def test_normalization_uses_union_not_corpus_and_zeroes_constant_channel(self):
        rows = self.build()['normalized_rows']
        self.assertEqual([(r['bm25_score'], r['dense_score'], r['visual_score']) for r in rows],
                         [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 1.0),
                          (0.0, 0.0, 0.0), (0.0, 1.0, 1.0)])

    def test_float64_range_at_epsilon_is_exact_zero(self):
        scores = {channel: np.array([[0.0, 1e-15]]) for channel in self.scores}
        bundle = self.api.build_candidates(scores, ['q'], ['p1', 'p2'], top_k=2)
        self.assertEqual([row['dense_score'] for row in bundle['normalized_rows']], [0.0, 0.0])
        scores['dense'][0, 1] = np.nextafter(1e-15, np.inf)
        bundle = self.api.build_candidates(scores, ['q'], ['p1', 'p2'], top_k=2)
        self.assertEqual([row['dense_score'] for row in bundle['normalized_rows']], [0.0, 1.0])

    def test_default_depth_caps_at_number_of_pages(self):
        bundle = self.api.build_candidates(self.scores, self.qids, self.pids)
        self.assertEqual(bundle['counts']['candidate_count'], 8)
        self.assertEqual(len(bundle['top_lists']), 24)

    def test_invalid_array_values_and_shapes_fail_closed(self):
        bad_scores = []
        for bad in (np.nan, np.inf, -np.inf):
            values = copy.deepcopy(self.scores)
            values['visual'][0, 2] = bad  # A page outside the selected union still matters.
            bad_scores.append(values)
        for bad in (np.ones((2, 4), dtype=bool), np.full((2, 4), '1'),
                    np.array([[1, 2, 3, 4], [1, True, 3, 4]], dtype=object),
                    np.ones((2, 3)), np.ones((2, 4), dtype=complex)):
            values = dict(self.scores, dense=bad)
            bad_scores.append(values)
        bad_scores.extend([{'bm25': self.scores['bm25'], 'dense': self.scores['dense']},
                           dict(self.scores, label=np.ones((2, 4)))])
        for scores in bad_scores:
            with self.subTest(scores=scores), self.assertRaises(ValueError):
                self.build(scores=scores)

    def test_invalid_ids_and_depth_fail_closed(self):
        invalid = [dict(query_ids=['q1', 'q1']), dict(query_ids=['q1', '']),
                   dict(query_ids=['q1', ' q2']), dict(query_ids=['q1', 2]),
                   dict(page_ids=['p1', 'p1', 'p3', 'p4']),
                   dict(page_ids=['p1', 'p2', None, 'p4']), dict(query_ids=[]),
                   dict(top_k=0), dict(top_k=-1), dict(top_k=True), dict(top_k=1.5)]
        for case in invalid:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.build(**case)


class CandidatePublicationTests(unittest.TestCase):
    setUp = CandidateConstructionTests.setUp
    build = CandidateConstructionTests.build

    def freeze(self, directory):
        self.assertTrue(callable(getattr(self.api, 'freeze_candidates', None)),
                        'Create-once candidate publication is not implemented')
        return self.api.freeze_candidates(Path(directory), self.build(), {'run_id': 'fixture'})

    def verify(self, directory, scores=None):
        self.assertTrue(callable(getattr(self.api, 'verify_candidates', None)),
                        'Candidate semantic verification is not implemented')
        return self.api.verify_candidates(Path(directory), scores or self.scores,
                                          self.qids, self.pids, top_k=1)

    @staticmethod
    def refresh_hash(directory, filename):
        manifest_path = Path(directory)/'candidate_freeze.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        data = (Path(directory)/filename).read_bytes()
        manifest['artifacts'][filename]['sha256'] = hashlib.sha256(data).hexdigest()
        manifest['artifacts'][filename]['size_bytes'] = len(data)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')

    def test_frozen_parquet_schemas_and_existing_trainers_are_compatible(self):
        from qpaf.m24.dataset import build_records, read_score_rows
        from qpaf.m25.leakage import audit_score_rows
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.freeze(directory)
            self.assertEqual(set(manifest['artifacts']), {
                'raw_scores.parquet', 'normalized_scores.parquet',
                'channel_top_lists.parquet', 'candidate_set.parquet'})
            self.assertEqual(manifest['provenance'], {'run_id': 'fixture'})
            self.assertTrue(manifest['created_utc'].endswith('Z'))
            self.assertEqual(json.loads((Path(directory)/'candidate_freeze.json').read_text()), manifest)
            raw_path = Path(directory)/'raw_scores.parquet'
            schema = pq.read_schema(raw_path)
            self.assertEqual(schema.names, ['query_id', 'page_id', 'bm25_score',
                                            'dense_score', 'visual_score'])
            self.assertEqual(schema.types, [pa.string(), pa.string(), pa.float64(),
                                           pa.float64(), pa.float64()])
            self.assertEqual(pq.read_schema(Path(directory)/'channel_top_lists.parquet').types,
                             [pa.string(), pa.string(), pa.string(), pa.int64(), pa.float64()])
            rows = read_score_rows(raw_path)
            splits = {'train': ['q2'], 'validation': ['q1'], 'test': []}
            self.assertEqual(audit_score_rows(rows, splits)['status'], 'PASS')
            records = build_records(rows, {'q1': 'one', 'q2': 'two'},
                                    {'q1': {'p1': 1}, 'q2': {'p2': 1}}, splits,
                                    ['train', 'validation'])
            self.assertEqual(records['train'][0].raw_scores[0], (8.0, 0.0, 0.0))
            result = self.verify(directory)
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(result['candidate_freeze_sha256'], hashlib.sha256(
                (Path(directory)/'candidate_freeze.json').read_bytes()).hexdigest())

    def test_publication_is_create_once_and_preserves_first_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            self.freeze(directory)
            before = {p.name: p.read_bytes() for p in Path(directory).iterdir()}
            with self.assertRaises(FileExistsError):
                self.freeze(directory)
            self.assertEqual({p.name: p.read_bytes() for p in Path(directory).iterdir()}, before)

    def test_publication_rejects_label_columns_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self.build()
            bundle['raw_rows'][0]['relevance'] = 1
            self.assertTrue(callable(getattr(self.api, 'freeze_candidates', None)))
            with self.assertRaises(ValueError):
                self.api.freeze_candidates(Path(directory), bundle, {})
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_changed_artifact_bytes_fail_hash_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            self.freeze(directory)
            path = Path(directory)/'raw_scores.parquet'
            with path.open('ab') as handle:
                handle.write(b'tampered')
            with self.assertRaises(ValueError):
                self.verify(directory)

    def test_semantic_verification_rejects_rehashed_scores_toplists_and_candidates(self):
        cases = [('raw_scores.parquet', 'dense_score', 99.0),
                 ('normalized_scores.parquet', 'visual_score', 0.5),
                 ('channel_top_lists.parquet', 'rank', 2),
                 ('candidate_set.parquet', 'page_id', 'p4')]
        for filename, column, value in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                self.freeze(directory)
                path = Path(directory)/filename
                table = pq.read_table(path)
                rows = table.to_pylist()
                rows[0][column] = value
                pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), path)
                self.refresh_hash(directory, filename)
                with self.assertRaises(ValueError):
                    self.verify(directory)

    def test_wrong_float_precision_is_rejected_after_rehashing(self):
        with tempfile.TemporaryDirectory() as directory:
            self.freeze(directory)
            path = Path(directory)/'raw_scores.parquet'
            table = pq.read_table(path)
            field = pa.field('dense_score', pa.float32(), nullable=False)
            schema = table.schema.set(3, field)
            pq.write_table(table.cast(schema), path)
            self.refresh_hash(directory, path.name)
            with self.assertRaises(ValueError):
                self.verify(directory)

    def test_complete_array_identity_includes_pages_outside_union(self):
        with tempfile.TemporaryDirectory() as directory:
            self.freeze(directory)
            changed = copy.deepcopy(self.scores)
            changed['bm25'][0, 2] = -101.0
            with self.assertRaises(ValueError):
                self.verify(directory, changed)


class CandidateCoverageTests(unittest.TestCase):
    setUp = CandidateConstructionTests.setUp
    build = CandidateConstructionTests.build

    def audit(self, candidates=None, qrels=None, query_ids=None, splits=None):
        self.assertTrue(callable(getattr(self.api, 'audit_coverage', None)),
                        'Full-denominator page-coverage audit is not implemented')
        return self.api.audit_coverage(
            self.build()['candidates'] if candidates is None else candidates,
            {'q2': {'p2': 1, 'p4': 1}, 'q1': {'p1': 1, 'p3': 2, 'p4': 0}}
            if qrels is None else qrels,
            self.qids if query_ids is None else query_ids,
            {'train': ['q2'], 'validation': ['q1'], 'test': []} if splits is None else splits)

    def test_positives_outside_union_stay_in_full_denominator(self):
        result = self.audit()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['evaluation_unit'], 'page')
        self.assertEqual(result['macro_recall'], 0.75)
        self.assertEqual(result['uncovered_query_ids'], [])
        self.assertEqual(result['per_query'][0], {
            'query_id': 'q2', 'candidate_count': 3, 'relevant_total': 2,
            'captured_relevant': 1, 'recall': 0.5})
        self.assertEqual(result['by_split']['train']['macro_recall'], 0.5)
        self.assertEqual(result['by_split']['validation']['macro_recall'], 1.0)

    def test_uncovered_queries_are_retained_even_when_macro_exceeds_threshold(self):
        query_ids = [f'q{index:02}' for index in range(21)]
        candidates = [{'query_id': query_id, 'page_id': 'p1'} for query_id in query_ids[:-1]]
        qrels = {query_id: {'p1': 1} for query_id in query_ids}
        splits = {'train': query_ids[:-1], 'validation': [], 'test': query_ids[-1:]}
        result = self.audit(candidates, qrels, query_ids, splits)
        self.assertGreater(result['macro_recall'], 0.95)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(len(result['per_query']), 21)
        self.assertEqual(result['uncovered_query_ids'], ['q20'])
        self.assertEqual(result['by_split']['test']['uncovered_query_ids'], ['q20'])

    def test_threshold_is_inclusive_and_zero_positive_qrels_block(self):
        candidates = [{'query_id': 'q', 'page_id': f'p{index}'} for index in range(19)]
        qrels = {'q': {f'p{index}': 1 for index in range(20)}}
        splits = {'train': ['q'], 'validation': [], 'test': []}
        result = self.audit(candidates, qrels, ['q'], splits)
        self.assertEqual(result['macro_recall'], 0.95)
        self.assertEqual(result['status'], 'PASS')
        result = self.audit(candidates, {'q': {'p0': 0}}, ['q'], splits)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['uncovered_query_ids'], ['q'])
        self.assertEqual(result['per_query'][0]['relevant_total'], 0)

    def test_all_1142_queries_including_test_are_audited(self):
        query_ids = [f'q{index:04}' for index in range(1142)]
        candidates = [{'query_id': query_id, 'page_id': 'p1'} for query_id in query_ids]
        qrels = {query_id: {'p1': 1} for query_id in query_ids}
        splits = {'train': query_ids[:799], 'validation': query_ids[799:970],
                  'test': query_ids[970:]}
        result = self.audit(candidates, qrels, query_ids, splits)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(len(result['per_query']), 1142)
        self.assertEqual(result['by_split']['test']['query_count'], 172)
        self.assertEqual(result['by_split']['test']['macro_recall'], 1.0)

    def test_invalid_candidates_qrels_and_split_namespaces_fail(self):
        candidates = self.build()['candidates']
        qrels = {'q2': {'p2': 1}, 'q1': {'p1': 1}}
        invalid = [dict(candidates=candidates+[candidates[0]]),
                   dict(candidates=[{'query_id': 'orphan', 'page_id': 'p1'}]),
                   dict(candidates=[{'query_id': 'q1', 'page_id': ''}]),
                   dict(qrels={'q2': {'p2': 1}}),
                   dict(qrels=dict(qrels, q1={'p1': True})),
                   dict(qrels=dict(qrels, q1={'p1': np.inf})),
                   dict(splits={'train': ['q2', 'q1'], 'validation': ['q1'], 'test': []}),
                   dict(splits={'train': ['q2'], 'validation': [], 'test': []})]
        for case in invalid:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.audit(**case)


if __name__ == '__main__':
    unittest.main()
