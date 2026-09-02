import hashlib
import json
import multiprocessing as mp
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest
import yaml

import oracle_study.vidoseek_p1_02r_oracle as safeguards
import oracle_study.vidoseek_p1_02r_sharded as sharded


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "vidoseek_p1_02r_oracle_w7_v1.yaml"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parquet_contract(path: Path) -> dict:
    parquet = pq.ParquetFile(path)
    return {
        "bytes": path.stat().st_size,
        "rows": parquet.metadata.num_rows,
        "row_groups": parquet.metadata.num_row_groups,
        "byte_sha256": _sha256(path),
        "columns": [field.name for field in parquet.schema_arrow],
        "column_types": {field.name: str(field.type) for field in parquet.schema_arrow},
    }


def _make_fixture_bundle(tmp_path: Path) -> Path:
    protocol = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    protocol["status"] = safeguards.PREPARED_STATUS
    authorization = protocol["authorization"]
    authorization.pop("performance_probe_execution", None)
    authorization.pop("replacement_performance_probe_execution", None)
    authorization.pop("performance_probe_pass_recording", None)
    authorization.pop("sharded_wrapper_preparation", None)
    protocol.pop("performance_probe_result", None)
    protocol.pop("full_w7_runtime_resource_review", None)
    protocol.pop("sharded_wrapper", None)
    protocol.pop("full_page_calibration", None)
    protocol["performance_probe"].update(
        {
            "attempt_marker_produced": False,
            "output_manifest_produced": False,
            "command_currently_authorized": False,
        }
    )
    protocol["execution_readiness"].update(
        {
            "ready_for_performance_probe_execution_approval": True,
            "performance_probe_runtime_measured": False,
            "performance_probe_authorized": False,
            "performance_probe_executed": False,
            "full_oracle_protocol_wrapper_exists": False,
            "next_gate": "separate_human_performance_probe_execution_approval",
        }
    )
    for field in [
        "query_sharded_resume_contract_exists",
        "exact_semantic_equivalence_tests_exist",
        "ready_for_full_page_calibration_approval",
        "full_page_calibration_authorized",
        "full_page_calibration_executed",
    ]:
        protocol["execution_readiness"].pop(field, None)
    protocol["execution"] = {field: False for field in protocol["execution"]}
    for index, source in enumerate(protocol["implementation_contract"]["source_files"]):
        source_path = tmp_path / source["path"]
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(f"# fixture source {index}\n", encoding="utf-8")
        source["sha256"] = _text_sha256(source_path)

    artifact_dir = tmp_path / "artifacts" / "bundle"
    artifact_dir.mkdir(parents=True)
    score_path = artifact_dir / "retrieval_scores.parquet"
    audit_path = artifact_dir / "candidate_audit.parquet"
    manifest_path = artifact_dir / "extraction_manifest.json"
    review_path = tmp_path / "artifacts" / "integrity_review.json"

    score_frame = pd.DataFrame(
        {
            "dataset": ["fixture"] * 8,
            "query_id": ["q0"] * 4 + ["q1"] * 4,
            "page_id": [f"p{index}" for index in range(4)] * 2,
            "source": ["fixture"] * 8,
            "relevance": [1.0, 0.0, 0.0, 0.0] * 2,
            "bm25_score": [index / 7 for index in range(8)],
            "dense_score": [(7 - index) / 7 for index in range(8)],
            "stage1_score": [0.5] * 8,
            "visual_score": [0.25] * 8,
            "branch_ranks": ["{}"] * 8,
        }
    )
    score_frame.to_parquet(score_path, index=False)
    audit_frame = pd.DataFrame(
        {
            "dataset": ["fixture", "fixture"],
            "query_id": ["q0", "q1"],
            "relevant_total": [1, 1],
            "relevant_selected": [1, 1],
            "coverage": [1.0, 1.0],
            "candidate_count": [4, 4],
        }
    )
    audit_frame.to_parquet(audit_path, index=False)

    score_contract = _parquet_contract(score_path)
    score_contract.update(
        {
            "path": score_path.relative_to(tmp_path).as_posix(),
            "content_sha256": "f" * 64,
            "queries": 2,
            "pages_per_query": 4,
            "coverage": 1.0,
            "missing_relevant_pairs": 0,
            "queries_with_zero_relevant_candidates": 0,
        }
    )
    audit_contract = _parquet_contract(audit_path)
    audit_contract["path"] = audit_path.relative_to(tmp_path).as_posix()

    manifest = {
        "artifacts": {
            "retrieval_scores.parquet": {
                "bytes": score_contract["bytes"],
                "rows": score_contract["rows"],
                "sha256": score_contract["byte_sha256"],
                "content_sha256": score_contract["content_sha256"],
            },
            "candidate_audit.parquet": {
                "bytes": audit_contract["bytes"],
                "rows": audit_contract["rows"],
                "sha256": audit_contract["byte_sha256"],
            },
        }
    }
    _write_json(manifest_path, manifest)
    review = {
        "status": "PASS",
        "checks": {"fixture_contract": True},
        "contract": {
            "rows_checked_each_score_file": score_contract["rows"],
            "queries": score_contract["queries"],
            "pages_per_query": score_contract["pages_per_query"],
            "coverage": score_contract["coverage"],
            "missing_relevant_pairs": 0,
            "queries_with_zero_relevant_candidates": 0,
            "full_score_produced": False,
        },
        "boundaries": {
            "frozen_p1_02_status": "BLOCKED",
            "p1_03_authorized": False,
        },
        "payloads": manifest["artifacts"],
    }
    _write_json(review_path, review)

    score_contract.update(
        {
            "manifest_path": manifest_path.relative_to(tmp_path).as_posix(),
            "manifest_bytes": manifest_path.stat().st_size,
            "manifest_sha256": _sha256(manifest_path),
            "integrity_review_path": review_path.relative_to(tmp_path).as_posix(),
            "integrity_review_bytes": review_path.stat().st_size,
            "integrity_review_sha256": _sha256(review_path),
        }
    )
    protocol["input_bundle"]["retrieval_scores"] = score_contract
    protocol["input_bundle"]["candidate_audit"] = audit_contract
    protocol["planned_outputs"]["immutable_output_dir"] = (
        "artifacts/fixture_oracle_output"
    )
    protocol["performance_probe"]["output_manifest_path"] = (
        "artifacts/fixture_probe/run_manifest.json"
    )
    protocol["run_manifest_contract"]["path"] = protocol["performance_probe"][
        "output_manifest_path"
    ]

    protocol_path = tmp_path / "configs" / PROTOCOL_PATH.name
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_text(
        yaml.safe_dump(protocol, sort_keys=False),
        encoding="utf-8",
    )
    return protocol_path


