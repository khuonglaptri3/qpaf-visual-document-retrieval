"""R7 / TEST-172: label-free records, seal-before-open order, approval rules. Never reads test labels."""
import hashlib
import inspect
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT))
from qpaf.m24.dataset import build_records  # noqa: E402
from qpaf.r7 import sealed  # noqa: E402

BUNDLE = ROOT/'results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01'
RESTORED = (BUNDLE/'inputs/raw_scores.parquet').is_file()
SPLITS = {'train': ['a'], 'validation': ['b'], 'test': ['c', 'd']}
QUERIES = {'a': 'qa', 'b': 'qb', 'c': 'qc', 'd': 'qd'}
ROWS = [{'query_id': q, 'page_id': p, 'bm25_score': s, 'dense_score': s/2, 'visual_score': 1-s}
        for q, p, s in [('a', 'p1', .1), ('b', 'p2', .2), ('c', 'z9', .3), ('c', 'a1', .4), ('d', 'm5', .5)]]
RUN_ID = 'RUN-QPAF-R7-TEST-001-20261101T000000Z-A01'


def approved(**changes):
    auth = {'status': 'APPROVED', 'task_id': 'TEST-172', 'roster_id': 'R7', 'run_id': RUN_ID,
            'scope': list(sealed.SCOPE), 'permissions': dict(sealed.PERMISSIONS), 'limits': dict(sealed.LIMITS),
            'approval': {'approver': 'Tấn Phát', 'approval_text': 'duyệt', 'approved_utc': '2026-11-01T00:00:00Z'},
            'source_commit': 'a'*40, 'source_files_sha256': {'x': '1'}, 'runtime': {'python': '3.13.7'}}
    auth.update(changes)
    return auth


def check(auth, **changes):
    arguments = {'run_id': RUN_ID, 'clean': True, 'source_hashes': {'x': '1'}, 'runtime': {'python': '3.13.7'},
                 'output_exists': False, **changes}
    sealed.check_approval(auth, **arguments)


class LabelFreeRecordTests(unittest.TestCase):
    def test_matches_build_records_without_labels(self):
        free = sealed.label_free_records(ROWS, QUERIES, SPLITS)
        qrels = {'c': {'a1': 1}, 'd': {'m5': 1}}
        labeled = build_records(ROWS, QUERIES, qrels, SPLITS, ('test',))['test']
        sealed.same_candidates(free, labeled)
        self.assertEqual([r.page_ids for r in free], [('a1', 'z9'), ('m5',)])
        self.assertTrue(all(not any(r.labels) and r.relevant_total == 0 for r in free))

    def test_refuses_unknown_nonfinite_or_missing_rows(self):
        with self.assertRaisesRegex(sealed.SealedError, 'not in any split'):
            sealed.label_free_records([*ROWS, {**ROWS[0], 'query_id': 'x'}], QUERIES, SPLITS)
        with self.assertRaisesRegex(sealed.SealedError, 'finite'):
            sealed.label_free_records([*ROWS[:4], {**ROWS[4], 'bm25_score': float('nan')}], QUERIES, SPLITS)
        with self.assertRaisesRegex(sealed.SealedError, 'no candidate rows'):
            sealed.label_free_records(ROWS[:4], QUERIES, SPLITS)

    def test_changed_candidates_are_refused(self):
        free = sealed.label_free_records(ROWS, QUERIES, SPLITS)
        other = sealed.label_free_records([*ROWS[:4], {**ROWS[4], 'bm25_score': .6}], QUERIES, SPLITS)
        with self.assertRaisesRegex(sealed.SealedError, 'differ'):
            sealed.same_candidates(free, other)


