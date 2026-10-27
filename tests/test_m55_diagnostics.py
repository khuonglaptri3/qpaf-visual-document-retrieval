"""M5.5 fixed validation diagnostics; no service, retriever or GPU execution."""
from dataclasses import replace
import copy
import hashlib
import json
import math
from pathlib import Path
import socket
import sys
import tempfile
import subprocess
import unittest
from unittest import mock
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m24.dataset import QueryRecord
from qpaf.m55 import diagnostics as api
from qpaf.m55 import runner as runner


def record():
    return QueryRecord('q1', 'fixture query', ('a', 'b', 'c'),
                       ((0., 10., 0.), (5., 5., 10.), (10., 0., 5.)),
                       (0, 1, 0), 2)


def saved(rec):
    return {rec.query_id: {'page_ids': list(rec.page_ids),
                          'scores': [[0., 1., 0.], [.5, .5, 1.], [1., 0., .5]]}}


class NormalizationTests(unittest.TestCase):
    def test_minmax_is_per_channel_and_preserves_candidate_order(self):
        self.assertEqual(api.normalize_scores(record().raw_scores, 'minmax'),
                         ((0., 1., 0.), (.5, .5, 1.), (1., 0., .5)))

    def test_zscore_uses_population_std_and_keeps_negative_scores(self):
        result = api.normalize_scores(((0., 3., 2.), (1., 3., 4.), (2., 3., 6.)), 'zscore')
        edge = math.sqrt(1.5)
        for row, expected in zip(result, ((-edge, 0., -edge), (0., 0., 0.), (edge, 0., edge))):
            for actual, target in zip(row, expected):
                self.assertAlmostEqual(actual, target, places=14)
        self.assertLess(result[0][0], 0.)

    def test_constant_and_one_candidate_channels_are_zero(self):
        for kind in ('minmax', 'zscore'):
            self.assertEqual(api.normalize_scores(((7., -2., 0.),), kind), ((0., 0., 0.),))

    def test_bad_shapes_boolean_and_nonfinite_inputs_are_rejected(self):
        for raw in ((), ((1., 2.),), ((True, 2., 3.),), ((1., math.nan, 3.),),
                    ((1., 2., math.inf),), ((1., 2., '3'),)):
            with self.subTest(raw=raw), self.assertRaises(api.DiagnosticError):
                api.normalize_scores(raw, 'zscore')
        with self.assertRaises(api.DiagnosticError):
            api.normalize_scores(record().raw_scores, 'unregistered')


class FixedScoringTests(unittest.TestCase):
    def test_all_eight_rows_and_fixed_order_are_preserved(self):
        self.assertEqual(api.METHODS, ('bm25', 'bge_m3', 'colqwen25', 'uniform_combsum',
                                     'without_bm25', 'without_bge_m3', 'without_colqwen25',
                                     'uniform_zscore'))

    def test_each_drop_has_only_the_two_remaining_half_weights(self):
        rec = record()
        expected = {'without_bm25': [.5, .75, .25],
                    'without_bge_m3': [0., .75, .75],
                    'without_colqwen25': [.5, .5, .5]}
        for method, scores in expected.items():
            with self.subTest(method=method):
                self.assertEqual(api.score_record(rec, method), scores)

    def test_labels_do_not_affect_scores_and_dropped_pages_are_retained(self):
        rec = record()
        changed = replace(rec, labels=(1, 0, 1), relevant_total=3)
        for method in api.METHODS:
            with self.subTest(method=method):
                self.assertEqual(api.score_record(rec, method), api.score_record(changed, method))
                self.assertEqual(len(api.score_record(rec, method)), len(rec.page_ids))

    def test_a_duplicate_or_misaligned_candidate_is_refused(self):
        for rec in (replace(record(), page_ids=('a', 'a', 'c')),
                    replace(record(), page_ids=('a', 'b'))):
            with self.assertRaises(api.DiagnosticError):
                api.score_record(rec, 'uniform_combsum')

    def test_uniform_reference_uses_the_frozen_arithmetic(self):
        self.assertEqual(api.score_record(record(), 'uniform_combsum'), [1/3, 2/3, .5])


