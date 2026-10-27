"""The M3.4 supervisor runs QPAF only against an accepted, matched QARF run, once, with the M3.2 markers."""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import psutil

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = 'RUN-QPAF-M3_4-MTH-001-20261022T120000Z-A01'
QARF_RUN_ID = 'RUN-QPAF-M3_2-MTH-001-20261022T090000Z-A01'
QARF_ATTEMPT = f'results/m3.2/{QARF_RUN_ID}/QARF/20261022T090001-abcd1234'
CONFIG_BYTES = b'{"fixture": "resolved config"}\n'
CONFIG_OBJECT_HASH = 'objhash-fixture'
DATA_MANIFEST = b'{"test": {"queries": 1, "state": "not_opened"}, "train": {"queries": 2}, "validation": {"queries": 1}}'
INPUTS = {'config': 'c0', 'scores': 's0', 'queries': 'q0', 'qrels': 'r0', 'splits': {'train_ids.txt': 't0'}}
TEMPLATE = ROOT/'evidence/revisions/m3.4-001/authorization.json'
MATCHED = {'methods': {'QARF': {'gate_granularity': 'query'}, 'QPAF': {'gate_granularity': 'page'}}}

# Stand-ins for scripts/seal_m31_inputs.py and scripts/run_m24_pipeline.py: they leave the same
# files the real ones leave, so the supervisor's contract is exercised without any training.
VERIFY = '''
import json, os, sys
from pathlib import Path
Path('results').mkdir(exist_ok=True)
Path('results/verify_args.json').write_text(json.dumps(sys.argv[1:]))
sys.exit(int(os.environ.get('STUB_VERIFY_EXIT', '0')))
'''
RUNNER = '''
import argparse, json, subprocess, sys, time
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--method', required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--mode', default='ok')
parser.add_argument('--pid-file', type=Path)
args = parser.parse_args()
mode = args.mode
stage = args.output/args.method
attempt = stage/'20261022T120001-abcd1234'
attempt.mkdir(parents=True)
if mode == 'sleep':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    args.pid_file.write_text(str(child.pid))
    time.sleep(120)
head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
(attempt/'status.json').write_text(json.dumps({'status': 'failed' if mode == 'fail' else 'completed'}))
if mode == 'fail':
    sys.exit(1)
(attempt/'resolved_config.json').write_bytes(b'{"fixture": "resolved config"}\\n')
inputs = %(inputs)r
if mode == 'otherinputs':
    inputs = {**inputs, 'scores': 'a different score cache'}
(attempt/'provenance.json').write_text(json.dumps({'config_sha256': 'objhash-fixture', 'source': {'git_commit': head},
                                                   'inputs': inputs}))
granularity = 'query' if mode == 'badsummary' else 'page'
(attempt/'summary.json').write_text(json.dumps({'reload_parity': {'passed': True}, 'test_split': 'not_opened',
                                                'method': args.method, 'granularity': granularity, 'seed': 20260820}))
manifest = %(manifest)r
if mode == 'otherrows':
    manifest = manifest.replace(b'"queries": 2', b'"queries": 3')
if mode == 'testopened':
    manifest = manifest.replace(b'not_opened', b'opened')
(attempt/'data_manifest.json').write_bytes(manifest)
(attempt/'receipt.json').write_text('{}')
(attempt/'hashes.csv').write_text('path,sha256\\n')
if mode != 'nocomplete':
    (stage/'complete.json').write_text(json.dumps({'attempt': attempt.name}))
''' % {'inputs': INPUTS, 'manifest': DATA_MANIFEST}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    # Temporary repositories must have no detached writer when cleanup starts.
    return subprocess.run(['git', '-c', 'user.name=tester', '-c', 'user.email=tester@example.test',
                           '-c', 'commit.gpgsign=false', '-c', 'maintenance.autoDetach=false',
                           '-c', 'gc.autoDetach=false', *args],
                          cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return sha(path.read_bytes())


def as_qarf(auth):
    """The fixture comparator: the QPAF authorization with the method and output root swapped back."""
    qarf = copy.deepcopy(auth)
    qarf.update(task_id='M3.2', run_id=QARF_RUN_ID)
    qarf['method'].update(name='QARF', gate_granularity='query')
    arguments = qarf['command']['arguments']
    arguments[arguments.index('--method')+1] = 'QARF'
    arguments[arguments.index('--output')+1] = 'results/m3.2/<run_id>'
    del qarf['comparator']
    return qarf


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('qpaf.m34.supervisor')
        except ModuleNotFoundError:
            self.fail('M3.4 supervisor is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, 'init', '-q')
        (self.root/'.gitignore').write_text('/results/\n')
        (self.root/'scripts').mkdir()
        (self.root/'scripts/seal_m31_inputs.py').write_text(VERIFY)
        (self.root/'scripts/stub_runner.py').write_text(RUNNER)
        (self.root/'tracked.txt').write_text('base\n')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'base')
        self.base = git(self.root, 'rev-parse', 'HEAD')
        write_json(self.root/'results/m3.1/SEAL/inputs/matched.json', MATCHED)
        attempt = self.root/QARF_ATTEMPT
        attempt.mkdir(parents=True)
        (attempt/'data_manifest.json').write_bytes(DATA_MANIFEST)
        write_json(attempt/'provenance.json', {'inputs': INPUTS})
        self.auth_path = self.root/'evidence/revisions/m3.4-001/authorization.json'
        self.namespace = self.root/'results/m3.4'/RUN_ID
        self.authorize()

    def authorize(self, mutate=None, mode='ok', extra=(), seconds=30, qarf_mutate=None, event_mutate=None):
        auth = json.loads(TEMPLATE.read_text(encoding='utf-8'))
        auth['status'] = 'APPROVED'
        auth['run_id'] = RUN_ID
        auth['actor'] = 'tester'
        auth['approval'] = {'approver': 'Tấn Phát (Research Lead)', 'approved_utc': '2026-10-22T12:00:00Z',
                            'approval_text': 'Approved for this test fixture only'}
        auth['git']['code_base_commit'] = self.base
        auth['git']['allowed_diff_from_base'] = ['evidence/revisions/']
        auth['git']['allowed_untracked'] = ['NOTES.md']
        auth['sealed_inputs']['run_path'] = 'results/m3.1/SEAL'
        auth['command'].update(interpreter=sys.executable, script='scripts/stub_runner.py',
                               arguments=['--method', 'QPAF', '--output', 'results/m3.4/<run_id>', '--mode', mode,
                                          *extra])
        auth['limits']['wall_time_seconds'] = seconds
        auth['config']['expected_resolved_config_json_sha256'] = sha(CONFIG_BYTES)
        auth['config']['expected_provenance_config_object_hash'] = CONFIG_OBJECT_HASH
        qarf = as_qarf(auth)
        if qarf_mutate:
            qarf_mutate(qarf)
        evidence = self.root/'evidence/revisions'
        comparator = auth['comparator']
        comparator.update(run_id=QARF_RUN_ID, attempt_path=QARF_ATTEMPT,
                          authorization_sha256=write_json(evidence/'m3.2-001/authorization.json', qarf),
                          data_manifest_sha256=sha(DATA_MANIFEST),
                          provenance_sha256=sha((self.root/QARF_ATTEMPT/'provenance.json').read_bytes()))
        event = {'registry_event_id': comparator['acceptance']['registry_event_id'], 'event_type': 'ACCEPTANCE_RECORDED',
                 'registry_status': 'PASS', 'run_id': QARF_RUN_ID,
                 'authorization_manifest_sha256': comparator['authorization_sha256'],
                 'verification_ref': 'evidence/revisions/m3.3-001/validation.json',
                 'verification_sha256': write_json(evidence/'m3.3-001/validation.json', {'technical_verdict': 'PASS'})}
        if event_mutate:
            event_mutate(event)
        (evidence/'m3.2-001/governance_events.jsonl').write_text(json.dumps({'registry_event_id': 'earlier'})+'\n'
                                                                  + json.dumps(event)+'\n', encoding='utf-8')
        if mutate:
            mutate(auth)
        self.pin = write_json(self.auth_path, auth)
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '--allow-empty', '-m', 'authorization')

    def supervise(self, pin=None, run_id=RUN_ID, actor='tester'):
        return self.api.supervise(self.root, self.auth_path, pin or self.pin, run_id, actor=actor)

    def assert_refused_before_the_seal_check(self, error=None):
        with self.assertRaises(error or self.api.Refused):
            self.supervise()
        self.assertFalse(self.namespace.exists())
        self.assertFalse((self.root/'results/verify_args.json').exists())

    def test_an_approved_matched_run_succeeds_and_leaves_the_markers(self):
        (self.root/'NOTES.md').write_text('allowed untracked file\n')
        result = self.supervise()
        self.assertEqual(result['status'], 'SUCCESS', result['reason'])
        attempted = json.loads((self.namespace/'_ATTEMPTED.json').read_text(encoding='utf-8'))
        self.assertEqual((attempted['run_id'], attempted['actor'], attempted['comparator_run_id']),
                         (RUN_ID, 'tester', QARF_RUN_ID))
        self.assertEqual(attempted['git_head'], git(self.root, 'rev-parse', 'HEAD'))
        self.assertEqual(attempted['authorization_sha256'], self.pin)
        self.assertTrue((self.namespace/'_SUCCESS.json').is_file())
        self.assertFalse((self.namespace/'_FAILED.json').exists())
        self.assertEqual(sorted(p.name for p in self.namespace.iterdir()),
                         ['QPAF', '_ATTEMPTED.json', '_SUCCESS.json', 'supervisor.log'])
        verify_args = json.loads((self.root/'results/verify_args.json').read_text())
        self.assertEqual(verify_args, ['--verify', 'results/m3.1/SEAL', '--expected-manifest-sha256',
                                       '0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893'])

    def test_an_unapproved_or_mismatched_authorization_is_refused(self):
        cases = {'draft': lambda a: a.update(status='DRAFT_NOT_APPROVED'),
                 'pending text': lambda a: a['approval'].update(approval_text='PENDING_EXACT_TEXT_FROM_APPROVER'),
                 'pending time': lambda a: a['approval'].update(approved_utc='PENDING'),
                 'pending actor': lambda a: a.update(actor='PENDING_CONFIRM')}
        for label, mutate in cases.items():
            with self.subTest(label):
                self.authorize(mutate)
                self.assert_refused_before_the_seal_check()

    def test_a_pin_run_id_or_actor_other_than_the_approved_one_is_refused(self):
        for kwargs in ({'pin': '0'*64}, {'run_id': 'RUN-QPAF-M3_4-MTH-001-20261022T130000Z-A01'},
                       {'run_id': QARF_RUN_ID}, {'actor': 'someone else'}):
            with self.subTest(**kwargs):
                with self.assertRaises(self.api.Refused):
                    self.supervise(**kwargs)
                self.assertFalse(self.namespace.exists())

    def test_a_qarf_run_without_an_accepted_review_is_refused(self):
        cases = {'no PASS': lambda e: e.update(registry_status='STARTED'),
                 'not an acceptance': lambda e: e.update(event_type='VERIFICATION_RECORDED'),
                 'another run': lambda e: e.update(run_id='RUN-QPAF-M3_2-MTH-001-20261022T100000Z-A02'),
                 'another authorization': lambda e: e.update(authorization_manifest_sha256='f'*64),
                 'missing event': lambda e: e.update(registry_event_id='QPAF-REG-20261022-9999'),
                 'tampered review': lambda e: e.update(verification_sha256='e'*64)}
        for label, mutate in cases.items():
            with self.subTest(label):
                self.authorize(event_mutate=mutate)
                self.assert_refused_before_the_seal_check()

    def test_an_authorization_that_differs_from_qarf_in_more_than_the_method_is_refused(self):
        cases = {'learning rate': lambda q: q['config']['frozen_values'].update(learning_rate=0.02),
                 'seed': lambda q: q['method'].update(seed=20260821),
                 'wall limit': lambda q: q['limits'].update(wall_time_seconds=7200),
                 'sealed manifest': lambda q: q['sealed_inputs'].update(manifest_sha256='a'*64),
                 'runtime': lambda q: q['runtime'].update(torch='2.12.0+cpu'),
                 'metric': lambda q: q['metric'].update(primary='mrr_at_10'),
                 'command': lambda q: q['command']['arguments'].append('--extra'),
                 'not approved': lambda q: q.update(status='DRAFT_NOT_APPROVED')}
        for label, mutate in cases.items():
            with self.subTest(label):
                self.authorize(qarf_mutate=mutate)
                self.assert_refused_before_the_seal_check()

    def test_the_method_must_be_the_matched_counterpart(self):
        cases = {'same as QARF': lambda a: (a['method'].update(name='QARF', gate_granularity='query'),
                                            a['command']['arguments'].__setitem__(1, 'QARF')),
                 'wrong granularity': lambda a: a['method'].update(gate_granularity='query')}
        for label, mutate in cases.items():
            with self.subTest(label):
                self.authorize(mutate)
                self.assert_refused_before_the_seal_check()

    def test_a_changed_qarf_file_after_its_pin_is_refused(self):
        for name in ('data_manifest.json', 'provenance.json'):
            with self.subTest(name):
                self.authorize()
                path = self.root/QARF_ATTEMPT/name
                original = path.read_bytes()
                path.write_bytes(original+b' ')
                self.assert_refused_before_the_seal_check()
                path.write_bytes(original)
        self.authorize()
        (self.root/'evidence/revisions/m3.2-001/authorization.json').write_text('{}', encoding='utf-8')
        git(self.root, 'commit', '-q', '-am', 'rewrite the comparator authorization')
        self.assert_refused_before_the_seal_check()

    def test_an_unreadable_comparator_is_refused_not_crashed(self):
        (self.root/QARF_ATTEMPT/'provenance.json').unlink()
        self.assert_refused_before_the_seal_check()

    def test_forbidden_arguments_and_dirty_trees_are_refused(self):
        self.authorize(extra=('--resume', '1'))
        with self.assertRaises(self.api.Refused):
            self.supervise()
        self.authorize()
        (self.root/'tracked.txt').write_text('edited after review\n')
        with self.assertRaises(self.api.Refused):
            self.supervise()
        self.assertFalse(self.namespace.exists())

    def test_a_failed_seal_verification_refuses_without_consuming_the_attempt(self):
        with mock.patch.dict(os.environ, {'STUB_VERIFY_EXIT': '3'}):
            with self.assertRaises(self.api.Refused):
                self.supervise()
        self.assertFalse(self.namespace.exists())

    def test_an_existing_namespace_is_refused_and_left_untouched(self):
        self.namespace.mkdir(parents=True)
        (self.namespace/'keep.txt').write_text('keep')
        with self.assertRaises(self.api.AlreadyAttempted):
            self.supervise()
        self.assertEqual([p.name for p in self.namespace.iterdir()], ['keep.txt'])
        self.assertFalse((self.root/'results/verify_args.json').exists())

    def test_a_namespace_outside_results_m3_4_is_refused(self):
        self.authorize(lambda a: a['output'].update(namespace_root='results/m3.2/<run_id>'))
        with self.assertRaises(self.api.Refused):
            self.supervise()
        self.assertFalse((self.root/'results/m3.2'/RUN_ID).exists())

    def test_a_failed_attempt_is_recorded_and_cannot_be_retried(self):
        self.authorize(mode='fail')
        self.assertEqual(self.supervise()['status'], 'FAILED')
        self.assertTrue((self.namespace/'_FAILED.json').is_file())
        self.assertFalse((self.namespace/'_SUCCESS.json').exists())
        with self.assertRaises(self.api.AlreadyAttempted):
            self.supervise()

    def test_exceeding_the_wall_limit_kills_the_whole_process_tree(self):
        pid_file = self.root/'child.pid'
        self.authorize(mode='sleep', extra=('--pid-file', str(pid_file)), seconds=2)
        started = time.monotonic()
        result = self.supervise()
        self.assertLess(time.monotonic()-started, 30)
        self.assertEqual((result['status'], result['reason']), ('FAILED', 'wall_time_exceeded'))
        child = int(pid_file.read_text())
        deadline = time.monotonic()+10
        while psutil.pid_exists(child) and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertFalse(psutil.pid_exists(child), 'the runner\'s child process survived the kill')

    def test_a_run_that_is_not_matched_to_qarf_or_breaks_a_check_is_marked_failed(self):
        expected = {'otherrows': 'data_manifest.json differs from the QARF run',
                    'otherinputs': 'consumed inputs other than those of the QARF run',
                    'badsummary': 'summary method, granularity or seed differs',
                    'testopened': 'test split was not reported as not_opened',
                    'nocomplete': 'missing outputs'}
        for mode, reason in expected.items():
            with self.subTest(mode=mode):
                self.authorize(mode=mode)
                if self.namespace.exists():
                    shutil.rmtree(self.namespace)
                result = self.supervise()
                self.assertEqual(result['status'], 'FAILED')
                self.assertIn(reason, result['reason'])
                self.assertTrue((self.namespace/'_FAILED.json').is_file())
                self.assertFalse((self.namespace/'_SUCCESS.json').exists())


