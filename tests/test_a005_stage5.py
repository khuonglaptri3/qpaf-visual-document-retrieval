"""A005 Stage 5 one-time confirmation runner on a synthetic cache and a synthetic sealed file only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import torch  # noqa: E402

from qpaf.a005.model import AnchoredFusionGate  # noqa: E402
from qpaf.a005.stage2 import CACHE_FILES, SPLITS  # noqa: E402
from qpaf.a005.stage4 import GRANULARITIES, METHOD, SEEDS, STAGE3, run_dir  # noqa: E402
from qpaf.a005.stage5 import (CONFIRMATION_IDS, OUTPUT, PREPARE_MARKER, Stage5Error, confirmation_inputs,  # noqa: E402
                              create, run, sealed_sha256)
from qpaf.m43.freeze import read, sha  # noqa: E402

sys.path.insert(0, str(ROOT/'tests'))
from test_a005_vimdoc import cache as synthetic_cache  # noqa: E402

ANCHOR = [0., 0.1, 0.9]


def git(root, *args):
    subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=root, check=True,
                   capture_output=True)


class Stage5Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.cache = Path(self.tmp.name)/'repo', Path(self.tmp.name)/'cache'
        self.cache.mkdir()
        frame, qrels = synthetic_cache(queries=30, good_channel=1)
        ids = sorted(qrels)
        roles = {'train': ids[:14], 'validation': ids[14:20], 'confirmation': ids[20:]}
        self.confirmation = roles['confirmation']
        self.uncovered = self.confirmation[0]
        qrels[self.uncovered] = ['d_not_in_any_pool']  # the pool cannot cover this query
        (self.root/SPLITS).mkdir(parents=True)
        for role, members in roles.items():
            (self.root/SPLITS/f'{role}_ids.txt').write_text('\n'.join(members)+'\n', encoding='utf-8')
        pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), self.cache/'candidate_scores.parquet')
        (self.cache/'queries.jsonl').write_text(
            ''.join(json.dumps({'query_id': q, 'text': 'synthetic query'})+'\n' for q in qrels), encoding='utf-8')
        (self.cache/'dev_qrels.json').write_text(json.dumps(
            {r: {q: qrels[q] for q in roles[r]} for r in ('train', 'validation')}), encoding='utf-8')
        self.sealed = self.cache/'confirmation_qrels.sealed.json'
        self.sealed.write_text(json.dumps({q: qrels[q] for q in self.confirmation}), encoding='utf-8')
        self.write_marker(sha(self.sealed))
        self.write_stage3_and_stage4()

    def tearDown(self):
        self.tmp.cleanup()

    def write_marker(self, digest):
        (self.root/PREPARE_MARKER).parent.mkdir(parents=True, exist_ok=True)
        (self.root/PREPARE_MARKER).write_text(json.dumps({'confirmation_qrels_sealed_sha256': digest}))

    def write_stage3_and_stage4(self):
        (self.root/STAGE3).parent.mkdir(parents=True, exist_ok=True)
        (self.root/STAGE3).write_text(json.dumps(
            {'train_fitted_static_weights': ANCHOR, 'stage4_anchor_weights': ANCHOR}), encoding='utf-8')
        for granularity in GRANULARITIES:
            for number, seed in enumerate(SEEDS):
                torch.manual_seed(seed)
                model = AnchoredFusionGate(ANCHOR, granularity)
                model.delta.weight.data += 0.3*torch.randn_like(model.delta.weight)
                directory = run_dir(self.root, granularity, seed)
                directory.mkdir(parents=True)
                torch.save(model.state_dict(), directory/'checkpoint.pt')
                (directory/'result.json').write_text(json.dumps({
                    'method': METHOD[granularity], 'granularity': granularity, 'seed': seed,
                    'checkpoint_sha256': sha(directory/'checkpoint.pt'), 'reload_pass': True,
                    'finite_parameters': True, 'stage3_sha256': sha(self.root/STAGE3),
                    'anchor_weights': ANCHOR,
                    'inputs_sha256': {name: sha(self.cache/name) for name in CACHE_FILES}}), encoding='utf-8')

    def init_repo(self):
        git(self.root, 'init', '-q')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'fixture')

    def test_default_hash_source_is_the_prepare_marker(self):
        self.assertEqual(PREPARE_MARKER, 'evidence/revisions/a005-s1-001/markers/prepare.json')
        self.assertEqual(CONFIRMATION_IDS, SPLITS+'/confirmation_ids.txt')
        self.assertEqual(sealed_sha256(self.root), sha(self.sealed))

    def test_wrong_sealed_hash_refused_before_parsing(self):
        self.sealed.write_text('{ this is not json', encoding='utf-8')     # parsing would raise another error
        with self.assertRaisesRegex(Stage5Error, 'sealed file hash'):
            confirmation_inputs(self.root, self.cache, self.sealed)
        self.write_marker('0'*64)
        self.sealed.write_text(json.dumps({'q20': ['d0']}), encoding='utf-8')
        with self.assertRaisesRegex(Stage5Error, 'sealed file hash'):
            confirmation_inputs(self.root, self.cache, self.sealed)

    def test_qrels_must_match_the_confirmation_ids(self):
        self.sealed.write_text(json.dumps({q: ['d0'] for q in self.confirmation[:-1]}), encoding='utf-8')
        self.write_marker(sha(self.sealed))
        with self.assertRaisesRegex(Stage5Error, 'do not match'):
            confirmation_inputs(self.root, self.cache, self.sealed)

    def test_inputs_cover_only_confirmation_queries(self):
        records, qrels = confirmation_inputs(self.root, self.cache, self.sealed)
        self.assertEqual([r.query_id for r in records], sorted(self.confirmation, key=lambda q: q.encode()))
        self.assertEqual(set(qrels), set(self.confirmation))

    def test_requires_all_stage4_runs(self):
        (run_dir(self.root, 'page', SEEDS[2])/'result.json').unlink()
        with self.assertRaisesRegex(Stage5Error, 'Stage 4 run missing'):
            create(self.root, self.cache, self.sealed)
        self.assertFalse((self.root/OUTPUT).exists())

    def test_stage4_run_must_match_the_checkpoint_and_cache(self):
        (run_dir(self.root, 'query', SEEDS[0])/'checkpoint.pt').write_bytes(b'tampered')
        with self.assertRaisesRegex(Stage5Error, 'checkpoint differs'):
            create(self.root, self.cache, self.sealed)

    def test_create_once(self):
        self.init_repo()
        record = create(self.root, self.cache, self.sealed)
        self.assertEqual(read(self.root/OUTPUT)['confirmation_query_count'], len(self.confirmation))
        self.assertEqual(record['source_commit'], read(self.root/OUTPUT)['source_commit'])
        with self.assertRaisesRegex(Stage5Error, 'already exists'):
            create(self.root, self.cache, self.sealed)

    def test_create_needs_a_clean_tree(self):
        self.init_repo()
        (self.root/'evidence'/'stray.txt').write_text('x')
        git(self.root, 'add', '-A')
        with self.assertRaisesRegex(Stage5Error, 'clean tracked tree'):
            create(self.root, self.cache, self.sealed)

    def test_uncovered_query_scores_zero_and_is_counted(self):
        result = run(self.root, self.cache, self.sealed)
        self.assertEqual(result['queries_without_positive_candidate'], 1)
        for entry in result['baselines'].values():
            self.assertIn(self.uncovered, entry['per_query'])
            self.assertEqual(entry['per_query'][self.uncovered], 0.)
        for runs in result['methods'].values():
            for entry in runs.values():
                self.assertEqual(entry['per_query'][self.uncovered], 0.)

    def test_same_rows_for_all_methods(self):
        result = run(self.root, self.cache, self.sealed)
        self.assertEqual(set(result['methods']), {'QARF-SA-v2', 'QPAF-SA-v2'})
        self.assertEqual({'bm25', 'bge_m3', 'colqwen25', 'uniform_combsum', 'rrf_k60', 'train_fitted_static'},
                         set(result['baselines']))
        expected = set(self.confirmation)
        entries = list(result['baselines'].values()) + [e for runs in result['methods'].values()
                                                        for e in runs.values()]
        self.assertEqual(len(entries), 6+6)
        for entry in entries:
            self.assertEqual(set(entry['per_query']), expected)
            self.assertAlmostEqual(entry['ndcg_at_10'], sum(entry['per_query'].values())/len(expected), places=12)
        self.assertEqual(result['confirmation_query_count'], len(expected))
        for runs in result['methods'].values():
            self.assertEqual(set(runs), {str(seed) for seed in SEEDS})


if __name__ == '__main__':
    unittest.main()
