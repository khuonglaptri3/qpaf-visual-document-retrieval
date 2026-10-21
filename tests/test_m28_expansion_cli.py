"""End-to-end A003 phases on a synthetic M2.8 source run with real top_k=200."""
import importlib.util
from contextlib import redirect_stdout
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
spec = importlib.util.spec_from_file_location('m28_expansion_cli', ROOT/'scripts/run_m28_expansion.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
from qpaf.m11.artifacts import digest, file_manifest, object_hash, read_json, write_json
from qpaf.m28 import bundle as base

RUN_ID = 'RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01'
SPLITS = {'train': ['q0', 'q1'], 'validation': ['q2'], 'test': ['q3']}
QIDS = ['q0', 'q1', 'q2', 'q3']
PIDS = [f'd{doc:02d}_page_{page:04d}' for doc in range(30) for page in range(1, 16)]


def _scores(seed=7):
    rng = np.random.default_rng(seed)
    scores = {c: rng.uniform(0.1, 0.9, size=(len(QIDS), len(PIDS))) for c in base.CHANNELS}
    first, last = PIDS.index('d00_page_0001'), PIDS.index('d00_page_0015')
    for channel in base.CHANNELS:
        scores[channel][0, first] = 1.0
        scores[channel][0, last] = 0.0
    return scores


def _qrels(uncovered_query_gets_last_page=True):
    qrels = {'q0': {'d00_page_0015' if uncovered_query_gets_last_page else 'd00_page_0001': 1}}
    for index, query_id in enumerate(QIDS[1:], 1):
        scores = _scores()['bm25'][index]
        qrels[query_id] = {PIDS[int(np.argmax(scores))]: 1}
    return qrels


def make_source(root, scores, qrels):
    folder = root/'results/m2.8'/RUN_ID
    remote, bundle = folder/'remote', folder/'bundle'
    resolved, source = {'experiment_id': 'QPAF-M2_8-CACHE-001'}, {'digest': 'f'*64}
    inputs = {'query_ids': QIDS, 'page_ids': PIDS, 'query_count': len(QIDS), 'page_count': len(PIDS)}
    identity = {'config_sha256': object_hash(resolved), 'source_sha256': source['digest'],
                'input_sha256': object_hash(inputs)}
    for channel in base.CHANNELS:
        (remote/channel).mkdir(parents=True)
        path = remote/channel/'scores.npy'
        np.save(path, scores[channel])
        write_json(path.with_suffix('.json'), {'identity': {**identity, 'kind': channel+'_full'},
                   'shape': list(scores[channel].shape), 'dtype': 'float64',
                   'sha256': digest(path), 'size_bytes': path.stat().st_size})
    write_json(remote/'summary.json', {'status': 'COMPLETE', 'identity': identity})
    write_json(remote/'portable_manifest.json', {'status': 'COMPLETE', 'files': file_manifest(remote)})
    write_json(folder/'collection.json', {'portable_manifest_sha256': digest(remote/'portable_manifest.json')})
    write_json(folder/'resolved_config.json', resolved)
    write_json(folder/'source.json', source)
    write_json(folder/'input_manifest.json', inputs)
    frozen = base.build_candidates(scores, QIDS, PIDS)
    base.freeze_candidates(bundle, frozen, {'uses_qrels': False})
    write_json(bundle/'coverage_report.json', base.audit_coverage(frozen['candidates'], qrels, QIDS, SPLITS))
    keys = sorted({(r['query_id'], r['page_id']) for r in frozen['candidates']})
    write_json(bundle/'handover.json', {'m24_m25_row_audit': {'candidate_keys_sha256': hashlib.sha256(
        ''.join(f'{q}\t{p}\n' for q, p in keys).encode('utf-8')).hexdigest()}})
    write_json(bundle/'split_ids.json', SPLITS)
    write_json(bundle/'queries.json', {q: f'question {q}' for q in QIDS})
    write_json(bundle/'qrels_development.json', {q: qrels[q] for q in SPLITS['train']+SPLITS['validation']})
    write_json(bundle/'qrels_test_sealed.json', {q: qrels[q] for q in SPLITS['test']})
    for role, name in cli.SPLIT_FILES.items():
        (bundle/'splits').mkdir(exist_ok=True)
        (bundle/'splits'/name).write_bytes(''.join(q+'\n' for q in SPLITS[role]).encode('utf-8'))
    amendment = root/'evidence/A003.md'
    amendment.parent.mkdir(parents=True)
    amendment.write_text('A003 fixture\n', encoding='utf-8')
    names = ('candidate_freeze', 'handover', 'coverage_report', 'split_ids', 'qrels_development')
    config = read_json(ROOT/'configs/m2.8/expansion.json')
    config['amendment'].update(path='evidence/A003.md', sha256=digest(amendment))
    config['source_run'].update(
        path=f'results/m2.8/{RUN_ID}', portable_manifest_sha256=digest(remote/'portable_manifest.json'),
        query_texts_sha256=digest(bundle/'queries.json'), qrels_test_sha256=digest(bundle/'qrels_test_sealed.json'),
        **{f'{name}_sha256': digest(bundle/f'{name}.json') for name in names})
    write_json(root/'expansion.json', config)
    return frozen


class ExpansionCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.saved = cli.ROOT, cli.CONFIG
        cli.ROOT, cli.CONFIG = self.root, self.root/'expansion.json'

    def tearDown(self):
        cli.ROOT, cli.CONFIG = self.saved
        self.temp.cleanup()

    def run_quietly(self, function, *args, **kwargs):
        with redirect_stdout(io.StringIO()):
            return function(*args, **kwargs)

    def test_develop_finalize_verify_cover_the_baseline_miss(self):
        frozen = make_source(self.root, _scores(), _qrels())
        baseline = read_json(self.root/'results/m2.8'/RUN_ID/'bundle/coverage_report.json')
        self.assertEqual(baseline['uncovered_query_ids'], ['q0'])
        self.assertNotIn(('q0', 'd00_page_0015'),
                         {(r['query_id'], r['page_id']) for r in frozen['candidates']})
        run = self.run_quietly(cli.develop, cli.CONFIG)
        report = read_json(run/'development_report.json')
        self.assertEqual((report['status'], report['test_qrels_opened']), ('PASS', False))
        self.assertFalse((run/'bundle/qrels_test_sealed.json').exists())
        handover = self.run_quietly(cli.finalize, run)
        self.assertEqual((handover['status'], handover['uncovered_query_ids']), ('PASS', []))
        self.assertLessEqual(handover['max_candidates_per_query'], 600)
        self.assertGreater(handover['added_page_count'], 0)
        self.assertEqual(self.run_quietly(cli.finalize, run, verify_only=True), handover)

    def test_failed_development_blocks_finalize(self):
        make_source(self.root, _scores(), _qrels())
        run = self.run_quietly(cli.develop, cli.CONFIG)
        report = read_json(run/'development_report.json')
        write_json(run/'development_report.json', {**report, 'status': 'BLOCKED'})
        with self.assertRaisesRegex(ValueError, 'forbids tuning'):
            cli.finalize(run)
        self.assertFalse((run/'bundle/handover.json').exists())

    def test_verify_rejects_tampered_bundle_and_never_creates_handover(self):
        make_source(self.root, _scores(), _qrels())
        run = self.run_quietly(cli.develop, cli.CONFIG)
        with self.assertRaisesRegex(ValueError, 'Missing immutable handover'):
            cli.finalize(run, verify_only=True)
        self.run_quietly(cli.finalize, run)
        path = run/'bundle/candidate_expansion_log.parquet'
        path.write_bytes(path.read_bytes()+b'\0')
        with self.assertRaises(ValueError):
            cli.finalize(run, verify_only=True)

    def test_source_payload_must_match_the_portable_manifest(self):
        make_source(self.root, _scores(), _qrels())
        path = self.root/'results/m2.8'/RUN_ID/'remote/visual/scores.npy'
        np.save(path, _scores(seed=8)['visual'])
        with self.assertRaisesRegex(ValueError, 'portable manifest'):
            cli.load_source(cli.load_config(cli.CONFIG))


if __name__ == '__main__':
    unittest.main()
