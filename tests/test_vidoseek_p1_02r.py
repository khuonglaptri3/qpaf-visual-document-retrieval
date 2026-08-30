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


def test_protocol_approves_local_integration_only_and_locks_unchanged_retrievers() -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)

    assert protocol["classification"] == "post_hoc"
    assert protocol["status"] == "approved_local_integration_only"
    assert protocol["authorization"]["local_integration"] == {
        "scope": "local_integration_and_cpu_audit_preparation_only",
        "approved_by": "user",
        "approved_on": "2026-08-30",
        "approval_text": (
            "Approve P1-02R all-corpus protocol for local integration and CPU-audit "
            "preparation only. Do not execute Modal"
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
    assert protocol["execution"]["modal_allowed"] is False
    assert protocol["execution"]["modal_code_preparation_allowed"] is True
    assert protocol["execution"]["cpu_audit_entrypoint_preparation_allowed"] is True
    assert protocol["execution"]["cpu_audit_execution_allowed"] is False
    assert protocol["execution"]["gpu_execution_allowed"] is False
    assert protocol["execution"]["prior_l4_approval_reused"] is False
    assert protocol["execution"]["explicit_execution_approval_required"] is True


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


def test_cpu_audit_execution_remains_blocked() -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)

    with pytest.raises(RuntimeError, match="CPU-audit execution is not approved"):
        vidoseek_p1_02r.require_cpu_audit_execution_approval(protocol)


def test_persisted_audit_rejects_a_non_parent_protocol_path(tmp_path: Path) -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)

    with pytest.raises(ValueError, match="must match the frozen P1-02 parent"):
        vidoseek_p1_02r.audit_persisted_p1_02r_coverage(
            {"datasets": []},
            protocol,
            tmp_path,
            "a" * 64,
        )


def test_protocol_validation_rejects_modal_authorization() -> None:
    protocol = vidoseek_p1_02r.load_protocol(PROTOCOL_PATH)
    protocol["execution"]["modal_allowed"] = True

    with pytest.raises(ValueError, match="must not authorize Modal"):
        vidoseek_p1_02r.validate_protocol(protocol)
