"""M5.10/G3A: bound the generalization claim to sealed, accepted evidence.

Reads governance records only. It never opens labels, evaluates a model, or
authorizes an external run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    'g3_decision': 'evidence/revisions/m5.9-001/decision.json',
    'g3_confirmation': 'evidence/revisions/m5.9-001/owner_confirmation.json',
    'external_disposition': 'evidence/revisions/m5.8-001/decision.json',
    'g2a_freeze': 'evidence/revisions/m4.7-001/g2a_freeze.json',
    'r8_summary': 'evidence/revisions/m5.7-001/summary.json',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def g3a_outcome(g3, confirmation, external, freeze, r8, *, g3_sha, freeze_sha, r8_sha):
    require(g3.get('task_id') == 'M5.9' and g3.get('gate') == 'G3_ROBUSTNESS'
            and g3.get('decision') == 'LIMITED-CLAIM', 'confirmed G3 decision differs')
    require(confirmation.get('task_id') == 'M5.9' and confirmation.get('decision') == 'CONFIRMED'
            and confirmation.get('confirmed_g3_decision') == 'LIMITED-CLAIM'
            and confirmation.get('decision_sha256') == g3_sha,
            'Research Lead confirmation does not bind this G3 decision')
    require(set(g3.get('reasons', [])) == {'BASELINE_NOT_BEATEN', 'LATENCY_GATE_NOT_ESTABLISHED'}
            and g3.get('external_generalization_claimed') is False,
            'G3 claim limits differ')
    require(external.get('task_id') == 'M5.8' and external.get('roster_id') == 'R9'
            and external.get('status') == 'NOT_RUN_DEFERRED'
            and external.get('external_result_claimed') is False
            and external.get('new_training_or_evaluation_executed') is False
            and external.get('authorization_granted_by_this_record') is False
            and external.get('g2a_sha256') == freeze_sha
            and external.get('r8_summary_sha256') == r8_sha,
            'M5.8 does not support a NOT RUN G3A record')
    roster = {row['id']: row for row in freeze.get('roster', [])}
    require(roster.get('R9', {}).get('task') == 'M5.8'
            and roster['R9'].get('tier') == 'deferred'
            and freeze.get('vimdoc', {}).get('status') == 'NOT_RUN_DEFERRED',
            'G2A external roster or ViMDoc status differs')
    require(r8.get('task_id') == 'M5.7' and r8.get('query_count') == 172
            and r8.get('quality_signals', {}).get('overall_quality_gate') is False,
            'R8 quality/coverage differs')
    return {
        'schema_version': 1,
        'task_id': 'M5.10',
        'gate': 'G3A_GENERALIZATION',
        'owner': 'Thanh',
        'decision': 'NOT_RUN',
        'detail': 'NOT_RUN_DEFERRED',
        'reason': 'No authorized, verified sealed external evaluation is recorded in the pinned evidence; M5.8/R9 and ViMDoc remain deferred.',
        'upstream_g3': {'decision': 'LIMITED-CLAIM', 'confirmed': True,
                        'reasons': ['BASELINE_NOT_BEATEN', 'LATENCY_GATE_NOT_ESTABLISHED']},
        'evidence_scope': {'dataset': 'ViDoSeek', 'split': 'TEST-172',
                           'query_count': 172, 'seeds': r8['seeds']},
        'permitted_claim': 'Frozen QPAF-v1 exceeds matched QARF-v1 on ViDoSeek TEST-172 across three preregistered seeds.',
        'required_limits': [
            'QPAF-v1 does not exceed the validation-selected train_fitted_static on TEST-172.',
            'The operational latency gate is not established under the 1,000 measured-query rule.',
            'No external-benchmark or ViMDoc generalization result is available.',
        ],
        'external_generalization_claimed': False,
        'external_result_status': 'NOT_RUN',
        'test_labels_read_by_this_record': False,
        'new_training_or_evaluation_executed': False,
        'authorizes_execution': False,
    }


def decide(root, inputs):
    require(inputs.get('task_id') == 'M5.10'
            and inputs.get('files') == {path: inputs['files'].get(path) for path in REQUIRED.values()}
            and len(inputs['files']) == len(REQUIRED), 'G3A input inventory differs')
    for path, expected in inputs['files'].items():
        require(len(expected) == 64 and sha(root/path) == expected, 'pin drift: ' + path)
    records = {key: read(root/path) for key, path in REQUIRED.items()}
    return g3a_outcome(records['g3_decision'], records['g3_confirmation'],
                       records['external_disposition'], records['g2a_freeze'], records['r8_summary'],
                       g3_sha=inputs['files'][REQUIRED['g3_decision']],
                       freeze_sha=inputs['files'][REQUIRED['g2a_freeze']],
                       r8_sha=inputs['files'][REQUIRED['r8_summary']])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    inputs = read(args.inputs)
    result = decide(ROOT, inputs)
    result['inputs_sha256'] = sha(args.inputs)
    payload = (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode('utf8')
    if args.verify:
        require(args.output is not None and args.output.read_bytes() == payload,
                'saved G3A decision differs from replay')
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(payload)
    else:
        print(payload.decode('utf8'), end='')
    if args.output:
        print(f"G3A {result['decision']}: {args.output}")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print(f'G3A refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
