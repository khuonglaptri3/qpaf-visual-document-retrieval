"""Seal ViMDoc ID-only confirmation split and its evaluation/access contract.

Reads only the Parquet ``id`` column after verifying the pinned source SHA-256.
Never deserializes query text, document IDs, qrels or scores. No training or
confirmation evaluation is authorized by this seal.
"""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / 'artifacts/dataset_materialization_vimdoc.json'
G2_DECISION = ROOT / 'evidence/revisions/m3.7-001/decision.json'
G2_CONFIRMATION = ROOT / 'evidence/revisions/m3.7-001/owner_confirmation.json'
SOURCE_SHA256 = '7ccac6c8715cc338c041e9276583b9dbd79a818131a9b13a5abf4b9ced73bcc0'
SOURCE_REVISION = '25657f1fe0358f49147148ca89e231291ba42788'
POLICIES = (
    'evidence/M1_FINAL/02_protocol/frozen_protocol.md',
    'evidence/M1_FINAL/02_protocol/dataset_split_policy.md',
    'evidence/M1_FINAL/02_protocol/metric_policy.md',
    'evidence/M1_FINAL/02_protocol/statistical_policy.md',
    'evidence/M1_FINAL/02_protocol/baseline_policy.md',
    'evidence/M1_FINAL/02_protocol/candidate_policy.md',
    'evidence/M1_FINAL/02_protocol/seed_policy.md',
    'evidence/M1_FINAL/02_protocol/run_policy.md',
)
SPLIT_NAMESPACE = 'vimdoc_m3_local_v1:dev_split:20260820'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def ids_bytes(ids):
    require(ids and len(ids) == len(set(ids)) and
            all(isinstance(q, str) and q and not any(ch in q for ch in '\r\n\t') for q in ids),
            'IDs must be unique nonempty strings without line delimiters')
    return ('\n'.join(ids) + '\n').encode('utf-8')


def hash_order(ids, namespace):
    return sorted(ids, key=lambda q: (hashlib.sha256(f'{namespace}:{q}'.encode('utf-8')).digest(), q))


def split_ids(all_ids, historical_sample):
    require(len(all_ids) == len(set(all_ids)) == 10904, 'source ID count/uniqueness differs')
    ordered = hash_order(all_ids, '20260820')
    development, confirmation = ordered[:2000], ordered[2000:]
    require(development == historical_sample, 'historical 2,000-ID sample differs')
    development_ordered = hash_order(development, SPLIT_NAMESPACE)
    train, validation = development_ordered[:1600], development_ordered[1600:]
    require((len(train), len(validation), len(confirmation)) == (1600, 400, 8904),
            'frozen split sizes differ')
    require(not (set(train) & set(validation) or set(train) & set(confirmation) or
                 set(validation) & set(confirmation)), 'split overlap')
    require(set(train) | set(validation) | set(confirmation) == set(all_ids), 'split union differs')
    return {'train': train, 'validation': validation, 'confirmation': confirmation,
            'development': development}