class DiagnosticEvaluationTests(unittest.TestCase):
    def test_metrics_keep_all_qrels_positives_and_deterministic_ties(self):
        result = api.compute_diagnostics([record()], saved(record()))
        by_method = {row['method']: row for row in result['metrics']}
        # Removing visual yields tied scores: a,b,c; the relevant b is rank 2.
        row = by_method['without_colqwen25']
        self.assertAlmostEqual(row['ndcg_at_10'], (1/math.log2(3))/(1+1/math.log2(3)))
        self.assertEqual((row['recall_at_1'], row['recall_at_3'], row['mrr_at_10']), (0., .5, .5))
        self.assertEqual(result['query_count'], 1)
        self.assertEqual(result['candidate_count'], 3)
        tied = [row for row in result['top10'] if row['method'] == 'without_colqwen25']
        self.assertEqual([row['page_id'] for row in tied], ['a', 'b', 'c'])
        self.assertEqual(result['normalization_audit']['max_abs_difference'], 0.)

    def test_saved_keys_order_values_and_finiteness_are_checked(self):
        rec = record()
        cases = [({}, 'missing'),
                 ({'q1': {'page_ids': ['b', 'a', 'c'], 'scores': saved(rec)['q1']['scores']}}, 'order'),
                 ({'q1': {'page_ids': ['a', 'b', 'c'], 'scores': [[0., 1., 0.]]}}, 'count'),
                 ({'q1': {'page_ids': ['a', 'b', 'c'], 'scores': [[.1, 1., 0.], [.5, .5, 1.], [1., 0., .5]]}}, 'drift'),
                 ({'q1': {'page_ids': ['a', 'b', 'c'], 'scores': [[math.nan, 1., 0.], [.5, .5, 1.], [1., 0., .5]]}}, 'nan')]
        for cache, name in cases:
            with self.subTest(name=name), self.assertRaises(api.DiagnosticError):
                api.compute_diagnostics([rec], cache)

    def test_empty_duplicate_queries_and_invalid_labels_fail(self):
        for records in ([], [record(), record()], [replace(record(), labels=(0, 2, 0))],
                        [replace(record(), labels=(1,))], [replace(record(), relevant_total=0)]):
            with self.subTest(records=records), self.assertRaises(api.DiagnosticError):
                api.compute_diagnostics(records, saved(record()))

    def test_paired_deltas_are_descriptive_and_query_aligned(self):
        result = api.compute_diagnostics([record()], saved(record()))
        contrasts = {row['method']: row for row in result['contrasts']}
        same = contrasts['uniform_combsum']
        self.assertEqual((same['mean_ndcg_delta'], same['wins'], same['ties'], same['losses']), (0., 0, 1, 0))
        self.assertEqual(same['reference'], 'uniform_combsum')
        self.assertFalse(result['confirmatory_claim'])


class AuthorizationAndReferenceTests(unittest.TestCase):
    def authorization(self):
        return {'status': 'APPROVED', 'task_id': 'M5.5',
                'run_id': 'RUN-QPAF-M5_5-ABL-001-20261027T040000Z-A01',
                'scope': ['R5-01', 'R5-02', 'R5-03'], 'permissions': dict(runner.PERMISSIONS),
                'approval': {'approver': 'Khương', 'approval_text': 'Run the CPU diagnostics; defer GPU.',
                             'approved_utc': '2026-10-27T04:00:00Z'},
                'source_commit': '1'*40, 'source_files_sha256': {'fixture.py': 'a'*64},
                'authority_pins': {'fixture.json': 'b'*64}, 'runtime': {'python': 'fixture'},
                'limits': {'wall_time_seconds': 1800, 'invocations': 1, 'automatic_retries': 0}}

    def check(self, auth):
        return runner.check_approval(auth, run_id=self.authorization()['run_id'], clean=True,
                                     source_hashes={'fixture.py': 'a'*64}, authority_pins={'fixture.json': 'b'*64},
                                     runtime={'python': 'fixture'})

    def test_explicit_cpu_authorization_is_accepted_without_inventing_a_research_lead(self):
        self.check(self.authorization())

    def test_gpu_scope_runtime_source_and_approval_drift_are_refused(self):
        cases = {'gpu': lambda a: a['permissions'].update(gpu=True),
                 'modal': lambda a: a['permissions'].update(modal=True),
                 'labels': lambda a: a['permissions'].update(test_labels=True),
                 'scope': lambda a: a['scope'].append('R5-04'),
                 'source': lambda a: a['source_files_sha256'].update({'fixture.py': 'c'*64}),
                 'authority': lambda a: a['authority_pins'].update({'fixture.json': 'd'*64}),
                 'runtime': lambda a: a['runtime'].update(python='other'),
                 'approval': lambda a: a['approval'].update(approval_text='PENDING'),
                 'retry': lambda a: a['limits'].update(invocations=2),
                 'run_id': lambda a: a.update(run_id='elsewhere')}
        for name, mutate in cases.items():
            with self.subTest(name=name):
                auth = self.authorization()
                mutate(auth)
                with self.assertRaises(api.DiagnosticError):
                    self.check(auth)
        with self.assertRaises(api.DiagnosticError):
            runner.check_approval(self.authorization(), run_id=self.authorization()['run_id'], clean=False,
                                  source_hashes={'fixture.py': 'a'*64}, authority_pins={'fixture.json': 'b'*64},
                                  runtime={'python': 'fixture'})

    def test_reference_comparison_rejects_metric_drift_and_missing_queries(self):
        names = api.METHODS[:4]
        rows = [{'method': name, 'query_count': 1, **{k: .5 for k in api.METRICS}} for name in names]
        per_query = [{'method': name, 'query_id': 'q', **{k: .5 for k in api.METRICS}} for name in names]
        result = {'metrics': rows, 'per_query': per_query}
        self.assertEqual(runner.reference_parity(result, {'deployable': rows}, per_query)['status'], 'PASS')
        changed = copy.deepcopy(rows)
        changed[0]['ndcg_at_10'] = .6
        with self.assertRaises(api.DiagnosticError):
            runner.reference_parity(result, {'deployable': changed}, per_query)
        with self.assertRaises(api.DiagnosticError):
            runner.reference_parity(result, {'deployable': rows}, per_query[:-1])


class RunAndReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.auth_path = self.root/'authorization.json'
        self.auth = AuthorizationAndReferenceTests().authorization()
        self.auth['runtime'] = runner.runtime_versions()
        self.auth_path.write_text(json.dumps(self.auth), encoding='utf-8')
        self.pin = hashlib.sha256(self.auth_path.read_bytes()).hexdigest()
        self.context = {'records': [record()], 'bundle': self.root/'bundle',
                        'access': {'test_labels_deserialized': False, 'train_qrels_used': False},
                        'coverage': {'query_count': 1, 'macro_relevant_page_recall': .5}}
        self.context['bundle'].mkdir()
        (self.context['bundle']/'manifest.json').write_text('{}')
        for name, value in (('check_authorization', (self.auth, '2'*40)),
                            ('load_inputs', (self.context, saved(record()))),
                            ('load_reference', ({}, [])),
                            ('reference_parity', {'status': 'PASS', 'max_abs_difference': 0.})):
            patcher = mock.patch.object(runner, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(runner, 'validate_bindings')
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_fixture(self):
        return runner.execute(self.root, self.auth_path, self.pin, self.auth['run_id'])

    def test_run_and_replay_are_offline_create_once_and_preserve_all_run_bytes(self):
        with mock.patch.object(socket, 'socket', side_effect=AssertionError('network is forbidden')):
            summary = self.run_fixture()
            output = self.root/'results/m5.5'/self.auth['run_id']
            self.assertEqual(summary['cpu_status'], 'TECHNICAL_PASS')
            self.assertEqual(summary['resource_status'], 'NOT_RUN_DEFERRED_MODAL_NETWORK_BLOCKED')
            self.assertFalse(summary['m55_complete'])
            manifest_hash = hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest()
            before = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
            verified = runner.verify(self.root, output, manifest_hash)
            self.assertEqual(verified['status'], 'PASS')
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()})
            with self.assertRaises(api.DiagnosticError):
                self.run_fixture()
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()})

    def test_tampered_result_and_wrong_external_manifest_pin_are_refused(self):
        self.run_fixture()
        output = self.root/'results/m5.5'/self.auth['run_id']
        manifest_hash = hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest()
        with self.assertRaises(api.DiagnosticError):
            runner.verify(self.root, output, '0'*64)
        (output/'diagnostics.json').write_text('{}')
        with self.assertRaises(api.DiagnosticError):
            runner.verify(self.root, output, manifest_hash)

    def test_success_cannot_claim_full_completion_and_attempt_head_is_bound(self):
        self.run_fixture()
        output = self.root/'results/m5.5'/self.auth['run_id']
        manifest_hash = hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest()
        marker = output/'_SUCCESS.json'
        original = marker.read_bytes()
        value = json.loads(original)
        value['m55_complete'] = True
        marker.write_text(json.dumps(value))
        with self.assertRaises(api.DiagnosticError):
            runner.verify(self.root, output, manifest_hash)
        marker.write_bytes(original)
        attempt = output/'_ATTEMPTED.json'
        value = json.loads(attempt.read_bytes())
        value['git_head'] = 'f'*40
        attempt.write_text(json.dumps(value))
        with self.assertRaises(api.DiagnosticError):
            runner.verify(self.root, output, manifest_hash)


class CommittedAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        freeze_path = 'evidence/revisions/m4.3-001/method_freeze.json'
        freeze = json.loads((ROOT/freeze_path).read_text(encoding='utf-8'))
        paths = (set(runner.SOURCE_FILES) | set(runner.AUTHORITY_PINS) | set(freeze['source_sha256'])
                 | {freeze_path, 'configs/m4.4/evaluation.json'})
        for name in paths:
            target = self.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        self.git('init', '-q')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'implementation')
        self.auth = AuthorizationAndReferenceTests().authorization()
        self.auth.update(source_commit=self.git('rev-parse', 'HEAD'),
                         source_files_sha256=runner.source_hashes(self.root),
                         authority_pins=dict(runner.AUTHORITY_PINS), runtime=runner.runtime_versions())
        self.path = self.root/runner.AUTHORIZATION_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.auth, ensure_ascii=False), encoding='utf-8')
        self.pin = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.git('add', runner.AUTHORIZATION_PATH)
        self.git('commit', '-q', '-m', 'CPU authorization')

    def git(self, *args):
        return subprocess.check_output(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.test',
                                        '-c', 'commit.gpgsign=false', *args], cwd=self.root, text=True).strip()

    def test_committed_cpu_authorization_passes_and_bad_pin_or_dirty_source_fails(self):
        auth, head = runner.check_authorization(self.root, self.path, self.pin, self.auth['run_id'])
        self.assertEqual(head, self.git('rev-parse', 'HEAD'))
        self.assertEqual(auth['source_commit'], self.auth['source_commit'])
        with self.assertRaises(api.DiagnosticError):
            runner.check_authorization(self.root, self.path, '0'*64, self.auth['run_id'])
        (self.root/runner.SOURCE_FILES[0]).write_text('changed')
        with self.assertRaises(api.DiagnosticError):
            runner.check_authorization(self.root, self.path, self.pin, self.auth['run_id'])

    def test_unrelated_committed_change_after_source_is_not_authorized(self):
        (self.root/'unrelated.py').write_text('pass\n')
        self.git('add', 'unrelated.py')
        self.git('commit', '-q', '-m', 'not authorized')
        with self.assertRaises(api.DiagnosticError):
            runner.check_authorization(self.root, self.path, self.pin, self.auth['run_id'])

    def test_committed_vietnamese_authorization_does_not_depend_on_terminal_encoding(self):
        with mock.patch('subprocess._text_encoding', return_value='ascii'):
            auth, _ = runner.check_authorization(self.root, self.path, self.pin, self.auth['run_id'])
        self.assertEqual(auth['approval']['approver'], 'Khương')

    def test_config_drift_fails_binding_and_replay_before_any_input_loading(self):
        bundle = self.root/'bundle'
        bundle.mkdir()
        (bundle/'manifest.json').write_text('{}')
        context = {'records': [record()], 'bundle': bundle, 'access': {'test_labels_deserialized': False}}
        with mock.patch.object(runner, 'load_inputs', return_value=(context, saved(record()))), \
                mock.patch.object(runner, 'load_reference', return_value=({}, [])), \
                mock.patch.object(runner, 'reference_parity', return_value={'status': 'PASS'}):
            summary = runner.execute(self.root, self.path, self.pin, self.auth['run_id'])
        output = Path(summary['output'])
        config = self.root/'configs/m4.4/evaluation.json'
        value = json.loads(config.read_text(encoding='utf-8'))
        value['unused_modified_field'] = True
        config.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaises(api.DiagnosticError):
            runner.validate_bindings(self.root, self.auth)
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        with mock.patch.object(runner, 'load_inputs', side_effect=AssertionError('data must stay unopened')):
            with self.assertRaises(api.DiagnosticError):
                runner.verify(self.root, output, summary['manifest_sha256'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})


class RestorationTests(unittest.TestCase):
    def test_archive_pin_and_existing_bytes_are_checked_before_any_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root/'payload.zip'
            prefix = runner.BUNDLE_NAME+'/'
            with ZipFile(archive, 'w') as z:
                z.writestr(prefix+'inputs/raw_scores.parquet', b'fixture')
                z.writestr(prefix+'manifest.json', b'{}')
            with self.assertRaises(api.DiagnosticError):
                runner.restore_inputs(root, archive)
            pin = hashlib.sha256(archive.read_bytes()).hexdigest()
            target = root/'results/m4.2'/runner.BUNDLE_NAME/'manifest.json'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'other')
            with mock.patch.object(runner, 'ARCHIVE_SHA256', pin), self.assertRaises(api.DiagnosticError):
                runner.restore_inputs(root, archive)
            self.assertFalse((target.parent/'inputs/raw_scores.parquet').exists())
            self.assertEqual(target.read_bytes(), b'other')

    def test_archive_path_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root/'payload.zip'
            with ZipFile(archive, 'w') as z:
                z.writestr('../escape', b'bad')
            pin = hashlib.sha256(archive.read_bytes()).hexdigest()
            with mock.patch.object(runner, 'ARCHIVE_SHA256', pin), self.assertRaises(api.DiagnosticError):
                runner.restore_inputs(root, archive)
            self.assertFalse((root.parent/'escape').exists())


if __name__ == '__main__':
    unittest.main()
