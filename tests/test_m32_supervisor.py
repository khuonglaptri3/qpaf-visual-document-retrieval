"""The M3.2 supervisor refuses unapproved runs and enforces one attempt, the wall limit and the markers."""
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
RUN_ID = 'RUN-QPAF-M3_2-MTH-001-20261022T090000Z-A01'
CONFIG_BYTES = b'{"fixture": "resolved config"}\n'
CONFIG_OBJECT_HASH = 'objhash-fixture'
TEMPLATE = ROOT/'evidence/revisions/m3.2-001/authorization.json'

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
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--mode', default='ok')
parser.add_argument('--pid-file', type=Path)
args = parser.parse_args()
mode = args.mode
stage = args.output/'QARF'
attempt = stage/'20261022T090001-abcd1234'
attempt.mkdir(parents=True)
if mode == 'sleep':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    args.pid_file.write_text(str(child.pid))
    time.sleep(120)
head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
(attempt/'status.json').write_text(json.dumps({'status': 'failed' if mode == 'fail' else 'completed'}))
if mode == 'fail':
    sys.exit(1)
config = b'{"fixture": "tampered"}\\n' if mode == 'badconfig' else b'{"fixture": "resolved config"}\\n'
(attempt/'resolved_config.json').write_bytes(config)
(attempt/'provenance.json').write_text(json.dumps({'config_sha256': 'objhash-fixture', 'source': {'git_commit': head}}))
(attempt/'summary.json').write_text(json.dumps({'reload_parity': {'passed': mode != 'noreload'}, 'test_split': 'not_opened'}))
(attempt/'data_manifest.json').write_text(json.dumps({'train': {}, 'validation': {},
    'test': {'queries': 1, 'state': 'opened' if mode == 'testopened' else 'not_opened'}}))
(attempt/'receipt.json').write_text('{}')
(attempt/'hashes.csv').write_text('path,sha256\\n')
if mode != 'nocomplete':
    (stage/'complete.json').write_text(json.dumps({'attempt': attempt.name}))
