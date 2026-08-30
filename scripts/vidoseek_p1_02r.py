from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from scripts.extract_vidore_baseline import MINIMUM_COVERAGE
from scripts.vidoseek_dataset import parse_annotations


LOCAL_INTEGRATION_STATUS = "approved_local_integration_only"
PROTOCOL_ID = "vidoseek_p1_02r_all_corpus_v1"
CANDIDATE_METHOD = "all_corpus"
DATASET_KEY = "vidoseek"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def validate_protocol(protocol: dict[str, Any]) -> None:
    """Validate local integration approval without authorizing Modal execution."""
    if protocol.get("schema_version") != 1:
        raise ValueError("P1-02R schema_version must be 1")
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise ValueError(f"P1-02R protocol_id must be {PROTOCOL_ID}")
    if protocol.get("status") != LOCAL_INTEGRATION_STATUS:
        raise ValueError(f"P1-02R status must be {LOCAL_INTEGRATION_STATUS}")

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

    execution = protocol.get("execution")
    if not isinstance(execution, dict) or execution.get("modal_allowed") is not False:
        raise ValueError("P1-02R local integration must not authorize Modal execution")
    if execution.get("modal_code_preparation_allowed") is not True:
        raise ValueError("P1-02R must authorize only local Modal code preparation")
    if execution.get("cpu_audit_entrypoint_preparation_allowed") is not True:
        raise ValueError("P1-02R must authorize CPU-audit entry-point preparation")
    if execution.get("cpu_audit_execution_allowed") is not False:
        raise ValueError("P1-02R CPU-audit execution must remain disabled")
    if execution.get("gpu_execution_allowed") is not False:
        raise ValueError("P1-02R GPU execution must remain disabled")
    if execution.get("explicit_execution_approval_required") is not True:
        raise ValueError("P1-02R requires explicit execution approval")


def load_protocol(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("P1-02R protocol must be a YAML mapping")
    validate_protocol(value)
    return value


def require_cpu_audit_execution_approval(protocol: dict[str, Any]) -> None:
    validate_protocol(protocol)
    if protocol["execution"]["cpu_audit_execution_allowed"] is not True:
        raise RuntimeError("P1-02R CPU-audit execution is not approved")


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
