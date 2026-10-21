"""QPAF-M1.5-A003: label-free top-document expansion of the frozen M2.8 union."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pyarrow.parquet as pq


PIDS = ['docA_page_0001', 'docA_page_0002', 'docA_page_0003',
        'docB_page_0001', 'docB_page_0002']
# Hand-ranked fixture, top_k=1 so the per-query cap is 3.
# q0: C0 = {A1 (bm25, dense), B1 (visual)}; doc A wins on max RRF; one slot
#     is left, so only A2 (RRF 2/63+1/62) is added before A3 (1/64+1/62+1/63).
# q1: C0 = {A1}; two slots; A3 (2/62+1/63) is added before A2 (2/63+1/62).
SCORES = {
    'bm25': np.array([[5, 3, 1, 4, 0], [9, 1, 2, 0, 0]], dtype=np.float64),
    'dense': np.array([[5, 1, 3, 0, 0], [9, 1, 2, 0, 0]], dtype=np.float64),
    'visual': np.array([[0, 2, 1, 9, 0], [9, 2, 1, 0, 0]], dtype=np.float64),
}


class ExpansionConstructionTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('qpaf.m28.expansion')
        except ModuleNotFoundError:
            self.fail('A003 candidate expansion is not implemented')
        self.base = importlib.import_module('qpaf.m28.bundle')

    def build(self, scores=SCORES, qids=('q0', 'q1'), pids=PIDS, top_k=1):
        return self.api.build_expanded_candidates(scores, list(qids), list(pids), top_k=top_k)

    def pages(self, bundle, query_id):
        return [row['page_id'] for row in bundle['candidates'] if row['query_id'] == query_id]

    def test_policy_constants_match_the_amendment(self):
        self.assertEqual(self.api.POLICY_ID, 'qpaf_m28_top_document_expansion_v1')
        self.assertEqual(self.api.RRF_K, 60)
        self.assertEqual(self.api.BASE_TOP_K, 200)
        self.assertEqual(self.api.EXPANSION_DOCUMENTS, 1)

    def test_baseline_union_is_kept_and_spare_capacity_is_filled_by_rrf_priority(self):
        bundle = self.build()
        self.assertEqual(self.pages(bundle, 'q0'),
                         ['docA_page_0001', 'docA_page_0002', 'docB_page_0001'])
        self.assertEqual(self.pages(bundle, 'q1'),
                         ['docA_page_0001', 'docA_page_0002', 'docA_page_0003'])
        log = [(r['query_id'], r['page_id'], r['document_id'], r['priority'], r['reason'])
               for r in bundle['expansion_log']]
        self.assertEqual(log, [
            ('q0', 'docA_page_0002', 'docA', 1, 'top_document_expansion'),
            ('q1', 'docA_page_0003', 'docA', 1, 'top_document_expansion'),
            ('q1', 'docA_page_0002', 'docA', 2, 'top_document_expansion'),
        ])
        q0_a2 = bundle['expansion_log'][0]['rrf_score']
        self.assertEqual(q0_a2, (1/63+1/63)+1/62)

    def test_top_lists_and_c0_are_identical_to_the_frozen_baseline(self):
        bundle = self.build()
        baseline = self.base.build_candidates(SCORES, ['q0', 'q1'], PIDS, top_k=1)
        self.assertEqual(bundle['top_lists'], baseline['top_lists'])
        base_keys = {(r['query_id'], r['page_id']) for r in baseline['candidates']}
        keys = {(r['query_id'], r['page_id']) for r in bundle['candidates']}
        self.assertTrue(base_keys <= keys)
        self.assertEqual(keys-base_keys, {(r['query_id'], r['page_id'])
                                          for r in bundle['expansion_log']})

    def test_raw_scores_come_from_full_arrays_and_normalization_uses_new_union(self):
        bundle = self.build()
        q0 = [r for r in bundle['raw_rows'] if r['query_id'] == 'q0']
        self.assertEqual([(r['bm25_score'], r['dense_score'], r['visual_score']) for r in q0],
                         [(5.0, 5.0, 0.0), (3.0, 1.0, 2.0), (4.0, 0.0, 9.0)])
        normalized = [r for r in bundle['normalized_rows'] if r['query_id'] == 'q0']
        self.assertEqual([(r['bm25_score'], r['dense_score'], r['visual_score']) for r in normalized],
                         [(1.0, 1.0, 0.0), (0.0, 0.2, 2/9), (0.5, 0.0, 1.0)])

    def test_query_summaries_record_selection_for_every_query(self):
        bundle = self.build()
        self.assertEqual([(r['query_id'], r['selected_document_id'], r['base_count'],
                           r['added_count'], r['final_count']) for r in bundle['query_summaries']],
                         [('q0', 'docA', 2, 1, 3), ('q1', 'docA', 1, 2, 3)])
        counts = bundle['counts']
        self.assertEqual((counts['base_candidate_count'], counts['added_page_count'],
                          counts['candidate_count'], counts['queries_with_additions'],
                          counts['max_candidates_per_query']), (3, 3, 6, 2, 3))

    def test_full_baseline_union_receives_no_pages(self):
        scores = {c: np.array([[5, 4, 3, 2, 1]], dtype=np.float64) for c in SCORES}
        scores['dense'] = np.array([[1, 5, 4, 3, 2]], dtype=np.float64)
        scores['visual'] = np.array([[1, 2, 5, 4, 3]], dtype=np.float64)
        bundle = self.build(scores=scores, qids=['q'])
        self.assertEqual(len(self.pages(bundle, 'q')), 3)
        self.assertEqual(bundle['expansion_log'], [])

    def test_selected_document_already_inside_union_adds_nothing_and_no_second_document(self):
        pids = ['docA_page_0001', 'docB_page_0001', 'docB_page_0002']
        scores = {c: np.array([[9, 1, 0]], dtype=np.float64) for c in SCORES}
        bundle = self.build(scores=scores, qids=['q'], pids=pids)
        self.assertEqual(self.pages(bundle, 'q'), ['docA_page_0001'])
        self.assertEqual(bundle['query_summaries'][0]['selected_document_id'], 'docA')
        self.assertEqual(bundle['expansion_log'], [])

    def test_document_ties_break_by_ascending_document_id(self):
        page_rrf = np.array([0.5, 0.25, 0.5])
        documents = ['docB', 'docB', 'docA']
        self.assertEqual(self.api.select_document(page_rrf, documents), 'docA')

    def test_query_id_content_is_never_read(self):
        renamed = self.build(qids=('docB_0', 'docB_1'))
        original = self.build()
        for index, query_id in enumerate(('docB_0', 'docB_1')):
            self.assertEqual(self.pages(renamed, query_id), self.pages(original, f'q{index}'))

    def test_builder_accepts_no_label_input(self):
        import inspect
        parameters = set(inspect.signature(self.api.build_expanded_candidates).parameters)
        self.assertEqual(parameters, {'scores', 'query_ids', 'page_ids', 'top_k'})

    def test_noncanonical_page_ids_fail_closed(self):
        with self.assertRaises(ValueError):
            self.build(pids=PIDS[:-1]+['docB-page-2'])

    def test_rebuild_is_deterministic(self):
        self.assertEqual(self.build(), self.build())


class ExpansionPublicationTests(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module('qpaf.m28.expansion')
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)/'bundle'
        self.bundle = self.api.build_expanded_candidates(SCORES, ['q0', 'q1'], PIDS, top_k=1)

    def tearDown(self):
        self.temp.cleanup()

    def test_freeze_writes_six_artifacts_and_a_v2_manifest(self):
        manifest = self.api.freeze_expanded_candidates(self.output, self.bundle, {'uses_qrels': False})
        self.assertEqual(manifest['schema_version'], 'qpaf_m28_candidate_freeze_v2')
        self.assertEqual(manifest['policy']['policy_id'], 'qpaf_m28_top_document_expansion_v1')
        self.assertEqual(set(manifest['artifacts']), {
            'raw_scores.parquet', 'normalized_scores.parquet', 'channel_top_lists.parquet',
            'candidate_set.parquet', 'candidate_expansion_log.parquet',
            'candidate_expansion_queries.parquet'})
        raw = pq.read_table(self.output/'raw_scores.parquet')
        self.assertEqual(raw.column_names,
                         ['query_id', 'page_id', 'bm25_score', 'dense_score', 'visual_score'])
        self.assertEqual(json.loads((self.output/'candidate_freeze.json').read_text('utf-8')),
                         manifest)

    def test_freeze_rejects_an_unlogged_injected_candidate(self):
        injected = {key: (list(value) if isinstance(value, list) else value)
                    for key, value in self.bundle.items()}
        extra = {'query_id': 'q0', 'page_id': 'docB_page_0002'}
        injected['candidates'] = sorted(injected['candidates']+[extra],
                                        key=lambda r: (r['query_id'] != 'q0', r['page_id']))
        with self.assertRaises(ValueError):
            self.api.freeze_expanded_candidates(self.output, injected, {'uses_qrels': False})
        self.assertFalse(self.output.exists())

    def test_freeze_is_create_once(self):
        self.api.freeze_expanded_candidates(self.output, self.bundle, {'uses_qrels': False})
        with self.assertRaises(FileExistsError):
            self.api.freeze_expanded_candidates(self.output, self.bundle, {'uses_qrels': False})

    def test_verify_replays_every_artifact_from_full_arrays(self):
        self.api.freeze_expanded_candidates(self.output, self.bundle, {'uses_qrels': False})
        result = self.api.verify_expanded_candidates(self.output, SCORES, ['q0', 'q1'], PIDS, top_k=1)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['counts']['candidate_count'], 6)

    def test_verify_rejects_changed_scores_and_tampered_artifacts(self):
        self.api.freeze_expanded_candidates(self.output, self.bundle, {'uses_qrels': False})
        changed = {c: v.copy() for c, v in SCORES.items()}
        changed['visual'][0, 4] = 100.0
        with self.assertRaises(ValueError):
            self.api.verify_expanded_candidates(self.output, changed, ['q0', 'q1'], PIDS, top_k=1)
        path = self.output/'candidate_expansion_log.parquet'
        path.write_bytes(path.read_bytes()+b'\0')
        with self.assertRaises(ValueError):
            self.api.verify_expanded_candidates(self.output, SCORES, ['q0', 'q1'], PIDS, top_k=1)

    def test_expanded_candidates_feed_the_existing_coverage_audit(self):
        base = importlib.import_module('qpaf.m28.bundle')
        qrels = {'q0': {'docA_page_0002': 1}, 'q1': {'docA_page_0003': 1}}
        splits = {'train': ['q0'], 'validation': ['q1'], 'test': []}
        coverage = base.audit_coverage(self.bundle['candidates'], qrels, ['q0', 'q1'], splits)
        self.assertEqual(coverage['status'], 'PASS')
        self.assertEqual(coverage['uncovered_query_ids'], [])


if __name__ == '__main__':
    unittest.main()