class SealTests(unittest.TestCase):
    def test_seal_detects_changed_predictions(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(sealed.SealedError, 'not sealed'):
                sealed.check_seal(folder)
            (Path(folder)/'p.csv.gz').write_bytes(b'scores')
            seal = sealed.write_seal(folder, 'p.csv.gz')
            self.assertEqual(sealed.check_seal(folder)['sha256'], seal['sha256'])
            (Path(folder)/'p.csv.gz').write_bytes(b'edited')
            with self.assertRaisesRegex(sealed.SealedError, 'changed'):
                sealed.check_seal(folder)

    def test_execute_seals_before_it_opens_and_preflight_never_opens(self):
        from qpaf.r7 import runner
        body = inspect.getsource(runner.execute)
        self.assertLess(body.index('write_seal('), body.index('check_seal('))
        self.assertLess(body.index('check_seal('), body.index('open_sealed_qrels('))
        for function in (runner.preflight, runner.test_predictions, runner.check_bindings):
            self.assertNotIn('open_sealed_qrels', inspect.getsource(function))


class SealedQrelsTests(unittest.TestCase):
    def test_pinned_bytes_and_exact_ids(self):
        ids = [f'q{i}' for i in range(172)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'qrels.json'
            data = json.dumps({q: {'p': 1} for q in ids}).encode()
            path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(len(sealed.open_sealed_qrels(path, digest, ids)), 172)
            with self.assertRaisesRegex(sealed.SealedError, 'hash'):
                sealed.open_sealed_qrels(path, '0'*64, ids)
            with self.assertRaisesRegex(sealed.SealedError, '172'):
                sealed.open_sealed_qrels(path, digest, ids[:-1])


class ContrastTests(unittest.TestCase):
    def test_two_contrasts_per_seed_with_qpaf_first(self):
        row = lambda q, v: {'query_id': q, 'ndcg_at_10': v, 'recall_at_1': v, 'recall_at_3': v, 'mrr_at_10': v}
        per_query = {'train_fitted_static': [row('c', .5)]}
        for seed in sealed.SEEDS:
            per_query[f'qpaf_{seed}'], per_query[f'qarf_{seed}'] = [row('c', .9)], [row('c', .6)]
        result = sealed.contrasts(per_query)
        self.assertEqual(len(result), 6)
        self.assertAlmostEqual(result['qpaf_20260821-qarf_20260821'][0]['delta_ndcg_at_10'], .3)
        self.assertAlmostEqual(result['qpaf_20260822-train_fitted_static'][0]['delta_ndcg_at_10'], .4)


class ApprovalTests(unittest.TestCase):
    def test_approved_record_passes(self):
        check(approved())

    def test_refusals(self):
        cases = [(approved(status='DRAFT_SOURCE_PENDING'), {}, 'APPROVED'),
                 (approved(approval={'approver': 'PENDING', 'approval_text': 'x', 'approved_utc': 'x'}), {},
                  'approval'),
                 (approved(run_id='RUN-QPAF-R7-TEST-001-x'), {}, 'run ID'),
                 (approved(), {'run_id': RUN_ID.replace('A01', 'A02')}, 'run ID'),
                 (approved(limits={**sealed.LIMITS, 'automatic_retries': 1}), {}, 'invocation'),
                 (approved(), {'clean': False}, 'clean'),
                 (approved(), {'source_hashes': {'x': '2'}}, 'source'),
                 (approved(), {'runtime': {'python': '3.12'}}, 'runtime'),
                 (approved(), {'output_exists': True}, 'amendment')]
        for auth, changes, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(sealed.SealedError, message):
                check(auth, **changes)


@unittest.skipUnless(RESTORED, 'M4.2 payload not restored')
class PreflightTests(unittest.TestCase):
    def test_preflight_scores_test_without_reading_labels(self):
        from qpaf.r7 import runner
        auth = json.loads((ROOT/runner.AUTHORIZATION_PATH).read_text(encoding='utf8'))
        sealed_path = (ROOT/auth['held_out']['sealed_qrels']).resolve()
        def guard(original):
            def guarded(path, *args, **kwargs):
                if Path(path).resolve() == sealed_path:
                    raise AssertionError('sealed qrels were read')
                return original(path, *args, **kwargs)
            return guarded
        with mock.patch.object(Path, 'read_text', guard(Path.read_text)), \
                mock.patch.object(Path, 'read_bytes', guard(Path.read_bytes)):
            state = runner.preflight(ROOT, auth)
            predictions = runner.test_predictions(state, ROOT)
        self.assertEqual(state['report']['test_queries'], 172)
        self.assertEqual(state['report']['baseline_reference_max_abs_difference'], 0.0)
        self.assertEqual(set(predictions), set(sealed.COLUMNS))
        self.assertTrue(all(p['score_max_abs_difference'] == 0.0 for p in state['report']['learned_parity'].values()))


if __name__ == '__main__':
    unittest.main()
