"""A005-R1 ensembles, the validation table and the one-time confirmation record on synthetic data."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.a005 import stage5  # noqa: E402
from qpaf.a005.model import AnchoredFusionGate  # noqa: E402
from qpaf.a005.refine import RefineError, create_run  # noqa: E402
from qpaf.a005.refine_eval import (CONFIRMATION_OUTPUT, VALIDATION_OUTPUT, confirmation_record,  # noqa: E402
                                   ensemble_scores, validation_table)
from qpaf.a005.stage2 import split_inputs  # noqa: E402
from qpaf.a005.stage4 import GRANULARITIES, SEEDS, STAGE3, run_dir as s4_run_dir, validation_scores  # noqa: E402
from qpaf.m43.freeze import read, sha  # noqa: E402

sys.path.insert(0, str(ROOT/'tests'))
from test_a005_refine import quiet  # noqa: E402
import test_a005_stage5 as stage5_tests  # noqa: E402

ANCHOR = stage5_tests.ANCHOR

SMALL = dict(epochs=2, average_from=1)
STATIC = 0.5


class RefineEvalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = stage5_tests.Stage5Tests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root, self.cache, self.sealed = self.fixture.root, self.fixture.cache, self.fixture.sealed
        # Stage 3 needs the roster the table reads; the Stage 4 results need the field the table averages.
        (self.root/STAGE3).write_text(json.dumps({
            'train_fitted_static_weights': ANCHOR, 'stage4_anchor_weights': ANCHOR,
            'roster': {'train_fitted_static': {'ndcg_at_10': STATIC}}}), encoding='utf-8')
        for granularity in GRANULARITIES:
            for seed in SEEDS:
                path = s4_run_dir(self.root, granularity, seed)/'result.json'
                result = read(path)
                result.update(stage3_sha256=sha(self.root/STAGE3), validation_ndcg_at_10=0.6)
                path.write_text(json.dumps(result), encoding='utf-8')
        self.fixture.init_repo()
        stage5.create(self.root, self.cache, self.sealed)

    def train(self, variant, seeds):
        for granularity in GRANULARITIES:
            for seed in seeds:
                create_run(self.root, self.cache, variant, granularity, seed, log=quiet, **SMALL)

    def test_ensemble_of_identical_models_equals_single(self):
        records, _ = split_inputs(self.root, self.cache, 'validation')
        model = AnchoredFusionGate(ANCHOR, 'page')
        model.delta.weight.data += 0.3
        single = validation_scores(model, records)
        ensemble = ensemble_scores([model, model, model], records)
        self.assertEqual(set(ensemble), set(single))
        for query_id, values in single.items():
            for a, b in zip(values, ensemble[query_id]):
                self.assertAlmostEqual(a, b, places=12)

    def test_table_rows_cover_both_granularities(self):
        self.train('full', SEEDS)
        self.train('eps1e3', SEEDS[:1])
        self.train('constlr', SEEDS[:1])
        table = validation_table(self.root, self.cache)
        self.assertEqual(table['train_fitted_static'], STATIC)
        self.assertEqual(set(table['rows']), set(GRANULARITIES))
        for rows in table['rows'].values():
            self.assertEqual([row['id'] for row in rows], ['a005_original', 'full_ensemble', 'full_seed_mean',
                                                           'full_best_epoch_ensemble', 'eps1e3_seed1',
                                                           'constlr_seed1', 'full_seed1'])
            for row in rows:
                self.assertAlmostEqual(row['delta_vs_static'], row['ndcg_at_10']-STATIC, places=12)
            self.assertAlmostEqual(rows[0]['ndcg_at_10'], 0.6)
        self.assertTrue((self.root/VALIDATION_OUTPUT).is_file())
        with self.assertRaisesRegex(RefineError, 'already exists'):
            validation_table(self.root, self.cache)

    def test_confirmation_refuses_a_wrong_sealed_hash_and_writes_nothing(self):
        self.train('full', SEEDS)
        self.fixture.write_marker('0'*64)
        stage5_tests.git(self.root, 'commit', '-qam', 'tamper the marker')
        with self.assertRaisesRegex(stage5.Stage5Error, 'sealed file hash'):
            confirmation_record(self.root, self.cache, self.sealed)
        self.assertFalse((self.root/CONFIRMATION_OUTPUT).exists())

    def test_confirmation_needs_all_full_runs_before_opening_the_seal(self):
        self.train('full', SEEDS[:2])
        self.sealed.write_text('{ not json', encoding='utf-8')          # opening it would fail differently
        with self.assertRaisesRegex(RefineError, 'run missing'):
            confirmation_record(self.root, self.cache, self.sealed)

    def test_confirmation_record_is_post_hoc_and_create_once(self):
        self.train('full', SEEDS)
        record = confirmation_record(self.root, self.cache, self.sealed)
        stored = read(self.root/CONFIRMATION_OUTPUT)
        self.assertTrue(stored['post_hoc'])
        self.assertIn('already opened once', stored['note'])
        self.assertEqual(stored['source_commit'], record['source_commit'])
        self.assertEqual(set(stored['comparisons']), {'a_qpaf_r1_vs_static', 'b_qpaf_r1_vs_qarf_r1',
                                                      'c_qpaf_r1_vs_qpaf_sa_v2'})
        count = len(self.fixture.confirmation)
        for report in stored['comparisons'].values():
            self.assertEqual(report['query_count'], count)
        self.assertEqual(set(stored['per_seed_averaged']), {'QARF-SA-R1', 'QPAF-SA-R1'})
        a = stored['comparisons']['a_qpaf_r1_vs_static']
        ensemble, static = stored['ndcg_at_10']['QPAF-SA-R1 ensemble'], stored['ndcg_at_10']['train_fitted_static']
        self.assertAlmostEqual(a['mean_of_seed_means'], ensemble-static, places=12)
        with self.assertRaisesRegex(RefineError, 'already exists'):
            confirmation_record(self.root, self.cache, self.sealed)


if __name__ == '__main__':
    unittest.main()