def build(source):
    require(sha(source) == SOURCE_SHA256, 'source Parquet SHA-256 differs')
    receipt = read(RECEIPT)
    sample = receipt['validation']['confirmation_sample']
    require(receipt['revision'] == SOURCE_REVISION and
            receipt['file_sha256']['data/ViMDoc-00000-of-00001.parquet'] == SOURCE_SHA256,
            'historical materialization receipt differs')
    require(hashlib.sha256(ids_bytes(sample['selected_query_ids'])).hexdigest() ==
            sample['selected_query_ids_sha256'] ==
            '0fc5a2f0de3eb1afa0b14e82e9f143dd57743864ac9468b5a112defb96a3482a',
            'historical development sample hash differs')
    decision, confirmation = read(G2_DECISION), read(G2_CONFIRMATION)
    require(decision['decision'] == 'GO' and decision['m4_branch'] == 'continue_qpaf' and
            confirmation['decision'] == 'CONFIRMED' and
            confirmation['decision_sha256'] == sha(G2_DECISION), 'G2 GO is not confirmed')
    # Column projection is intentional: Parquet stores labels in doc_ids.
    import pyarrow.parquet as pq
    source_ids = pq.read_table(source, columns=['id']).column('id').to_pylist()
    require(all(isinstance(q, str) for q in source_ids), 'source IDs are not strings')
    groups = split_ids(source_ids, sample['selected_query_ids'])
    payloads = {f'{name}_ids.txt': ids_bytes(groups[name])
                for name in ('train', 'validation', 'confirmation')}
    policy_hashes = {path: sha(ROOT / path) for path in POLICIES}
    manifest = {
        'schema_version': 1, 'task_id': 'M4.1', 'owner': 'Thanh',
        'status': 'ID_SPLITS_SEALED_CONFIRMATION_ACCESS_CLOSED',
        'dataset': {'id': 'kaistdata/ViMDoc', 'revision': SOURCE_REVISION,
                    'source_parquet_sha256': SOURCE_SHA256,
                    'historical_receipt_ref': RECEIPT.relative_to(ROOT).as_posix(),
                    'historical_receipt_sha256': sha(RECEIPT),
                    'historical_document_qrels_sha256': receipt['qrels_sha256'],
                    'document_qrels_hash_replayed_here': False},
        'g2': {'decision': 'GO', 'branch': 'continue_qpaf',
               'decision_sha256': sha(G2_DECISION), 'owner_confirmation_sha256': sha(G2_CONFIRMATION)},
        'split': {'selection': 'SHA256(UTF8("20260820:<query_id>")), digest bytes then query ID',
                  'development_sample_sha256': sample['selected_query_ids_sha256'],
                  'development_split_namespace': SPLIT_NAMESPACE,
                  'confirmation_order': 'remaining IDs in the same full-universe hash order',
                  'serialization': 'UTF-8, one ID per line, final newline',
                  'files': {name: {'count': len(groups[name.split('_ids.txt')[0]]),
                                   'sha256': hashlib.sha256(payload).hexdigest()}
                            for name, payload in payloads.items()},
                  'query_overlap': 0, 'union_count': len(source_ids)},
        'evaluation': {'policy_sha256': policy_hashes,
                       'unit': 'document', 'primary_metric': 'mean_per_query_document_ndcg_at_10',
                       'page_to_document': 'remove_final_underscore_segment',
                       'document_score': 'max_fused_page_score',
                       'rank_tie_break': 'ascending_document_id',
                       'idcg': 'all_relevant_documents',
                       'paired_bootstrap': {'unit': 'query_after_seed_averaging',
                                            'resamples': 10000, 'seed': 20260820,
                                            'ci95': 'linear_percentile_2.5_97.5'},
                       'implementation_sha256': None,
                       'implementation_status': 'PENDING_INDEPENDENT_VERIFICATION'},
        'method_and_checkpoint': {
            'methods': ['QARF', 'QPAF'], 'seeds': [20260820, 20260821, 20260822],
            'proposed_selection_rule': 'validation_document_ndcg_at_10_earliest_epoch_on_tie',
            'selection_rule_adopted': False,
            'preparation_ref': 'configs/vimdoc_m3_local_v1.json',
            'preparation_sha256': sha(ROOT / 'configs/vimdoc_m3_local_v1.json'),
            'preparation_status': 'PREPARED_NOT_ADOPTED_FOR_EXECUTION',
            'matched_training_config_sha256': None,
            'checkpoint_sha256_by_method_seed': None,
            'status': 'PENDING_M4_3_VIMDOC_RUNS_AND_INDEPENDENT_REVIEW'},
        'baseline_selection': {'policy_sha256': policy_hashes['evidence/M1_FINAL/02_protocol/baseline_policy.md'],
                               'rule': 'validation_mean_document_ndcg_at_10_all_co_strongest_within_1e-12',
                               'selected_baseline_ids_and_hashes': None,
                               'status': 'PENDING_M4_2_M4_4'},
        'access': {'id_only_seal_completed': True, 'confirmation_queries_and_labels_opened': False,
                   'confirmation_evaluation_authorized': False,
                   'document_overlap_status': 'PENDING_AUTHORIZED_LABEL_ACCESS',
                   'requires_before_open': [
                       'verified ViMDoc candidate/cache and document-qrels contract',
                       'frozen matched method configs and all three seed checkpoints',
                       'independently verified evaluation implementation hash',
                       'all required baseline validation runs and co-strongest selection',
                       'separate result-bearing authorization with one attempt and no automatic retry'],
                   'test_labels_deserialized': False, 'training_executed': False},
    }
    return manifest, payloads


def verify(output, manifest, payloads):
    require(read(output / 'manifest.json') == manifest, 'committed manifest differs')
    for name, payload in payloads.items():
        require((output / name).read_bytes() == payload, f'{name} differs')
    require(sorted(p.name for p in output.iterdir()) ==
            ['README.md', 'confirmation_ids.txt', 'manifest.json', 'train_ids.txt', 'validation_ids.txt'],
            'unexpected/missing seal artifact')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-parquet', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    manifest, payloads = build(args.source_parquet)
    if args.verify:
        verify(args.output_dir, manifest, payloads)
        print('M4.1 ID-only seal verification: PASS')
    else:
        require(not args.output_dir.exists(), 'output directory already exists')
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for name, payload in payloads.items():
            (args.output_dir / name).write_bytes(payload)
        with (args.output_dir / 'manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print('M4.1 ID-only splits sealed; confirmation access remains closed')


if __name__ == '__main__':
    try:
        main()
    except ValueError as exc:
        parser_error = f'M4.1 refused: {exc}'
        raise SystemExit(parser_error)