def _valid_manifest() -> dict:
    return {
        "schema_version": 1,
        "status": "PASS",
        "classification": "engineering_performance_probe_not_result",
        "protocol_id": safeguards.PROTOCOL_ID,
        "protocol_sha256": "a" * 64,
        "source_commit": "b" * 40,
        "attempt_marker_sha256": "c" * 64,
        "completed_at": "2026-09-01T00:00:00+00:00",
        "environment": {
            "device": "cpu",
            "thread_limits": {name: "1" for name in safeguards.CPU_THREAD_ENV},
        },
        "preflight": {
            "actual_relevance_loaded": False,
            "oracle_executed": False,
            "scientific_result_produced": False,
        },
        "probe_contract": {
            "query_indices": [0, 570, 1141],
            "page_limits": [128, 256, 512],
            "bootstrap_resamples": 100,
            "repetitions": 1,
            "max_case_candidate_rows": 1536,
            "max_concurrent_cases": 1,
            "cpu_thread_limit": 1,
            "per_case_timeout_seconds": 120,
            "ladder_timeout_seconds": 300,
            "actual_relevance_loaded": False,
            "synthetic_relevance_rule": (
                "first_and_middle_sampled_page_binary_relevant"
            ),
        },
        "timings": [
            {
                "queries": 3,
                "pages_per_query": page_limit,
                "candidate_rows": 3 * page_limit,
                "elapsed_seconds": 1.0,
            }
            for page_limit in [128, 256, 512]
        ],
        "boundaries": {
            "actual_relevance_loaded": False,
            "scientific_oracle_analysis_executed": False,
            "oracle_results_persisted": False,
            "full_w7_oracle_executed": False,
            "modal_or_gpu_used": False,
            "p1_03_authorized": False,
            "learned_qpaf_executed": False,
            "frozen_p1_02_status": "BLOCKED",
        },
    }


def _valid_attempt_marker() -> dict:
    return {
        "schema_version": 1,
        "status": "STARTED",
        "classification": "engineering_probe_attempt_not_result",
        "protocol_id": safeguards.PROTOCOL_ID,
        "protocol_sha256": "a" * 64,
        "approval_commit": "b" * 40,
        "started_at": "2026-09-02T00:00:00+00:00",
        "authorization": {
            "authorized_invocations": 1,
            "attempt_number": 1,
            "remaining_authorized_invocations_after_start": 0,
        },
        "boundaries": {
            "authorization_attempt_consumed": True,
            "automatic_retry_allowed": False,
            "actual_relevance_loaded": False,
            "scientific_oracle_analysis_executed": False,
            "oracle_results_persisted": False,
            "full_w7_oracle_executed": False,
            "modal_or_gpu_used": False,
            "p1_03_authorized": False,
            "learned_qpaf_executed": False,
            "frozen_p1_02_status": "BLOCKED",
        },
    }


def test_protocol_bound_preflight_accepts_exact_fixture_bundle(tmp_path: Path) -> None:
    protocol_path = _make_fixture_bundle(tmp_path)

    report = safeguards.protocol_bound_preflight(protocol_path)

    assert report["status"] == "PASS"
    assert report["rows"] == 8
    assert report["queries"] == 2
    assert report["pages_per_query"] == 4
    assert report["actual_relevance_loaded"] is False
    assert report["oracle_executed"] is False
    assert report["scientific_result_produced"] is False


