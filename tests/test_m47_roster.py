"""M4.7 roster: ten entries, protected core, test data only in R7."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m47.roster import ROSTER, RULES, RosterError, validate_roster  # noqa: E402


def edited(entry_id, **changes):
    roster = copy.deepcopy(list(ROSTER))
    for entry in roster:
        if entry['id'] == entry_id:
            entry.update(changes)
    return roster


class RosterTests(unittest.TestCase):
    def test_roster_matches_the_spec(self):
        self.assertEqual([r['id'] for r in ROSTER], [f'R{i}' for i in range(1, 11)])
        tiers = {t: {r['id'] for r in ROSTER if r['tier'] == t} for t in ('core', 'optional', 'deferred')}
        self.assertEqual(tiers, {'core': {'R1', 'R2', 'R3', 'R4', 'R7', 'R8'},
                                 'optional': {'R5', 'R6'}, 'deferred': {'R9', 'R10'}})
        self.assertEqual(len(RULES), 4)
        validate_roster(ROSTER)

    def test_only_r7_may_read_test(self):
        with self.assertRaisesRegex(RosterError, 'R5'):
            validate_roster(edited('R5', allowed_data=('validation', 'test')))
        with self.assertRaisesRegex(RosterError, 'R7'):
            validate_roster(edited('R7', allowed_data=('validation',)))

    def test_test_spelling_variants_refuse(self):
        for value in (('validation', 'Test'), ('test_172',)):
            with self.subTest(value), self.assertRaisesRegex(RosterError, 'R6'):
                validate_roster(edited('R6', allowed_data=value))

    def test_core_items_cannot_be_optional_or_missing(self):
        with self.assertRaises(RosterError):
            validate_roster(edited('R3', tier='optional'))
        with self.assertRaises(RosterError):
            validate_roster([r for r in ROSTER if r['id'] != 'R8'])

    def test_r7_waits_for_seed_reviews(self):
        with self.assertRaisesRegex(RosterError, 'R7'):
            validate_roster(edited('R7', depends_on=('R3',)))

    def test_r5_r6_use_validation_only(self):
        with self.assertRaisesRegex(RosterError, 'R5'):
            validate_roster(edited('R5', allowed_data=('train', 'validation')))


if __name__ == '__main__':
    unittest.main()
