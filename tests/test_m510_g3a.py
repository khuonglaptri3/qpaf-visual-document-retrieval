"""G3A must remain NOT RUN unless the pinned external record changes."""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.decide_g3a import REQUIRED, decide, g3a_outcome, read, sha  # noqa: E402

EVIDENCE = ROOT / 'evidence/revisions/m5.10-001'


class G3ATests(unittest.TestCase):
    def setUp(self):
        self.inputs = read(EVIDENCE / 'inputs.json')
        self.records = {key: read(ROOT / path) for key, path in REQUIRED.items()}

    def outcome(self, **changes):
        records = {**self.records, **changes}
        return g3a_outcome(records['g3_decision'], records['g3_confirmation'],
                           records['external_disposition'], records['g2a_freeze'], records['r8_summary'],
                           g3_sha=self.inputs['files'][REQUIRED['g3_decision']],
                           freeze_sha=self.inputs['files'][REQUIRED['g2a_freeze']],
                           r8_sha=self.inputs['files'][REQUIRED['r8_summary']])

    def test_pinned_decision_replays(self):
        result = decide(ROOT, self.inputs)
        result['inputs_sha256'] = sha(EVIDENCE / 'inputs.json')
        self.assertEqual(result, read(EVIDENCE / 'decision.json'))
        self.assertEqual(result['decision'], 'NOT_RUN')
        self.assertFalse(result['external_generalization_claimed'])

    def test_inconsistent_external_or_g3_record_refused(self):
        external = {**self.records['external_disposition'], 'status': 'PASS'}
        with self.assertRaisesRegex(ValueError, 'M5.8'):
            self.outcome(external_disposition=external)
        confirmation = {**self.records['g3_confirmation'], 'decision': 'PENDING'}
        with self.assertRaisesRegex(ValueError, 'Research Lead'):
            self.outcome(g3_confirmation=confirmation)

    def test_pin_drift_refused(self):
        bad = {**self.inputs, 'files': {**self.inputs['files'],
               REQUIRED['g3_decision']: '0' * 64}}
        with self.assertRaisesRegex(ValueError, 'pin drift'):
            decide(ROOT, bad)


if __name__ == '__main__':
    unittest.main()
