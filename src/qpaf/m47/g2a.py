"""M4.7 G2A record: freeze QPAF-v1, its inputs, the test-172 contract and the remaining roster.

Read-only over existing evidence: it hashes pins, checks the M4 prerequisites,
replays the M4.3 freeze and the M4.6 direction in child processes, and never
trains, evaluates or deserializes test, ViMDoc or confirmation labels.
"""
import json
from pathlib import Path
import subprocess
import sys

from qpaf.m43.freeze import git, read, serialize, sha, write_json

from .roster import ROSTER, RULES, validate_roster

BUNDLE = 'results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/'
QARF_RUN = 'results/m3.2/RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01/'
QPAF_RUN = 'results/m3.4/RUN-QPAF-M3_4-MTH-001-20261022T112102Z-A01/'
PINS = {
    'g2_decision': ('evidence/revisions/m3.7-001/decision.json', None),
    'g2_confirmation': ('evidence/revisions/m3.7-001/owner_confirmation.json', None),
    'm41_manifest': ('evidence/revisions/m4.1-001/manifest.json', None),
    'm42_manifest': (BUNDLE+'manifest.json', '4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86'),
    'm42_shared_inputs': (BUNDLE+'shared_inputs.json', None),
    'm42_baseline_contracts': (BUNDLE+'baseline_contracts.json',
                               'fa91905406f41fcff3bfd3fcb9e86b9169a7526ea3eb17c8df74ae5f1a247dcf'),
    'm42_shared_base': (BUNDLE+'inputs/shared_base.toml',
                        '3e58a867d11cebf72970cf0c141a90822cd7cbbdad65fb1e081cb14fa4889b58'),
    'm42_test_ids': (BUNDLE+'inputs/splits/test_ids.txt',
                     'd34210f901759a4f174da0c6c2e9b810616dcb33a71a0bd128a25d5d8d12e6f6'),
    'm43_freeze': ('evidence/revisions/m4.3-001/method_freeze.json',
                   '4015c74b54f5ac3d2cbce54f8424c0e9329c009595e81ced5eab0039af7761cc'),
    'm43_confirmation': ('evidence/revisions/m4.3-001/owner_confirmation.json', None),
    'qpaf_checkpoint': (QPAF_RUN+'QPAF/20261022T112355-77b54aa0/checkpoints/best.pt',
                        'e4b00ab49e186fffe8b369e26491873304b61177c11fd2ce0f455158e30e5c8e'),
    'qarf_checkpoint': (QARF_RUN+'QARF/20261022T040759-ff3934df/checkpoints/best.pt', None),
    'm44_mth_manifest': ('results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01/manifest.json',
                         'aa2ab51814c883b5552b1b45136c1f25dd7d9921a074891f4ae0397f4b03e4a7'),
    'm44_orc_manifest': ('results/m4.4/RUN-QPAF-M4_4-ORC-001-20261023T172102Z-A01/manifest.json',
                         '6d796a27537c191d5b39436cf6fcaffa9e58b4c01628d9558da6ba261739b5a2'),
    'm44_mth_success': ('results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01/_SUCCESS.json', None),
    'm44_orc_success': ('results/m4.4/RUN-QPAF-M4_4-ORC-001-20261023T172102Z-A01/_SUCCESS.json', None),
    'm45_verification': ('evidence/revisions/m4.5-001/verification.json',
                         'a60349aed7a4da30a65a5700b096dcf922ed5d2fcd4bfe24bc00202d3eb0a41f'),
    'm45_acceptance': ('evidence/revisions/m4.5-001/owner_confirmation.json',
                       'eb2fe90c794baef1c23c01372125a2eb1ec336029a77d39709c3c24e31144ec0'),
    'm46_decision': ('evidence/revisions/m4.6-001/decision.json',
                     '66392aecd1871f8860a933bf14ef601edcbc27f90b5dc192c5402ff5f2987b6f'),
    'm46_final_confirmation': ('evidence/revisions/m4.6-001/final_confirmation.json',
                               '6ff607e98ee0a79c021b5c2c0ce69afa036b7b7ef2950736788545be7fd49bb3'),
    'evaluator': ('src/qpaf/m24/evaluator.py', 'bfd25f331c5c377c708fd1d05f3e3edb85467488301e9658ea9bb486ef476742'),
    'oracle': ('src/qpaf/m44/oracle.py', 'b9416d9479124af5c0609bd79eaf815c466d237ec9d93f3c0cd83a528311b701'),
    'frozen_protocol': ('evidence/M1_FINAL/02_protocol/frozen_protocol.md', None),
    'spec': ('docs/superpowers/specs/2026-10-24-m47-g2a-freeze-design.md', None),
}
REPLAYS = {'m43': ['scripts/freeze_m43_qpaf.py', '--verify', 'evidence/revisions/m4.3-001'],
           'm46': ['scripts/decide_m46_direction.py', '--verify', 'evidence/revisions/m4.6-001']}
