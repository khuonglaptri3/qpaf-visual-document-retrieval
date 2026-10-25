"""M5.1 preregistration must preserve the G2A core and held-out boundary."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.preregister_m51 import (make_record, validate_freeze, validate_record,
                                     verify_signoff)


class M51PreregistrationTests(unittest.TestCase):
    def setUp(self):
        self.freeze = {
            'seed_plan': {'completed': [20260820], 'pending': [20260821, 20260822],
                          'rule': 'same resolved config and method sources; only training.seed changes'},
            'roster': [
                {'id': 'R1', 'tier': 'core', 'allowed_data': ['none']},
                {'id': 'R2', 'tier': 'core', 'allowed_data': ['no_labels']},
                {'id': 'R3', 'tier': 'core', 'allowed_data': ['train', 'validation']},
                {'id': 'R4', 'tier': 'core', 'allowed_data': ['train', 'validation']},
                {'id': 'R5', 'tier': 'optional', 'allowed_data': ['validation']},
                {'id': 'R6', 'tier': 'optional', 'allowed_data': ['validation']},
                {'id': 'R7', 'tier': 'core', 'allowed_data': ['test']},
                {'id': 'R8', 'tier': 'core', 'allowed_data': ['r7_outputs']},
                {'id': 'R9', 'tier': 'deferred', 'allowed_data': ['workbook']},
                {'id': 'R10', 'tier': 'deferred', 'allowed_data': ['none']},
            ],
            'held_out': {'dataset': 'Qiuchen-Wang/ViDoSeek', 'split': 'test',
                         'query_count': 172, 'labels_opened': False,
                         'ids_sha256': 'a' * 64, 'sealed_qrels_sha256': 'b' * 64},
            'main_method': {'name': 'QPAF-v1', 'loss': 'pairwise_logistic / query_mean (A001)'},
            'matched_comparator': {'name': 'QARF-v1'},
            'baselines': {'roster_size': 7, 'co_strongest': ['train_fitted_static']},
        }

    def test_rejects_changed_seed_or_core_tier(self):
        validate_freeze(self.freeze)
        altered = copy.deepcopy(self.freeze)
        altered['seed_plan']['pending'][1] = 20260823
        with self.assertRaisesRegex(ValueError, 'seed'):
            validate_freeze(altered)
        altered = copy.deepcopy(self.freeze)
        altered['roster'][6]['tier'] = 'optional'
        with self.assertRaisesRegex(ValueError, 'roster'):
            validate_freeze(altered)

    def test_matrix_pairs_all_three_seeds_and_test_stays_closed(self):
        record = make_record(self.freeze, {'g2a_freeze': 'a' * 64},
                             '2026-10-25T00:00:00Z')
        self.assertEqual([row['seed'] for row in record['seed_matrix']],
                         [20260820, 20260821, 20260822])
        self.assertTrue(all(row['methods'] == ['QARF', 'QPAF']
                            for row in record['seed_matrix']))
        self.assertEqual(record['test_plan']['query_count'], 172)
        self.assertFalse(record['test_plan']['labels_opened'])
        validate_record(record)

    def test_rejects_dropping_core_or_promoting_optional_result(self):
        record = make_record(self.freeze, {'g2a_freeze': 'a' * 64},
                             '2026-10-25T00:00:00Z')
        record['drop_first']['order'].append('R7')
        with self.assertRaisesRegex(ValueError, 'drop'):
            validate_record(record)
        record = make_record(self.freeze, {'g2a_freeze': 'a' * 64},
                             '2026-10-25T00:00:00Z')
        record['ablations'][0]['scope'] = 'test'
        with self.assertRaisesRegex(ValueError, 'ablation'):
            validate_record(record)

    def test_owner_signoff_binds_immutable_record(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            record = output / 'preregistration.json'
            record.write_text('{}\n', encoding='utf8')
            record_hash = hashlib.sha256(record.read_bytes()).hexdigest()
            confirmation = {'task_id': 'M5.1', 'owner': 'Thanh',
                            'decision': 'ACCEPTED',
                            'confirmation_text': 'Có, ghi Thanh chấp nhận M5.1',
                            'preregistration_sha256': record_hash,
                            'execution_authorized': False,
                            'test_labels_opened': False}
            signoff = output / 'owner_confirmation.json'
            signoff.write_text(json.dumps(confirmation), encoding='utf8')
            event = {'task_id': 'M5.1', 'event_type': 'ACCEPTANCE_RECORDED',
                     'registry_status': 'PASS', 'human_review': 'ACCEPTED_BY_THANH',
                     'preregistration_sha256': record_hash,
                     'confirmation_sha256': hashlib.sha256(signoff.read_bytes()).hexdigest(),
                     'execution_authorization': 'NOT_GRANTED_BY_THIS_EVENT',
                     'test_labels_opened': False}
            (output / 'governance_events.jsonl').write_text(json.dumps(event) + '\n',
                                                             encoding='utf8')
            verify_signoff(output)
            record.write_text('{"changed":true}\n', encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'confirmation'):
                verify_signoff(output)


if __name__ == '__main__':
    unittest.main()
