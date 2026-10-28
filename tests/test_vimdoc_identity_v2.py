"""ViMDoc v2 identity keeps both assets of a stem as separate pages of the same document."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.derive_vimdoc_identity_v2 import derive, page_row  # noqa: E402


def asset(path, sha='0' * 64):
    stem = path[len('pages/'):].rpartition('.')[0]
    doc, _, number = stem.rpartition('_')
    return {'asset_path': path, 'page_id': stem, 'document_id': doc, 'page_number': int(number),
            'asset_sha256': sha, 'asset_bytes': 1}


class IdentityV2Tests(unittest.TestCase):
    def test_both_extensions_become_sibling_pages_of_one_document(self):
        pages, counts = derive([asset('pages/doc_a_0.jpg', '1' * 64), asset('pages/doc_a_0.png', '2' * 64),
                                asset('pages/doc_a_1.png'), asset('pages/b_0.png')])
        self.assertEqual(counts, {'pages': 4, 'stems': 3, 'stems_with_two_assets': 1, 'documents': 2})
        jpg = next(p for p in pages if p['page_id'] == 'doc_a_0.jpg')
        self.assertEqual((jpg['document_id'], jpg['page_number'], jpg['stem_sibling_page_ids']),
                         ('doc_a', 0, ['doc_a_0.png']))
        self.assertEqual([p['page_id'] for p in pages], sorted(p['page_id'] for p in pages))

    def test_malformed_or_disagreeing_rows_refuse(self):
        for bad in ({**asset('pages/x_0.png'), 'asset_path': 'pages/sub/x_0.png'},
                    {**asset('pages/x_0.png'), 'asset_path': 'pages/x_0.gif'},
                    {**asset('pages/x_0.png'), 'asset_path': 'pages/x_a.png'},
                    {**asset('pages/x_0.png'), 'document_id': 'y'}):
            with self.assertRaises(ValueError):
                page_row(bad)

    def test_more_than_two_assets_per_stem_refuses(self):
        with self.assertRaises(ValueError):
            derive([asset('pages/x_0.png'), asset('pages/x_0.jpg'), asset('pages/x_0.jpeg')])


if __name__ == '__main__':
    unittest.main()
