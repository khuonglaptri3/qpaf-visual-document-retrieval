"""The A005 replay passes on committed evidence and fails when a cited fact is wrong."""
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scripts.verify_a005 as verify  # noqa: E402


def failed(results, prefix=''):
    return [r['check'] for r in results if r['status'] == 'FAIL' and r['check'].startswith(prefix)]


class A005ReplayTests(unittest.TestCase):
    def test_cited_facts_and_anchor_pass(self):
        # Identity rows are excluded: CI clones are shallow and later A005 code may change pinned files.
        results = verify.checks(verify.IDENTITY_COMMIT)
        self.assertEqual([c for c in failed(results) if not c.startswith('identity ')], [])

    def test_wrong_quoted_number_fails(self):
        wrong = tuple(row if row[0] != 'Validation static nDCG@10' else (*row[:3], 0.8715, 4) for row in verify.CITED)
        with mock.patch.object(verify, 'CITED', wrong):
            self.assertEqual(failed(verify.checks(None), 'cited: '), ['cited: Validation static nDCG@10'])

    def test_changed_amendment_bytes_fail(self):
        real = Path.read_bytes

        def tampered(path):
            data = real(path)
            return data + b'\n' if path.name == 'QPAF-M1.5-A005.md' else data
        with mock.patch.object(Path, 'read_bytes', tampered):
            self.assertIn('approved A005 bytes unchanged', failed(verify.checks(None)))


if __name__ == '__main__':
    unittest.main()
