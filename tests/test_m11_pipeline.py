import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from qpaf.m11.config import load_config
from qpaf.m11.artifacts import StageRun, digest, read_json, verify_manifest, write_json
from qpaf.m11.retrieval import bm25_scores, load_score_cache, save_score_cache
from qpaf.m11.pipeline import execute_stage

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_bm25_positive_idf_and_empty_pages(self):
        scores = bm25_scores(['apple', 'pear'], ['apple apple', 'pear', ''], 1.5, .75)
        self.assertGreater(scores[0, 0], scores[0, 1])
        self.assertGreater(scores[1, 1], scores[1, 0])
        self.assertEqual(scores[0, 2], 0)
        self.assertEqual(bm25_scores(['x'], ['', ''], 1.5, .75).tolist(), [[0., 0.]])

    def test_bm25_b_one_keeps_empty_pages_finite(self):
        import math
        scores = bm25_scores(['apple'], ['apple', ''], 1.5, 1.0)
        self.assertTrue(math.isfinite(scores[0, 1]))
        self.assertEqual(scores[0, 1], 0.)

    def test_local_evaluator_rejects_generation_config_mismatch(self):
        from qpaf.m11.pipeline import verify_generation_config
        config = load_config(ROOT/'configs/m1.1/vidoseek.toml')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with StageRun(root, 'dense', config, {}, {}) as run:
                pass
            changed = json.loads(json.dumps(config))
            changed['dense']['model_id'] = 'a-different-model'
            with self.assertRaises(ValueError):
                verify_generation_config(run.path, 'dense', changed)
            changed = json.loads(json.dumps(config))
            changed['oracle']['bootstrap_samples'] = 20
            verify_generation_config(run.path, 'dense', changed)

    def test_reordered_cache_is_rejected(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_score_cache(root, np.array([[1., 2.]]), ['q'], ['a', 'b'], 'bm25')
            with self.assertRaises(ValueError):
                load_score_cache(root, ['q'], ['b', 'a'], 'bm25')

    def test_nonfinite_cache_rejected_on_write(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            save_score_cache(Path(tmp), np.array([[float('inf')]]), ['q'], ['p'], 'dense')

    def test_cached_fixture_produces_verifiable_evidence_and_reuses_stages(self):
        import numpy as np
        config = load_config(ROOT/'configs/m1.1/vidoseek.toml', ['oracle.bootstrap_samples=20'])
        source = {'digest': 'test-fixture', 'kind': 'synthetic_software_test'}
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run_root = workspace/'runs'/'fixture'
            with StageRun(run_root, 'prepare', config, {}, source) as prep:
                write_json(prep.path/'queries.json', [{'query_id': 'q', 'text': 'fruit'}])
                write_json(prep.path/'pages.json', [{'page_id': 'a', 'text': 'fruit'}, {'page_id': 'b', 'text': 'tree'}])
                write_json(prep.path/'qrels.json', {'q': {'a': 1}})
                write_json(prep.path/'dataset.json', {'kind': 'synthetic_software_test'})
            inputs = {'prepare': digest(prep.path/'receipt.json')}
            for channel, scores in [('bm25', [[1., 0.]]), ('dense', [[0., 1.]]), ('visual', [[.5, .5]])]:
                with StageRun(run_root, channel, config, inputs, source) as run:
                    save_score_cache(run.path, np.asarray(scores), ['q'], ['a', 'b'], channel)
            output = execute_stage('oracle', config, workspace, 'fixture', source)
            for filename in ['query_ids.csv', 'per_query_metrics.csv', 'summary.json', 'review.md',
                             'provenance.json', 'hashes.csv', 'run.log', 'resolved_config.json']:
                self.assertTrue((output/filename).exists(), filename)
            self.assertEqual(read_json(output/'summary.json')['n_queries'], 1)
            verify_manifest(output, read_json(output/'receipt.json')['outputs'])
            self.assertEqual(execute_stage('oracle', config, workspace, 'fixture', source), output)
            from qpaf.m11.evidence import pack_evidence, verify_evidence
            from qpaf.m11.dataset import extract_zip
            import io
            import zipfile
            payload = pack_evidence(run_root, config, source)
            with zipfile.ZipFile(io.BytesIO(payload)) as zipped:
                self.assertIn('upstream/visual/provenance.json', zipped.namelist())
                self.assertNotIn('upstream/visual/scores.npy', zipped.namelist())
            exported = workspace/'exported'
            extract_zip(io.BytesIO(payload), exported)
            verify_evidence(exported)
            for stage in ('prepare', 'bm25', 'dense', 'visual'):
                for metadata in sorted((exported/'upstream'/stage).iterdir()):
                    if metadata.name == 'receipt.json':
                        continue
                    with self.subTest(missing_metadata=f'{stage}/{metadata.name}'):
                        content = metadata.read_bytes()
                        metadata.unlink()
                        try:
                            with self.assertRaises(ValueError):
                                verify_evidence(exported)
                        finally:
                            metadata.write_bytes(content)
            (exported/'upstream/visual/provenance.json').write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_evidence(exported)

    def test_launcher_dry_run_uses_runtime_config_without_credentials(self):
        result = subprocess.run([sys.executable, str(ROOT/'scripts/run_m11_modal.py'),
            '--config', str(ROOT/'configs/m1.1/vidoseek.toml'), '--run-id', 'unit-test',
            '--set', 'modal.gpu="L4"', '--set', 'modal.volume_name="test-artifacts"', '--dry-run'],
            capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan['config']['modal']['gpu'], 'L4')
        self.assertEqual(plan['config']['modal']['volume_name'], 'test-artifacts')
        self.assertEqual(plan['stages'], ['prepare', 'bm25', 'dense', 'visual', 'oracle'])


if __name__ == '__main__':
    unittest.main()