def test_protocol_bound_preflight_rejects_changed_payload(tmp_path: Path) -> None:
    protocol_path = _make_fixture_bundle(tmp_path)
    protocol = safeguards.load_protocol(protocol_path)
    score_path = tmp_path / protocol["input_bundle"]["retrieval_scores"]["path"]
    with score_path.open("ab") as handle:
        handle.write(b"changed")

    with pytest.raises(RuntimeError, match="byte count"):
        safeguards.protocol_bound_preflight(protocol_path)


def test_recorded_probe_guard_is_closed_before_git_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = safeguards.load_protocol(PROTOCOL_PATH)

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "closed recorded state must not inspect an execution checkout"
        )

    monkeypatch.setattr(safeguards.subprocess, "run", fail_if_called)

    with pytest.raises(RuntimeError, match="not authorized"):
        safeguards.require_performance_probe_execution_approval(protocol, ROOT)


def test_prepared_sharded_execution_guards_are_closed() -> None:
    protocol = safeguards.load_protocol(PROTOCOL_PATH)

    with pytest.raises(RuntimeError, match="full-page calibration.*not authorized"):
        sharded.require_full_page_calibration_execution_approval(protocol, ROOT)
    with pytest.raises(RuntimeError, match="full W7.*not authorized"):
        sharded.require_full_w7_execution_approval(protocol, ROOT)


def test_probe_case_uses_only_synthetic_relevance() -> None:
    rows = []
    query_ids = ["q0", "q1", "q2"]
    for query_id in query_ids:
        for page in range(8):
            rows.append(
                {
                    "dataset": "fixture",
                    "query_id": query_id,
                    "page_id": f"p{page:02d}",
                    "source": "fixture",
                    "bm25_score": page / 7,
                    "dense_score": (7 - page) / 7,
                    "visual_score": 0.5,
                }
            )
    candidates = pd.DataFrame(rows)

    case = safeguards.build_probe_case(candidates, query_ids, page_limit=4)

    assert len(case) == 12
    assert case.groupby("query_id")["relevance"].sum().to_dict() == {
        "q0": 2.0,
        "q1": 2.0,
        "q2": 2.0,
    }
    assert case["stage1_score"].eq(0.0).all()
    assert case["branch_ranks"].eq("synthetic_probe_placeholder").all()
    with pytest.raises(ValueError, match="must not contain actual relevance"):
        safeguards.build_probe_case(case, query_ids, page_limit=2)


def test_immutable_manifest_writer_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "probe" / "run_manifest.json"
    first = _valid_manifest()
    safeguards.write_immutable_run_manifest(path, first)
    original = path.read_bytes()

    second = _valid_manifest()
    second["completed_at"] = "2026-09-01T00:01:00+00:00"
    with pytest.raises(FileExistsError):
        safeguards.write_immutable_run_manifest(path, second)

    assert path.read_bytes() == original


def test_attempt_marker_consumes_authorization_and_refuses_retry(
    tmp_path: Path,
) -> None:
    protocol_path = _make_fixture_bundle(tmp_path)
    protocol = safeguards.load_protocol(protocol_path)
    marker_path = tmp_path / protocol["performance_probe"]["attempt_marker_path"]
    marker = _valid_attempt_marker()
    safeguards.write_immutable_attempt_marker(marker_path, marker)

    with pytest.raises(FileExistsError, match="already consumed"):
        safeguards.protocol_bound_preflight(protocol_path)
    report = safeguards.protocol_bound_preflight(
        protocol_path,
        allow_consumed_attempt=True,
    )
    assert report["authorization_attempt_consumed"] is True
    with pytest.raises(FileExistsError):
        safeguards.write_immutable_attempt_marker(marker_path, marker)


def test_manifest_writer_rejects_scientific_result_fields(tmp_path: Path) -> None:
    manifest = _valid_manifest()
    manifest["environment"]["ndcg10"] = 0.5

    with pytest.raises(ValueError, match="ndcg10"):
        safeguards.write_immutable_run_manifest(
            tmp_path / "run_manifest.json",
            manifest,
        )


def test_timeout_terminates_worker() -> None:
    process = mp.get_context("spawn").Process(target=time.sleep, args=(10,))

    with pytest.raises(TimeoutError, match="exceeded"):
        safeguards.complete_process_with_timeout(process, timeout_seconds=0.2)

    assert not process.is_alive()


def test_cli_exposes_prepared_but_unauthorized_wrapper_entry_points() -> None:
    parser = safeguards.parser()
    assert (
        parser.parse_args(["preflight", "--protocol", "protocol.yaml"]).command
        == "preflight"
    )
    assert (
        parser.parse_args(["performance-probe", "--protocol", "protocol.yaml"]).command
        == "performance-probe"
    )
    assert (
        parser.parse_args(
            ["full-page-calibration", "--protocol", "protocol.yaml"]
        ).command
        == "full-page-calibration"
    )
    assert (
        parser.parse_args(["full-w7", "--protocol", "protocol.yaml"]).command
        == "full-w7"
    )
    with pytest.raises(SystemExit):
        parser.parse_args(["oracle", "--protocol", "protocol.yaml"])
