"""The M5.3 supervisor runs seed 20260821 once, matched to seed 1, and QPAF only after an accepted seed-2 QARF."""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m53 import reload as reload_api  # noqa: E402
from qpaf.m53 import supervisor as api  # noqa: E402

TEMPLATE = ROOT/'evidence/revisions/m5.3-001/authorization.json'
QARF_RUN_ID = 'RUN-QPAF-M5_3-MTH-001-20261025T120000Z-A01'
QPAF_RUN_ID = 'RUN-QPAF-M5_3-MTH-002-20261025T130000Z-A01'
CONFIG_BYTES = b'{"fixture": "resolved config"}\n'
CONFIG_OBJECT_HASH = 'objhash-fixture'
DATA_MANIFEST = b'{"test": {"queries": 1, "state": "not_opened"}, "train": {"queries": 2}, "validation": {"queries": 1}}'
SEED1_INPUTS = {'config': 'seed1-config', 'scores': 's0', 'queries': 'q0', 'qrels': 'r0', 'splits': {'train_ids.txt': 't0'}}
MATCHED = {'methods': {'QARF': {'gate_granularity': 'query'}, 'QPAF': {'gate_granularity': 'page'}}}

VERIFY = '''
import json, os, sys
from pathlib import Path
Path('results').mkdir(exist_ok=True)
Path('results/verify_args.json').write_text(json.dumps(sys.argv[1:]))
sys.exit(int(os.environ.get('STUB_VERIFY_EXIT', '0')))
'''
RUNNER = '''
import argparse, json, subprocess, sys
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--method', required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--mode', default='ok')
args = parser.parse_args()
stage = args.output/args.method
attempt = stage/'20261025T120001-abcd1234'
attempt.mkdir(parents=True)
head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
(attempt/'status.json').write_text(json.dumps({'status': 'completed'}))
(attempt/'resolved_config.json').write_bytes(%(config)r)
inputs = {**%(inputs)r, 'config': %(config_sha)r}
if args.mode == 'otherinputs':
    inputs['scores'] = 'a different score cache'
(attempt/'provenance.json').write_text(json.dumps({'config_sha256': 'objhash-fixture', 'source': {'git_commit': head},
                                                   'inputs': inputs}))
granularity = {'QARF': 'query', 'QPAF': 'page'}[args.method]
(attempt/'summary.json').write_text(json.dumps({'reload_parity': {'passed': True}, 'test_split': 'not_opened',
                                                'method': args.method, 'granularity': granularity, 'seed': 20260821}))
manifest = %(manifest)r
if args.mode == 'otherrows':
    manifest = manifest.replace(b'"queries": 2', b'"queries": 3')
(attempt/'data_manifest.json').write_bytes(manifest)
(attempt/'receipt.json').write_text('{}')
(attempt/'hashes.csv').write_text('path,sha256\\n')
(stage/'complete.json').write_text(json.dumps({'attempt': attempt.name}))
'''
RELOAD = '''
import json, os, sys
if os.environ.get('STUB_RELOAD') == 'fail':
    print('reloaded scores differ by 0.5 > 1e-07', file=sys.stderr)
    sys.exit(1)
print(json.dumps({'status': 'PASS', 'worker_pid': os.getpid(), 'argv': sys.argv[1:]}))
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.run(['git', '-c', 'user.name=tester', '-c', 'user.email=tester@example.test',
                           '-c', 'commit.gpgsign=false', *args],
                          cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return sha(path.read_bytes())


def approved(auth, run_id):
    auth = copy.deepcopy(auth)
    auth.update(status='APPROVED', run_id=run_id, actor='tester')
    auth['approval'].update(approval_text='Approved for this test fixture only', approved_utc='2026-10-25T12:00:00Z')
    return auth


class SeedContractTests(unittest.TestCase):
    """Read-only checks against the real draft and the real pinned M5.1/M5.2/M4.3/M3.2 files."""

    def setUp(self):
        self.auth = json.loads(TEMPLATE.read_text(encoding='utf-8'))

    def test_the_draft_is_seed_one_with_only_the_seed_changed(self):
        attempt = api.check_seed_contract(ROOT, self.auth)
        self.assertEqual(attempt, ROOT/self.auth['seed_contract']['seed_reference']['attempt_path'])
        seed1 = api._read(ROOT/self.auth['seed_contract']['seed_reference']['authorization_path'])
        # The sealed payload copy is local; Git contains the same pinned config.
        frozen = (ROOT/'configs/m2.7/shared_base.toml').read_bytes()
        self.assertEqual(sha(frozen), seed1['config']['file_sha256'])
        self.assertEqual((ROOT/self.auth['config']['path']).read_bytes(),
                         frozen.replace(b'seed = 20260820', b'seed = 20260821'))

    def test_any_drift_from_the_seed_contract_is_refused(self):
        cases = {'third seed': lambda a: a['method'].update(seed=20260822),
                 'contract seed': lambda a: a['seed_contract'].update(seed=20260820),
                 'config pin': lambda a: a['config'].update(file_sha256='0'*64),
                 'frozen config path': lambda a: a['config'].update(path='configs/m2.7/shared_base.toml'),
                 'receipt pin': lambda a: a['seed_contract']['cache_receipt'].update(sha256='1'*64),
                 'preregistration pin': lambda a: a['seed_contract']['preregistration'].update(sha256='2'*64),
                 'granularity': lambda a: a['method'].update(gate_granularity='page'),
                 'method': lambda a: a['method'].update(name='QPAF'),
                 'extra argument': lambda a: a['command']['arguments'].append('--extra'),
                 'other output root': lambda a: a['command']['arguments'].__setitem__(-1, 'results/m5.4/<run_id>'),
                 'sealed inputs': lambda a: a['sealed_inputs'].update(manifest_sha256='3'*64),
                 'runtime': lambda a: a['runtime'].update(torch='2.12.0+cpu'),
                 'hardware': lambda a: a.update(hardware='GPU'),
                 'wall limit': lambda a: a['limits'].update(wall_time_seconds=7200),
                 'seed-1 pin': lambda a: a['seed_contract']['seed_reference'].update(authorization_sha256='4'*64),
                 'seed-1 rows': lambda a: a['seed_contract']['seed_reference'].update(data_manifest_sha256='5'*64)}
        for label, mutate in cases.items():
            with self.subTest(label):
                auth = copy.deepcopy(self.auth)
                mutate(auth)
                with self.assertRaises(api.Refused):
                    api.check_seed_contract(ROOT, auth)

    def test_an_unapproved_authorization_grants_nothing(self):
        unapproved = {**self.auth, 'status': 'DRAFT_PENDING_APPROVAL', 'run_id': QARF_RUN_ID,
                      'approval': {**self.auth['approval'], 'approval_text': 'PENDING', 'approved_utc': 'PENDING'}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'authorization.json'
            pin = write_json(path, unapproved)
            with self.assertRaises(api.Refused):
                api.load_authorization(path, pin, QARF_RUN_ID, 'Tấn Phát')

    def test_the_pinned_supervisor_sources_are_the_files_in_this_checkout(self):
        for path, digest in self.auth['supervisor']['source_files_sha256'].items():
            with self.subTest(path):
                self.assertEqual(sha((ROOT/path).read_bytes()), digest)


class ReloadCompareTests(unittest.TestCase):
    def setUp(self):
        self.saved = [{'query_id': 'q1', 'page_ids': ['a', 'b'], 'scores': [0.5, 0.25],
                       'weights': [[0.2, 0.3, 0.5], [0.2, 0.3, 0.5]]}]

    def test_identical_outputs_pass_with_zero_difference(self):
        report = reload_api.compare(self.saved, copy.deepcopy(self.saved), 1e-7)
        self.assertEqual((report['queries'], report['candidates'], report['score_max_abs_difference']), (1, 2, 0.0))

    def test_order_finiteness_and_tolerance_are_enforced(self):
        cases = {'page order': lambda q: q.update(page_ids=['b', 'a']),
                 'query id': lambda q: q.update(query_id='q2'),
                 'non-finite score': lambda q: q['scores'].__setitem__(0, math.nan),
                 'non-finite weight': lambda q: q['weights'][1].__setitem__(0, math.inf),
                 'score drift': lambda q: q['scores'].__setitem__(1, 0.25+1e-6),
                 'weight drift': lambda q: q['weights'][0].__setitem__(2, 0.5+1e-6)}
        for label, mutate in cases.items():
            with self.subTest(label):
                fresh = copy.deepcopy(self.saved)
                mutate(fresh[0])
                with self.assertRaises(reload_api.ReloadError):
                    reload_api.compare(self.saved, fresh, 1e-7)
        with self.assertRaises(reload_api.ReloadError):
            reload_api.compare(self.saved, [], 1e-7)


class SupervisorTests(unittest.TestCase):
    """End to end in a throwaway repository with stub seal, runner and reload scripts."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, 'init', '-q')
        (self.root/'.gitignore').write_text('/results/\n')
        (self.root/'scripts').mkdir()
        (self.root/'scripts/seal_m31_inputs.py').write_text(VERIFY)
        (self.root/'scripts/reload_m53_checkpoint.py').write_text(RELOAD)
        (self.root/'scripts/stub_runner.py').write_text(RUNNER % {
            'config': CONFIG_BYTES, 'inputs': SEED1_INPUTS, 'config_sha': 'seed2-config', 'manifest': DATA_MANIFEST})
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'base')
        self.base = git(self.root, 'rev-parse', 'HEAD')
        write_json(self.root/'results/m3.1/SEAL/inputs/matched.json', MATCHED)
        self.reference = self.root/'results/m3.2/SEED1/QARF/attempt'
        self.reference.mkdir(parents=True)
        (self.reference/'data_manifest.json').write_bytes(DATA_MANIFEST)
        write_json(self.reference/'provenance.json', {'inputs': SEED1_INPUTS})
        patcher = mock.patch.object(api, 'check_seed_contract', side_effect=lambda root, auth: self.reference)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.evidence = self.root/'evidence/revisions'

    def qarf_auth(self, mode='ok'):
        auth = approved(json.loads(TEMPLATE.read_text(encoding='utf-8')), QARF_RUN_ID)
        auth['git'].update(code_base_commit=self.base, allowed_diff_from_base=['evidence/revisions/'],
                           allowed_untracked=['NOTES.md'])
        auth['sealed_inputs']['run_path'] = 'results/m3.1/SEAL'
        auth['config'].update(file_sha256='seed2-config', expected_resolved_config_json_sha256=sha(CONFIG_BYTES),
                              expected_provenance_config_object_hash=CONFIG_OBJECT_HASH)
        auth['seed_contract']['seed_reference'].update(data_manifest_sha256=sha(DATA_MANIFEST))
        auth['command'].update(interpreter=sys.executable, script='scripts/stub_runner.py',
                               arguments=['--method', 'QARF', '--output', 'results/m5.3/<run_id>', '--mode', mode])
        auth['limits']['wall_time_seconds'] = 30
        return auth

    def commit(self, path, auth):
        pin = write_json(path, auth)
        git(self.root, 'add', 'evidence')
        git(self.root, 'commit', '-q', '-m', path.parent.name)
        return pin

    def run_qarf(self, mode='ok'):
        path = self.evidence/'m5.3-001/authorization.json'
        pin = self.commit(path, self.qarf_auth(mode))
        return api.supervise(self.root, path, pin, QARF_RUN_ID, actor='tester'), pin

    def qpaf_auth(self, qarf_pin, event_mutate=None):
        qarf = self.qarf_auth()
        attempt = f'results/m5.3/{QARF_RUN_ID}/QARF/20261025T120001-abcd1234'
        auth = copy.deepcopy(qarf)
        auth.update(run_id=QPAF_RUN_ID, experiment_id='QPAF-M5_3-MTH-002')
        auth['method'].update(name='QPAF', gate_granularity='page')
        auth['command']['arguments'][1] = 'QPAF'
        event = {'registry_event_id': 'QPAF-REG-20261025-0099', 'event_type': 'ACCEPTANCE_RECORDED',
                 'registry_status': 'PASS', 'run_id': QARF_RUN_ID, 'authorization_manifest_sha256': qarf_pin,
                 'verification_ref': 'evidence/revisions/m5.3-r01/review.json',
                 'verification_sha256': write_json(self.evidence/'m5.3-r01/review.json', {'verdict': 'PASS'})}
        if event_mutate:
            event_mutate(event)
        (self.evidence/'m5.3-001/governance_events.jsonl').write_text(json.dumps(event)+'\n', encoding='utf-8')
        auth['comparator'] = {
            'run_id': QARF_RUN_ID, 'authorization_path': 'evidence/revisions/m5.3-001/authorization.json',
            'authorization_sha256': qarf_pin, 'attempt_path': attempt,
            'data_manifest_sha256': sha((self.root/attempt/'data_manifest.json').read_bytes()),
            'provenance_sha256': sha((self.root/attempt/'provenance.json').read_bytes()),
            'acceptance': {'events_path': 'evidence/revisions/m5.3-001/governance_events.jsonl',
                           'registry_event_id': event['registry_event_id']}}
        return auth

    def test_an_approved_qarf_run_succeeds_and_records_the_fresh_reload(self):
        (self.root/'NOTES.md').write_text('allowed untracked file\n')
        result, pin = self.run_qarf()
        self.assertEqual(result['status'], 'SUCCESS', result['reason'])
        namespace = self.root/'results/m5.3'/QARF_RUN_ID
        self.assertEqual(sorted(p.name for p in namespace.iterdir()),
                         ['QARF', '_ATTEMPTED.json', '_SUCCESS.json', 'supervisor.log'])
        attempted = json.loads((namespace/'_ATTEMPTED.json').read_text(encoding='utf-8'))
        self.assertEqual((attempted['seed'], attempted['comparator_run_id'], attempted['authorization_sha256']),
                         (20260821, None, pin))
        reload = json.loads((namespace/'_SUCCESS.json').read_text(encoding='utf-8'))['fresh_process_reload']
        self.assertEqual(reload['status'], 'PASS')
        self.assertEqual(reload['argv'], ['--attempt', f'results/m5.3/{QARF_RUN_ID}/QARF/20261025T120001-abcd1234',
                                          '--config', 'configs/m5.3/shared_base_seed_20260821.toml',
                                          '--method', 'QARF', '--seal', 'results/m3.1/SEAL'])

    def test_a_failed_fresh_reload_consumes_the_attempt(self):
        with mock.patch.dict('os.environ', {'STUB_RELOAD': 'fail'}):
            result, _ = self.run_qarf()
        self.assertEqual(result['status'], 'FAILED')
        self.assertIn('fresh-process reload failed', result['reason'])
        namespace = self.root/'results/m5.3'/QARF_RUN_ID
        self.assertTrue((namespace/'_FAILED.json').is_file())
        self.assertFalse((namespace/'_SUCCESS.json').exists())

    def test_rows_or_inputs_other_than_seed_one_fail_the_run(self):
        for mode, message in (('otherrows', 'seed-1 run (rows'), ('otherinputs', 'seed-1 inputs')):
            with self.subTest(mode):
                result, _ = self.run_qarf(mode)
                self.assertEqual(result['status'], 'FAILED')
                self.assertIn(message, result['reason'])
                git(self.root, 'reset', '-q', '--hard', self.base)
                for path in (self.root/'results/m5.3').iterdir():
                    subprocess.run(['git', 'clean', '-qfdx', str(path)], cwd=self.root)

    def test_a_second_invocation_is_refused(self):
        result, pin = self.run_qarf()
        self.assertEqual(result['status'], 'SUCCESS', result['reason'])
        with self.assertRaises(api.AlreadyAttempted):
            api.supervise(self.root, self.evidence/'m5.3-001/authorization.json', pin, QARF_RUN_ID, actor='tester')

    def test_qpaf_runs_only_after_an_accepted_seed_two_qarf_review(self):
        result, qarf_pin = self.run_qarf()
        self.assertEqual(result['status'], 'SUCCESS', result['reason'])
        path = self.evidence/'m5.3-002/authorization.json'
        cases = {'no PASS': lambda e: e.update(registry_status='STARTED'),
                 'not an acceptance': lambda e: e.update(event_type='VERIFICATION_RECORDED'),
                 'another run': lambda e: e.update(run_id='RUN-QPAF-M5_3-MTH-001-20261025T000000Z-A02'),
                 'tampered review': lambda e: e.update(verification_sha256='e'*64)}
        for label, mutate in cases.items():
            with self.subTest(label):
                pin = self.commit(path, self.qpaf_auth(qarf_pin, mutate))
                with self.assertRaises(api.Refused):
                    api.supervise(self.root, path, pin, QPAF_RUN_ID, actor='tester')
                self.assertFalse((self.root/'results/m5.3'/QPAF_RUN_ID).exists())
        pin = self.commit(path, self.qpaf_auth(qarf_pin))
        result = api.supervise(self.root, path, pin, QPAF_RUN_ID, actor='tester')
        self.assertEqual(result['status'], 'SUCCESS', result['reason'])

    def test_qpaf_that_differs_from_the_seed_two_qarf_in_more_than_the_method_is_refused(self):
        _, qarf_pin = self.run_qarf()
        path = self.evidence/'m5.3-002/authorization.json'
        cases = {'learning rate': lambda a: a['config']['frozen_values'].update(learning_rate=0.02),
                 'seed contract': lambda a: a['seed_contract']['cache_receipt'].update(sha256='9'*64),
                 'command': lambda a: a['command']['arguments'].append('--extra'),
                 'granularity': lambda a: a['method'].update(gate_granularity='query')}
        for label, mutate in cases.items():
            with self.subTest(label):
                auth = self.qpaf_auth(qarf_pin)
                mutate(auth)
                pin = self.commit(path, auth)
                with self.assertRaises(api.Refused):
                    api.supervise(self.root, path, pin, QPAF_RUN_ID, actor='tester')


if __name__ == '__main__':
    unittest.main()
