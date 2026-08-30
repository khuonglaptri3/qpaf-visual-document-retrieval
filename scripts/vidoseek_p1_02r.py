from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

from scripts.extract_vidore_baseline import MINIMUM_COVERAGE
from scripts.vidoseek_dataset import parse_annotations


CALIBRATION_EXECUTION_STATUS = "approved_l4_cost_calibration_execution_only"
FULL_EXTRACTION_PREPARATION_STATUS = (
    "l4_cost_calibration_recorded_chunked_full_extraction_prepared"
)
FULL_EXTRACTION_EXECUTION_STATUS = "approved_l4_chunked_full_extraction_execution_only"
PROTOCOL_ID = "vidoseek_p1_02r_all_corpus_v1"
CANDIDATE_METHOD = "all_corpus"
DATASET_KEY = "vidoseek"
CPU_AUDIT_FUNCTION_NAME = "audit-vidoseek-p1-02r-all-corpus"
COST_CALIBRATION_FUNCTION_NAME = "calibrate-vidoseek-p1-02r-cost"
FULL_EXTRACTION_FUNCTION_NAME = "extract-vidoseek-p1-02r-scores"
COST_CALIBRATION_QUERY_LIMIT = 8
COST_CALIBRATION_PAGE_LIMIT = 512
COST_CALIBRATION_SCORE_BATCH_SIZE = 128
FULL_EXTRACTION_QUERY_CHUNK_SIZE = 8
FULL_EXTRACTION_PAGE_CHUNK_SIZE = 512
FULL_EXTRACTION_PASSAGE_BATCH_CANDIDATES = [2, 1]
FULL_EXTRACTION_QUERY_BATCH_CANDIDATES = [8, 4, 2]
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def validate_protocol(protocol: dict[str, Any]) -> None:
    """Validate the recorded calibration and guarded full-extraction contract."""
    if protocol.get("schema_version") != 1:
        raise ValueError("P1-02R schema_version must be 1")
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise ValueError(f"P1-02R protocol_id must be {PROTOCOL_ID}")
    status = protocol.get("status")
    if status not in {FULL_EXTRACTION_PREPARATION_STATUS, FULL_EXTRACTION_EXECUTION_STATUS}:
        raise ValueError("P1-02R status must be a supported full-extraction state")

    frozen_parent = protocol.get("frozen_parent")
    if not isinstance(frozen_parent, dict) or frozen_parent.get("status") != "BLOCKED":
        raise ValueError("P1-02R must retain the BLOCKED frozen parent")
    for field in ["extraction_protocol_sha256", "expanded_coverage_audit_sha256"]:
        value = frozen_parent.get(field)
        if not isinstance(value, str) or not HEX64.fullmatch(value):
            raise ValueError(f"P1-02R frozen_parent.{field} must be a SHA-256")

    retrievers = protocol.get("retrievers")
    if not isinstance(retrievers, dict) or retrievers.get("changed") is not False:
        raise ValueError("P1-02R must keep the frozen retrievers unchanged")
    if retrievers.get("contract_fields") != ["bm25", "models"]:
        raise ValueError("P1-02R must lock only the frozen BM25 and model definitions")
    contract_sha256 = retrievers.get("contract_sha256")
    if not isinstance(contract_sha256, str) or not HEX64.fullmatch(contract_sha256):
        raise ValueError("P1-02R requires a frozen retriever contract SHA-256")

    dataset = protocol.get("dataset")
    candidate_pool = protocol.get("candidate_pool")
    if not isinstance(dataset, dict) or not isinstance(candidate_pool, dict):
        raise ValueError("P1-02R requires dataset and candidate_pool mappings")
    if candidate_pool.get("method") != CANDIDATE_METHOD:
        raise ValueError(f"P1-02R candidate method must be {CANDIDATE_METHOD}")
    for flag in ["query_independent", "score_independent", "candidate_rows_frozen_before_qrels"]:
        if candidate_pool.get(flag) is not True:
            raise ValueError(f"P1-02R candidate_pool.{flag} must be true")
    if candidate_pool.get("qrels_used") is not False:
        raise ValueError("P1-02R candidate generation must not use qrels")

    queries = dataset.get("expected_queries")
    pages = dataset.get("expected_pages")
    if not isinstance(queries, int) or queries <= 0 or not isinstance(pages, int) or pages <= 0:
        raise ValueError("P1-02R expected query/page counts must be positive integers")
    if candidate_pool.get("candidates_per_query") != pages:
        raise ValueError("P1-02R all-corpus candidates_per_query must equal expected_pages")
    if candidate_pool.get("expected_candidate_pairs") != queries * pages:
        raise ValueError("P1-02R expected_candidate_pairs must equal queries * pages")

    coverage_gate = protocol.get("coverage_gate")
    if not isinstance(coverage_gate, dict):
        raise ValueError("P1-02R requires a coverage_gate mapping")
    if coverage_gate.get("minimum_relevant_pair_coverage") != MINIMUM_COVERAGE:
        raise ValueError("P1-02R must preserve the frozen minimum coverage gate")
    if coverage_gate.get("maximum_queries_with_zero_relevant_candidates") != 0:
        raise ValueError("P1-02R must preserve the zero-uncovered-query gate")

    audit = protocol.get("coverage_audit_result")
    if not isinstance(audit, dict) or audit.get("status") != "PASS":
        raise ValueError("P1-02R requires a recorded CPU coverage-audit PASS")
    if audit.get("decision") != "p1_02r_coverage_gate_passes":
        raise ValueError("P1-02R recorded coverage-audit decision must pass")
    for field in ["artifact_sha256", "executed_protocol_config_sha256", "image_definition_sha256"]:
        value = audit.get(field)
        if not isinstance(value, str) or not HEX64.fullmatch(value):
            raise ValueError(f"P1-02R coverage_audit_result.{field} must be a SHA-256")
    if not isinstance(audit.get("source_commit"), str) or not HEX40.fullmatch(
        audit["source_commit"]
    ):
        raise ValueError("P1-02R coverage_audit_result.source_commit must be a Git SHA")
    if float(audit.get("coverage", -1.0)) < MINIMUM_COVERAGE:
        raise ValueError("P1-02R recorded coverage must satisfy the frozen gate")
    if audit.get("relevant_pairs") != audit.get("selected_relevant_pairs"):
        raise ValueError("P1-02R recorded audit must cover every relevant pair")
    if audit.get("missing_relevant_pairs") != 0:
        raise ValueError("P1-02R recorded audit must have no missing relevant pairs")
    if audit.get("queries_with_zero_relevant_candidates") != 0:
        raise ValueError("P1-02R recorded audit must have no uncovered queries")
    if audit.get("gpu_used") is not False:
        raise ValueError("P1-02R coverage audit must remain CPU-only")

    calibration = protocol.get("cost_calibration")
    if not isinstance(calibration, dict):
        raise ValueError("P1-02R requires a bounded cost_calibration mapping")
    query_limit = calibration.get("query_limit")
    page_limit = calibration.get("page_limit")
    if query_limit != COST_CALIBRATION_QUERY_LIMIT:
        raise ValueError("P1-02R calibration query limit must remain fixed at 8")
    if page_limit != COST_CALIBRATION_PAGE_LIMIT:
        raise ValueError("P1-02R calibration page limit must remain fixed at 512")
    if calibration.get("candidate_pairs") != query_limit * page_limit:
        raise ValueError("P1-02R calibration candidate_pairs must equal its bounded shape")
    if calibration.get("visual_score_batch_size") != COST_CALIBRATION_SCORE_BATCH_SIZE:
        raise ValueError("P1-02R must preserve visual score batch size 128")
    if calibration.get("gpu_if_approved") != "L4":
        raise ValueError("P1-02R bounded cost calibration must target L4")
    if calibration.get("qrels_used") is not False:
        raise ValueError("P1-02R cost-calibration sampling must not use qrels")
    if calibration.get("membership_rule") != "every_sampled_page_for_every_sampled_query":
        raise ValueError("P1-02R calibration must retain all-corpus membership on its sample")
    if calibration.get("status") != "complete":
        raise ValueError("P1-02R bounded cost calibration must be recorded as complete")

    calibration_result = protocol.get("cost_calibration_result")
    if not isinstance(calibration_result, dict):
        raise ValueError("P1-02R requires a recorded cost-calibration result")
    if calibration_result.get("status") != "complete":
        raise ValueError("P1-02R recorded cost-calibration status must be complete")
    if calibration_result.get("decision") != "requires_human_cost_review":
        raise ValueError("P1-02R calibration decision must remain cost-review evidence")
    for field in [
        "artifact_sha256",
        "executed_protocol_config_sha256",
        "image_definition_sha256",
        "calibration_score_cache_sha256",
    ]:
        value = calibration_result.get(field)
        if not isinstance(value, str) or not HEX64.fullmatch(value):
            raise ValueError(f"P1-02R cost_calibration_result.{field} must be a SHA-256")
    if not isinstance(calibration_result.get("source_commit"), str) or not HEX40.fullmatch(
        calibration_result["source_commit"]
    ):
        raise ValueError("P1-02R cost_calibration_result.source_commit must be a Git SHA")
    if calibration_result.get("executed_protocol_status") != CALIBRATION_EXECUTION_STATUS:
        raise ValueError("P1-02R calibration must retain its executed protocol status")
    if calibration_result.get("artifact_path") != calibration.get("output_artifact_path"):
        raise ValueError("P1-02R calibration artifact path drifted")
    if calibration_result.get("requested_gpu") != "L4" or "L4" not in str(
        calibration_result.get("actual_gpu", "")
    ):
        raise ValueError("P1-02R recorded calibration must use an L4")
    if calibration_result.get("sample_queries") != query_limit:
        raise ValueError("P1-02R recorded calibration query count drifted")
    if calibration_result.get("sample_pages") != page_limit:
        raise ValueError("P1-02R recorded calibration page count drifted")
    if calibration_result.get("candidate_pairs") != query_limit * page_limit:
        raise ValueError("P1-02R recorded calibration pair count drifted")
    for field in [
        "actual_gpu_vram_gib",
        "total_seconds",
        "peak_memory_allocated_bytes",
        "projected_total_gpu_seconds",
        "projected_total_gpu_hours",
    ]:
        value = calibration_result.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"P1-02R cost_calibration_result.{field} must be positive")
    if calibration_result.get("full_extraction_started") is not False:
        raise ValueError("P1-02R calibration must not be relabeled as a full extraction")

    full_extraction = protocol.get("full_extraction")
    if not isinstance(full_extraction, dict):
        raise ValueError("P1-02R requires a chunked full_extraction mapping")
    expected_full_status = (
        "prepared_not_executed"
        if status == FULL_EXTRACTION_PREPARATION_STATUS
        else "approved_for_execution"
    )
    if full_extraction.get("status") != expected_full_status:
        raise ValueError("P1-02R full_extraction.status does not match protocol authorization")
    if full_extraction.get("function_name") != FULL_EXTRACTION_FUNCTION_NAME:
        raise ValueError("P1-02R full extraction Function name drifted")
    if full_extraction.get("gpu_if_approved") != "L4":
        raise ValueError("P1-02R chunked full extraction must target L4")
    if full_extraction.get("source_score_cache_root") != "frozen_parent_full_run":
        raise ValueError("P1-02R full extraction must reuse the frozen parent cache root")
    if full_extraction.get("required_source_score_caches") != {
        "bm25": "cache/bm25_scores.pt",
        "bge_m3": "cache/bge_m3_scores.pt",
        "dse": "cache/dse_scores.pt",
    }:
        raise ValueError("P1-02R frozen parent score-cache contract drifted")
    if full_extraction.get("query_chunk_size") != FULL_EXTRACTION_QUERY_CHUNK_SIZE:
        raise ValueError("P1-02R full query chunk size must remain 8")
    if full_extraction.get("page_chunk_size") != FULL_EXTRACTION_PAGE_CHUNK_SIZE:
        raise ValueError("P1-02R full page chunk size must remain 512")
    if (
        full_extraction.get("passage_encode_batch_candidates")
        != FULL_EXTRACTION_PASSAGE_BATCH_CANDIDATES
    ):
        raise ValueError("P1-02R full passage batches must remain [2, 1]")
    if (
        full_extraction.get("query_encode_batch_candidates")
        != FULL_EXTRACTION_QUERY_BATCH_CANDIDATES
    ):
        raise ValueError("P1-02R full query batches must remain [8, 4, 2]")
    if full_extraction.get("visual_score_batch_size") != COST_CALIBRATION_SCORE_BATCH_SIZE:
        raise ValueError("P1-02R full visual score batch size must remain 128")
    expected_query_chunks = (queries + FULL_EXTRACTION_QUERY_CHUNK_SIZE - 1) // (
        FULL_EXTRACTION_QUERY_CHUNK_SIZE
    )
    expected_page_chunks = (pages + FULL_EXTRACTION_PAGE_CHUNK_SIZE - 1) // (
        FULL_EXTRACTION_PAGE_CHUNK_SIZE
    )
    if full_extraction.get("expected_query_chunks") != expected_query_chunks:
        raise ValueError("P1-02R full query chunk count drifted")
    if full_extraction.get("expected_page_chunks") != expected_page_chunks:
        raise ValueError("P1-02R full page chunk count drifted")
    if full_extraction.get("expected_candidate_pairs") != queries * pages:
        raise ValueError("P1-02R full candidate-pair count drifted")
    if full_extraction.get("candidate_provenance") != "all_corpus_p1_02r_v1":
        raise ValueError("P1-02R full candidate provenance drifted")
    if full_extraction.get("qrels_use") != (
        "post_candidate_coverage_audit_and_evaluation_only"
    ):
        raise ValueError("P1-02R full extraction must preserve the qrels boundary")

    execution = protocol.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("P1-02R requires an execution mapping")
    if execution.get("modal_code_preparation_allowed") is not True:
        raise ValueError("P1-02R must authorize only local Modal code preparation")
    if execution.get("cpu_audit_entrypoint_preparation_allowed") is not True:
        raise ValueError("P1-02R must authorize CPU-audit entry-point preparation")
    if execution.get("cost_calibration_entrypoint_preparation_allowed") is not True:
        raise ValueError("P1-02R must authorize cost-calibration entry-point preparation")
    if execution.get("full_extraction_entrypoint_preparation_allowed") is not True:
        raise ValueError("P1-02R must authorize full-extraction entry-point preparation")
    if execution.get("prepared_modal_function") != FULL_EXTRACTION_FUNCTION_NAME:
        raise ValueError("P1-02R must name the prepared chunked full-extraction Function")
    if execution.get("cpu_audit_execution_allowed") is not False:
        raise ValueError("P1-02R completed CPU audit must no longer be executable")
    if execution.get("cost_calibration_execution_allowed") is not False:
        raise ValueError("P1-02R completed cost calibration must no longer be executable")
    if execution.get("cpu_audit_execution_approval_required") is not False:
        raise ValueError("P1-02R CPU-audit approval must be recorded as satisfied")
    if execution.get("cost_calibration_execution_approval_required") is not False:
        raise ValueError("P1-02R cost-calibration approval must be recorded as satisfied")
    if execution.get("prior_l4_approval_reused") is not False:
        raise ValueError("P1-02R must not reuse the frozen P1-02 L4 approval")

    if status == FULL_EXTRACTION_PREPARATION_STATUS:
        expected = {
            "modal_allowed": False,
            "modal_execution_scope": "none",
            "allowed_modal_function": None,
            "full_extraction_execution_allowed": False,
            "gpu_execution_allowed": False,
            "cost_review_required": True,
            "full_extraction_execution_approval_required": True,
            "gpu_execution_approval_required": True,
            "next_gate": "explicit_p1_02r_chunked_full_extraction_execution_approval",
        }
    else:
        expected = {
            "modal_allowed": True,
            "modal_execution_scope": "l4_chunked_full_extraction_only",
            "allowed_modal_function": FULL_EXTRACTION_FUNCTION_NAME,
            "full_extraction_execution_allowed": True,
            "gpu_execution_allowed": True,
            "cost_review_required": False,
            "full_extraction_execution_approval_required": False,
            "gpu_execution_approval_required": False,
            "next_gate": "completed_p1_02r_chunked_full_extraction_and_integrity_review",
        }
    for field, value in expected.items():
        if execution.get(field) != value:
            raise ValueError(f"P1-02R execution.{field} must be {value!r} for status {status}")


