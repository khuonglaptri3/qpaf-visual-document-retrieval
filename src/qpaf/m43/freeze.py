"""Freeze the G2-accepted QPAF pilot as the main method; no training, no test labels."""
import hashlib
import json
import math
from pathlib import Path

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