if mode == 'stray':
    (args.output/'stray.txt').write_text('outside the attempt')
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.run(['git', '-c', 'user.name=tester', '-c', 'user.email=tester@example.test',
                           '-c', 'commit.gpgsign=false', *args],
                          cwd=root, capture_output=True, text=True, check=True).stdout.strip()


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        try:
            self.api = importlib.import_module('qpaf.m32.supervisor')
        except ModuleNotFoundError:
            self.fail('M3.2 supervisor is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, 'init', '-q')
        (self.root/'.gitignore').write_text('/results/\n')
        (self.root/'scripts').mkdir()
        (self.root/'scripts/seal_m31_inputs.py').write_text(VERIFY)
        (self.root/'scripts/stub_runner.py').write_text(RUNNER)
        (self.root/'tracked.txt').write_text('base\n')
        (self.root/'TRACKED_NOTES.md').write_text('base\n')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'base')
        self.base = git(self.root, 'rev-parse', 'HEAD')
        self.auth_path = self.root/'evidence/revisions/m3.2-001/authorization.json'
        self.namespace = self.root/'results/m3.2'/RUN_ID
        self.authorize()

    def authorize(self, mutate=None, mode='ok', extra=(), seconds=30):
        auth = json.loads(TEMPLATE.read_text(encoding='utf-8'))
        auth['status'] = 'APPROVED'
        auth['run_id'] = RUN_ID
        auth['actor'] = 'tester'
        auth['approval'] = {'approver': 'Tấn Phát (Research Lead)', 'approved_utc': '2026-10-22T09:00:00Z',
                            'approval_text': 'Approved for this test fixture only'}
        auth['git']['code_base_commit'] = self.base
        auth['git']['allowed_diff_from_base'] = ['evidence/revisions/m3.2-001/']
        auth['git']['allowed_untracked'] = ['NOTES.md', 'TRACKED_NOTES.md']
        auth['sealed_inputs']['run_path'] = 'results/m3.1/SEAL'
        auth['command'].update(interpreter=sys.executable, script='scripts/stub_runner.py',
                               arguments=['--output', 'results/m3.2/<run_id>', '--mode', mode, *extra])
        auth['limits']['wall_time_seconds'] = seconds
        auth['config']['expected_resolved_config_json_sha256'] = sha(CONFIG_BYTES)
        auth['config']['expected_provenance_config_object_hash'] = CONFIG_OBJECT_HASH
        if mutate:
            mutate(auth)
        self.commit_authorization(auth)

    def commit_authorization(self, auth):
        self.auth_path.parent.mkdir(parents=True, exist_ok=True)
        self.auth_path.write_text(json.dumps(auth, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'authorization')
        self.pin = sha(self.auth_path.read_bytes())

    def supervise(self, pin=None, run_id=RUN_ID):
        return self.api.supervise(self.root, self.auth_path, pin or self.pin, run_id, actor='tester')

    def attempts(self):
        return sorted(p.name for p in (self.namespace/'QARF').glob('*') if p.is_dir())

    def test_an_approved_run_succeeds_and_leaves_the_markers(self):
        (self.root/'NOTES.md').write_text('allowed untracked file\n')
        result = self.supervise()
        self.assertEqual(result['status'], 'SUCCESS')
        attempted = json.loads((self.namespace/'_ATTEMPTED.json').read_text())
        self.assertEqual((attempted['run_id'], attempted['actor']), (RUN_ID, 'tester'))
        self.assertEqual(attempted['git_head'], git(self.root, 'rev-parse', 'HEAD'))
        self.assertEqual(attempted['authorization_sha256'], self.pin)
        self.assertTrue((self.namespace/'_SUCCESS.json').is_file())
        self.assertFalse((self.namespace/'_FAILED.json').exists())
        self.assertEqual(self.attempts(), ['20261022T090001-abcd1234'])
        verify_args = json.loads((self.root/'results/verify_args.json').read_text())
        self.assertEqual(verify_args, ['--verify', 'results/m3.1/SEAL', '--expected-manifest-sha256',
                                       '0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893'])

    def test_a_draft_authorization_is_refused(self):
        self.authorize(lambda a: a.update(status='DRAFT_NOT_APPROVED'))
        with self.assertRaises(self.api.Refused):
            self.supervise()
        self.assertFalse(self.namespace.exists())

    def test_a_pending_approval_text_is_refused(self):
        self.authorize(lambda a: a['approval'].update(approval_text='PENDING_EXACT_TEXT_FROM_APPROVER'))
        with self.assertRaises(self.api.Refused):
            self.supervise()
        self.assertFalse(self.namespace.exists())

    def test_an_authorization_that_differs_from_the_external_pin_is_refused(self):
        wrong_pin = self.pin
        self.authorize(lambda a: a['limits'].update(wall_time_seconds=99999))
        with self.assertRaises(self.api.Refused):
            self.supervise(pin=wrong_pin)
        self.assertFalse(self.namespace.exists())

    def test_a_run_id_other_than_the_approved_one_is_refused(self):
        with self.assertRaises(self.api.Refused):
            self.supervise(run_id='RUN-QPAF-M3_2-MTH-001-20261022T100000Z-A01')
        self.assertFalse(self.namespace.exists())

    def test_an_actor_other_than_the_authorized_one_is_refused(self):
        with self.assertRaises(self.api.Refused):
            self.api.supervise(self.root, self.auth_path, self.pin, RUN_ID, actor='someone else')
        self.assertFalse(self.namespace.exists())

    def test_an_authorization_that_names_no_confirmed_actor_is_refused(self):
        pending = 'PENDING_CONFIRM (to be named at approval)'
        self.authorize(lambda a: a.update(actor=pending))
        with self.assertRaises(self.api.Refused):
            self.api.supervise(self.root, self.auth_path, self.pin, RUN_ID, actor=pending)
        self.assertFalse(self.namespace.exists())

    def test_forbidden_arguments_are_refused(self):
        for flag in ('--resume', '--epochs'):
            with self.subTest(flag=flag):
                self.authorize(extra=(flag, '1'))
                with self.assertRaises(self.api.Refused):
                    self.supervise()
                self.assertFalse(self.namespace.exists())

    def test_a_modified_tracked_file_is_refused(self):
        (self.root/'tracked.txt').write_text('edited after review\n')
        with self.assertRaises(self.api.Refused):
            self.supervise()
        self.assertFalse(self.namespace.exists())

    def test_a_modified_tracked_file_cannot_hide_behind_the_untracked_allowlist(self):
        (self.root/'TRACKED_NOTES.md').write_text('edited although it is tracked\n')
        with self.assertRaises(self.api.Refused):
            self.supervise()
        self.assertFalse(self.namespace.exists())

    def test_a_head_with_rewritten_history_is_refused_even_when_the_tree_matches(self):
        git(self.root, 'checkout', '-q', '--orphan', 'rewritten')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'same tree, unrelated history')
        with self.assertRaises(self.api.Refused):
            self.supervise()
        self.assertFalse(self.namespace.exists())

    def test_an_unlisted_untracked_file_is_refused(self):
        (self.root/'stray.txt').write_text('not on the allowlist\n')
        with self.assertRaises(self.api.Refused):
            self.supervise()
        self.assertFalse(self.namespace.exists())

    def test_a_commit_that_changes_code_outside_the_allowed_paths_is_refused(self):
        (self.root/'tracked.txt').write_text('changed in a later commit\n')
        git(self.root, 'commit', '-q', '-am', 'code change after the base commit')
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
        # The seal check takes minutes on real data, so a taken namespace must be refused before it.
        self.assertFalse((self.root/'results/verify_args.json').exists())

    def test_a_failed_attempt_is_recorded_and_cannot_be_retried(self):
        self.authorize(mode='fail')
        result = self.supervise()
        self.assertEqual(result['status'], 'FAILED')
        self.assertTrue((self.namespace/'_FAILED.json').is_file())
        self.assertFalse((self.namespace/'_SUCCESS.json').exists())
        with self.assertRaises(self.api.AlreadyAttempted):
            self.supervise()
        self.assertEqual(self.attempts(), ['20261022T090001-abcd1234'])

    def test_exceeding_the_wall_limit_kills_the_whole_process_tree(self):
        pid_file = self.root/'child.pid'
        self.authorize(mode='sleep', extra=('--pid-file', str(pid_file)), seconds=2)
        started = time.monotonic()
        result = self.supervise()
        self.assertLess(time.monotonic()-started, 30)
        self.assertEqual((result['status'], result['reason']), ('FAILED', 'wall_time_exceeded'))
        self.assertTrue((self.namespace/'_FAILED.json').is_file())
        child = int(pid_file.read_text())
        deadline = time.monotonic()+10
        while psutil.pid_exists(child) and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertFalse(psutil.pid_exists(child), 'the runner\'s child process survived the kill')

    def test_a_run_that_breaks_a_post_run_check_is_marked_failed(self):
        for mode in ('badconfig', 'testopened', 'noreload', 'nocomplete', 'stray'):
            with self.subTest(mode=mode):
                self.authorize(mode=mode)
                if self.namespace.exists():
                    shutil.rmtree(self.namespace)
                result = self.supervise()
                self.assertEqual(result['status'], 'FAILED')
                self.assertTrue((self.namespace/'_FAILED.json').is_file())
                self.assertFalse((self.namespace/'_SUCCESS.json').exists())


class CommandLineTests(unittest.TestCase):
    def test_a_refused_run_exits_with_status_3_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            auth = json.loads(TEMPLATE.read_text(encoding='utf-8'))
            path = Path(folder)/'authorization.json'
            path.write_text(json.dumps(auth, ensure_ascii=False), encoding='utf-8')
            before = sorted(p.name for p in (ROOT/'results').iterdir())
            done = subprocess.run([sys.executable, str(ROOT/'scripts/run_m32_authorized.py'),
                                   '--authorization', str(path),
                                   '--expected-authorization-sha256', sha(path.read_bytes()),
                                   '--run-id', RUN_ID, '--actor', 'tester'],
                                  cwd=ROOT, capture_output=True, text=True)
            # 3 is distinct from 2, which Python and argparse use for a missing script or bad usage.
            self.assertEqual(done.returncode, 3, done.stdout+done.stderr)
            self.assertEqual(sorted(p.name for p in (ROOT/'results').iterdir()), before)


if __name__ == '__main__':
    unittest.main()
