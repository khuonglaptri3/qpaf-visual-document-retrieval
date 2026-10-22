"""Prepare a label-free GPU protocol/workload for review; never launch compute.

This deliberately produces a DRAFT, not an execution authorization or a GPU
executor. Review the held-out feature access and measurement scope first.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_m33_qarf import read, sha  # noqa: E402
from scripts.audit_m35_paired import PINS  # noqa: E402

NAMESPACE = 'qpaf-m36-label-free-resource-v1:'


def make_workload(splits):
    """Select 20 disjoint warm-ups and all remaining >=1000 distinct IDs, label-free."""
    if set(splits) != {'train', 'validation', 'test'}:
        raise ValueError('train/validation/test ID partitions are required')
    rows, seen = [], set()
    for role, ids in splits.items():
        for query_id in ids:
            if not isinstance(query_id, str) or not query_id.strip() or query_id != query_id.strip():
                raise ValueError('blank or padded query ID')
            if query_id in seen:
                raise ValueError('duplicate query ID cannot count as a new measured query')
            seen.add(query_id)
            rows.append({'query_id': query_id, 'source_split': role})
    if len(rows)-20 < 1000:
        raise ValueError('20 disjoint warm-ups plus at least 1000 distinct measured queries are required')
    rows.sort(key=lambda row: (hashlib.sha256((NAMESPACE+row['query_id']).encode('utf-8')).hexdigest(),
                               row['query_id']))
    return {'schema_version': 1, 'status': 'PROPOSED_REQUIRES_REVIEW',
            'selection': {'algorithm': 'ascending SHA256(namespace + query_id), then query_id',
                          'namespace': NAMESPACE, 'uses_labels_or_model_outputs': False},
            'warmup': rows[:20], 'measured': rows[20:],
            'unique_query_count': len(rows), 'warmup_count': 20, 'measured_count': len(rows)-20,
            'warmup_split_counts': dict(Counter(row['source_split'] for row in rows[:20])),
            'measured_split_counts': dict(Counter(row['source_split'] for row in rows[20:])),
            'held_out_query_ids_included': len(splits['test']), 'test_label_access_permitted': False,
            'held_out_text_score_access': 'PROPOSED_NOT_YET_AUTHORIZED',
            'training_or_model_selection_permitted': False}


def prepare(output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError(f'output directory already exists: {output_dir}')
    auth_rel, auth_sha = PINS['qpaf_authorization']
    if sha(ROOT/auth_rel) != auth_sha:
        raise ValueError('authorization SHA256 differs')
    auth = read(ROOT/auth_rel)
    seal = ROOT/auth['sealed_inputs']['run_path']
    splits = {}
    for role, filename in [('train', 'train_ids.txt'), ('validation', 'val_ids.txt'), ('test', 'test_ids.txt')]:
        rel = 'inputs/splits/'+filename
        if sha(seal/rel) != auth['sealed_inputs']['files_relative_to_run_path'][rel]:
            raise ValueError('split SHA256 differs: '+role)
        splits[role] = (seal/rel).read_text(encoding='utf-8').splitlines()
    workload = make_workload(splits)
    policy = ROOT/'evidence/M1_FINAL/02_protocol/metric_policy.md'
    plan = {
        'schema_version': 1, 'task_id': 'M3.6', 'status': 'DRAFT_NOT_AUTHORIZED',
        'execution_ready': False, 'preparation_only': True,
        'seal_manifest_sha256': auth['sealed_inputs']['manifest_sha256'],
        'workload_path': 'gpu_workload.json',
        'source_inputs': auth['sealed_inputs']['files_relative_to_run_path'],
        'excluded_payloads': ['qrels_development.json', 'qrels_test_sealed.json'],
        'checkpoint_payload_note': 'Original best.pt contains optimizer metadata; it may be loaded safely '
                                   'but must never be used for optimization, resumption or selection.',
        'checkpoint_inputs': {name: {'authorization': PINS[name.lower()+'_authorization'][0],
                                      'authorization_sha256': PINS[name.lower()+'_authorization'][1],
                                      'predictions_sha256': PINS[name.lower()+'_predictions'][1]}
                              for name in ('QARF', 'QPAF')},
        'policy': {'path': policy.relative_to(ROOT).as_posix(), 'sha256': sha(policy), 'section': 5},
        'gates': {'warmup_queries': 20, 'minimum_distinct_measured_queries': 1000,
                  'median_added_fusion_latency_ms_max_inclusive': 10.0,
                  'peak_learned_fusion_cuda_gib_max_exclusive': 1.50,
                  'checkpoint_score_abs_tolerance': 1e-7},
        'proposed_execution': {'platform': 'Modal', 'gpu': 'A10', 'gpu_count': 1,
                              'cpu_physical_cores': 2, 'memory_mib': 4096,
                              'timeout_seconds': 900, 'invocations': 1, 'automatic_retries': 0,
                              'paid_budget_usd_requested': 0.50,
                              'gpu_hourly_rate_source': 'https://modal.com/pricing',
                              'pricing_checked_on': '2026-10-22',
                              'estimated_allocated_compute_at_timeout_usd':
                                  round(900*(0.000306+2*0.0000131+4*0.00000222), 6),
                              'cost_limit_note': 'Estimate covers allocated GPU/CPU/RAM at listed rates; '
                                                 'image-build and lifecycle charges need a separate bound before approval.'},
        'proposed_runtime': {'python': '3.13.7', 'torch': '2.11.0+cu126',
                             'wheel_index': 'https://download.pytorch.org/whl/cu126',
                             'numpy': '2.5.4', 'pandas': '3.0.6', 'pyarrow': '26.0.0',
                             'modal': '1.5.5', 'dtype': 'float64', 'threads': 1,
                             'immutable_image_identity': 'PENDING_IMAGE_PREPARATION_AFTER_PROTOCOL_REVIEW'},
        'measurement_proposal': {
            'batch_size': 1, 'repeated_passes': 3,
            'repetition_count_authority': 'PROPOSED_ENGINEERING_CHOICE_NOT_A_PAPER_REQUIREMENT',
            'query_order': 'same frozen measured order for both methods and all passes',
            'cold_start': 'separate record; excluded from warm per-query gate',
            'separate_stages': ['CPU tensor construction and existing 13-feature preprocessing',
                                'host-to-device transfer', 'CUDA gate and fusion',
                                'device-to-host transfer', 'CPU deterministic page ranking'],
            'primary_latency_proposal': 'synchronized per-query wall time for the entire online fusion path '
                                        'after retriever scores are in RAM; no file I/O or retriever extraction',
            'primary_latency_statistic': 'median across unique measured queries of each query median across 3 passes',
            'secondary_latency': 'p95 across per-query medians, raw per-pass p50/p95, paired QPAF-minus-QARF',
            'cuda_timing': 'CUDA events, synchronize before wall start and after the timed CUDA work',
            'memory': 'reset CUDA peak stats per isolated method process; report allocated/reserved peaks '
                      'and CPU RSS separately, include model and live fusion tensors, exclude retrievers',
            'page_vs_document_scope': 'active ViDoSeek pilot is page-level; document aggregation is not silently added',
            'model_compatibility': 'verify frozen weights and GPU-vs-pinned-CPU validation scores <=1e-7 before timing',
            'quality_labels_used': False, 'checkpoint_or_hyperparameter_selection_allowed': False},
        'review_decisions_required': [
            'Allow label-free text/score access for 172 held-out query IDs, without labels, fitting or selection.',
            'Confirm the full online fusion latency interpretation and page-level ranking scope.',
            'Review the proposed 3 passes, Modal A10 runtime and bounded resource budget.'],
        'before_execution_required': ['accepted protocol/workload review', 'implemented and reviewed GPU executor',
                                      'immutable runtime image and exact source commit',
                                      'exact command and create-once namespace',
                                      'Research Lead authorization with external manifest SHA256 pin'],
        'gpu_execution_performed': False, 'test_labels_deserialized': False}
    for name, binding in plan['checkpoint_inputs'].items():
        prediction_path = ROOT/PINS[name.lower()+'_predictions'][0]
        checkpoint = prediction_path.parent/'checkpoints/best.pt'
        summary = read(prediction_path.parent/'summary.json')
        if sha(checkpoint) != summary['checkpoint_sha256']['best']:
            raise ValueError('checkpoint hash differs: '+name)
        binding.update(path=checkpoint.relative_to(ROOT).as_posix(), sha256=sha(checkpoint))
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, value in [('gpu_workload.json', workload), ('gpu_review_plan.json', plan)]:
        with (output_dir/name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    manifest = {'status': 'PREPARED_FOR_PROTOCOL_REVIEW_NOT_EXECUTION',
                'files': {name: sha(output_dir/name) for name in ('gpu_workload.json', 'gpu_review_plan.json')},
                'preparation_source_sha256': sha(Path(__file__))}
    with (output_dir/'package_hashes.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.output_dir), indent=2))


if __name__ == '__main__':
    main()
