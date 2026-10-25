"""Create or verify the M5.1 R1 plan without training or reading labels."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FREEZE = 'evidence/revisions/m4.7-001/g2a_freeze.json'
CONFIRMATION = 'evidence/revisions/m4.7-001/owner_confirmation.json'
FROZEN_SHA = '26d9bab6e7d47fe7dd1e89f6bec2c95265641df5cde8d9bd25c867b9d3a73217'
CONFIRMATION_SHA = '5f80b4312188721dc2c2033a85ce1a9631bffa32479c576e0500471e622b95e6'
POLICIES = {
    'active_primary_scope': 'evidence/revisions/m1.5-002/scoped_contract.md',
    'baseline': 'evidence/M1_FINAL/02_protocol/baseline_policy.md',
    'seed': 'evidence/M1_FINAL/02_protocol/seed_policy.md',
    'statistics': 'evidence/M1_FINAL/02_protocol/statistical_policy.md',
    'metric': 'evidence/M1_FINAL/02_protocol/metric_policy.md',
    'frozen_protocol': 'evidence/M1_FINAL/02_protocol/frozen_protocol.md',
}
TIERS = {'R1': 'core', 'R2': 'core', 'R3': 'core', 'R4': 'core',
         'R5': 'optional', 'R6': 'optional', 'R7': 'core', 'R8': 'core',
         'R9': 'deferred', 'R10': 'deferred'}
DATA = {'R1': ['none'], 'R2': ['no_labels'], 'R3': ['train', 'validation'],
        'R4': ['train', 'validation'], 'R5': ['validation'],
        'R6': ['validation'], 'R7': ['test'], 'R8': ['r7_outputs'],
        'R9': ['workbook'], 'R10': ['none']}
CORE = ['R1', 'R2', 'R3', 'R4', 'R7', 'R8']
OPTIONAL_DROP_ORDER = ['R6', 'R5']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def validate_freeze(freeze):
    seeds = freeze['seed_plan']
    require(seeds['completed'] == [20260820] and
            seeds['pending'] == [20260821, 20260822] and
            seeds['rule'] == 'same resolved config and method sources; only training.seed changes',
            'G2A seed plan differs')
    roster = freeze['roster']
    require([row['id'] for row in roster] == list(TIERS) and
            all(row['tier'] == TIERS[row['id']] and
                row['allowed_data'] == DATA[row['id']] for row in roster),
            'G2A roster tiers or allowed data differ')
    held = freeze['held_out']
    require(held['dataset'] == 'Qiuchen-Wang/ViDoSeek' and
            held['split'] == 'test' and held['query_count'] == 172 and
            held['labels_opened'] is False, 'G2A held-out boundary differs')
    require(freeze['main_method']['name'] == 'QPAF-v1' and
            freeze['main_method']['loss'] == 'pairwise_logistic / query_mean (A001)' and
            freeze['matched_comparator']['name'] == 'QARF-v1' and
            freeze['baselines']['roster_size'] == 7 and
            freeze['baselines']['co_strongest'] == ['train_fitted_static'],
            'G2A method or baseline differs')


def load_inputs(root):
    root = Path(root)
    require(sha256(root / FREEZE) == FROZEN_SHA, 'G2A freeze hash differs')
    require(sha256(root / CONFIRMATION) == CONFIRMATION_SHA,
            'G2A owner confirmation hash differs')
    freeze = read_json(root / FREEZE)
    confirmation = read_json(root / CONFIRMATION)
    validate_freeze(freeze)
    require(confirmation['decision'] == 'CONFIRMED' and
            confirmation['gate'] == 'G2A' and
            confirmation['freeze_sha256'] == FROZEN_SHA,
            'G2A confirmation is not valid')
    pins = {'g2a_freeze': FROZEN_SHA, 'g2a_confirmation': CONFIRMATION_SHA}
    pins.update({name: sha256(root / path) for name, path in POLICIES.items()})
    return freeze, pins


def make_record(freeze, pins, registered_at):
    validate_freeze(freeze)
    seed_matrix = [
        {'seed': 20260820, 'methods': ['QARF', 'QPAF'],
         'state': 'completed_pilot', 'task': 'M3.2/M3.4'},
        {'seed': 20260821, 'methods': ['QARF', 'QPAF'],
         'state': 'pending', 'task': 'M5.3/R3'},
        {'seed': 20260822, 'methods': ['QARF', 'QPAF'],
         'state': 'pending', 'task': 'M5.4/R4'},
    ]
    ablations = [
        {'order': 1, 'id': 'R5-01', 'task': 'M5.5', 'scope': 'validation',
         'factor': 'retriever_singletons',
         'contrast': 'BM25, BGE-M3 and ColQwen2.5 saved singleton rows on the fixed candidate pool; no refit'},
        {'order': 2, 'id': 'R5-02', 'task': 'M5.5', 'scope': 'validation',
         'factor': 'one_channel_removed_from_uniform_fusion',
         'contrast': 'Independently omit BM25, BGE-M3, then ColQwen2.5; each remaining pair has fixed 0.5/0.5 weights on the saved normalized scores and identical candidate rows'},
        {'order': 3, 'id': 'R5-03', 'task': 'M5.5', 'scope': 'validation',
         'factor': 'normalization',
         'contrast': 'Uniform CombSUM only: frozen min-max versus per-query raw-score z-score (population std, zero-variance channel -> 0); weights stay 1/3 each'},
        {'order': 4, 'id': 'R5-04', 'task': 'M5.5', 'scope': 'validation',
         'factor': 'efficiency',
         'contrast': 'Measure frozen QARF/QPAF fusion latency and memory separately from retriever extraction under metric_policy.md; no checkpoint change'},
        {'order': 5, 'id': 'R6-01', 'task': 'M5.6', 'scope': 'validation',
         'factor': 'remove_rank_feature_group',
         'contrast': 'Diagnostic QPAF training from full 13-feature contract, omit only rr_bm25/rr_dense/rr_visual'},
        {'order': 6, 'id': 'R6-02', 'task': 'M5.6', 'scope': 'validation',
         'factor': 'remove_gap_feature_group',
         'contrast': 'Diagnostic QPAF training from full contract, omit only gap_bm25/gap_dense/gap_visual'},
        {'order': 7, 'id': 'R6-03', 'task': 'M5.6', 'scope': 'validation',
         'factor': 'remove_disagreement_feature_group',
         'contrast': 'Diagnostic QPAF training from full contract, omit only the three disagreement features'},
        {'order': 8, 'id': 'R6-04', 'task': 'M5.6', 'scope': 'validation',
         'factor': 'remove_query_length',
         'contrast': 'Diagnostic QPAF training from full contract, omit only query_length'},
        {'order': 9, 'id': 'R6-05', 'task': 'M5.6', 'scope': 'validation',
         'factor': 'query_vs_page_conditioning',
         'contrast': 'Reuse matched QARF/QPAF per-seed development outputs; gate granularity is the sole factor; no new primary checkpoint'},
    ]
    record = {
        'schema_version': 1, 'task_id': 'M5.1', 'roster_id': 'R1',
        'owner': 'Thanh', 'experiment_id': 'QPAF-M5_1-GAT-001',
        'experiment_class': 'governance', 'evidence_class': 'governance_record',
        'status': 'PREREGISTERED_PENDING_OWNER_SIGNOFF',
        'registered_at_utc': registered_at, 'pins_sha256': pins,
        'core_roster': list(CORE), 'optional_roster': ['R5', 'R6'],
        'deferred_roster': ['R9', 'R10'],
        'seed_matrix': seed_matrix,
        'matched_run_rule': {
            'same_across_methods_and_seeds': [
                'candidate IDs and order', 'score cache and normalization',
                '13 features', 'loss and optimizer', 'epochs and batch',
                'hardware class and execution limits', 'evaluation implementation'],
            'only_seed_change': 'training.seed',
            'method_difference': 'gate_granularity: query for QARF, page for QPAF',
            'per_run_authorization_required': True,
            'qarf_review_before_matched_qpaf': True,
            'cache_parity_receipt_required': 'M5.2/R2',
            'fresh_process_reload_max_abs_difference': 1e-7,
            'finite_output_required': True,
            'retain_all_valid_seeds': True,
            'replacement_seed_without_amendment': False,
        },
        'ablations': ablations,
        'ablation_rule': {
            'diagnostic_only': True, 'validation_only': True,
            'r5_no_training': True, 'r6_diagnostic_training_seed': 20260820,
            'r6_same_training_budget_as_frozen_pilot': True,
            'one_factor_at_a_time_from_full_reference': True,
            'separate_authorization_before_new_run': True,
            'cannot_replace_frozen_method_config_or_checkpoints': True,
            'cannot_reselect_baseline_or_primary_method': True,
            'a004_adopted': False,
        },
        'drop_first': {
            'order': list(OPTIONAL_DROP_ORDER),
            'trigger': 'Before diagnostic results or TEST-172, if approved resources or schedule cannot cover both optional tasks while preserving all core items',
            'record_required': 'Document available budget/deadline, omitted task, reason and claim impact before omission',
            'core_droppable': False,
            'missing_operational_measurement_allows_operational_claim': False,
        },
        'test_plan': {
            'dataset': 'ViDoSeek', 'split': 'test',
            'query_count': freeze['held_out']['query_count'],
            'ids_sha256': freeze['held_out']['ids_sha256'],
            'sealed_qrels_sha256': freeze['held_out']['sealed_qrels_sha256'],
            'labels_opened': False, 'only_R7_may_open_labels': True,
            'run_count': 1, 'after_independent_reviews_of': ['R3', 'R4'],
            'baseline_count': 7, 'qarf_seeds': [20260820, 20260821, 20260822],
            'qpaf_seeds': [20260820, 20260821, 20260822],
            'oracle_context_only': ['W7', 'W66'],
            'post_test_selection_allowed': False,
        },
        'statistics': {
            'primary_unit': 'ViDoSeek page nDCG@10, per query',
            'per_query_seed_mean_before_bootstrap': True,
            'bootstrap_unit': 'paired query', 'resamples': 10000,
            'rng': 'numpy.default_rng', 'rng_seed': 20260820,
            'ci95': 'percentile 2.5/97.5', 'wtl_tolerance': 1e-12,
            'comparators': ['matched QARF', 'train_fitted_static'],
            'all_co_strongest_baselines_required': True,
            'secondary_cannot_reverse_primary': True,
        },
        'claim_boundary': {
            'main_method': 'M4.3-frozen QPAF-v1 with A001 loss',
            'a004': 'FAILED_GATE_NOT_ADOPTED; Thanh review remains separate',
            'oracle_not_deployable': True,
            'vimdoc': 'NOT_RUN_DEFERRED',
            'new_training_or_test_execution': False,
            'execution_authorization': 'NOT_GRANTED_BY_THIS_RECORD',
        },
    }
    validate_record(record)
    return record


def validate_record(record):
    require(record['core_roster'] == CORE and
            record['optional_roster'] == ['R5', 'R6'] and
            record['deferred_roster'] == ['R9', 'R10'], 'core roster differs')
    require(record['drop_first']['order'] == OPTIONAL_DROP_ORDER and
            record['drop_first']['core_droppable'] is False and
            record['drop_first']['missing_operational_measurement_allows_operational_claim'] is False,
            'drop-first rule differs')
    matrix = record['seed_matrix']
    require([row['seed'] for row in matrix] == [20260820, 20260821, 20260822] and
            all(row['methods'] == ['QARF', 'QPAF'] for row in matrix) and
            [row['state'] for row in matrix] == ['completed_pilot', 'pending', 'pending'],
            'matched seed matrix differs')
    test = record['test_plan']
    require(test['query_count'] == 172 and test['labels_opened'] is False and
            test['only_R7_may_open_labels'] is True and test['run_count'] == 1 and
            test['after_independent_reviews_of'] == ['R3', 'R4'] and
            test['baseline_count'] == 7 and
            test['qarf_seeds'] == test['qpaf_seeds'] == [20260820, 20260821, 20260822] and
            test['post_test_selection_allowed'] is False, 'TEST-172 plan differs')
    ablations = record['ablations']
    require(len(ablations) == 9 and
            [row['order'] for row in ablations] == list(range(1, 10)) and
            all(row['scope'] == 'validation' and row['task'] in ('M5.5', 'M5.6')
                for row in ablations) and
            record['ablation_rule']['diagnostic_only'] is True and
            record['ablation_rule']['a004_adopted'] is False,
            'one-factor ablation scope differs')


def encoded_record(record):
    return (json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')


def verify_signoff(output_dir):
    output_dir = Path(output_dir)
    signoff_path = output_dir / 'owner_confirmation.json'
    confirmation = read_json(signoff_path)
    require(confirmation['task_id'] == 'M5.1' and
            confirmation['owner'] == 'Thanh' and
            confirmation['decision'] == 'ACCEPTED' and
            confirmation['confirmation_text'] == 'Có, ghi Thanh chấp nhận M5.1' and
            confirmation['preregistration_sha256'] == sha256(output_dir / 'preregistration.json') and
            confirmation['execution_authorized'] is False and
            confirmation['test_labels_opened'] is False,
            'M5.1 owner confirmation does not bind the preregistration')
    lines = (output_dir / 'governance_events.jsonl').read_text(encoding='utf8').splitlines()
    require(len(lines) == 1, 'M5.1 governance event count differs')
    event = json.loads(lines[0])
    require(event['task_id'] == 'M5.1' and
            event['event_type'] == 'ACCEPTANCE_RECORDED' and
            event['registry_status'] == 'PASS' and
            event['human_review'] == 'ACCEPTED_BY_THANH' and
            event['preregistration_sha256'] == confirmation['preregistration_sha256'] and
            event['confirmation_sha256'] == sha256(signoff_path) and
            event['execution_authorization'] == 'NOT_GRANTED_BY_THIS_EVENT' and
            event['test_labels_opened'] is False,
            'M5.1 governance event does not bind owner confirmation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--create', type=Path)
    actions.add_argument('--verify', type=Path)
    args = parser.parse_args()
    freeze, pins = load_inputs(ROOT)
    if args.create:
        require(not args.create.exists(), 'M5.1 evidence directory already exists')
        timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        record = make_record(freeze, pins, timestamp)
        args.create.mkdir(parents=True)
        (args.create / 'preregistration.json').write_bytes(encoded_record(record))
        print('M5.1 preregistration created; Thanh signoff pending')
    else:
        saved = read_json(args.verify / 'preregistration.json')
        timestamp = saved['registered_at_utc']
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None, 'preregistration timestamp lacks timezone')
        expected = make_record(freeze, pins, timestamp)
        require((args.verify / 'preregistration.json').read_bytes() == encoded_record(expected),
                'M5.1 preregistration differs from frozen inputs')
        require(sorted(path.name for path in args.verify.iterdir()) ==
                ['README.md', 'governance_events.jsonl', 'owner_confirmation.json',
                 'preregistration.json'], 'M5.1 evidence file set differs')
        verify_signoff(args.verify)
        print('M5.1 preregistration verification: PASS')


if __name__ == '__main__':
    try:
        main()
    except (KeyError, OSError, ValueError) as exc:
        raise SystemExit(f'M5.1 refused: {exc}')
