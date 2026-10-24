"""Independent M4.5 audit boundaries on hand-checkable data."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from scripts.audit_m45_baselines import (fit_static_grid, paired_summary,
                                         query_metrics, select_co_strongest,
                                         verify_manifest, verify_owner_acceptance)


class M45AuditTests(unittest.TestCase):
    def test_page_tie_uses_ascending_id_and_all_qrels_for_idcg(self):
        values = query_metrics(['b', 'c', 'a'], [1.0, 0.0, 1.0], {'a', 'c'})
        expected = (1 + 1 / math.log2(4)) / (1 + 1 / math.log2(3))
        self.assertAlmostEqual(values['ndcg_at_10'], expected)
        self.assertEqual(values['recall_at_1'], 0.5)
        self.assertEqual(values['recall_at_3'], 1.0)
        self.assertEqual(values['mrr_at_10'], 1.0)

    def test_static_fit_uses_only_named_train_query(self):
        grouped = {
            'train': {'a': (1.0, 0.0, 0.0), 'b': (0.0, 0.0, 1.0)},
            'validation': {'a': (0.0, 0.0, 1.0), 'b': (1.0, 0.0, 0.0)},
        }
        qrels = {'train': {'b': 1}, 'validation': {'b': 1}}
        result = fit_static_grid(grouped, qrels, ['train'])
        self.assertEqual(result['weights'], [0.0, 0.0, 1.0])
        self.assertEqual(result['train_queries'], 1)
        self.assertEqual(result['train_ndcg_at_10'], 1.0)
        self.assertEqual(len(result['grid_ndcg']), 66)

    def test_co_strongest_keeps_near_tie_and_excludes_proposed(self):
        roster = ['a', 'b', 'c']
        metrics = {'a': 0.8, 'b': 0.8 - 5e-13, 'c': 0.7, 'qpaf': 0.9}
        self.assertEqual(select_co_strongest(metrics, roster, 1e-12), ['a', 'b'])

    def test_bootstrap_keeps_query_pairing_and_zero_ties(self):
        result = paired_summary([0.2, 0.0, -0.1], seed=20260820, resamples=10000)
        self.assertAlmostEqual(result['mean_delta'], 1 / 30)
        self.assertEqual(result['wtl'], {'wins': 1, 'ties': 1, 'losses': 1})
        self.assertEqual(result['top_5pct_positive_gain_share'], 1.0)
        self.assertLessEqual(result['ci95'][0], 0.0)
        self.assertGreaterEqual(result['ci95'][1], 0.0)
        zero = paired_summary([0.0, 0.0], seed=20260820, resamples=100)
        self.assertEqual(zero['wtl'], {'wins': 0, 'ties': 2, 'losses': 0})
        self.assertEqual(zero['ci95'], [0.0, 0.0])

    def test_manifest_rejects_tampered_result_file(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            artifact = run / 'selection.json'
            artifact.write_text('{}\n', encoding='utf8')
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = {'files': [{'path': artifact.name, 'sha256': digest,
                                   'size_bytes': artifact.stat().st_size}]}
            (run / 'manifest.json').write_text(json.dumps(manifest), encoding='utf8')
            pin = hashlib.sha256((run / 'manifest.json').read_bytes()).hexdigest()
            (run / '_ATTEMPTED.json').write_text('{}', encoding='utf8')
            (run / '_SUCCESS.json').write_text(json.dumps({'manifest_sha256': pin}), encoding='utf8')
            verify_manifest(run, pin)
            artifact.write_text('{"changed": true}\n', encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'hash|size'):
                verify_manifest(run, pin)

    def test_owner_acceptance_binds_report_and_event(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            report = output / 'verification.json'
            deltas = output / 'per_query_deltas.csv'
            report.write_text('{}\n', encoding='utf8')
            deltas.write_text('delta\n', encoding='utf8')
            confirmation = {
                'task_id': 'M4.5', 'reviewer': 'Thanh', 'decision': 'ACCEPTED',
                'confirmation_text': 'Có, ghi Thanh chấp nhận M4.5',
                'technical_report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
                'per_query_sha256': hashlib.sha256(deltas.read_bytes()).hexdigest(),
                'm46_direction_decided': False,
                'qpaf_superiority_claimed': False,
            }
            signoff = output / 'owner_confirmation.json'
            signoff.write_text(json.dumps(confirmation), encoding='utf8')
            event = {
                'task_id': 'M4.5', 'event_type': 'ACCEPTANCE_RECORDED',
                'registry_status': 'PASS', 'human_review': 'ACCEPTED_BY_THANH',
                'verification_sha256': confirmation['technical_report_sha256'],
                'per_query_sha256': confirmation['per_query_sha256'],
                'review_signoff_sha256': hashlib.sha256(signoff.read_bytes()).hexdigest(),
                'm46_direction_decided': False,
                'qpaf_superiority_claimed': False,
            }
            (output / 'governance_events.jsonl').write_text(json.dumps(event) + '\n',
                                                             encoding='utf8')
            verify_owner_acceptance(output)
            confirmation['technical_report_sha256'] = '0' * 64
            signoff.write_text(json.dumps(confirmation), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'owner confirmation'):
                verify_owner_acceptance(output)


if __name__ == '__main__':
    unittest.main()
