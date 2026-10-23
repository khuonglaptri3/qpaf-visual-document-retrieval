"""Freeze the G2-accepted QPAF pilot as the main method; no training, no test labels."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]

PINS = {
    'g2_decision': ('evidence/revisions/m3.7-001/decision.json',
                    '888c51d5c1f5309d80ec9f1218d935d4659512a5867b42b031f275196edad621'),
    'g2_owner_confirmation': ('evidence/revisions/m3.7-001/owner_confirmation.json',
                              '20e7fdde52b9ea995e83333ffb7d53606353f3714b6f00d2386e4789e4aa298c'),
    'g2_inputs': ('evidence/revisions/m3.7-001/inputs.json',
                  '42074ad0a7766923269f736b879401b96d1ad9a24bcc3621c42727bf7cb0dde6'),
    'g2_criteria': ('evidence/revisions/m3.7-001/criteria.json',
                    '6dac26ab7b8b54f8c3d7f7cddce598982df789f4691b0a30ea27ad8822d1128a'),
    'qarf_authorization': ('evidence/revisions/m3.2-001/authorization.json',
                           'ae51a3a5601d43b0a758d5feb69b74b4ba24b0413965e5fee96ed7015ede9b4b'),
    'qpaf_authorization': ('evidence/revisions/m3.4-001/authorization.json',
                           '4be026b852574e7687fdc4b9337f716aa96a64ac39556ae288193bdba99e5365'),
    'm35_comparison': ('evidence/revisions/m3.5-001/comparison.json',
                       'ac29ce5b1d691d8ecc8f8b46e665c726494885de3b73f84a82e8adf8979d0c57'),
    'm36_integrity': ('evidence/revisions/m3.6-001/integrity_review.json',
                      '497b934ce6222e6e4e70363ef374e88236b7592bb549b0c81bbb89b45291e66f'),
}
# Files that define the gate, features, loss, training/selection and evaluation.
METHOD_SOURCES = ('src/qpaf/m11/artifacts.py', 'src/qpaf/m12/config.py', 'src/qpaf/m12/features.py',
                  'src/qpaf/m12/losses.py', 'src/qpaf/m12/model.py', 'src/qpaf/m24/checkpoint.py',
                  'src/qpaf/m24/config.py', 'src/qpaf/m24/dataset.py', 'src/qpaf/m24/evaluator.py',
                  'src/qpaf/m24/trainer.py')
REPLAY_KEYS = ('query_count', 'candidate_count', 'score_max_abs_difference', 'weight_max_abs_difference',
               'ranking_disagreements', 'metric_max_abs_difference', 'tolerance')
VALIDATION_QUERIES = 171


class FreezeError(ValueError):
    """The accepted G2 evidence or its replay does not support a frozen QPAF."""


def require(ok, message):
    if not ok:
        raise FreezeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def branch_disposition(decision):
    """Only the confirmed GO branch freezes QPAF; revise/pivot need their own path."""
    require(decision.get('decision') == 'GO' and decision.get('m4_branch') == 'continue_qpaf',
            f"G2 {decision.get('decision')}/{decision.get('m4_branch')} is not the frozen-QPAF branch")
    return {'g2_decision': 'GO', 'm4_branch': 'continue_qpaf', 'frozen_qpaf': 'FROZEN',
            'revise_once': 'NOT_TRIGGERED', 'negative_qpaf_result': 'NOT_TRIGGERED'}


def check_pins(root, pins):
    found = {}
    for name, (relative, expected) in pins.items():
        path = Path(root)/relative
        require(path.is_file(), f'{name}: pinned file missing: {relative}')
        found[name] = sha(path)
        require(found[name] == expected, f'{name}: pin differs for {relative}')
    return found


def check_sources(root, provenance, paths):
    """Method sources must still be the bytes the run recorded in its provenance."""
    recorded = {entry['path']: entry['sha256'] for entry in provenance['source']['files']}
    current = {}
    for relative in paths:
        require(relative in recorded, f'{relative}: absent from run provenance')
        current[relative] = sha(Path(root)/relative)
        require(current[relative] == recorded[relative], f'{relative}: source changed since the run')
    return current


def check_replay(worker, *, tolerance=1e-7):
    """Keep only deterministic replay fields; pids and timings stay in verification.json."""
    require(worker.get('status') == 'PASS_FRESH_PROCESS', 'replay did not pass in a fresh process')
    require(worker.get('query_count') == VALIDATION_QUERIES, 'replay did not cover the 171 validation queries')
    for key in ('score_max_abs_difference', 'weight_max_abs_difference'):
        value = worker.get(key)
        require(type(value) in (int, float) and math.isfinite(value) and value <= tolerance,
                f'{key} {value} exceeds {tolerance}')
    require(worker.get('ranking_disagreements') == 0, 'replayed ranking differs')
    metric = worker.get('metric_max_abs_difference')
    require(type(metric) in (int, float) and math.isfinite(metric) and metric <= 1e-12,
            f'recomputed validation metric differs by {metric}')
    return {key: worker[key] for key in REPLAY_KEYS}


def compare_freeze(stored, recomputed, *, is_ancestor):
    """A later checkout may verify the record if the creating commit is in its history."""
    strip = lambda record: json.dumps({k: v for k, v in record.items() if k != 'source_commit'},
                                      sort_keys=True, ensure_ascii=False)
    require(strip(stored) == strip(recomputed), 'stored freeze record differs from the replay')
    if stored['source_commit'] != recomputed['source_commit']:
        require(is_ancestor(stored['source_commit']), 'freeze source commit is not in this history')


def serialize(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n').encode('utf8')


def record_sha256(record):
    return hashlib.sha256(serialize(record)).hexdigest()


def write_json(path, data):
    with Path(path).open('xb') as stream:
        stream.write(serialize(data))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def _replay_g2(root, integrity):
    """The confirmed decision must be what decide_g2.py still derives from its pinned inputs."""
    command = [sys.executable, str(root/'scripts/decide_g2.py')]
    for flag, name in [('--inputs', 'g2_inputs'), ('--criteria', 'g2_criteria')]:
        command += [flag, str(root/PINS[name][0]), f'--expected-{flag[2:]}-sha256', PINS[name][1]]
    replayed = json.loads(integrity.prior.run_read_only(command))
    require(replayed == read(root/PINS['g2_decision'][0]), 'decide_g2.py no longer reproduces decision.json')
    return replayed


def _replay_seal(root, integrity, auth):
    sealed = auth['sealed_inputs']
    require(sha(root/sealed['seal_pin']['path']) == sealed['seal_pin']['sha256'], 'M3.1 seal pin file differs')
    require(read(root/sealed['seal_pin']['path'])['manifest_sha256'] == sealed['manifest_sha256'],
            'M3.1 seal manifest pin differs')
    replay = json.loads(integrity.prior.run_read_only(
        [sys.executable, str(root/'scripts/seal_m31_inputs.py'), '--verify', str(root/sealed['run_path']),
         '--expected-manifest-sha256', sealed['manifest_sha256']]))
    require(replay['status'] == 'PASS' and replay['parity_identical'], 'M3.1 seal replay failed')
    return replay


def _replay_run(root, integrity, method):
    """Reuse the reviewed M3.6 checks and fresh-process checkpoint replay unchanged."""
    auth, attempt, summary, _, _, _ = integrity.checked_run(method)
    worker = json.loads(integrity.prior.run_read_only(
        [sys.executable, str(root/'scripts/audit_m36_integrity.py'), '--replay-method', method]))
    integrity.check_fresh_process(worker, os.getpid())
    sources = check_sources(root, read(attempt/'provenance.json'), METHOD_SOURCES)
    run = {'run_id': auth['run_id'], 'attempt': attempt.relative_to(root).as_posix(),
           'authorization_sha256': PINS[method.lower()+'_authorization'][1],
           'gate_granularity': summary['granularity'], 'seed': summary['seed'],
           'resolved_config_sha256': sha(attempt/'resolved_config.json'),
           'checkpoint': {'path': (attempt/'checkpoints/best.pt').relative_to(root).as_posix(),
                          'sha256': summary['checkpoint_sha256']['best'],
                          'selected_epoch': summary['selected_epoch']}}
    return auth, summary, run, sources, worker


def collect(root):
    """Replay every input of the freeze; return (deterministic record, verification log)."""
    root = Path(root).resolve()
    require(root == ROOT.resolve(), 'M4.3 must replay from the executing checkout')
    pins = check_pins(root, PINS)
    sys.path.insert(0, str(root))
    from scripts import audit_m36_integrity as integrity
    from qpaf.m12.features import FEATURE_NAMES
    decision = _replay_g2(root, integrity)
    disposition = branch_disposition(decision)
    qpaf_auth, qpaf_summary, qpaf, qpaf_sources, qpaf_worker = _replay_run(root, integrity, 'QPAF')
    _, _, qarf, qarf_sources, qarf_worker = _replay_run(root, integrity, 'QARF')
    require(qpaf['resolved_config_sha256'] == qarf['resolved_config_sha256'] and qpaf_sources == qarf_sources,
            'QPAF and QARF no longer share one resolved config and method source')
    seal = _replay_seal(root, integrity, qpaf_auth)
    config = qpaf_auth['config']
    frozen = {**qpaf, 'name': 'QPAF', 'feature_names': list(FEATURE_NAMES),
              'parameter_count': qpaf_summary['parameter_count'],
              'config': {'path': config['path'], 'file_sha256': config['file_sha256'],
                         'resolved_config_sha256': qpaf['resolved_config_sha256'],
                         'provenance_config_object_hash': config['expected_provenance_config_object_hash'],
                         'frozen_values': config['frozen_values']},
              'selection_rule': 'maximum validation ndcg_at_10 over 20 epochs; ties keep the earlier epoch',
              'validation': {**qpaf_summary['validation'], 'optimistic_same_split_selection': True}}
    record = {
        'schema_version': 1, 'task_id': 'M4.3', 'owner': 'Tấn Phát', 'experiment_id': 'QPAF-M4_3-GAT-001',
        'experiment_class': 'governance', 'evidence_class': 'governance_record',
        'status': 'FROZEN_TECHNICAL_PASS_PENDING_OWNER_CONFIRMATION',
        'g2': {'decision': decision['decision'], 'm4_branch': decision['m4_branch'],
               'replayed_by': 'scripts/decide_g2.py', 'replay_equal': True,
               **{name+'_sha256': pins[name] for name in
                  ('g2_decision', 'g2_owner_confirmation', 'g2_inputs', 'g2_criteria')}},
        'branch_disposition': disposition, 'frozen_method': frozen, 'matched_comparator': {**qarf, 'name': 'QARF'},
        'sealed_inputs': {'run_path': qpaf_auth['sealed_inputs']['run_path'],
                          'manifest_sha256': qpaf_auth['sealed_inputs']['manifest_sha256'],
                          'seal_pin': qpaf_auth['sealed_inputs']['seal_pin'], 'replay_status': seal['status']},
        'source_sha256': qpaf_sources,
        'reviews': {'m35_comparison_sha256': pins['m35_comparison'], 'm36_integrity_sha256': pins['m36_integrity']},
        'replay': {'QPAF': check_replay(qpaf_worker), 'QARF': check_replay(qarf_worker)},
        'seed_plan': {'frozen_seed_set': [20260820, 20260821, 20260822], 'completed': [20260820],
                      'pending': {'20260821': 'M5.3', '20260822': 'M5.4'},
                      'rule': 'Same resolved config and method sources; only training.seed differs; '
                              'QARF and QPAF use identical seeds.'},
        'downstream': {'M4.4': 'The proposed-method row loads frozen_method.checkpoint by SHA-256.',
                       'M4.5': 'Independent fairness/uncertainty audit uses this record unchanged.',
                       'M4.6': 'The direction decision cites this freeze; it does not reopen G2.'},
        'claim_boundary': 'One development seed; the checkpoint was selected on the validation split used by '
                          'G2, so validation numbers are optimistic. No baseline comparison, no test or '
                          'confirmation access, no three-seed claim, no protocol change.',
        'test_labels_opened': False, 'training_executed': False, 'authorizes_execution': False,
        'source_commit': git(root, 'rev-parse', 'HEAD')}
    verification = {'schema_version': 1, 'task_id': 'M4.3', 'checked_utc': datetime.now(timezone.utc).isoformat(),
                    'runtime': integrity.runtime_versions(), 'g2_replay': 'EQUAL', 'm31_seal_replay': seal,
                    'fresh_process_replay': {'QPAF': qpaf_worker, 'QARF': qarf_worker},
                    'freeze_sha256': record_sha256(record), 'test_labels_deserialized': False}
    return record, verification


def create(root, output_dir):
    root, output_dir = Path(root).resolve(), Path(output_dir)
    require(not output_dir.exists(), f'output already exists: {output_dir}')
    require(not git(root, 'status', '--porcelain', '--untracked-files=no'),
            'freeze creation requires a clean tracked tree')
    record, verification = collect(root)
    output_dir.mkdir(parents=True, exist_ok=False)
    write_json(output_dir/'method_freeze.json', record)
    require(sha(output_dir/'method_freeze.json') == verification['freeze_sha256'], 'written freeze bytes differ')
    write_json(output_dir/'verification.json', verification)
    return record


def verify(root, output_dir):
    """Read-only: re-run every replay and require the stored record field for field."""
    root, output_dir = Path(root).resolve(), Path(output_dir)
    stored = read(output_dir/'method_freeze.json')
    require(read(output_dir/'verification.json')['freeze_sha256'] == sha(output_dir/'method_freeze.json'),
            'verification.json does not pin method_freeze.json')
    recomputed, _ = collect(root)
    ancestor = lambda commit: subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'],
                                             cwd=root).returncode == 0
    compare_freeze(stored, recomputed, is_ancestor=ancestor)
    return {'status': 'PASS', 'freeze_sha256': sha(output_dir/'method_freeze.json'),
            'm4_branch': stored['branch_disposition']['m4_branch'],
            'checkpoint_sha256': stored['frozen_method']['checkpoint']['sha256'],
            'replay': stored['replay'], 'test_labels_deserialized': False}
