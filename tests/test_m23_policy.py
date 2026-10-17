import math
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from qpaf.m23.policy import bag_metrics, covered_fraction, enforce_failure_cap, rectangles_to_pixels, resolve_page, tsv_words, load_frozen_policy
from qpaf.m23.review import metrics
from qpaf.m23.worker import parse_tsv


POLICY = {'supplement_min_confidence': 80., 'warning_mean_confidence': 60.,
          'native_overlap_fraction': .5, 'min_printable_ratio': .85}


class PolicyTests(unittest.TestCase):
    def test_frozen_policy_bytes_cannot_be_silently_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'policy.toml'
            raw = b'schema_version=1\nquality_status="FROZEN"\n[engine]\ndpi=300\n[routing]\nmode="native_plus_uncovered_ocr"\n'
            path.write_bytes(raw)
            expected = hashlib.sha256(raw).hexdigest()
            self.assertEqual(load_frozen_policy(path, expected)['engine']['dpi'], 300)
            path.write_bytes(raw + b'# changed\n')
            with self.assertRaises(ValueError):
                load_frozen_policy(path, expected)

    def test_literal_quote_in_tsv_cannot_absorb_later_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'words.tsv'
            path.write_text('level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
                            '5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t70\t"quote\n'
                            '5\t1\t1\t1\t1\t2\t20\t0\t10\t10\t90\tnext\n', encoding='utf-8')
            words = tsv_words(path)
            self.assertEqual([w['text'] for w in words], ['"quote', 'next'])
            self.assertEqual(parse_tsv(path)['word_count'], 2)
            self.assertEqual(parse_tsv(path)['mean_word_confidence'], 80.)

    def test_bag_diagnostic_separates_reading_order_and_keeps_multiplicity(self):
        self.assertEqual(bag_metrics('b a a', 'a a b')['bwe'], 0.)
        self.assertGreater(metrics('b a a', 'a a b')['cer'], 0.)
        self.assertEqual(bag_metrics('a b', 'a a b')['missing_tokens'], 1)
        self.assertEqual(bag_metrics('EXAMPLE!', 'example', retrieval=True)['bwe'], 0.)
        self.assertEqual(bag_metrics('hallucination', '')['bwe'], 1.)
        self.assertIsNone(bag_metrics('', '')['bwe'])

    def test_union_coverage_does_not_double_count_overlapping_rectangles(self):
        self.assertEqual(covered_fraction([0, 0, 10, 10], [[0, 0, 4, 10]] * 3), .4)
        self.assertEqual(covered_fraction([0, 0, 10, 10], [[0, 0, 4, 10], [4, 0, 10, 10]]), 1.)
        self.assertEqual(covered_fraction([0, 0, 10, 10], [[30, 30, 40, 40]]), 0.)

    def test_pdf_coordinate_transform_and_rotations(self):
        geometry = {'width': 100, 'height': 50, 'native_rectangles': [[10, 10, 30, 20]]}
        expected = {0: [10., 30., 30., 40.], 90: [10., 10., 20., 30.],
                    180: [70., 10., 90., 20.], 270: [30., 70., 40., 90.]}
        for rotation, box in expected.items():
            image_size = [50, 100] if rotation in (90, 270) else [100, 50]
            self.assertEqual(rectangles_to_pixels(dict(geometry, rotation=rotation), image_size), [box])

    def test_preserves_native_deduplicates_overlap_and_adds_uncovered_text(self):
        geom = {'width': 100, 'height': 100, 'native_rectangles': [[0, 80, 50, 100]]}
        words = [{'text': 'OCR_wrong', 'confidence': 99, 'box': [0, 0, 40, 20], 'line': [1, 1, 1]},
                 {'text': 'FigureLabel', 'confidence': 95, 'box': [60, 60, 90, 80], 'line': [2, 1, 1]},
                 {'text': 'noise', 'confidence': 10, 'box': [60, 80, 90, 90], 'line': [3, 1, 1]}]
        out = resolve_page('Native correct', {'status': 'OK', 'text': 'raw', 'mean_word_confidence': 90},
                           words, geom, [100, 100], POLICY)
        self.assertEqual(out['text'], 'Native correct\nFigureLabel')
        self.assertEqual(out['text_source'], 'native+ocr')
        self.assertEqual(out['supplement_words'], 1)
        self.assertFalse(out['technical_failure'])

    def test_short_native_survives_bad_ocr(self):
        out = resolve_page('PRESS KIT', {'status': 'OK', 'text': 'gibberish', 'mean_word_confidence': 2.}, [],
                           {'width': 10, 'height': 10, 'native_rectangles': []}, [10, 10], POLICY)
        self.assertEqual(out['text'], 'PRESS KIT')
        self.assertIn('low_ocr_confidence', out['warnings'])

    def test_empty_ocr_never_means_visually_blank_or_engine_failure(self):
        out = resolve_page('', {'status': 'NO_TEXT_DETECTED', 'text': '', 'mean_word_confidence': None},
                           [], {}, [], POLICY)
        self.assertEqual(out['extraction_status'], 'NO_TEXT_DETECTED')
        self.assertFalse(out['technical_failure'])
        self.assertIn('no_text_requires_visual_channel', out['warnings'])
        failed = resolve_page('', {'status': 'TIMEOUT', 'error': 'deadline'}, [], {}, [], POLICY)
        self.assertTrue(failed['technical_failure'])
        self.assertEqual(failed['extraction_status'], 'EXTRACTION_FAILED')
        with self.assertRaises(ValueError):
            enforce_failure_cap([out, failed], .01)

    def test_engine_failure_with_usable_native_is_still_counted(self):
        out = resolve_page('usable native', {'status': 'ERROR'}, [], {}, [], POLICY)
        self.assertEqual(out['text'], 'usable native')
        self.assertEqual(out['extraction_status'], 'NATIVE_TEXT_OCR_FAILED')
        self.assertTrue(out['technical_failure'])

    def test_invalid_success_payload_and_thresholds_fail(self):
        with self.assertRaises(ValueError):
            resolve_page('', {'status': 'OK', 'text': None}, [], {}, [], POLICY)
        with self.assertRaises(ValueError):
            resolve_page('', {}, [], {}, [], dict(POLICY, supplement_min_confidence=math.nan))
        with self.assertRaises(ValueError):
            rectangles_to_pixels({'width': 10, 'height': 10, 'native_rectangles': [[0, 0, 20, 20]]}, [10, 10])


if __name__ == '__main__':
    unittest.main()