class GitFixtureTests(unittest.TestCase):
    def test_fixture_commits_do_not_detach_maintenance_before_cleanup(self):
        # Reproduce a runner that enables maintenance even for a tiny repository.
        # A detached writer can otherwise recreate .git/objects during rmtree.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'repo'
            root.mkdir()
            git(root, 'init', '-q')
            settings = {'maintenance.auto': 'true', 'maintenance.autoDetach': 'true',
                        'gc.autoDetach': 'true', 'maintenance.gc.enabled': 'false',
                        'maintenance.loose-objects.enabled': 'true',
                        'maintenance.loose-objects.auto': '1'}
            for key, value in settings.items():
                git(root, 'config', key, value)
            (root/'tracked.txt').write_text('fixture data\n')
            git(root, 'add', 'tracked.txt')
            trace = Path(folder)/'trace.jsonl'
            try:
                with mock.patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
                    git(root, 'commit', '-q', '-m', 'fixture')
                events = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
                workers = [event['argv'] for event in events if event.get('event') == 'child_start'
                           and 'maintenance' in event.get('argv', [])]
                self.assertTrue(workers, 'the commit must exercise real automatic maintenance')
                self.assertFalse(any('--detach' in argv for argv in workers), workers)
                self.assertEqual(git(root, 'show', 'HEAD:tracked.txt'), 'fixture data')
                with self.assertRaises(subprocess.CalledProcessError):
                    git(root, 'show', 'HEAD:missing.txt')
            finally:
                # Drain the pre-fix detached worker so the regression can fail
                # cleanly instead of racing TemporaryDirectory's own cleanup.
                deadline = time.monotonic()+10
                while (root/'.git/maintenance.lock').exists() and time.monotonic() < deadline:
                    time.sleep(0.05)


