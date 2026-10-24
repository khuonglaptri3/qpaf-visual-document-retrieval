"""M4.6 direction record: binds the revise_once decision to its evidence and the A004 gate.

The record follows the preregistered stop rule: the train-only gate decides
whether A004 may go on to approval and training, or the direction returns to
the Research Lead. It never authorizes a run.
"""
import json
from pathlib import Path
import subprocess

from qpaf.m43.freeze import git, read, serialize, sha, write_json

PINS = {
    'g2_decision': ('evidence/revisions/m3.7-001/decision.json', None),
    'g2_confirmation': ('evidence/revisions/m3.7-001/owner_confirmation.json', None),
    'm43_freeze': ('evidence/revisions/m4.3-001/method_freeze.json',
                   '4015c74b54f5ac3d2cbce54f8424c0e9329c009595e81ced5eab0039af7761cc'),
    'm43_confirmation': ('evidence/revisions/m4.3-001/owner_confirmation.json', None),
    'm44_mth_manifest': ('results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01/manifest.json',
                         'aa2ab51814c883b5552b1b45136c1f25dd7d9921a074891f4ae0397f4b03e4a7'),
    'm44_orc_manifest': ('results/m4.4/RUN-QPAF-M4_4-ORC-001-20261023T172102Z-A01/manifest.json',
                         '6d796a27537c191d5b39436cf6fcaffa9e58b4c01628d9558da6ba261739b5a2'),
    'm45_verification': ('evidence/revisions/m4.5-001/verification.json',
                         'a60349aed7a4da30a65a5700b096dcf922ed5d2fcd4bfe24bc00202d3eb0a41f'),
    'm45_acceptance': ('evidence/revisions/m4.5-001/owner_confirmation.json',
                       'eb2fe90c794baef1c23c01372125a2eb1ec336029a77d39709c3c24e31144ec0'),
    'probe': ('evidence/revisions/m4.6-001/loss_alignment_probe.json', None),
    'a004': ('evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A004.md', None),
    'spec': ('docs/superpowers/specs/2026-10-24-m46-revise-once-design.md', None),
    'owner_confirmation': ('evidence/revisions/m4.6-001/owner_confirmation.json', None),
}
STATUS = {'PASS': 'REVISE_ONCE_GATE_PASSED_AWAITING_A004_APPROVAL',
          'REVISION_GATE_FAILED': 'REVISION_GATE_FAILED_RETURN_TO_RESEARCH_LEAD'}
AMENDMENT_STATE = {'PASS': 'PROPOSED_PENDING_APPROVALS', 'REVISION_GATE_FAILED': 'NOT_ADOPTED_GATE_FAILED'}
NEXT_STEP = {
    'PASS': 'Research Lead approval of A004 in their own words, Thanh\'s independent A004 review, then a '
            'separate authorization request for QPAF-M4_6-MTH-001 (QARF-v2) and -002 (QPAF-v2).',
    'REVISION_GATE_FAILED': 'No v2 training. The Research Lead chooses continue_qpaf or negative_qpaf_result; '
                            'no second loss is tried.',
}
STOP_RULE = [
    'Apply the frozen G2 rule (evidence/revisions/m3.7-001/criteria.json, unchanged) to QPAF-v2 vs QARF-v2.',
    'G2 NO-GO–PIVOT or PARTIAL–INVESTIGATE leads to negative_qpaf_result; there is no second revision.',
    'G2 GO makes QPAF-v2 the main method for M4.7 whatever its validation delta against train_fitted_static; '
    'v1 and v2 are not picked between on validation.',
    'QPAF-v1, its M4.3 freeze and the M4.4/M4.5 results remain reported and are never deleted.',
]
TIMING = ('revise_once was chosen on 2026-10-24 after the M4.4 validation table, the M4.5 audit and a train-only '
          'loss probe were seen; it is post hoc. The A004 loss and the gate thresholds were fixed in the design '
          'before the gate ran, and were not changed after it.')


class DirectionError(ValueError):
    """A prerequisite, pin or stored record violates the M4.6 contract."""