def load_protocol(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("P1-02R protocol must be a YAML mapping")
    validate_protocol(value)
    return value


def require_cpu_audit_execution_approval(protocol: dict[str, Any]) -> None:
    validate_protocol(protocol)
    raise RuntimeError("P1-02R CPU audit is complete and no longer authorized")


def require_cost_calibration_execution_approval(protocol: dict[str, Any]) -> None:
    validate_protocol(protocol)
    raise RuntimeError("P1-02R L4 cost calibration is complete and no longer authorized")


def require_full_extraction_execution_approval(protocol: dict[str, Any]) -> None:
    validate_protocol(protocol)
    if protocol["status"] != FULL_EXTRACTION_EXECUTION_STATUS:
        raise RuntimeError("P1-02R chunked full-extraction execution is not approved")


def _validated_ids(
    query_ids: np.ndarray,
    page_ids: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    queries = np.asarray(query_ids)
    pages = np.asarray(page_ids)
    if queries.ndim != 1 or pages.ndim != 1:
        raise ValueError("P1-02R query_ids and page_ids must be one-dimensional")
    if len(queries) == 0 or len(pages) == 0:
        raise ValueError("P1-02R query_ids and page_ids must be non-empty")
    if len({str(value) for value in queries.tolist()}) != len(queries):
        raise ValueError("P1-02R query IDs must be unique")
    if len({str(value) for value in pages.tolist()}) != len(pages):
        raise ValueError("P1-02R page IDs must be unique")
    return queries, pages


def build_all_corpus_candidates(
    query_ids: np.ndarray,
    page_ids: np.ndarray,
) -> list[np.ndarray]:
    """Build a query-independent pool containing every page, without scores or qrels."""
    queries, pages = _validated_ids(query_ids, page_ids)
    all_pages = np.arange(len(pages), dtype=np.int64)
    return [all_pages.copy() for _ in range(len(queries))]


def audit_all_corpus_coverage(
    query_ids: np.ndarray,
    page_ids: np.ndarray,
    qrel_lookup: dict[tuple[Any, Any], float],
    dataset_id: str,
) -> dict[str, Any]:
    """Audit all-corpus membership without materializing every query-page pair."""
    queries, pages = _validated_ids(query_ids, page_ids)
    query_keys = [str(value) for value in queries.tolist()]
    page_keys = {str(value) for value in pages.tolist()}
    relevant_by_query: dict[str, set[str]] = {query_id: set() for query_id in query_keys}
    for (query_id, page_id), relevance in qrel_lookup.items():
        query_key = str(query_id)
        if float(relevance) > 0 and query_key in relevant_by_query:
            relevant_by_query[query_key].add(str(page_id))

    relevant_pairs = sum(len(values) for values in relevant_by_query.values())
    selected_relevant_pairs = sum(
        len(values & page_keys) for values in relevant_by_query.values()
    )
    coverage = 1.0 if relevant_pairs == 0 else selected_relevant_pairs / relevant_pairs
    zero_ids = sorted(
        query_id
        for query_id, relevant_pages in relevant_by_query.items()
        if not relevant_pages.intersection(page_keys)
    )
    gate_passes = coverage >= MINIMUM_COVERAGE and not zero_ids
    return {
        "protocol_id": PROTOCOL_ID,
        "dataset": dataset_id,
        "coverage": coverage,
        "minimum_coverage": MINIMUM_COVERAGE,
        "queries": len(queries),
        "corpus_pages": len(pages),
        "candidate_pairs": len(queries) * len(pages),
        "relevant_pairs": relevant_pairs,
        "selected_relevant_pairs": selected_relevant_pairs,
        "missing_relevant_pairs": relevant_pairs - selected_relevant_pairs,
        "queries_with_zero_relevant_candidates": len(zero_ids),
        "zero_relevant_query_ids": zero_ids,
        "mean_candidates": float(len(pages)),
        "decision": "p1_02r_coverage_gate_passes" if gate_passes else "p1_02r_coverage_gate_fails",
        "candidate_generation_used_qrels": False,
        "qrels_use": "post_candidate_coverage_audit_only",
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_recorded_cpu_audit(
    protocol: dict[str, Any],
    artifact_path: Path,
) -> dict[str, Any]:
    """Verify that the checked-in artifact is the exact approved CPU-audit PASS."""
    validate_protocol(protocol)
    evidence = protocol["coverage_audit_result"]
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Missing P1-02R CPU-audit artifact: {artifact_path}")
    if _file_sha256(artifact_path) != evidence["artifact_sha256"]:
        raise RuntimeError("P1-02R CPU-audit artifact hash does not match the protocol")

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    expected = {
        "status": "complete",
        "decision": evidence["decision"],
        "protocol_id": PROTOCOL_ID,
        "function_call_id": evidence["function_call_id"],
        "source_commit": evidence["source_commit"],
        "protocol_config_sha256": evidence["executed_protocol_config_sha256"],
        "image_definition_sha256": evidence["image_definition_sha256"],
        "source_protocol_sha256": protocol["frozen_parent"]["extraction_protocol_sha256"],
        "coverage": evidence["coverage"],
        "relevant_pairs": evidence["relevant_pairs"],
        "selected_relevant_pairs": evidence["selected_relevant_pairs"],
        "missing_relevant_pairs": 0,
        "queries_with_zero_relevant_candidates": 0,
        "candidate_pairs": protocol["candidate_pool"]["expected_candidate_pairs"],
        "gpu_used": False,
        "candidate_generation_used_qrels": False,
    }
    mismatches = [
        field for field, value in expected.items() if artifact.get(field) != value
    ]
    if mismatches:
        raise RuntimeError(
            "P1-02R CPU-audit artifact contract mismatch: " + ", ".join(mismatches)
        )
    if artifact.get("candidate_pool_contract", {}).get("method") != CANDIDATE_METHOD:
        raise RuntimeError("P1-02R CPU-audit artifact candidate method is not all-corpus")
    return artifact


def validate_recorded_cost_calibration(
    protocol: dict[str, Any],
    artifact_path: Path,
) -> dict[str, Any]:
    """Verify the exact returned L4 calibration manifest without claiming a full run."""
    validate_protocol(protocol)
    evidence = protocol["cost_calibration_result"]
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Missing P1-02R cost-calibration artifact: {artifact_path}")
    if _file_sha256(artifact_path) != evidence["artifact_sha256"]:
        raise RuntimeError("P1-02R cost-calibration artifact hash does not match the protocol")

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    expected = {
        "status": "complete",
        "calibration_only": True,
        "full_extraction_started": False,
        "decision": evidence["decision"],
        "protocol_id": PROTOCOL_ID,
        "protocol_status": evidence["executed_protocol_status"],
        "source_commit": evidence["source_commit"],
        "image_definition_sha256": evidence["image_definition_sha256"],
        "protocol_config_sha256": evidence["executed_protocol_config_sha256"],
        "function_call_id": evidence["function_call_id"],
        "source_protocol_sha256": protocol["frozen_parent"]["extraction_protocol_sha256"],
        "requested_gpu": evidence["requested_gpu"],
        "actual_gpu": evidence["actual_gpu"],
        "actual_gpu_vram_gib": evidence["actual_gpu_vram_gib"],
        "peak_memory_allocated_bytes": evidence["peak_memory_allocated_bytes"],
        "retrievers_changed": False,
        "retriever_contract_sha256": protocol["retrievers"]["contract_sha256"],
    }
    mismatches = [
        field for field, value in expected.items() if artifact.get(field) != value
    ]
    if mismatches:
        raise RuntimeError(
            "P1-02R cost-calibration artifact contract mismatch: " + ", ".join(mismatches)
        )

    dataset = artifact.get("dataset", {})
    if dataset != {
        "id": protocol["dataset"]["id"],
        "revision": protocol["dataset"]["revision"],
        "full_queries": protocol["dataset"]["expected_queries"],
        "full_pages": protocol["dataset"]["expected_pages"],
        "sample_queries": evidence["sample_queries"],
        "sample_pages": evidence["sample_pages"],
    }:
        raise RuntimeError("P1-02R cost-calibration dataset contract mismatch")
    candidate_pool = artifact.get("candidate_pool", {})
    if candidate_pool != {
        "method": CANDIDATE_METHOD,
        "membership_rule": protocol["cost_calibration"]["membership_rule"],
        "candidate_pairs": evidence["candidate_pairs"],
        "visual_score_batch_size": protocol["cost_calibration"]["visual_score_batch_size"],
        "qrels_used": False,
    }:
        raise RuntimeError("P1-02R cost-calibration candidate contract mismatch")
    if artifact.get("batch_sizes") != {
        "p1_02r_colqwen25_passages": 2,
        "p1_02r_colqwen25_queries": 8,
    }:
        raise RuntimeError("P1-02R cost-calibration batch sizes drifted")
    if artifact.get("timings", {}).get("total_seconds") != evidence["total_seconds"]:
        raise RuntimeError("P1-02R cost-calibration total timing mismatch")
    projection = artifact.get("projection", {})
    if projection.get("projected_total_gpu_seconds") != evidence["projected_total_gpu_seconds"]:
        raise RuntimeError("P1-02R cost-calibration projected seconds mismatch")
    if projection.get("projected_total_gpu_hours") != evidence["projected_total_gpu_hours"]:
        raise RuntimeError("P1-02R cost-calibration projected hours mismatch")
    if projection.get("interpretation") != "cost_review_input_only_not_a_full_extraction_result":
        raise RuntimeError("P1-02R cost projection was relabeled as an extraction result")
    score_cache = artifact.get("calibration_score_cache", {})
    if score_cache.get("sha256") != evidence["calibration_score_cache_sha256"]:
        raise RuntimeError("P1-02R cost-calibration score-cache hash mismatch")
    if score_cache.get("shape") != [evidence["sample_queries"], evidence["sample_pages"]]:
        raise RuntimeError("P1-02R cost-calibration score-cache shape mismatch")
    if score_cache.get("scope") != "calibration_sample_only_not_full_scores":
        raise RuntimeError("P1-02R calibration cache must remain sample-only")
    if artifact.get("cuda_available") is not True:
        raise RuntimeError("P1-02R recorded L4 calibration must report CUDA")
    return artifact


def audit_persisted_p1_02r_coverage(
    dataset_config: dict[str, Any],
    protocol: dict[str, Any],
    volume_root: Path,
    source_protocol_sha256: str,
) -> dict[str, Any]:
    """Audit the approved all-corpus rule against a persisted prepared corpus."""
    validate_protocol(protocol)
    if not HEX64.fullmatch(source_protocol_sha256):
        raise ValueError("source_protocol_sha256 must be 64 lowercase hex characters")
    if source_protocol_sha256 != protocol["frozen_parent"]["extraction_protocol_sha256"]:
        raise ValueError("source_protocol_sha256 must match the frozen P1-02 parent")

    dataset = next(
        item for item in dataset_config["datasets"] if item["key"] == DATASET_KEY
    )
    if dataset["id"] != protocol["dataset"]["id"]:
        raise RuntimeError("P1-02R dataset ID does not match the approved protocol")
    if dataset["revision"] != protocol["dataset"]["revision"]:
        raise RuntimeError("P1-02R dataset revision does not match the approved protocol")

    run_root = (
        volume_root
        / "score_extraction"
        / DATASET_KEY
        / source_protocol_sha256
        / "full"
    )
    preparation_path = run_root / "prepared_corpus" / "_PREPARED.json"
    if not preparation_path.is_file():
        raise FileNotFoundError(f"Missing preparation marker: {preparation_path}")
    preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
    if preparation.get("status") != "complete" or not isinstance(preparation.get("pages"), list):
        raise RuntimeError("Persisted ViDoSeek preparation marker is incomplete")
    page_ids = np.asarray([str(row["page_id"]) for row in preparation["pages"]])
    if len(page_ids) != int(preparation.get("page_count", -1)):
        raise RuntimeError("Persisted ViDoSeek page count does not match its marker")

    annotation_path = Path(dataset["local_dir"]) / dataset["discovery_extraction"]["annotation_file"]
    expected_annotation_sha256 = dataset["qrels_metadata"]["annotation_file_sha256"]
    if _file_sha256(annotation_path) != expected_annotation_sha256:
        raise RuntimeError("ViDoSeek annotation hash does not match the frozen contract")
    annotations = parse_annotations(json.loads(annotation_path.read_text(encoding="utf-8")))

    expected_queries = protocol["dataset"]["expected_queries"]
    expected_pages = protocol["dataset"]["expected_pages"]
    if len(annotations.query_ids) != expected_queries or len(page_ids) != expected_pages:
        raise RuntimeError("Persisted ViDoSeek counts do not match the P1-02R protocol")

    coverage = audit_all_corpus_coverage(
        annotations.query_ids,
        page_ids,
        annotations.qrel_lookup,
        dataset_id=dataset["id"],
    )
    return {
        "schema_version": 1,
        "status": "complete",
        "audit_type": "vidoseek_p1_02r_all_corpus_coverage",
        "audit_only": True,
        "gpu_used": False,
        "protocol_status": protocol["status"],
        "source_protocol_sha256": source_protocol_sha256,
        "source_run_root": str(run_root),
        "dataset_contract": {
            "id": dataset["id"],
            "revision": dataset["revision"],
            "queries": len(annotations.query_ids),
            "pages": len(page_ids),
            "annotation_sha256": expected_annotation_sha256,
            "preparation_marker_sha256": _file_sha256(preparation_path),
        },
        "candidate_pool_contract": {
            "method": protocol["candidate_pool"]["method"],
            "membership_rule": protocol["candidate_pool"]["membership_rule"],
            "ordering": protocol["candidate_pool"]["ordering"],
            "candidates_per_query": len(page_ids),
            "candidate_pairs": len(annotations.query_ids) * len(page_ids),
        },
        **coverage,
    }


def systematic_sample_indices(population_size: int, limit: int) -> np.ndarray:
    """Select a deterministic spread over frozen order without scores or qrels."""
    if not isinstance(population_size, int) or population_size <= 0:
        raise ValueError("population_size must be a positive integer")
    if not isinstance(limit, int) or limit <= 0 or limit > population_size:
        raise ValueError("limit must be positive and no larger than population_size")
    return (np.arange(limit, dtype=np.int64) * population_size) // limit


def _query_records_without_qrels(payload: dict[str, Any]) -> list[dict[str, str]]:
    examples = payload.get("examples")
    if not isinstance(examples, list) or not examples:
        raise ValueError("ViDoSeek annotations require a non-empty examples list")
    records: list[dict[str, str]] = []
    for example in examples:
        if not isinstance(example, dict):
            raise ValueError("Every ViDoSeek example must be an object")
        query_id = str(example.get("uid", ""))
        query_text = str(example.get("query", "")).strip()
        meta = example.get("meta_info")
        if not query_id or not query_text or not isinstance(meta, dict):
            raise ValueError("ViDoSeek cost-calibration query metadata is incomplete")
        records.append(
            {
                "query_id": query_id,
                "query_text": query_text,
                "source": (
                    f"source_type={meta.get('source_type') or 'unknown'}|"
                    f"query_type={meta.get('query_type') or 'unknown'}"
                ),
            }
        )
    records.sort(key=lambda row: row["query_id"])
    if len({row["query_id"] for row in records}) != len(records):
        raise ValueError("ViDoSeek cost-calibration query IDs must be unique")
    return records


def project_full_cost_from_calibration(
    timings: dict[str, float],
    sample_queries: int,
    sample_pages: int,
    full_queries: int,
    full_pages: int,
) -> dict[str, Any]:
    """Produce a transparent linear GPU-time projection, never a result claim."""
    required = [
        "model_load_seconds",
        "passage_encoding_seconds",
        "query_encoding_seconds",
        "visual_scoring_seconds",
        "total_seconds",
    ]
    if any(name not in timings or float(timings[name]) < 0 for name in required):
        raise ValueError("Calibration timings must contain non-negative required values")
    if min(sample_queries, sample_pages, full_queries, full_pages) <= 0:
        raise ValueError("Calibration and full dimensions must be positive")
    if sample_queries > full_queries or sample_pages > full_pages:
        raise ValueError("Calibration dimensions must not exceed full dimensions")
    visual_seconds = float(timings["visual_scoring_seconds"])
    if visual_seconds <= 0:
        raise ValueError("visual_scoring_seconds must be positive for cost projection")

    sample_pairs = sample_queries * sample_pages
    full_pairs = full_queries * full_pages
    components = {
        "fixed_and_model_load_seconds": float(timings["model_load_seconds"]),
        "passage_encoding_seconds": float(timings["passage_encoding_seconds"])
        * full_pages
        / sample_pages,
        "query_encoding_seconds": float(timings["query_encoding_seconds"])
        * full_queries
        / sample_queries,
        "visual_scoring_seconds": visual_seconds * full_pairs / sample_pairs,
    }
    measured_components = sum(float(timings[name]) for name in required[:-1])
    unassigned_overhead = max(0.0, float(timings["total_seconds"]) - measured_components)
    components["other_measured_overhead_seconds"] = unassigned_overhead
    projected_seconds = sum(components.values())
    return {
        "method": "componentwise_linear_engineering_projection_v1",
        "sample_candidate_pairs": sample_pairs,
        "full_candidate_pairs": full_pairs,
        "measured_visual_pairs_per_second": sample_pairs / visual_seconds,
        "projected_components": components,
        "projected_total_gpu_seconds": projected_seconds,
        "projected_total_gpu_hours": projected_seconds / 3600.0,
        "interpretation": "cost_review_input_only_not_a_full_extraction_result",
        "excludes": [
            "modal_queue_time",
            "retries_or_oom_backoff",
            "monetary_price_changes",
            "bm25_bge_dse_cache_regeneration",
            "full_output_materialization",
        ],
    }


def run_bounded_cost_calibration(
    dataset_config: dict[str, Any],
    environment: dict[str, Any],
    protocol: dict[str, Any],
    audit_artifact_path: Path,
    volume_root: Path,
    source_commit: str,
    image_definition_sha256: str,
    protocol_config_sha256: str,
    function_call_id: str,
    gpu_metadata: dict[str, Any],
    commit: Callable[[], None],
) -> dict[str, Any]:
    """Measure a fixed all-corpus sample using only the frozen ColQwen scorer."""
    total_started = time.perf_counter()
    require_cost_calibration_execution_approval(protocol)
    audit = validate_recorded_cpu_audit(protocol, audit_artifact_path)
    if not HEX64.fullmatch(protocol_config_sha256):
        raise ValueError("protocol_config_sha256 must be 64 lowercase hex characters")

    dataset = next(
        item for item in dataset_config["datasets"] if item["key"] == DATASET_KEY
    )
    if dataset["id"] != protocol["dataset"]["id"]:
        raise RuntimeError("P1-02R calibration dataset ID drifted")
    if dataset["revision"] != protocol["dataset"]["revision"]:
        raise RuntimeError("P1-02R calibration dataset revision drifted")
    retriever_contract = {
        name: environment[name] for name in protocol["retrievers"]["contract_fields"]
    }
    retriever_contract_sha256 = hashlib.sha256(
        json.dumps(retriever_contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if retriever_contract_sha256 != protocol["retrievers"]["contract_sha256"]:
        raise RuntimeError("P1-02R frozen retriever contract drifted")

    source_protocol_sha256 = protocol["frozen_parent"]["extraction_protocol_sha256"]
    source_run_root = (
        volume_root / "score_extraction" / DATASET_KEY / source_protocol_sha256 / "full"
    )
    preparation_path = source_run_root / "prepared_corpus" / "_PREPARED.json"
    if _file_sha256(preparation_path) != audit["dataset_contract"]["preparation_marker_sha256"]:
        raise RuntimeError("P1-02R prepared-corpus marker drifted after the CPU audit")
    preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
    page_records = preparation.get("pages")
    if preparation.get("status") != "complete" or not isinstance(page_records, list):
        raise RuntimeError("P1-02R prepared corpus is incomplete")
    if len(page_records) != protocol["dataset"]["expected_pages"]:
        raise RuntimeError("P1-02R prepared page count drifted")

    annotation_path = (
        Path(dataset["local_dir"])
        / dataset["discovery_extraction"]["annotation_file"]
    )
    if _file_sha256(annotation_path) != audit["dataset_contract"]["annotation_sha256"]:
        raise RuntimeError("P1-02R annotation file drifted after the CPU audit")
    queries = _query_records_without_qrels(
        json.loads(annotation_path.read_text(encoding="utf-8"))
    )
    if len(queries) != protocol["dataset"]["expected_queries"]:
        raise RuntimeError("P1-02R query count drifted")

    calibration = protocol["cost_calibration"]
    query_indices = systematic_sample_indices(len(queries), calibration["query_limit"])
    page_indices = systematic_sample_indices(len(page_records), calibration["page_limit"])
    selected_queries = [queries[int(index)] for index in query_indices]
    selected_pages = [page_records[int(index)] for index in page_indices]
    image_paths = [Path(record["image"]) for record in selected_pages]
    if not all(path.is_file() for path in image_paths):
        raise FileNotFoundError("P1-02R calibration sample has missing prepared page images")

    run_root = (
        volume_root
        / "score_extraction"
        / DATASET_KEY
        / PROTOCOL_ID
        / protocol_config_sha256
        / "cost_calibration"
        / function_call_id
    )
    cache_dir = run_root / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    ephemeral_hf_root = Path("/tmp/qpaf_hf_cache")
    os.environ["HF_HOME"] = str(ephemeral_hf_root)
    os.environ["HF_HUB_CACHE"] = str(ephemeral_hf_root / "hub")

    import torch

    from scripts.colqwen25_retriever import ColQwen25Retriever
    from scripts.extract_vidore_baseline import (
        _atomic_torch_save,
        _clear_cuda,
        _encode_with_backoff,
    )
    from scripts.vidoseek_dataset import LazyPageImages

    timings: dict[str, float] = {}
    batch_sizes: dict[str, Any] = {}
    torch.cuda.reset_peak_memory_stats()
    colqwen = environment["models"]["colqwen25"]
    stage_started = time.perf_counter()
    retriever = ColQwen25Retriever(
        base_model_id=colqwen["base_id"],
        base_revision=colqwen["base_revision"],
        adapter_model_id=colqwen["id"],
        adapter_revision=colqwen["revision"],
        device="cuda",
        num_workers=0,
    )
    timings["model_load_seconds"] = time.perf_counter() - stage_started

    stage_started = time.perf_counter()
    passage_embeddings = _encode_with_backoff(
        "p1_02r_colqwen25_passages",
        retriever.forward_passages,
        LazyPageImages(image_paths),
        cache_dir / "colqwen25_passage_embeddings.pt",
        [2, 1],
        batch_sizes,
        commit,
    )
    timings["passage_encoding_seconds"] = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    query_embeddings = _encode_with_backoff(
        "p1_02r_colqwen25_queries",
        retriever.forward_queries,
        [row["query_text"] for row in selected_queries],
        cache_dir / "colqwen25_query_embeddings.pt",
        [8, 4, 2],
        batch_sizes,
        commit,
    )
    timings["query_encoding_seconds"] = time.perf_counter() - stage_started

    stage_started = time.perf_counter()
    score_rows = []
    for query_embedding in query_embeddings:
        scores = retriever.get_scores(
            [query_embedding],
            passage_embeddings,
            batch_size=calibration["visual_score_batch_size"],
        )[0].float().cpu()
        if len(scores) != len(selected_pages) or not bool(torch.isfinite(scores).all()):
            raise RuntimeError("P1-02R bounded calibration produced invalid visual scores")
        score_rows.append(scores)
    timings["visual_scoring_seconds"] = time.perf_counter() - stage_started
    candidate_scores = torch.stack(score_rows)
    score_path = cache_dir / "colqwen25_all_corpus_sample_scores.pt"
    _atomic_torch_save(candidate_scores, score_path)
    commit()
    peak_memory_allocated_bytes = int(torch.cuda.max_memory_allocated())
    del retriever, passage_embeddings, query_embeddings, candidate_scores, score_rows
    _clear_cuda()
    timings["total_seconds"] = time.perf_counter() - total_started

    projection = project_full_cost_from_calibration(
        timings,
        sample_queries=len(selected_queries),
        sample_pages=len(selected_pages),
        full_queries=protocol["dataset"]["expected_queries"],
        full_pages=protocol["dataset"]["expected_pages"],
    )
    return {
        "schema_version": 1,
        "status": "complete",
        "calibration_only": True,
        "full_extraction_started": False,
        "decision": "requires_human_cost_review",
        "protocol_id": PROTOCOL_ID,
        "protocol_status": protocol["status"],
        "source_commit": source_commit,
        "image_definition_sha256": image_definition_sha256,
        "protocol_config_sha256": protocol_config_sha256,
        "function_call_id": function_call_id,
        "source_protocol_sha256": source_protocol_sha256,
        "source_run_root": str(source_run_root),
        "dataset": {
            "id": dataset["id"],
            "revision": dataset["revision"],
            "full_queries": protocol["dataset"]["expected_queries"],
            "full_pages": protocol["dataset"]["expected_pages"],
            "sample_queries": len(selected_queries),
            "sample_pages": len(selected_pages),
        },
        "sample": {
            "selection": calibration["sample_selection"],
            "query_ids": [row["query_id"] for row in selected_queries],
            "page_ids": [str(row["page_id"]) for row in selected_pages],
        },
        "candidate_pool": {
            "method": CANDIDATE_METHOD,
            "membership_rule": calibration["membership_rule"],
            "candidate_pairs": len(selected_queries) * len(selected_pages),
            "visual_score_batch_size": calibration["visual_score_batch_size"],
            "qrels_used": False,
        },
        "retrievers_changed": False,
        "retriever_contract_sha256": retriever_contract_sha256,
        "batch_sizes": batch_sizes,
        "timings": timings,
        "projection": projection,
        "calibration_score_cache": {
            "path": str(score_path),
            "sha256": _file_sha256(score_path),
            "shape": [len(selected_queries), len(selected_pages)],
            "scope": "calibration_sample_only_not_full_scores",
        },
        "peak_memory_allocated_bytes": peak_memory_allocated_bytes,
        **gpu_metadata,
    }
