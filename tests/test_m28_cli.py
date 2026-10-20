"""Closure verification must be read-only; invocation tracking includes resumes."""
import importlib.util
from contextlib import nullcontext, redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
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
                # A cloud handover must carry the exact query bytes and the
                # split directory consumed by the real M2.4 runner.
                from qpaf.m24.dataset import read_split_ids
                self.assertEqual((folder/'bundle'/'queries.json').read_bytes(),
                                 (folder/'queries.json').read_bytes())
                self.assertEqual(read_split_ids(folder/'bundle'/'splits'),
                                 read_json(folder/'split_ids.json'))
                with mock.patch('builtins.print'):
                    cli.finalize(folder, verify_only=True)
                bundle_hashes = folder/'bundle'/'hashes.json'
                manifest_bytes = bundle_hashes.read_bytes()
                bundle_hashes.unlink()
                with self.assertRaisesRegex(ValueError, 'hash'):
                    cli.finalize(folder, verify_only=True)
                self.assertFalse(bundle_hashes.exists())
                bundle_hashes.write_bytes(manifest_bytes)
                query_copy = folder/'bundle'/'queries.json'
                query_bytes = query_copy.read_bytes()
                query_copy.write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError, 'input artifact'):
                    cli.finalize(folder, verify_only=True)
                query_copy.write_bytes(query_bytes)
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