class RepositoryTests(unittest.TestCase):
    def test_the_committed_authorization_is_matched_to_the_accepted_qarf_run(self):
        api = importlib.import_module('qpaf.m34.supervisor')
        auth = json.loads(TEMPLATE.read_text(encoding='utf-8'))
        # The large M3.1 seal stays local. Reconstruct only the comparator's
        # required inputs from committed, hash-bound bytes in an isolated root.
        # This exercises the real check on a clean checkout, without weakening
        # the supervisor or requiring private run payloads in CI.
        matched = (ROOT/'configs/m2.7/matched.json').read_bytes()
        self.assertEqual(sha(matched),
                         auth['sealed_inputs']['files_relative_to_run_path']['inputs/matched.json'])
        pinned = auth['comparator']
        with tempfile.TemporaryDirectory() as folder:
            review_root = Path(folder)
            for rel in (pinned['authorization_path'], pinned['acceptance']['events_path'],
                        pinned['acceptance']['review_ref'],
                        pinned['attempt_path']+'/data_manifest.json',
                        pinned['attempt_path']+'/provenance.json'):
                target = review_root/rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT/rel).read_bytes())
            target = review_root/auth['sealed_inputs']['run_path']/'inputs/matched.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(matched)
            self.assertEqual(api.check_comparator(review_root, auth), review_root/pinned['attempt_path'])

    def test_a_refused_run_exits_with_status_3_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            auth = json.loads(TEMPLATE.read_text(encoding='utf-8'))
            auth['status'] = 'DRAFT_NOT_APPROVED'
            path = Path(folder)/'authorization.json'
            path.write_text(json.dumps(auth, ensure_ascii=False), encoding='utf-8')
            before = sorted(p.name for p in (ROOT/'results').iterdir())
            done = subprocess.run([sys.executable, str(ROOT/'scripts/run_m34_authorized.py'),
                                   '--authorization', str(path),
                                   '--expected-authorization-sha256', sha(path.read_bytes()),
                                   '--run-id', RUN_ID, '--actor', 'tester'],
                                  cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(done.returncode, 3, done.stdout+done.stderr)
            self.assertEqual(sorted(p.name for p in (ROOT/'results').iterdir()), before)


if __name__ == '__main__':
    unittest.main()
