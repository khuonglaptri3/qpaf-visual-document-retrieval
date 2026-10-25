"""The M5.4 supervisor is the tested M5.3 one with seed 20260822, and the seed-3 draft matches seed 1 but for the seed."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from qpaf.m54 import supervisor as api  # noqa: E402

TEMPLATE = ROOT/'evidence/revisions/m5.4-001/authorization.json'
# Every difference from the M5.3 sources; anything else would need its own tests (tests/test_m53_supervisor.py).
PORT = [('M5_3', 'M5_4'), ('results/m5.3', 'results/m5.4'), ('m5.3-00', 'm5.4-00'),
        ('qpaf.m53.supervisor', 'qpaf.m54.supervisor'), ('20260821', '20260822'), ('M5.3', 'M5.4'),
        ('seed-2', 'seed-3'), ('Seed-2', 'Seed-3')]


def port(text):
    for old, new in PORT:
        text = text.replace(old, new)
    return text


def sha(data):
    return hashlib.sha256(data).hexdigest()


class PortTests(unittest.TestCase):
    def test_the_m54_sources_differ_from_m53_only_in_seed_task_and_paths(self):
        for m53, m54 in (('src/qpaf/m53/supervisor.py', 'src/qpaf/m54/supervisor.py'),
                         ('scripts/run_m53_authorized.py', 'scripts/run_m54_authorized.py')):
            with self.subTest(m54):
                self.assertEqual((ROOT/m54).read_text(encoding='utf-8'), port((ROOT/m53).read_text(encoding='utf-8')))
        self.assertEqual((api.SEED, api.TASK, api.OUTPUT_ROOT, api.RELOAD_SCRIPT),
                         (20260822, 'M5.4', 'results/m5.4', 'scripts/reload_m53_checkpoint.py'))
        self.assertTrue(api.RUN_ID.fullmatch('RUN-QPAF-M5_4-MTH-001-20261025T150000Z-A01'))
        self.assertFalse(api.RUN_ID.fullmatch('RUN-QPAF-M5_3-MTH-001-20261025T135954Z-A01'))


class SeedContractTests(unittest.TestCase):
    """Read-only checks against the real draft and the real pinned M5.1/M5.2/M4.3/M3.2 files."""

    def setUp(self):
        self.auth = json.loads(TEMPLATE.read_text(encoding='utf-8'))

    def test_the_draft_is_seed_one_with_only_the_seed_changed(self):
        attempt = api.check_seed_contract(ROOT, self.auth)
        self.assertEqual(attempt, ROOT/self.auth['seed_contract']['seed_reference']['attempt_path'])
        seed1 = api._read(ROOT/self.auth['seed_contract']['seed_reference']['authorization_path'])
        self.assertEqual((ROOT/self.auth['config']['path']).read_bytes(),
                         (ROOT/seed1['config']['path']).read_bytes().replace(b'seed = 20260820', b'seed = 20260822'))

    def test_any_drift_from_the_seed_contract_is_refused(self):
        cases = {'second seed': lambda a: a['method'].update(seed=20260821),
                 'contract seed': lambda a: a['seed_contract'].update(seed=20260821),
                 'seed-2 config': lambda a: a['config'].update(path='configs/m5.3/shared_base_seed_20260821.toml'),
                 'config pin': lambda a: a['config'].update(file_sha256='0'*64),
                 'receipt pin': lambda a: a['seed_contract']['cache_receipt'].update(sha256='1'*64),
                 'method': lambda a: a['method'].update(name='QPAF'),
                 'other output root': lambda a: a['command']['arguments'].__setitem__(-1, 'results/m5.3/<run_id>'),
                 'wall limit': lambda a: a['limits'].update(wall_time_seconds=7200)}
        for label, mutate in cases.items():
            with self.subTest(label):
                auth = copy.deepcopy(self.auth)
                mutate(auth)
                with self.assertRaises(api.Refused):
                    api.check_seed_contract(ROOT, auth)

    def test_an_unapproved_authorization_grants_nothing(self):
        run_id = 'RUN-QPAF-M5_4-MTH-001-20261025T150000Z-A01'
        unapproved = {**self.auth, 'status': 'DRAFT_PENDING_APPROVAL', 'run_id': run_id,
                      'approval': {**self.auth['approval'], 'approval_text': 'PENDING', 'approved_utc': 'PENDING'}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'authorization.json'
            path.write_text(json.dumps(unapproved, ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(api.Refused):
                api.load_authorization(path, sha(path.read_bytes()), run_id, 'Tấn Phát')

    def test_the_pinned_supervisor_sources_are_the_files_in_this_checkout(self):
        for path, digest in self.auth['supervisor']['source_files_sha256'].items():
            with self.subTest(path):
                self.assertEqual(sha((ROOT/path).read_bytes()), digest)


if __name__ == '__main__':
    unittest.main()
