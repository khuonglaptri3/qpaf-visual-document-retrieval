"""Real M4.2 boundaries: expanded shared pool, train-only fit, immutable evidence."""
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pyarrow as pa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m24.dataset import QueryRecord


def tables():
    rows = [dict(query_id='q', page_id=page, bm25_score=s[0], dense_score=s[1],
                 visual_score=s[2]) for page, s in
            [('a_0', (10., 0., 0.)), ('b_0', (0., 10., 10.)), ('c_0', (5., 5., 5.))]]
    normalized = copy.deepcopy(rows)
    for r in normalized:
        for c in ('bm25_score', 'dense_score', 'visual_score'):
            r[c] /= 10
    candidates = [{k:r[k] for k in ('query_id', 'page_id')} for r in rows]
    tops = [dict(query_id='q', page_id=p, channel=c, rank=1, raw_score=10.)
            for p,c in [('a_0','bm25'), ('b_0','dense'), ('b_0','visual')]]
    extra = [dict(query_id='q', page_id='c_0')]
    return [pa.Table.from_pylist(r) for r in (rows, normalized, candidates, tops, extra)]


class ActivePrimaryTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('qpaf.m42.active_primary')
        except ModuleNotFoundError:
            self.fail('Active-primary M4.2 execution is not implemented')

    def test_shared_pool_includes_the_approved_expansion_and_replays_normalization(self):
        result = self.api.audit_tables(*tables(), ['q'], top_k=1, cap=3)
        self.assertEqual(result['candidate_rows'], 3)
        self.assertEqual(result['query_count'], 1)
        self.assertEqual(result['normalization_max_abs_difference'], 0.)
        self.assertEqual(result['expanded_rows'], 1)

    def test_original_unexpanded_pool_cannot_replace_the_matched_m3_pool(self):
        data = tables()
        data[4] = data[4].slice(0,0)
        with self.assertRaisesRegex(ValueError, 'union'):
            self.api.audit_tables(*data, ['q'], top_k=1, cap=3)

    def test_wrong_candidate_order_or_normalized_values_are_rejected(self):
        data = tables()
        data[2] = data[2].take(pa.array([2,1,0]))
        with self.assertRaisesRegex(ValueError, 'order'):
            self.api.audit_tables(*data, ['q'], top_k=1, cap=3)
        data = tables()
        rows = data[1].to_pylist()
        rows[2]['visual_score'] = .7
        data[1] = pa.Table.from_pylist(rows)
        with self.assertRaisesRegex(ValueError, 'normalization'):
            self.api.audit_tables(*data, ['q'], top_k=1, cap=3)

    def test_label_columns_and_invalid_channel_scores_are_rejected(self):
        for bad in ['label', 'nan']:
            data = tables()
            rows = data[0].to_pylist()
            if bad == 'label':
                for r in rows: r['relevance'] = 1
            else:
                rows[0]['dense_score'] = float('nan')
            data[0] = pa.Table.from_pylist(rows)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.api.audit_tables(*data, ['q'], top_k=1, cap=3)

    def test_orphan_queries_duplicates_and_cap_violations_fail_closed(self):
        with self.assertRaises(ValueError):
            self.api.audit_tables(*tables(), ['different'], top_k=1, cap=3)
        with self.assertRaises(ValueError):
            self.api.audit_tables(*tables(), ['q'], top_k=1, cap=2)
        data = tables()
        data[0] = pa.concat_tables([data[0], data[0].slice(0,1)])
        with self.assertRaises(ValueError):
            self.api.audit_tables(*data, ['q'], top_k=1, cap=4)

    def test_top_list_rank_and_channel_contract_cannot_change(self):
        for key,value in [('rank',0), ('channel','dse')]:
            data = tables()
            rows = data[3].to_pylist()
            rows[0][key] = value
            data[3] = pa.Table.from_pylist(rows)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.api.audit_tables(*data, ['q'], top_k=1, cap=3)

    def test_top_list_raw_score_must_match_the_common_score_cache(self):
        data = tables()
        rows = data[3].to_pylist()
        rows[0]['raw_score'] = 50.
        data[3] = pa.Table.from_pylist(rows)
        with self.assertRaisesRegex(ValueError, 'raw score'):
            self.api.audit_tables(*data, ['q'], top_k=1, cap=3)

    def test_alternate_checkout_cannot_supply_a_different_executing_fitter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for call in [lambda:self.api.prepare_context(root),
                         lambda:self.api.verify(root, root/'output', 'untrusted-pin')]:
                try:
                    with self.assertRaisesRegex(ValueError, 'executing checkout'):
                        call()
                except OSError:
                    self.fail('Alternate checkout accessed files before authenticating executing dependencies')

    def test_near_zero_range_cannot_silently_change_frozen_m25_semantics(self):
        data = tables()
        rows = data[0].to_pylist()
        for r in rows: r['bm25_score'] *= 1e-17
        data[0] = pa.Table.from_pylist(rows)
        with self.assertRaisesRegex(ValueError, 'M2.5'):
            self.api.audit_tables(*data, ['q'], top_k=1, cap=3)

    def test_actual_fitter_is_the_frozen_66_grid_with_a_hand_derived_optimum(self):
        records = [QueryRecord('train','question',('a','b'),
                               ((10.,0.,0.),(0.,10.,10.)),(0,1),1)]
        result = self.api.fit_train_records(records, ['train'])
        self.assertEqual(result['weights'], (0.,0.,1.))
        self.assertEqual(result['train_ndcg_at_10'], 1.)
        self.assertEqual(result['candidates'], 66)

    def test_validation_records_or_duplicate_train_ids_cannot_reach_fitting(self):
        record = QueryRecord('validation','question',('a','b'),
                             ((10.,0.,0.),(0.,10.,10.)),(0,1),1)
        for ids in [['train'], ['validation','validation'], 'validation']:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.api.fit_train_records([record], ids)

    def test_all_seven_baselines_bind_the_same_shared_bundle(self):
        contracts = self.api.baseline_contracts('shared', (.2,.3,.5), 'checkpoint')
        self.assertEqual(set(contracts), {'bm25','bge_m3','colqwen25','uniform_combsum',
                                         'rrf_k60','train_fitted_static','learned_qarf'})
        self.assertTrue(all(c['shared_inputs_sha256']=='shared' for c in contracts.values()))
        self.assertEqual(contracts['rrf_k60']['rank_constant'],60)
        self.assertEqual(contracts['train_fitted_static']['weights'],[.2,.3,.5])
        self.assertEqual(contracts['learned_qarf']['checkpoint_sha256'],'checkpoint')
        self.assertEqual(contracts['learned_qarf']['seed'],20260820)

    def test_existing_attempt_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'attempt'
            self.api.reserve_attempt(output, {'invocations':1})
            before = (output/'_ATTEMPTED.json').read_bytes()
            with self.assertRaises(ValueError):
                self.api.reserve_attempt(output, {'invocations':2})
            self.assertEqual((output/'_ATTEMPTED.json').read_bytes(),before)

    def test_manifest_pin_hash_tampering_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'input.txt').write_bytes(b'input')
            manifest = {'files':[{'path':'input.txt','sha256':self.api.sha(root/'input.txt')}]}
            self.api.write_json(root/'manifest.json',manifest)
            pin = self.api.sha(root/'manifest.json')
            self.api.verify_files(root,pin)
            (root/'input.txt').write_bytes(b'tampered')
            with self.assertRaises(ValueError): self.api.verify_files(root,pin)
            with self.assertRaises(ValueError): self.api.verify_files(root,'wrong-pin')
            (root/'manifest.json').unlink()
            self.api.write_json(root/'manifest.json', {'files':[{'path':'../escape','sha256':'x'}]})
            with self.assertRaises(ValueError): self.api.verify_files(root,self.api.sha(root/'manifest.json'))


if __name__ == '__main__':
    unittest.main()
