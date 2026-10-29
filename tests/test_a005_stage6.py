"""A005 Stage 6 aggregation and verdict rule, on synthetic per-query nDCG only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.a005 import stage6  # noqa: E402
from qpaf.a005.stage4 import METHOD, SEEDS, STAGE3  # noqa: E402
from qpaf.a005.stage5 import OUTPUT as CONFIRMATION  # noqa: E402
from qpaf.a005.stage6 import OUTPUT, Stage6Error, aggregate, build, verdict  # noqa: E402
from qpaf.m43.freeze import read  # noqa: E402

IDS = [f'q{i:02d}' for i in range(40)]
BASE = {q: 0.3+0.05*((i*7) % 10) for i, q in enumerate(IDS)}       # values in [0.3, 0.75]


def shifted(delta):
    return {q: min(1., max(0., v+delta)) for q, v in BASE.items()}


def mean(per_query):
    return sum(per_query.values())/len(per_query)


class Stage6Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)/'repo'

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, qpaf_delta, qarf_delta=-0.01, baselines=('colqwen25', 'train_fitted_static'),
              deltas=None, co_strongest=None):
        """Baselines share BASE; QPAF-SA is BASE + delta per baseline name (or one delta for all)."""
        entry = lambda per_query: {'ndcg_at_10': mean(per_query), 'per_query': per_query}  # noqa: E731
        roster = {name: entry(shifted(0.)) for name in (*baselines, 'bm25')}
        for name, delta in (deltas or {}).items():
            roster[name] = entry(shifted(qpaf_delta-delta))      # QPAF-SA minus this baseline is `delta`
        confirmation = {
            'baselines': roster,
            'methods': {METHOD['page']: {str(s): entry(shifted(qpaf_delta)) for s in SEEDS},
                        METHOD['query']: {str(s): entry(shifted(qarf_delta)) for s in SEEDS}}}
        stage3 = {'co_strongest': list(co_strongest or baselines)}
        for relative, record in ((CONFIRMATION, confirmation), (STAGE3, stage3)):
            (self.root/relative).parent.mkdir(parents=True, exist_ok=True)
            (self.root/relative).write_text(json.dumps(record), encoding='utf-8')

    def init_repo(self):
        for args in (('init', '-q'), ('add', '-A'), ('commit', '-q', '-m', 'fixture')):
            subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=self.root, check=True,
                           capture_output=True)

    def test_verdict_positive_when_all_lower_bounds_positive(self):
        self.write(0.02)
        record = build(self.root)
        self.assertEqual(record['verdict'], 'QPAF_SA_BEATS_BASELINE')
        for report in record['vs_co_strongest'].values():
            self.assertAlmostEqual(report['mean_of_seed_means'], 0.02, places=9)
            self.assertGreater(report['ci95'][0], 0)
        self.assertEqual(set(record['vs_co_strongest']), {'colqwen25', 'train_fitted_static'})

    def test_verdict_not_established_on_tie(self):
        self.write(0.)
        self.assertEqual(build(self.root)['verdict'], 'NOT_ESTABLISHED')

    def test_one_failing_co_strongest_baseline_blocks_the_verdict(self):
        self.write(0.02, deltas={'train_fitted_static': 0.})
        self.assertEqual(build(self.root)['verdict'], 'NOT_ESTABLISHED')

    def test_only_co_strongest_baselines_decide(self):
        self.write(0.02, co_strongest=['colqwen25'], deltas={'bm25': -0.1})
        record = build(self.root)
        self.assertEqual(set(record['vs_co_strongest']), {'colqwen25'})
        self.assertEqual(record['verdict'], 'QPAF_SA_BEATS_BASELINE')

    def test_qarf_comparison_is_reported_but_does_not_decide(self):
        self.write(0.02, qarf_delta=0.05)           # QPAF-SA is worse than QARF-SA
        record = build(self.root)
        self.assertLess(record['vs_qarf_sa']['mean_of_seed_means'], 0)
        self.assertEqual(record['verdict'], 'QPAF_SA_BEATS_BASELINE')

    def test_baseline_replicated_across_seeds(self):
        self.write(0.02)
        with mock.patch.object(stage6, 'paired_report', wraps=stage6.paired_report) as spy:
            build(self.root)
        self.assertEqual(spy.call_count, 3)            # two co-strongest baselines and QARF-SA
        for call in spy.call_args_list[:2]:
            qpaf, comparator = call.args
            self.assertEqual(set(qpaf), set(SEEDS))
            self.assertEqual(set(comparator), set(SEEDS))
            self.assertEqual(len({id(comparator[s]) for s in SEEDS}), 1)   # one dict, three seed keys

    def test_verdict_rule_needs_positive_mean_and_lower_bound(self):
        good = {'mean_of_seed_means': 0.01, 'ci95': [0.001, 0.02]}
        self.assertEqual(verdict([good]), 'QPAF_SA_BEATS_BASELINE')
        self.assertEqual(verdict([good, {**good, 'ci95': [0., 0.02]}]), 'NOT_ESTABLISHED')
        self.assertEqual(verdict([{**good, 'mean_of_seed_means': 0.}]), 'NOT_ESTABLISHED')
        self.assertEqual(verdict([]), 'NOT_ESTABLISHED')

    def test_unknown_co_strongest_baseline_refused(self):
        self.write(0.02, co_strongest=['missing'])
        with self.assertRaisesRegex(Stage6Error, 'co-strongest baseline'):
            build(self.root)

    def test_aggregate_is_create_once(self):
        self.write(0.02)
        self.init_repo()
        record = aggregate(self.root)
        self.assertEqual(read(self.root/OUTPUT)['verdict'], record['verdict'])
        self.assertEqual(read(self.root/OUTPUT)['source_commit'], record['source_commit'])
        with self.assertRaisesRegex(Stage6Error, 'already exists'):
            aggregate(self.root)


if __name__ == '__main__':
    unittest.main()
