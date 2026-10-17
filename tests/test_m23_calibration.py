import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m11.artifacts import digest, file_manifest, write_json
from qpaf.m23.config import load_config, validate
from qpaf.m23.review import distance, metrics, normalize, review_data, summarize, validate_reviews
from qpaf.m23.sample import choose_pages, projected_pixels, select_documents, text_signals
from qpaf.m23.worker import parse_tsv, run_ocr


def config():
    return load_config(ROOT / 'configs/m2.3/ocr_calibration.toml')


def dynamic_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        row = [i]
        for j, right in enumerate(b, 1):
            row.append(min(row[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = row
    return previous[-1]


class CalibrationTests(unittest.TestCase):
    def test_cpu_and_caps_fail_closed(self):
        base = config()
        for change in ('gpu', 'pages', 'hash'):
            modified = copy.deepcopy(base)
            if change == 'gpu':
                modified['modal']['gpu'] = 'A10G'
            elif change == 'pages':
                modified['caps']['max_pages'] = 200
            else:
                modified['text']['traineddata_sha256'] = 'main'
            with self.assertRaises(ValueError):
                validate(modified)

    def test_document_selection_is_deterministic_and_disjoint(self):
        rows = [{'document_id': f'{group}-{index}'} for group, count in [('short', 8), ('medium', 15), ('long', 22)]
                for index in range(18) for _ in range(count)]
        picked = select_documents(rows, config())
        random.Random(1).shuffle(rows)
        self.assertEqual(picked, select_documents(rows, config()))
        self.assertEqual(len(picked), 30)
        self.assertEqual(sum(p['calibration_split'] == 'holdout' for p in picked), 10)
        development = {p['document_id'] for p in picked if p['calibration_split'] == 'development'}
        holdout = {p['document_id'] for p in picked if p['calibration_split'] == 'holdout'}
        self.assertFalse(development & holdout)

    def test_page_selection_includes_sparse_rich_and_boundaries(self):
        pages = [{'page_id': f'doc_page_{i:04d}', 'page_number': i,
                  'native_signals': {'nonspace_chars': length}} for i, length in enumerate([80, 0, 200, 60, 90], 1)]
        self.assertEqual([p['page_number'] for p in choose_pages(pages, 4, 2026)], [1, 2, 3, 5])

    def test_signals_do_not_treat_newlines_as_corrupt_content(self):
        result = text_signals('A\nB\nC')
        self.assertEqual(result['meaningful_printable_ratio'], 1.)
        self.assertLess(result['printable_ratio'], 1.)
        self.assertEqual(text_signals('')['text_stratum'], 'empty')

    def test_render_projection_handles_large_square_pages(self):
        page = {'pdf_width_points': 1440., 'pdf_height_points': 1440.}
        self.assertEqual(projected_pixels(page, 300), 36000000)
        self.assertEqual(projected_pixels(page, 150), 9000000)
        self.assertLess(projected_pixels(page, 300), config()['caps']['max_pixels'])

    def test_bit_distance_matches_independent_dynamic_programming(self):
        rng = random.Random(2026)
        for _ in range(300):
            a = ''.join(rng.choice('abé🙂 ') for _ in range(rng.randrange(25)))
            b = ''.join(rng.choice('abé🙂 ') for _ in range(rng.randrange(25)))
            self.assertEqual(distance(a, b), dynamic_distance(a, b))

    def test_metrics_unicode_empty_reference_and_insertions(self):
        self.assertEqual(metrics('e\u0301', 'é')['cer'], 0.)
        self.assertEqual(metrics('ABC', '')['false_positive_chars'], 3)
        self.assertIsNone(metrics('ABC', '')['cer'])
        self.assertGreater(metrics('abc abc abc', 'a')['cer'], 1.)
        self.assertEqual(metrics('100', '180')['char_edits'], 1)
        self.assertEqual(normalize('\ufeffA\u00a0B\n'), 'A B')
        self.assertEqual(normalize('A\u0085B'), 'A\u0085B')

    def test_tsv_confidence_excludes_layout_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'words.tsv'
            path.write_text('level\tconf\ttext\n1\t-1\t\n5\t90\tab\n5\t30\tc\n5\tNaN\tx\n', encoding='utf-8')
            result = parse_tsv(path)
            self.assertEqual(result['word_count'], 3)
            self.assertEqual(result['mean_word_confidence'], 60.)
            self.assertEqual(result['character_weighted_confidence'], 70.)

    def test_timeout_kills_real_child_and_records_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = subprocess.Popen
            def slow_process(command, **kwargs):
                return original([sys.executable, '-c', 'import time;time.sleep(3)'], **kwargs)
            with patch('qpaf.m23.worker.subprocess.Popen', side_effect=slow_process):
                result = run_ocr(Path(tmp) / 'in.png', Path(tmp) / 'out', 150, config(), .1)
            self.assertEqual(result['status'], 'TIMEOUT')
            self.assertIsNone(result['text'])
            self.assertLess(result['seconds'], 2.)
            self.assertTrue((Path(tmp) / 'out.stderr.txt').exists())


class ReviewTests(unittest.TestCase):
    def make_run(self, root):
        (root / 'inputs').mkdir()
        (root / 'remote/images300').mkdir(parents=True)
        image = root / 'remote/images300/page.png'
        image.write_bytes(b'Image bytes for namespace/hash tests; not a renderer fixture')
        write_json(root / 'inputs/sample_manifest.json', {'fixture': True})
        page = {'page_id': 'doc_page_0001', 'document_id': 'doc', 'page_number': 1, 'native_text': '100',
                'native_text_sha256': 'fixture', 'pdf_sha256': 'fixture', 'image300': 'images300/page.png',
                'image300_sha256': digest(image), 'image300_size': [100, 100], 'reference_required': True,
                'calibration_split': 'development', 'length_stratum': 'short',
                'ocr': {'150': {'text': '180', 'status': 'OK'}, '300': {'text': '100', 'status': 'OK'}}}
        write_json(root / 'remote/pages.json', [page])
        write_json(root / 'remote/hashes.json', file_manifest(root / 'remote'))
        data = review_data(root, root / 'review')
        pending = {'status': 'PENDING', 'issues': [], 'note': '', 'image_checked': False, 'reviewer': '', 'reviewed_at': None}
        draft = {'status': 'DRAFT', 'text': '', 'scope': 'full_page', 'region': '', 'no_text': False, 'reviewer': '', 'reviewed_at': None}
        payload = {'schema_version': 1, 'artifact_type': 'm23_human_review', 'demo': False,
                   'dataset_sha256': data['dataset_sha256'], 'dataset_id': data['dataset_id'], 'source_run': data['source_run'],
                   'pages': [{'page_id': page['page_id'], 'image_sha256': digest(image), 'native': pending, 'reference': draft}]}
        return data, payload

    def test_dataset_identity_is_independent_of_workspace_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data, _ = self.make_run(root)
            other = review_data(root, root / 'other/review')
            self.assertEqual(data['dataset_sha256'], other['dataset_sha256'])
            self.assertNotEqual(data['pages'][0]['image_data'], other['pages'][0]['image_data'])

    def test_import_rejects_demo_and_wrong_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, payload = self.make_run(Path(tmp))
            validate_reviews(payload, data)
            payload['demo'] = True
            with self.assertRaises(ValueError):
                validate_reviews(payload, data)
            payload['demo'] = False
            payload['pages'][0]['image_sha256'] = 'bad'
            with self.assertRaises(ValueError):
                validate_reviews(payload, data)

    def test_partial_review_does_not_claim_calibration_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, payload = self.make_run(root)
            write_json(root / 'reviews.json', payload)
            result = summarize(root, root / 'reviews.json', root / 'summary')
            self.assertEqual(result['status'], 'HUMAN_REVIEW_INCOMPLETE')
            self.assertFalse(result['thresholds_frozen'])
            self.assertEqual(result['aggregates'], [])

    def test_confirmed_reference_computes_real_errors_without_freezing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, payload = self.make_run(root)
            row = payload['pages'][0]
            row['native'].update(status='PASS', image_checked=True, reviewer='Fixture', reviewed_at='2026-10-17T00:00:00Z')
            row['reference'].update(status='CONFIRMED', text='100', reviewer='Fixture', reviewed_at='2026-10-17T00:00:00Z')
            write_json(root / 'reviews.json', payload)
            result = summarize(root, root / 'reviews.json', root / 'summary')
            self.assertEqual(result['status'], 'REVIEW_COMPLETE_THRESHOLDS_PENDING')
            scores = {r['channel']: r for r in result['aggregates']}
            self.assertAlmostEqual(scores['ocr150']['micro_cer'], 1 / 3)
            self.assertEqual(scores['ocr300']['micro_cer'], 0.)
            self.assertFalse(result['thresholds_frozen'])
            with self.assertRaises(FileExistsError):
                summarize(root, root / 'reviews.json', root / 'summary')


if __name__ == '__main__':
    unittest.main()