STATUS = 'G2A_FROZEN_TECHNICAL_PASS_PENDING_OWNER_CONFIRMATION'
LIMITATIONS = [
    'The A001 training loss orders static fusion weights against nDCG@10 (train Spearman +0.537; minimum at '
    'BM25-only [1, 0, 0], the lowest-nDCG grid point).',
    'Amendment A004 (|ΔnDCG@10|-weighted pairwise loss) did not pass its preregistered train-only gate and is '
    'not adopted.',
    'Learned QARF is a weak comparator (validation nDCG@10 0.752147), so QPAF − QARF mainly shows page-level '
    'gating tolerating that loss better; frozen_protocol.md §5 item 4 (QPAF beats train_fitted_static) is the '
    'decisive test.',
]


class G2AError(ValueError):
    """A prerequisite, pin, replay, roster rule or stored record violates the G2A contract."""


def require(ok, message):
    if not ok:
        raise G2AError(message)


def is_ancestor(root, commit):
    return subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'], cwd=root).returncode == 0


def hash_pins(root, pins):
    found = {}
    for name, (relative, expected) in pins.items():
        path = Path(root)/relative
        require(path.is_file(), f'{name}: pinned file missing: {relative}')
        found[name] = sha(path)
        require(expected is None or found[name] == expected, f'{name}: pin differs for {relative}')
    return found


def prerequisites(root, pins=PINS):
    checks = [('g2_decision', lambda d: d.get('decision') == 'GO' and d.get('m4_branch') == 'continue_qpaf'),
              ('g2_confirmation', lambda d: d.get('decision') == 'CONFIRMED'),
              ('m43_confirmation', lambda d: d.get('decision') == 'CONFIRMED'),
              ('m45_acceptance', lambda d: d.get('decision') == 'ACCEPTED'),
              ('m46_final_confirmation', lambda d: d.get('decision') == 'CONFIRMED' and
               d.get('m4_branch_final') == 'continue_qpaf')]
    for name, ok in checks:
        relative = pins[name][0]
        require(ok(read(Path(root)/relative)), f'{name}: prerequisite not met in {relative}')
    return {'G2': 'GO_CONFIRMED', 'M4.1': 'SEALED', 'M4.2': 'BUNDLE_PINNED', 'M4.3': 'CONFIRMED',
            'M4.4': 'SUCCESS', 'M4.5': 'ACCEPTED', 'M4.6': 'CONTINUE_QPAF_CONFIRMED'}


def run_replay(root, argv):
    """Child process; exit 0 and a JSON stdout with status PASS are both required."""
    done = subprocess.run([sys.executable, '-X', 'utf8', *argv], cwd=root, capture_output=True, text=True,
                          encoding='utf8')
    require(done.returncode == 0, f'replay {argv[0]} exited {done.returncode}: {done.stderr.strip()[-300:]}')
    try:
        output = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise G2AError(f'replay {argv[0]} printed no JSON record') from exc
    require(isinstance(output, dict) and output.get('status') == 'PASS', f'replay {argv[0]} did not PASS')
    return output


