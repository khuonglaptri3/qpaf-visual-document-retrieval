from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from scripts import vidoseek_p1_02r
from scripts.extract_vidore_baseline import EXPANDED_DEPTHS, INITIAL_DEPTHS


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "vidoseek_p1_02r.yaml"
AUDIT_PATH = ROOT / "artifacts" / "vidoseek_p1_02r_coverage_audit.json"


def test_protocol_records_cpu_audit_pass_and_prepares_calibration_only() -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)

    assert protocol["classification"] == "post_hoc"
    assert protocol["status"] == "cpu_audit_passed_cost_calibration_prepared"
    assert protocol["authorization"]["local_integration"] == {
        "scope": "local_integration_and_cpu_audit_preparation_only",
        "approved_by": "user",
        "approved_on": "2026-08-30",
        "approval_text": (
            "Approve P1-02R all-corpus protocol for local integration and CPU-audit "
            "preparation only. Do not execute Modal"
        ),
    }
    assert protocol["authorization"]["cpu_audit_execution"] == {
        "scope": "p1_02r_cpu_coverage_audit_only",
        "approved_by": "user",
        "approved_on": "2026-08-30",
        "approval_text": (
            "Approve execution of the P1-02R CPU-only coverage audit on Modal. "
            "Do not run GPU"
        ),
    }
    assert protocol["authorization"]["cost_calibration_preparation"] == {
        "scope": "local_code_tests_and_command_only",
        "approved_by": "user",
        "approved_on": "2026-08-30",
        "approval_text": (
            "Record the P1-02R CPU-audit PASS and prepare a bounded L4 "
            "cost-calibration command locally. Do not execute Modal or GPU"
        ),
    }
    assert protocol["retrievers"]["changed"] is False
    environment = yaml.safe_load((ROOT / "configs" / "environment.yaml").read_text(encoding="utf-8"))
    retriever_contract = {name: environment[name] for name in ["bm25", "models"]}
    expected_hash = hashlib.sha256(
        json.dumps(retriever_contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert protocol["retrievers"]["contract_fields"] == ["bm25", "models"]
    assert protocol["retrievers"]["contract_sha256"] == expected_hash
    assert protocol["coverage_audit_result"]["status"] == "PASS"
    assert protocol["coverage_audit_result"]["artifact_sha256"] == hashlib.sha256(
        AUDIT_PATH.read_bytes()
    ).hexdigest()
    assert protocol["cost_calibration"] == {
        "status": "prepared_not_executed",
        "function_name": "calibrate-vidoseek-p1-02r-cost",
        "gpu_if_approved": "L4",
        "query_limit": 8,
        "page_limit": 512,
        "candidate_pairs": 4096,
        "visual_score_batch_size": 128,
        "sample_selection": "systematic_floor_indices_over_frozen_order",
        "membership_rule": "every_sampled_page_for_every_sampled_query",
        "qrels_used": False,
        "output_artifact_path": "artifacts/vidoseek_p1_02r_l4_cost_calibration.json",
        "result_scope": "cost_projection_only_not_score_extraction",
    }
    assert protocol["execution"]["modal_allowed"] is False
    assert protocol["execution"]["modal_execution_scope"] == "none"
    assert protocol["execution"]["allowed_modal_function"] is None
    assert protocol["execution"]["prepared_modal_function"] == (
        "calibrate-vidoseek-p1-02r-cost"
    )
    assert protocol["execution"]["modal_code_preparation_allowed"] is True
    assert protocol["execution"]["cpu_audit_entrypoint_preparation_allowed"] is True
    assert protocol["execution"]["cost_calibration_entrypoint_preparation_allowed"] is True
    assert protocol["execution"]["cpu_audit_execution_allowed"] is False
    assert protocol["execution"]["cost_calibration_execution_allowed"] is False
    assert protocol["execution"]["gpu_execution_allowed"] is False
    assert protocol["execution"]["prior_l4_approval_reused"] is False
    assert protocol["execution"]["cpu_audit_execution_approval_required"] is False
    assert protocol["execution"]["cost_calibration_execution_approval_required"] is True
    assert protocol["execution"]["gpu_execution_approval_required"] is True


def test_protocol_preserves_frozen_p1_02_depths_and_strict_coverage_gate() -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)

    assert INITIAL_DEPTHS == {"stage1": 200, "bm25": 100, "dense": 100}
    assert EXPANDED_DEPTHS == {"stage1": 300, "bm25": 200, "dense": 200}
    assert protocol["candidate_pool"]["method"] == "all_corpus"
    assert protocol["candidate_pool"]["expected_candidate_pairs"] == 1_142 * 5_385
    assert protocol["coverage_gate"] == {
        "minimum_relevant_pair_coverage": 0.95,
        "maximum_queries_with_zero_relevant_candidates": 0,
        "qrels_use": "post_candidate_coverage_audit_and_evaluation_only",
    }


def test_all_corpus_builder_is_query_independent_and_accepts_no_scores_or_qrels() -> None:
    assert list(inspect.signature(vidoseek_p1_02r.build_all_corpus_candidates).parameters) == [
        "query_ids",
        "page_ids",
    ]
    query_ids = np.asarray(["q1", "q0"])
    page_ids = np.asarray(["p2", "p0", "p1"])

    candidates = vidoseek_p1_02r.build_all_corpus_candidates(query_ids, page_ids)

    assert [pages.tolist() for pages in candidates] == [[0, 1, 2], [0, 1, 2]]
    assert not np.shares_memory(candidates[0], candidates[1])


def test_all_corpus_pool_covers_every_relevant_page_present_in_the_corpus() -> None:
    query_ids = np.asarray(["q0", "q1"])
    page_ids = np.asarray(["p0", "p1", "p2"])
    assert "candidates" not in inspect.signature(
        vidoseek_p1_02r.audit_all_corpus_coverage
    ).parameters

    result = vidoseek_p1_02r.audit_all_corpus_coverage(
        query_ids,
        page_ids,
        {("q0", "p2"): 1.0, ("q1", "p0"): 1.0},
        dataset_id="synthetic",
    )

    assert result["coverage"] == 1.0
    assert result["queries_with_zero_relevant_candidates"] == 0
    assert result["mean_candidates"] == 3.0
    assert result["decision"] == "p1_02r_coverage_gate_passes"
    assert result["candidate_generation_used_qrels"] is False


def test_all_corpus_audit_keeps_gate_red_when_a_qrel_page_is_absent() -> None:
    query_ids = np.asarray(["q0"])
    page_ids = np.asarray(["p0", "p1"])

    result = vidoseek_p1_02r.audit_all_corpus_coverage(
        query_ids,
        page_ids,
        {("q0", "missing"): 1.0},
        dataset_id="synthetic",
    )

    assert result["coverage"] == 0.0
    assert result["zero_relevant_query_ids"] == ["q0"]
    assert result["decision"] == "p1_02r_coverage_gate_fails"


def test_persisted_audit_uses_prepared_page_ids_without_score_caches(tmp_path: Path) -> None:
    source_protocol_sha256 = "a" * 64
    volume_root = tmp_path / "vol"
    run_root = (
        volume_root
        / "score_extraction"
        / "vidoseek"
        / source_protocol_sha256
        / "full"
    )
    first_document = "b" * 40
    second_document = "c" * 40
    page_ids = [f"{first_document}_1", "d" * 40 + "_1", f"{second_document}_1"]
    preparation_path = run_root / "prepared_corpus" / "_PREPARED.json"
    preparation_path.parent.mkdir(parents=True)
    preparation_path.write_text(
        json.dumps(
            {
                "status": "complete",
                "page_count": len(page_ids),
                "pages": [{"page_id": page_id} for page_id in page_ids],
            }
        ),
        encoding="utf-8",
    )

    dataset_root = volume_root / "datasets" / "vidoseek" / "revision"
    dataset_root.mkdir(parents=True)
    annotation_path = dataset_root / "vidoseek.json"
    annotation_path.write_text(
        json.dumps(
            {
                "examples": [
                    {
                        "uid": f"{first_document}_0",
                        "query": "first",
                        "meta_info": {
                            "file_name": f"{first_document}.pdf",
                            "reference_page": [1],
                        },
                    },
                    {
                        "uid": f"{second_document}_0",
                        "query": "second",
                        "meta_info": {
                            "file_name": f"{second_document}.pdf",
                            "reference_page": [1],
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    dataset_config = {
        "datasets": [
            {
                "key": "vidoseek",
                "id": "Qiuchen-Wang/ViDoSeek",
                "revision": "revision",
                "local_dir": str(dataset_root),
                "qrels_metadata": {
                    "annotation_file_sha256": hashlib.sha256(
                        annotation_path.read_bytes()
                    ).hexdigest()
                },
                "discovery_extraction": {"annotation_file": annotation_path.name},
            }
        ]
    }
    protocol = copy.deepcopy(vidoseek_p1_02r.load_protocol(PROTOCOL_PATH))
    protocol["frozen_parent"]["extraction_protocol_sha256"] = source_protocol_sha256
    protocol["dataset"]["revision"] = "revision"
    protocol["dataset"]["expected_queries"] = 2
    protocol["dataset"]["expected_pages"] = 3
    protocol["candidate_pool"]["candidates_per_query"] = 3
    protocol["candidate_pool"]["expected_candidate_pairs"] = 6

    result = vidoseek_p1_02r.audit_persisted_p1_02r_coverage(
        dataset_config,
        protocol,
        volume_root,
        source_protocol_sha256,
    )

    assert result["status"] == "complete"
    assert result["gpu_used"] is False
    assert result["candidate_pairs"] == 6
    assert result["candidate_pool_contract"] == {
        "method": "all_corpus",
        "membership_rule": "every_prepared_corpus_page_for_every_query",
        "ordering": "prepared_corpus_marker_order",
        "candidates_per_query": 3,
        "candidate_pairs": 6,
    }
    assert result["coverage"] == 1.0
    assert result["queries_with_zero_relevant_candidates"] == 0
    assert result["decision"] == "p1_02r_coverage_gate_passes"
    assert not (run_root / "cache").exists()


def test_completed_cpu_audit_and_unapproved_gpu_calibration_are_blocked() -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)

    with pytest.raises(RuntimeError, match="CPU audit is complete"):
        vidoseek_p1_02r.require_cpu_audit_execution_approval(protocol)
    with pytest.raises(RuntimeError, match="cost-calibration execution is not approved"):
        vidoseek_p1_02r.require_cost_calibration_execution_approval(protocol)


def test_only_the_explicit_l4_calibration_state_opens_the_execution_guard() -> None:
    protocol = copy.deepcopy(vidoseek_p1_02r.load_protocol(PROTOCOL_PATH))
    protocol["status"] = "approved_l4_cost_calibration_execution_only"
    protocol["cost_calibration"]["status"] = "approved_for_execution"
    protocol["execution"].update(
        {
            "modal_allowed": True,
            "modal_execution_scope": "l4_cost_calibration_only",
            "allowed_modal_function": "calibrate-vidoseek-p1-02r-cost",
            "cost_calibration_execution_allowed": True,
            "gpu_execution_allowed": True,
            "cost_calibration_execution_approval_required": False,
            "gpu_execution_approval_required": False,
        }
    )

    vidoseek_p1_02r.require_cost_calibration_execution_approval(protocol)


def test_persisted_audit_rejects_a_non_parent_protocol_path(tmp_path: Path) -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)

    with pytest.raises(ValueError, match="must match the frozen P1-02 parent"):
        vidoseek_p1_02r.audit_persisted_p1_02r_coverage(
            {"datasets": []},
            protocol,
            tmp_path,
            "a" * 64,
        )


def test_protocol_validation_rejects_gpu_authorization() -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)
    protocol["execution"]["gpu_execution_allowed"] = True

    with pytest.raises(ValueError, match="execution.gpu_execution_allowed"):
        vidoseek_p1_02r.validate_protocol(protocol)


def test_recorded_cpu_audit_artifact_matches_every_frozen_gate() -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)

    artifact = vidoseek_p1_02r.validate_recorded_cpu_audit(protocol, AUDIT_PATH)

    assert artifact["coverage"] == 1.0
    assert artifact["selected_relevant_pairs"] == artifact["relevant_pairs"] == 1_142
    assert artifact["missing_relevant_pairs"] == 0
    assert artifact["queries_with_zero_relevant_candidates"] == 0
    assert artifact["gpu_used"] is False
    assert artifact["candidate_generation_used_qrels"] is False


def test_cost_calibration_sampling_is_systematic_bounded_and_qrel_free() -> None:
    assert vidoseek_p1_02r.systematic_sample_indices(10, 4).tolist() == [0, 2, 5, 7]
    with pytest.raises(ValueError, match="no larger"):
        vidoseek_p1_02r.systematic_sample_indices(3, 4)

    records = vidoseek_p1_02r._query_records_without_qrels(
        {
            "examples": [
                {"uid": "q2", "query": "second", "meta_info": {}},
                {"uid": "q1", "query": "first", "meta_info": {}},
            ]
        }
    )
    assert [row["query_id"] for row in records] == ["q1", "q2"]


def test_cost_projection_is_componentwise_and_explicitly_not_a_result() -> None:
    projection = vidoseek_p1_02r.project_full_cost_from_calibration(
        {
            "model_load_seconds": 10.0,
            "passage_encoding_seconds": 20.0,
            "query_encoding_seconds": 5.0,
            "visual_scoring_seconds": 40.0,
            "total_seconds": 80.0,
        },
        sample_queries=2,
        sample_pages=4,
        full_queries=4,
        full_pages=8,
    )

    assert projection["sample_candidate_pairs"] == 8
    assert projection["full_candidate_pairs"] == 32
    assert projection["projected_components"] == {
        "fixed_and_model_load_seconds": 10.0,
        "passage_encoding_seconds": 40.0,
        "query_encoding_seconds": 10.0,
        "visual_scoring_seconds": 160.0,
        "other_measured_overhead_seconds": 5.0,
    }
    assert projection["projected_total_gpu_seconds"] == 225.0
    assert projection["interpretation"] == (
        "cost_review_input_only_not_a_full_extraction_result"
    )


def test_cost_calibration_runner_keeps_frozen_extractor_untouched() -> None:
    parameters = inspect.signature(
        vidoseek_p1_02r.run_bounded_cost_calibration
    ).parameters
    source = inspect.getsource(vidoseek_p1_02r.run_bounded_cost_calibration)

    assert "query_limit" not in parameters
    assert "page_limit" not in parameters
    assert "qrels" not in parameters
    assert "run_extraction" not in source
    assert "parse_annotations" not in source
    assert "systematic_sample_indices" in source
    assert "ColQwen25Retriever" in source
    assert '"qrels_used": False' in source
