"""M4.4 validation evaluation: inputs, authorization, table, selection, oracle context."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m44 import common  # noqa: E402

BUNDLE = ROOT/'results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01'
RESTORED = (BUNDLE/'inputs/raw_scores.parquet').is_file()

APPROVED = {'status': 'APPROVED', 'source_commit': 'abc', 'config': {'path': 'c.json', 'sha256': None},
            'experiments': {'QPAF-M4_4-MTH-001': {'run_id': 'RUN-QPAF-M4_4-MTH-001-20261024T000000Z-A01'}},
            'approval': {'approver': 'Tấn Phát (Research Lead)', 'approval_text': 'I approve',
                         'approved_utc': '2026-10-24T00:00:00Z'}}


class QrelsTests(unittest.TestCase):
    def test_validation_qrels_refuses_test_ids(self):
        splits = {'train': ['a'], 'validation': ['b'], 'test': ['c']}
        self.assertEqual(common.validation_qrels({'a': {'p': 1}, 'b': {'q': 1}}, splits), {'b': {'q': 1}})
        with self.assertRaisesRegex(common.EvaluationError, 'test'):
            common.validation_qrels({'b': {'q': 1}, 'c': {'r': 1}}, splits)
        with self.assertRaisesRegex(common.EvaluationError, 'validation'):
            common.validation_qrels({'a': {'p': 1}}, splits)


class RestoreTests(unittest.TestCase):
    def test_restore_refuses_wrong_bytes_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'source.bin').write_bytes(b'payload')
            good = hashlib.sha256(b'payload').hexdigest()
            files = [{'path': 'inputs/x.bin', 'sha256': good}]
            restored = common.restore_files(root/'bundle', files, {'inputs/x.bin': root/'source.bin'})
            self.assertEqual(restored, ['inputs/x.bin'])
            self.assertEqual((root/'bundle/inputs/x.bin').read_bytes(), b'payload')
            self.assertEqual(common.restore_files(root/'bundle', files, {'inputs/x.bin': root/'source.bin'}), [])
            (root/'bundle/inputs/x.bin').write_bytes(b'changed')
            with self.assertRaisesRegex(common.EvaluationError, 'differs'):
                common.restore_files(root/'bundle', files, {'inputs/x.bin': root/'source.bin'})
            self.assertEqual((root/'bundle/inputs/x.bin').read_bytes(), b'changed')
            wrong = [{'path': 'inputs/y.bin', 'sha256': '0'*64}]
            with self.assertRaisesRegex(common.EvaluationError, 'source'):
                common.restore_files(root/'bundle', wrong, {'inputs/y.bin': root/'source.bin'})
            self.assertFalse((root/'bundle/inputs/y.bin').exists())


class CsvTests(unittest.TestCase):
    def test_csv_gz_is_deterministic_and_lossless(self):
        rows = [['q1', 'p_1', 0.1+0.2, 1/3], ['q1', 'p_2', 5e-324, -0.0]]
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder)/'a.csv.gz', Path(folder)/'b.csv.gz'
            common.write_csv_gz(first, ['query_id', 'page_id', 'x', 'y'], rows)
            common.write_csv_gz(second, ['query_id', 'page_id', 'x', 'y'], rows)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            back = common.read_csv_gz(first)
            self.assertEqual([[r['query_id'], r['page_id'], float(r['x']), float(r['y'])] for r in back], rows)
            with self.assertRaises(FileExistsError):
                common.write_csv_gz(first, ['query_id'], [])


class AuthorizationTests(unittest.TestCase):
    def check(self, auth, **overrides):
        args = dict(experiment_id='QPAF-M4_4-MTH-001', run_id='RUN-QPAF-M4_4-MTH-001-20261024T000000Z-A01',
                    head='abc', clean=True, config_sha256=None, output_exists=False)
        args.update(overrides)
        return common.check_approval(auth, **args)

    def test_authorization_refusals(self):
        self.assertEqual(self.check(APPROVED)['run_id'], 'RUN-QPAF-M4_4-MTH-001-20261024T000000Z-A01')
        cases = {
            'empty approval': dict(auth=dict(APPROVED, approval=dict(APPROVED['approval'], approval_text=' '))),
            'pending approval': dict(auth=dict(APPROVED, approval=dict(APPROVED['approval'], approver='PENDING'))),
            'draft status': dict(auth=dict(APPROVED, status='DRAFT')),
            'commit': dict(auth=APPROVED, head='def'),
            'dirty tree': dict(auth=APPROVED, clean=False),
            'run id': dict(auth=APPROVED, run_id='RUN-other'),
            'experiment': dict(auth=APPROVED, experiment_id='QPAF-M4_4-ORC-001'),
            'config': dict(auth=APPROVED, config_sha256='f'*64),
            'output': dict(auth=APPROVED, output_exists=True)}
        for name, case in cases.items():
            auth = case.pop('auth')
            with self.subTest(name), self.assertRaises(common.EvaluationError):
                self.check(auth, **case)

    def test_wrong_authorization_pin_refuses(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'authorization.json'
            path.write_text('{}', encoding='utf8')
            with self.assertRaisesRegex(common.EvaluationError, 'pin'):
                common.check_authorization(ROOT, path, '0'*64, 'QPAF-M4_4-MTH-001', 'RUN-x')


ROSTER = ('bm25', 'bge_m3', 'colqwen25', 'uniform_combsum', 'rrf_k60', 'train_fitted_static', 'learned_qarf')


def metrics_for(values):
    return {method: {'query_count': 2, 'ndcg_at_10': value, 'recall_at_1': value, 'recall_at_3': value,
                     'mrr_at_10': value} for method, value in values.items()}


class SelectionTests(unittest.TestCase):
    def setUp(self):
        from qpaf.m44 import evaluation
        self.evaluation = evaluation
        self.contracts = {method: {'method': method} for method in ROSTER}

    def test_co_strongest_ties_and_qpaf_excluded(self):
        values = dict(zip(ROSTER, (.5, .6, .8, .7, .7, .8+5e-13, .75)), qpaf=.95)
        chosen = self.evaluation.selection(metrics_for(values), self.contracts, tolerance=1e-12)
        self.assertEqual(chosen['co_strongest'], ['colqwen25', 'train_fitted_static'])
        self.assertEqual(chosen['candidates'], list(ROSTER))
        self.assertNotIn('qpaf', chosen['validation_ndcg_at_10'])
        self.assertFalse(chosen['proposed_method_eligible'] or chosen['oracle_rows_eligible'])
        self.assertEqual(set(chosen['contract_sha256']), set(ROSTER))
        missing = metrics_for({m: v for m, v in values.items() if m != 'rrf_k60'})
        with self.assertRaises(ValueError):
            self.evaluation.selection(missing, self.contracts, tolerance=1e-12)

    def test_table_blocks(self):
        values = dict(zip(ROSTER, (.5, .6, .8, .7, .7, .79, .75)), qpaf=.9)
        metrics = metrics_for(values)
        chosen = self.evaluation.selection(metrics, self.contracts, tolerance=1e-12)
        table = self.evaluation.build_table(metrics, chosen, checkpoint_sha256='e4b0')
        self.assertEqual([row['method'] for row in table['deployable']], list(ROSTER))
        self.assertEqual([row['rank'] for row in table['deployable']], [7, 6, 1, 4, 4, 2, 3])
        self.assertTrue(table['deployable'][2]['co_strongest'])
        self.assertEqual(table['proposed_method']['method'], 'qpaf')
        self.assertTrue(table['proposed_method']['optimistic_same_split_selection'])
        self.assertTrue(table['deployable'][6]['optimistic_same_split_selection'])
        self.assertFalse(table['deployable'][0]['optimistic_same_split_selection'])
        self.assertIn('| colqwen25 |', self.evaluation.table_markdown(table))

    def test_paired_sign(self):
        per_query = {method: [{'query_id': q, 'ndcg_at_10': .5, 'recall_at_1': .5, 'recall_at_3': .5,
                               'mrr_at_10': .5} for q in ('a', 'b')] for method in ROSTER}
        per_query['qpaf'] = [{'query_id': q, 'ndcg_at_10': .75, 'recall_at_1': .5, 'recall_at_3': .5,
                              'mrr_at_10': .5} for q in ('a', 'b')]
        result = self.evaluation.paired(per_query, resamples=50, seed=20260820)
        self.assertEqual(set(result), set(ROSTER))
        self.assertAlmostEqual(result['bm25']['ndcg_at_10']['mean_delta'], .25)
        self.assertEqual(result['bm25']['ndcg_at_10']['wtl'], {'wins': 2, 'ties': 0, 'losses': 0})

    def test_learned_parity_failure(self):
        saved = [{'query_id': 'q', 'page_ids': ['a', 'b'], 'scores': [.2, .1],
                  'weights': [[1., 0., 0.], [0., 1., 0.]]}]
        fresh = [dict(saved[0], scores=[.2+2e-7, .1])]
        with self.assertRaises(ValueError):
            self.evaluation.check_parity(saved, fresh, tolerance=1e-7)
        self.assertEqual(self.evaluation.check_parity(saved, saved, tolerance=1e-7)['score_max_abs_difference'], 0.)


def oracle_fixture():
    import numpy as np
    from qpaf.m24.dataset import QueryRecord
    rng = np.random.default_rng(7)
    records = []
    for index, size in enumerate((12, 9, 15)):
        pages = tuple(sorted(f'd{index}_{page}' for page in range(size)))
        labels = tuple(int(page in (2, 5)) for page in range(size))
        scores = tuple(tuple(float(x) for x in row) for row in rng.random((size, 3)))
        records.append(QueryRecord(f'q{index}', 'query', pages, scores, labels, sum(labels)))
    return records


class OracleTests(unittest.TestCase):
    def setUp(self):
        from qpaf.m44 import oracle
        self.oracle = oracle

    def test_oracle_order_and_m24_metric(self):
        from qpaf.m24.evaluator import evaluate
        records = oracle_fixture()
        for grid in ('w7', 'w66'):
            rows, details = self.oracle.oracle_scores(records, grid)
            self.assertEqual(set(rows), {f'oracle_{kind}_{grid}' for kind in ('global', 'qarf', 'qpaf')})
            per = {name: evaluate(value, records)[1] for name, value in rows.items()}
            for g, q, p in zip(per[f'oracle_global_{grid}'], per[f'oracle_qarf_{grid}'], per[f'oracle_qpaf_{grid}']):
                self.assertGreaterEqual(q['ndcg_at_10'], g['ndcg_at_10']-1e-12)
                self.assertGreaterEqual(p['ndcg_at_10'], q['ndcg_at_10']-1e-12)
            self.assertEqual(len(details['per_query']), 3)
            self.assertEqual(len(details['global_profile']), 3)

    def test_oracle_rows_never_selectable(self):
        from qpaf.m44 import evaluation
        values = dict(zip(ROSTER, (.5, .6, .8, .7, .7, .79, .75)), qpaf=.9, oracle_qpaf_w66=.99)
        chosen = evaluation.selection(metrics_for(values), {m: {} for m in ROSTER}, tolerance=1e-12)
        self.assertEqual(chosen['co_strongest'], ['colqwen25'])
        self.assertNotIn('oracle_qpaf_w66', chosen['validation_ndcg_at_10'])

    def test_oracle_deadline_stops_the_run(self):
        calls = []
        def deadline():
            calls.append(1)
            if len(calls) > 1:
                raise common.EvaluationError('exceeded')
        with self.assertRaisesRegex(common.EvaluationError, 'exceeded'):
            self.oracle.oracle_scores(oracle_fixture(), 'w7', deadline=deadline)


class AttemptTests(unittest.TestCase):
    CONTEXT = {'access': {'test_labels_deserialized': False}, 'coverage': {}, 'records': [],
               'config': {'bundle': {'manifest_sha256': 'b'}, 'freeze': {'sha256': 'f'}}}
    EXPERIMENT = {'run_id': 'RUN-x', 'wall_time_seconds': 60, 'experiment_class': 'learned_evaluation',
                  'evidence_class': 'engineering_evidence'}

    def attempt(self, folder, produce):
        with mock.patch.object(common, 'check_authorization', return_value=({}, self.EXPERIMENT)), \
                mock.patch.object(common, 'load_context', return_value=self.CONTEXT):
            return common.execute_attempt(ROOT, 'auth.json', 'a'*64, 'QPAF-M4_4-MTH-001', 'RUN-x', produce,
                                          results_root=Path(folder))

    def test_success_and_failure_markers(self):
        def produce(context, output, deadline):
            common.write_json(output/'result.json', {'value': 1})
            return {'value': 1}
        with tempfile.TemporaryDirectory() as folder:
            manifest = self.attempt(folder, produce)
            run = Path(folder)/'RUN-x'
            self.assertEqual(sorted(p.name for p in run.iterdir()),
                             ['_ATTEMPTED.json', '_SUCCESS.json', 'access.json', 'manifest.json', 'result.json'])
            self.assertEqual([f['path'] for f in manifest['files']], ['access.json', 'result.json'])
            self.assertEqual(common.verify_run(run, common.sha(run/'manifest.json'))['summary'], {'value': 1})
            with self.assertRaisesRegex(common.EvaluationError, 'differ'):
                (run/'result.json').write_text('{}', encoding='utf8')
                common.verify_run(run, common.sha(run/'manifest.json'))
        def failing(context, output, deadline):
            raise common.EvaluationError('boom')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(common.EvaluationError, 'boom'):
                self.attempt(folder, failing)
            run = Path(folder)/'RUN-x'
            self.assertEqual(sorted(p.name for p in run.iterdir()), ['_ATTEMPTED.json', '_FAILED.json'])
            with self.assertRaises(FileExistsError):
                self.attempt(folder, produce)


@unittest.skipUnless(RESTORED, 'M4.2 bundle payload is not restored')
class RealContextTests(unittest.TestCase):
    def test_real_context(self):
        context = common.load_context(ROOT)
        self.assertEqual(len(context['records']), 171)
        self.assertEqual(context['coverage'], {'query_count': 171, 'macro_relevant_page_recall': 1.0,
                                               'uncovered_queries': 0})
        self.assertEqual(context['freeze']['frozen_method']['checkpoint']['sha256'],
                         'e4b00ab49e186fffe8b369e26491873304b61177c11fd2ce0f455158e30e5c8e')
        self.assertEqual(context['static_weights'], [0.0, 0.1, 0.9])
        self.assertFalse(context['access']['test_labels_deserialized'])


if __name__ == '__main__':
    unittest.main()
