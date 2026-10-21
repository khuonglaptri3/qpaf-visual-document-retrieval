"""M2.10 replay on the A003 revision must reach PASS only from real per-query evidence."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))

from scripts.audit_m210_a003_readiness import (audit_a003_lineage, check_label_order,
                                               replay_coverage)
from qpaf.m25.leakage import verify_frozen_splits

M28 = ROOT/'evidence/revisions/m2.8-002'


def load(name):
    return json.loads((M28/name).read_text(encoding='utf-8'))


class A003AuditTests(unittest.TestCase):
    def setUp(self):
        freeze = json.loads((ROOT/'configs/m2.5/freeze.json').read_text(encoding='utf-8'))
        self.splits = verify_frozen_splits(ROOT, freeze)['roles']

    def test_expanded_coverage_replays_to_pass_and_rejects_tampering(self):
        replay = replay_coverage(load('coverage_report.json'), self.splits)
        self.assertEqual(replay['overall']['status'], 'PASS')
        self.assertEqual(replay['overall']['uncovered_query_ids'], [])
        self.assertEqual({r: v['status'] for r, v in replay['by_split'].items()},
                         {'train': 'PASS', 'validation': 'PASS', 'test': 'PASS'})
        tampered = copy.deepcopy(load('coverage_report.json'))
        tampered['per_query'][0]['captured_relevant'] = 0
        tampered['per_query'][0]['recall'] = 0.0
        with self.assertRaises(ValueError):
            replay_coverage(tampered, self.splits)

    def test_label_access_order_is_enforced(self):
        freeze, development, handover = (load('candidate_freeze.json'), load('development_report.json'),
                                         load('handover.json'))
        self.assertEqual(check_label_order(freeze, development, handover)['status'], 'PASS')
        opened = dict(development, test_qrels_opened=True)
        with self.assertRaisesRegex(ValueError, 'test'):
            check_label_order(freeze, opened, handover)
        early = dict(development, created_utc='2026-01-01T00:00:00+00:00')
        with self.assertRaisesRegex(ValueError, 'before'):
            check_label_order(freeze, early, handover)
        labelled = copy.deepcopy(freeze)
        labelled['provenance']['uses_qrels'] = True
        with self.assertRaisesRegex(ValueError, 'label'):
            check_label_order(labelled, development, handover)

    def test_lineage_binds_amendment_baseline_and_binding(self):
        result = audit_a003_lineage(ROOT)
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(all(result['baseline_replay_checks'].values()))
        self.assertEqual(result['previously_uncovered']['04450a0f59f81025574451222aa26322ae7ede42_2'],
                         'COVERED')


if __name__ == '__main__':
    unittest.main()