def collect(root, pins=PINS, replay=run_replay):
    root = Path(root)
    hashes = hash_pins(root, pins)
    checked = prerequisites(root, pins)
    validate_roster(ROSTER)
    replays = {name: replay(root, argv) for name, argv in REPLAYS.items()}
    shared = read(root/pins['m42_shared_inputs'][0])
    record = {
        'schema_version': 1, 'task_id': 'M4.7', 'gate': 'G2A', 'experiment_id': 'QPAF-M4_7-GAT-001',
        'experiment_class': 'governance', 'evidence_class': 'governance_record', 'status': STATUS,
        'prerequisites': checked,
        'main_method': {'name': 'QPAF-v1', 'freeze_sha256': hashes['m43_freeze'],
                        'checkpoint_path': pins['qpaf_checkpoint'][0], 'checkpoint_sha256': hashes['qpaf_checkpoint'],
                        'selected_epoch': 19, 'config_sha256': hashes['m42_shared_base'],
                        'loss': 'pairwise_logistic / query_mean (A001)',
                        'selection_rule': 'max validation nDCG@10 over 20 epochs; ties keep the earlier epoch'},
        'matched_comparator': {'name': 'QARF-v1', 'checkpoint_path': pins['qarf_checkpoint'][0],
                               'checkpoint_sha256': hashes['qarf_checkpoint']},
        'seed_plan': {'completed': [20260820], 'pending': [20260821, 20260822],
                      'rule': 'same resolved config and method sources; only training.seed changes'},
        'baselines': {'roster_size': 7, 'contracts_sha256': hashes['m42_baseline_contracts'],
                      'co_strongest': ['train_fitted_static'], 'bundle_manifest_sha256': hashes['m42_manifest']},
        'evaluation': {'evaluator_sha256': hashes['evaluator'], 'oracle_sha256': hashes['oracle'],
                       'statistics': 'paired query bootstrap, 10,000 resamples, seed 20260820, percentile CI95, '
                                     'W/T/L, top-5% positive-gain share'},
        'held_out': {'dataset': 'Qiuchen-Wang/ViDoSeek', 'split': 'test', 'query_count': 172,
                     'ids_sha256': hashes['m42_test_ids'], 'sealed_qrels_sha256': shared['sealed_test_qrels_sha256'],
                     'labels_opened': False},
        'vimdoc': {'status': 'NOT_RUN_DEFERRED', 'query_count': 8904,
                   'reason': 'no verified ViMDoc score cache; the claim is bounded to ViDoSeek'},
        'claim_rules': {'ref': pins['frozen_protocol'][0], 'sha256': hashes['frozen_protocol'],
                        'section': '§5 items 1-9'},
        'limitations': LIMITATIONS, 'roster': [dict(entry) for entry in ROSTER], 'roster_rules': list(RULES),
        'claim_boundary': 'No new result. Validation numbers stay single-seed and optimistic. The record '
                          'authorizes no run; R3-R7 each need their own authorization.',
        'pins_sha256': hashes, 'authorizes_execution': False, 'training_executed': False,
        'test_labels_opened': False,
    }
    return record, {'schema_version': 1, 'task_id': 'M4.7', 'replays': replays}


def create(root, output_dir, pins=PINS, replay=run_replay):
    root, output_dir = Path(root).resolve(), Path(output_dir)
    require(not (output_dir/'g2a_freeze.json').exists(), f'output already exists: {output_dir}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'),
            'G2A creation requires a clean tracked tree')
    record, verification = collect(root, pins, replay)
    record['source_commit'] = git(root, 'rev-parse', 'HEAD')
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir/'g2a_freeze.json', record)
    verification['g2a_freeze_sha256'] = sha(output_dir/'g2a_freeze.json')
    write_json(output_dir/'verification.json', verification)
    return record


def verify(root, output_dir, pins=PINS, replay=run_replay):
    """Read-only: recollect and require the stored bytes, apart from a historical source commit."""
    root, output_dir = Path(root).resolve(), Path(output_dir)
    path = output_dir/'g2a_freeze.json'
    stored = path.read_bytes()
    record = json.loads(stored)
    require(read(output_dir/'verification.json').get('g2a_freeze_sha256') == sha(path),
            'verification.json does not pin g2a_freeze.json')
    recomputed, _ = collect(root, pins, replay)
    recomputed['source_commit'] = record.get('source_commit')
    require(serialize(recomputed) == stored, 'stored G2A record differs from the recomputation')
    require(is_ancestor(root, record['source_commit']), 'G2A source commit is not in this history')
    return {'status': 'PASS', 'g2a_freeze_sha256': sha(path), 'gate_status': record['status'],
            'main_method_checkpoint_sha256': record['main_method']['checkpoint_sha256']}
