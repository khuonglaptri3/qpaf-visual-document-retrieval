"""Closure verification must be read-only; invocation tracking includes resumes."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
spec = importlib.util.spec_from_file_location('m28_cli', ROOT/'scripts/run_m28_cache.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
from qpaf.m11.artifacts import digest, read_json, write_json, object_hash, file_manifest
import hashlib


class CliRegressionTests(unittest.TestCase):
    def test_query_text_and_split_ownership_are_bound_to_preflight(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder/'remote').mkdir()
            queries = {'q0': 'original zero', 'q1': 'original one', 'q2': 'original two'}
            splits = {'train': ['q0'], 'validation': ['q1'], 'test': ['q2']}
            inputs = {'query_ids': sorted(queries), 'query_texts_sha256': object_hash(queries),
                      'split_verification': {'role_counts': {k: len(v) for k, v in splits.items()},
                        'role_sha256': {k: hashlib.sha256(''.join(q+'\n' for q in v).encode()).hexdigest()
                                        for k, v in splits.items()}}}
            write_json(folder/'queries.json', queries)
            write_json(folder/'remote'/'queries.json', queries)
            write_json(folder/'split_ids.json', splits)
            cli.verify_prepared_inputs(folder, inputs)
            write_json(folder/'queries.json', {**queries, 'q0': 'tampered'})
            with self.assertRaisesRegex(ValueError, 'query|Query'):
                cli.verify_prepared_inputs(folder, inputs)
            write_json(folder/'queries.json', queries)
            write_json(folder/'split_ids.json', {**splits, 'train': ['q2'], 'test': ['q0']})
            with self.assertRaisesRegex(ValueError, 'split|Split'):
                cli.verify_prepared_inputs(folder, inputs)

    def test_collection_replay_rejects_corrupt_non_score_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            remote = folder/'remote'
            remote.mkdir()
            write_json(remote/'resources.json', {'seconds': 1})
            rows = file_manifest(remote)
            write_json(remote/'portable_manifest.json', {'status': 'COMPLETE', 'files': rows})
            write_json(folder/'collection.json', {'status': 'COMPLETE',
                       'portable_manifest_sha256': digest(remote/'portable_manifest.json'),
                       'verified_artifact_count': len(rows), 'bytes': sum(r['size_bytes'] for r in rows)})
            cli.verify_collection(folder)
            (remote/'resources.json').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'checksum|hash'):
                cli.verify_collection(folder)

    def test_verify_does_not_recreate_missing_handover(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder = root/'run'
            folder.mkdir()
            qids, pids = ['q0', 'q1', 'q2'], ['doc_page_0001']
            scores = {c: np.ones((3, 1), dtype=np.float64) for c in ('bm25', 'dense', 'visual')}
            write_json(root/'annotation.json', {'examples': [
                {'uid': q, 'meta_info': {'file_name': 'doc.pdf', 'reference_page': [1]}} for q in qids]})
            write_json(folder/'queries.json', {q: 'question' for q in qids})
            write_json(folder/'split_ids.json', {'train': ['q0'], 'validation': ['q1'], 'test': ['q2']})
            inputs = {'query_ids': qids, 'page_ids': pids,
                      'annotation': {'path': 'annotation.json', 'sha256': digest(root/'annotation.json')},
                      'preprocessing_identity_sha256': 'p', 'm27_manifest_sha256': 'm'}
            identity = {'config_sha256': 'c', 'source_sha256': 's', 'input_sha256': 'i'}
            with mock.patch.object(cli, 'ROOT', root), mock.patch.object(cli, '_scores', return_value=(scores, inputs, identity)):
                with mock.patch('builtins.print'):
                    cli.finalize(folder)
                (folder/'bundle'/'handover.json').unlink()
                before = {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
                with self.assertRaisesRegex(ValueError, 'handover'):
                    cli.finalize(folder, verify_only=True)
                after = {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
                self.assertEqual(before, after)

    def test_latest_invocation_includes_resumed_calls(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            write_json(folder/'execution.json', {'started_utc': '2026-10-20T01:00:00+00:00', 'function_call_id': 'old'})
            write_json(folder/'execution-resume-20261020T020000Z.json',
                       {'started_utc': '2026-10-20T02:00:00+00:00', 'function_call_id': 'active'})
            self.assertEqual(cli.latest_execution(folder)[1]['function_call_id'], 'active')


if __name__ == '__main__':
    unittest.main()