class InvocationResultTests(unittest.TestCase):
    class DeserializationError(Exception):
        pass

    def fixture(self, folder, error, summary=None):
        config = {'execution': {'requirements_file': 'fixture.lock', 'gpu': 'A10'},
                  'modal': {'volume_name': 'fixture-volume'}}
        source, inputs = {'digest': 'source-id'}, {'query_ids': ['q']}
        for name, value in [('resolved_config.json', config), ('source.json', source),
                            ('input_manifest.json', inputs), ('queries.json', {'q': 'query'}),
                            ('execution.json', {'started_utc': '2026-10-20T01:00:00Z',
                                                'function_call_id': 'first-call'}),
                            ('execution-resume-fixture.json', {'started_utc': '2026-10-20T02:00:00Z',
                                                              'function_call_id': 'latest-call'})]:
            write_json(folder/name, value)
        valid = {'run_id': folder.name, 'status': 'COMPLETE',
                 'completed_utc': '2026-10-20T03:00:00Z',
                 'identity': {'config_sha256': object_hash(config), 'source_sha256': source['digest'],
                              'input_sha256': object_hash(inputs)}}
        if summary is None:
            summary = valid

        def get(timeout):
            if timeout != 1:
                raise AssertionError('Unexpected result timeout')
            raise error

        def from_id(call_id):
            if call_id != 'latest-call':
                raise AssertionError('CLI must check the latest invocation')
            return SimpleNamespace(get=get)

        def read_file(path):
            if not isinstance(error, self.DeserializationError):
                raise AssertionError('Only deserialization failure permits Volume fallback')
            if path != '/runs/'+folder.name+'/summary.json':
                raise AssertionError('Only the exact committed run summary may be read')
            payload = json.dumps(summary).encode('utf-8')
            return iter([payload[:10], payload[10:]])

        volume = SimpleNamespace(read_file=read_file)
        def from_name(name):
            if name != 'fixture-volume':
                raise AssertionError('Output Volume identity changed')
            return volume
        modal = SimpleNamespace(FunctionCall=SimpleNamespace(from_id=from_id),
                                Volume=SimpleNamespace(from_name=from_name),
                                exception=SimpleNamespace(DeserializationError=self.DeserializationError),
                                enable_output=nullcontext)
        return modal, valid, source

    def status(self, folder, modal):
        output = io.StringIO()
        with mock.patch.dict(sys.modules, {'modal': modal}), redirect_stdout(output), \
                mock.patch.object(sys, 'argv', ['run_m28_cache.py', '--status', str(folder)]):
            cli.main()
        return output.getvalue()

    def test_status_recovers_committed_terminal_summary_after_deserialization_error(self):
        for terminal in ('COMPLETE', 'FAIL'):
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory() as d:
                folder = Path(d)
                modal, summary, _ = self.fixture(folder, self.DeserializationError('TorchVersion'))
                summary['status'] = terminal
                self.assertEqual(json.loads(self.status(folder, modal)), summary)

    def test_status_rejects_stale_nonterminal_and_mismatched_summary(self):
        changes = [dict(run_id='different-run'), dict(status='RUNNING'),
                   dict(completed_utc='2026-10-20T01:30:00Z'),
                   dict(completed_utc='not-a-time'), dict(completed_utc='2026-10-20T03:00:00'),
                   dict(identity={}), dict(completed_utc=None)]
        for field in ('config_sha256', 'source_sha256', 'input_sha256'):
            changes.append({'identity_field': field})
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as d:
                folder = Path(d)
                _, summary, _ = self.fixture(folder, self.DeserializationError('TorchVersion'))
                invalid = copy.deepcopy(summary)
                if 'identity_field' in change:
                    invalid['identity'][change['identity_field']] = 'wrong'
                else:
                    invalid.update(change)
                modal, _, _ = self.fixture(folder, self.DeserializationError('TorchVersion'), invalid)
                with self.assertRaises(ValueError):
                    self.status(folder, modal)

    def test_resume_accepts_valid_terminal_json_after_deserialization_error(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            modal, _, source = self.fixture(folder, self.DeserializationError('TorchVersion'))
            app = SimpleNamespace(app_id='new-app', run=lambda **kwargs: nullcontext())
            worker = SimpleNamespace(spawn=lambda *args: SimpleNamespace(object_id='new-call'))
            worker_module = SimpleNamespace(build_app=lambda *args: (app, worker))
            with mock.patch.dict(sys.modules, {'modal': modal, 'qpaf.m28.worker': worker_module}), \
                    mock.patch.object(cli, 'source_provenance', return_value=source), \
                    mock.patch('builtins.print'):
                cli.launch(folder, resume=True)
            latest = cli.latest_execution(folder)[1]
            self.assertEqual(latest['function_call_id'], 'new-call')
            self.assertTrue(latest['resume'])

    def test_resume_refuses_stale_json_after_deserialization_error(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            _, summary, source = self.fixture(folder, self.DeserializationError('TorchVersion'))
            summary['completed_utc'] = '2026-10-20T01:30:00Z'
            modal, _, _ = self.fixture(folder, self.DeserializationError('TorchVersion'), summary)
            worker_module = SimpleNamespace(build_app=lambda *args: self.fail('Stale summary must not launch'))
            with mock.patch.dict(sys.modules, {'modal': modal, 'qpaf.m28.worker': worker_module}), \
                    mock.patch.object(cli, 'source_provenance', return_value=source), \
                    self.assertRaises(ValueError):
                cli.launch(folder, resume=True)

    def test_timeouts_remain_running_and_unrelated_errors_propagate(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            modal, _, source = self.fixture(folder, TimeoutError('pending'))
            self.assertEqual(self.status(folder, modal).strip(), 'RUNNING')
            worker_module = SimpleNamespace(build_app=lambda *args: self.fail('Running worker must not launch'))
            with mock.patch.dict(sys.modules, {'modal': modal, 'qpaf.m28.worker': worker_module}), \
                    mock.patch.object(cli, 'source_provenance', return_value=source), \
                    self.assertRaisesRegex(RuntimeError, 'still running'):
                cli.launch(folder, resume=True)
            modal, _, _ = self.fixture(folder, RuntimeError('unrelated transport failure'))
            with self.assertRaisesRegex(RuntimeError, 'unrelated transport failure'):
                self.status(folder, modal)


if __name__ == '__main__':
    unittest.main()