def require(ok, message):
    if not ok:
        raise DirectionError(message)


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
    """Confirmed G2 GO, confirmed M4.3 freeze, accepted M4.5 and a revise_once owner confirmation."""
    load = lambda name: (read(Path(root)/pins[name][0]), pins[name][0])  # noqa: E731
    checks = [('g2_decision', lambda d: d.get('decision') == 'GO' and d.get('m4_branch') == 'continue_qpaf'),
              ('g2_confirmation', lambda d: d.get('decision') == 'CONFIRMED'),
              ('m43_confirmation', lambda d: d.get('decision') == 'CONFIRMED'),
              ('m45_acceptance', lambda d: d.get('decision') == 'ACCEPTED'),
              ('owner_confirmation', lambda d: d.get('decision') == 'CONFIRMED' and
               d.get('m4_branch') == 'revise_once')]
    for name, ok in checks:
        data, relative = load(name)
        require(ok(data), f'{name}: prerequisite not met in {relative}')
    return {'G2': 'GO_CONFIRMED', 'M4.3': 'CONFIRMED', 'M4.5': 'ACCEPTED', 'M4.6_owner': 'CONFIRMED'}


def direction_status(gate_status):
    require(gate_status in STATUS, f'unknown gate status {gate_status}')
    return STATUS[gate_status]


def collect(root, pins=PINS):
    root = Path(root)
    hashes = hash_pins(root, pins)
    checked = prerequisites(root, pins)
    m45 = read(root/pins['m45_verification'][0])
    probe = read(root/pins['probe'][0])
    gate = probe['gate_v2']['status']
    scores = m45['selection']['validation_ndcg_at_10']
    delta = m45['uncertainty']['qpaf_minus_baseline_ndcg_at_10']['train_fitted_static']
    return {
        'schema_version': 1, 'task_id': 'M4.6', 'experiment_id': 'QPAF-M4_6-GAT-001',
        'experiment_class': 'governance', 'evidence_class': 'governance_record',
        'question': 'Freeze the main-method direction: continue_qpaf / revise_once / negative_qpaf_result.',
        'owner': 'Tấn Phát (Research Lead)', 'm4_branch': 'revise_once', 'status': direction_status(gate),
        'owner_confirmation_ref': pins['owner_confirmation'][0], 'prerequisites': checked,
        'evidence': {
            'validation_ndcg_at_10': {k: scores[k] for k in ('train_fitted_static', 'qpaf', 'learned_qarf')},
            'qpaf_minus_train_fitted_static': {k: delta[k] for k in ('mean_delta', 'ci95', 'wtl')},
            'gate_v1': probe['gate_v1'], 'gate_v2': probe['gate_v2'],
        },
        'amendment': {'id': 'QPAF-M1.5-A004', 'path': pins['a004'][0], 'state': AMENDMENT_STATE[gate]},
        'timing_disclosure': TIMING, 'stop_rule': STOP_RULE, 'next_step': NEXT_STEP[gate],
        'claim_boundary': 'Validation and train only, seed 20260820; no test or confirmation label opened; '
                          'no performance claim.',
        'pins_sha256': hashes, 'test_labels_opened': False, 'training_executed': False,
        'authorizes_execution': False,
    }


def create(root, output_dir, pins=PINS):
    root, output_dir = Path(root).resolve(), Path(output_dir)
    path = output_dir/'decision.json'
    require(not path.exists(), f'output already exists: {path}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'),
            'direction record creation requires a clean tracked tree')
    record = {**collect(root, pins), 'source_commit': git(root, 'rev-parse', 'HEAD')}
    write_json(path, record)
    return record


def verify(root, output_dir, pins=PINS):
    """Read-only: recompute and require the stored bytes, apart from a historical source commit."""
    root, path = Path(root).resolve(), Path(output_dir)/'decision.json'
    stored = path.read_bytes()
    record = json.loads(stored)
    recomputed = {**collect(root, pins), 'source_commit': record.get('source_commit')}
    require(serialize(recomputed) == stored, 'stored decision record differs from the recomputation')
    require(is_ancestor(root, record['source_commit']), 'decision source commit is not in this history')
    return {'status': 'PASS', 'sha256': sha(path), 'm4_branch': record['m4_branch'],
            'direction_status': record['status']}
