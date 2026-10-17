import hashlib
import inspect
import json
import math
import unittest
from pathlib import Path

import numpy as np
import yaml

from oracle_study.constants import PREREGISTERED_THRESHOLDS, SCORE_COLUMNS, SEED
from oracle_study.profiles import W7
from oracle_study.qpaf import TOLERANCE, _candidate_oracle
from oracle_study.vidoseek_p1_02r_oracle import (
    APPROVAL_COMMIT_PATHS,
    APPROVED_SAFEGUARD_COMMIT,
    EXECUTION_APPROVAL_TEXT,
    EXECUTION_COMMIT_RULE,
    EXECUTED_PROBE_COMMIT,
    FAILED_EXECUTION_APPROVAL_COMMIT,
    FAILED_PERFORMANCE_PROBE_COMMAND_CMD,
    FAILED_PYTHON_ERROR,
    FULL_PAGE_CALIBRATION_APPROVAL_COMMIT_PATHS,
    FULL_PAGE_CALIBRATION_APPROVAL_PARENT_COMMIT,
    FULL_PAGE_CALIBRATION_APPROVAL_TEXT,
    FULL_PAGE_CALIBRATION_APPROVED_STATUS,
    FULL_PAGE_CALIBRATION_COMMAND_CMD,
    FULL_W7_COMMAND_CMD,
    ORIGINAL_EXECUTION_APPROVAL_TEXT,
    ORIGINAL_PROBE_SCOPE,
    PREPARATION_APPROVAL_TEXT,
    PREFLIGHT_COMMAND_CMD,
    PROBE_SCORE_COLUMNS,
    PROBE_SCOPE,
    RECORDING_APPROVAL_TEXT,
    REPLACEMENT_APPROVAL_PARENT_COMMIT,
    REVIEW_HARDENING_APPROVAL_TEXT,
    SHARDED_PREPARATION_APPROVAL_TEXT,
    validate_probe_attempt_marker,
    validate_probe_run_manifest,
    validate_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "vidoseek_p1_02r_oracle_w7_v1.yaml"
APPROVAL_TEXT = (
    "Approve creating and committing a separately versioned P1-02R post-hoc "
    "oracle/task-graph amendment using the verified local score bundle. Prepare "
    "the protocol and tests only. Do not execute oracle analysis, Modal/GPU work, "
    "or P1-03, and do not relabel frozen P1-02. Return the complete amendment diff "
    "and stop/go gates for review."
)
FUTURE_PROBE_COMMAND = (
    'set "OMP_NUM_THREADS=1" && set "MKL_NUM_THREADS=1" && '
    'set "OPENBLAS_NUM_THREADS=1" && set "NUMEXPR_NUM_THREADS=1" && '
    'set "PYTHONUTF8=1" && set "PYTHONIOENCODING=utf-8" && '
    'set "PYTHONPATH=src" && '
    "C:\\Python313\\python.exe -m oracle_study.vidoseek_p1_02r_oracle "
    "performance-probe --protocol configs\\vidoseek_p1_02r_oracle_w7_v1.yaml"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class VidoseekP102ROracleProtocolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.protocol = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_records_failed_original_and_closes_replacement_probe(self) -> None:
        protocol = self.protocol
        self.assertEqual(protocol["protocol_id"], "vidoseek_p1_02r_oracle_w7_v1")
        self.assertEqual(protocol["task_id"], "P1-02R-O1")
        self.assertEqual(protocol["status"], FULL_PAGE_CALIBRATION_APPROVED_STATUS)
        self.assertEqual(protocol["authorization"]["approval_text"], APPROVAL_TEXT)
        self.assertEqual(
            protocol["authorization"]["preexecution_preparation"]["approval_text"],
            PREPARATION_APPROVAL_TEXT,
        )
        prior = protocol["authorization"]["performance_probe_execution"]
        self.assertEqual(prior["scope"], ORIGINAL_PROBE_SCOPE)
        self.assertEqual(prior["approval_text"], ORIGINAL_EXECUTION_APPROVAL_TEXT)
        self.assertEqual(prior["approved_safeguard_commit"], APPROVED_SAFEGUARD_COMMIT)
        self.assertEqual(prior["approval_commit"], FAILED_EXECUTION_APPROVAL_COMMIT)
        self.assertEqual(prior["authorized_invocations"], 1)
        self.assertEqual(prior["consumed_invocations"], 1)
        self.assertEqual(prior["remaining_authorized_invocations"], 0)
        self.assertFalse(prior["automatic_retry_allowed"])
        failure = prior["failure_record"]
        self.assertEqual(failure["failure_stage"], "cpython_preinitialization")
        self.assertEqual(failure["error"], FAILED_PYTHON_ERROR)
        self.assertEqual(
            failure["failed_command_cmd"], FAILED_PERFORMANCE_PROBE_COMMAND_CMD
        )
        self.assertEqual(failure["pythonutf8_observed_value"], "1 ")
        for field in [
            "python_runtime_initialized",
            "project_module_imported",
            "attempt_marker_produced",
            "preflight_executed",
            "performance_probe_executed",
            "probe_manifest_produced",
            "oracle_result_produced",
        ]:
            self.assertFalse(failure[field], field)

        approval = protocol["authorization"]["replacement_performance_probe_execution"]
        self.assertEqual(approval["scope"], PROBE_SCOPE)
        self.assertEqual(approval["approval_text"], EXECUTION_APPROVAL_TEXT)
        self.assertEqual(
            approval["replaces_failed_approval_commit"],
            FAILED_EXECUTION_APPROVAL_COMMIT,
        )
        self.assertEqual(
            approval["approved_correction_base_commit"],
            REPLACEMENT_APPROVAL_PARENT_COMMIT,
        )
        self.assertFalse(approval["automatic_retry_under_prior_authorization"])
        self.assertEqual(approval["execution_commit_rule"], EXECUTION_COMMIT_RULE)
        self.assertEqual(
            approval["approval_commit_changed_paths"], APPROVAL_COMMIT_PATHS
        )
        self.assertEqual(approval["authorized_invocations"], 1)
        self.assertEqual(approval["consumed_invocations"], 1)
        self.assertEqual(approval["remaining_authorized_invocations"], 0)
        self.assertFalse(approval["automatic_retry_allowed"])
        self.assertEqual(approval["execution_actor"], "human")
        self.assertEqual(approval["outcome"], "PASS")

        recording = protocol["authorization"]["performance_probe_pass_recording"]
        self.assertEqual(
            recording["scope"],
            "local_probe_pass_recording_and_runtime_resource_review_only",
        )
        self.assertEqual(recording["approval_text"], RECORDING_APPROVAL_TEXT)
        self.assertFalse(recording["execution_authorized"])

        execution = protocol["execution"]
        self.assertTrue(execution)
        calibration_fields = {
            "full_page_calibration_allowed",
            "full_page_calibration_output_write_allowed",
            "checkpoint_writes_allowed",
        }
        for field, value in execution.items():
            self.assertEqual(value, field in calibration_fields, field)
        self.assertFalse(protocol["planned_outputs"]["produced"])
        readiness = protocol["execution_readiness"]
        self.assertTrue(readiness["protocol_bound_preflight_exists"])
        self.assertTrue(readiness["immutable_run_manifest_writer_exists"])
        self.assertTrue(readiness["performance_probe_entrypoint_exists"])
        self.assertFalse(readiness["ready_for_performance_probe_execution_approval"])
        self.assertTrue(readiness["performance_probe_runtime_measured"])
        self.assertFalse(readiness["performance_probe_authorized"])
        self.assertTrue(readiness["performance_probe_executed"])
        self.assertTrue(readiness["full_oracle_protocol_wrapper_exists"])
        self.assertTrue(readiness["query_sharded_resume_contract_exists"])
        self.assertTrue(readiness["exact_semantic_equivalence_tests_exist"])
        self.assertFalse(readiness["ready_for_full_page_calibration_approval"])
        self.assertTrue(readiness["full_page_calibration_authorized"])
        self.assertFalse(readiness["full_page_calibration_executed"])
        self.assertFalse(readiness["all_corpus_runtime_measured"])
        self.assertFalse(readiness["ready_for_execution_approval"])
        self.assertEqual(
            readiness["next_gate"],
            "one_human_full_page_single_query_calibration_execution_then_review",
        )

        validate_protocol(protocol, ROOT)

    def test_preserves_frozen_parent_task_graph(self) -> None:
        graph = self.protocol["parent_task_graph"]
        self.assertEqual(graph["frozen_p1_02"]["status"], "BLOCKED")
        self.assertFalse(graph["frozen_p1_02"]["relabel_allowed"])
        self.assertEqual(graph["verified_recovery"]["status"], "PASS")
        self.assertFalse(graph["verified_recovery"]["full_score_produced"])
        self.assertEqual(graph["frozen_p1_03"]["status"], "BLOCKED")
        self.assertFalse(graph["frozen_p1_03"]["dependency_rewritten"])
        self.assertFalse(graph["frozen_p1_03"]["execution_authorized"])
        self.assertFalse(self.protocol["decision_gates"]["w7_alone_can_unblock_p1_03"])
        self.assertFalse(self.protocol["decision_gates"]["w7_alone_can_enter_phase_2"])

        tasks = (ROOT / "Tasks.md").read_text(encoding="utf-8")
        self.assertIn("### TASK-ID: P1-02R-O1", tasks)
        p1_02 = tasks.split("### TASK-ID: P1-02\n", 1)[1].split("### TASK-ID:", 1)[0]
        p1_03 = tasks.split("### TASK-ID: P1-03\n", 1)[1].split("### TASK-ID:", 1)[0]
        self.assertIn("**STATUS:** BLOCKED", p1_02)
        self.assertIn("**DEPENDENCIES:** P1-02", p1_03)
        self.assertIn("**STATUS:** BLOCKED", p1_03)

    def test_pins_the_verified_recovery_bundle_without_requiring_local_payload(
        self,
    ) -> None:
        graph = self.protocol["parent_task_graph"]["verified_recovery"]
        parent_config = ROOT / graph["config_path"]
        self.assertEqual(graph["config_sha256_basis"], "utf8_lf_bytes")
        self.assertEqual(text_sha256(parent_config), graph["config_sha256"])

        scores = self.protocol["input_bundle"]["retrieval_scores"]
        manifest_path = ROOT / scores["manifest_path"]
        review_path = ROOT / scores["integrity_review_path"]
        self.assertEqual(sha256(manifest_path), scores["manifest_sha256"])
        self.assertEqual(sha256(review_path), scores["integrity_review_sha256"])

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact = manifest["artifacts"]["retrieval_scores.parquet"]
        self.assertEqual(artifact["bytes"], scores["bytes"])
        self.assertEqual(artifact["rows"], scores["rows"])
        self.assertEqual(artifact["sha256"], scores["byte_sha256"])
        self.assertEqual(artifact["content_sha256"], scores["content_sha256"])

        audit = self.protocol["input_bundle"]["candidate_audit"]
        audit_artifact = manifest["artifacts"]["candidate_audit.parquet"]
        self.assertEqual(audit_artifact["bytes"], audit["bytes"])
        self.assertEqual(audit_artifact["rows"], audit["rows"])
        self.assertEqual(audit_artifact["sha256"], audit["byte_sha256"])

        review = json.loads(review_path.read_text(encoding="utf-8"))
        self.assertEqual(review["status"], "PASS")
        self.assertTrue(all(review["checks"].values()))
        self.assertEqual(review["contract"]["coverage"], scores["coverage"])
        self.assertEqual(review["contract"]["queries"], scores["queries"])
        self.assertEqual(
            review["contract"]["pages_per_query"], scores["pages_per_query"]
        )
        self.assertFalse(review["contract"]["full_score_produced"])

        expected_columns = list(SCORE_COLUMNS)
        expected_columns.insert(3, "source")
        self.assertEqual(scores["columns"], expected_columns)
        self.assertFalse(self.protocol["input_bundle"]["full_score_required"])
        self.assertFalse(self.protocol["input_bundle"]["heaven_preflight_eligible"])

    def test_records_closed_non_result_cpu_probe_bounds(self) -> None:
        probe = self.protocol["performance_probe"]
        self.assertEqual(probe["device"], "cpu")
        self.assertEqual(probe["grid"], "w7")
        self.assertEqual(probe["query_indices"], [0, 570, 1141])
        self.assertEqual(probe["page_limits"], [128, 256, 512])
        self.assertEqual(probe["max_case_candidate_rows"], 1536)
        self.assertEqual(probe["max_concurrent_cases"], 1)
        self.assertEqual(probe["cpu_thread_limit"], 1)
        self.assertEqual(probe["bootstrap_resamples"], 100)
        self.assertEqual(probe["repetitions"], 1)
        self.assertEqual(probe["per_case_timeout_seconds"], 120)
        self.assertEqual(probe["ladder_timeout_seconds"], 300)
        self.assertFalse(probe["actual_relevance_loaded"])
        self.assertFalse(probe["automatic_retry_allowed"])
        self.assertFalse(probe["command_currently_authorized"])
        self.assertTrue(probe["attempt_marker_produced"])
        self.assertTrue(probe["output_manifest_produced"])
        self.assertEqual(probe["future_command_cmd"], FUTURE_PROBE_COMMAND)
        self.assertEqual(
            self.protocol["preflight_contract"]["command"], PREFLIGHT_COMMAND_CMD
        )
        for assignment in [
            "OMP_NUM_THREADS=1",
            "MKL_NUM_THREADS=1",
            "OPENBLAS_NUM_THREADS=1",
            "NUMEXPR_NUM_THREADS=1",
            "PYTHONUTF8=1",
            "PYTHONIOENCODING=utf-8",
            "PYTHONPATH=src",
        ]:
            self.assertIn(f'set "{assignment}"', FUTURE_PROBE_COMMAND)
            self.assertNotIn(f"set {assignment} &&", FUTURE_PROBE_COMMAND)
        self.assertNotIn("relevance", PROBE_SCORE_COLUMNS)
        self.assertEqual(
            self.protocol["run_manifest_contract"]["write_mode"],
            "atomic_create_once_no_overwrite",
        )
        self.assertEqual(
            self.protocol["attempt_marker_contract"]["write_mode"],
            "atomic_create_once_no_overwrite",
        )
        self.assertTrue(
            self.protocol["attempt_marker_contract"][
                "consumes_authorization_before_preflight"
            ]
        )

    def test_pins_immutable_probe_pass_evidence(self) -> None:
        result = self.protocol["performance_probe_result"]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(
            result["classification"], "engineering_performance_probe_not_result"
        )
        self.assertEqual(result["executed_source_commit"], EXECUTED_PROBE_COMMIT)
        self.assertFalse(result["full_w7_runtime_measured"])
        self.assertFalse(result["scientific_result_produced"])

        marker_record = result["attempt_marker"]
        manifest_record = result["run_manifest"]
        marker_path = ROOT / marker_record["path"]
        manifest_path = ROOT / manifest_record["path"]
        for path, record in [
            (marker_path, marker_record),
            (manifest_path, manifest_record),
        ]:
            self.assertEqual(path.stat().st_size, record["bytes"])
            self.assertEqual(sha256(path), record["sha256"])
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for record in [marker_record, manifest_record]:
            self.assertIn(f"{record['path']} -text -diff", attributes)

        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_probe_attempt_marker(marker)
        validate_probe_run_manifest(manifest)
        self.assertEqual(marker["approval_commit"], EXECUTED_PROBE_COMMIT)
        self.assertEqual(manifest["source_commit"], EXECUTED_PROBE_COMMIT)
        self.assertEqual(marker["protocol_sha256"], result["executed_protocol_sha256"])
        self.assertEqual(
            manifest["protocol_sha256"], result["executed_protocol_sha256"]
        )
        self.assertEqual(manifest["attempt_marker_sha256"], marker_record["sha256"])
        self.assertEqual(
            [case["elapsed_seconds"] for case in manifest["timings"]],
            [0.6704216001089662, 3.7113504000008106, 13.628036600071937],
        )
        self.assertAlmostEqual(
            sum(case["elapsed_seconds"] for case in manifest["timings"]),
            result["case_elapsed_seconds_total"],
            places=12,
        )
        for field, value in manifest["boundaries"].items():
            if field != "frozen_p1_02_status":
                self.assertFalse(value, field)
        self.assertEqual(manifest["boundaries"]["frozen_p1_02_status"], "BLOCKED")

    def test_records_review_only_full_w7_resource_estimate(self) -> None:
        review = self.protocol["full_w7_runtime_resource_review"]
        manifest_path = (
            ROOT / self.protocol["performance_probe_result"]["run_manifest"]["path"]
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            review["measured_query_count"], manifest["timings"][0]["queries"]
        )
        self.assertEqual(
            review["measured_page_limits"],
            [case["pages_per_query"] for case in manifest["timings"]],
        )
        self.assertEqual(
            review["measured_case_seconds"],
            [case["elapsed_seconds"] for case in manifest["timings"]],
        )
        self.assertEqual(review["full_shape_queries"], manifest["preflight"]["queries"])
        self.assertEqual(
            review["full_shape_pages_per_query"],
            manifest["preflight"]["pages_per_query"],
        )
        pages = np.asarray(review["measured_page_limits"], dtype=float)
        seconds = np.asarray(review["measured_case_seconds"], dtype=float)
        local_exponents = np.log(seconds[1:] / seconds[:-1]) / math.log(2.0)
        fit_exponent, fit_intercept = np.polyfit(np.log(pages), np.log(seconds), 1)
        np.testing.assert_allclose(
            review["empirical_page_doubling_exponents"],
            local_exponents,
            rtol=0,
            atol=1e-12,
        )
        self.assertAlmostEqual(
            review["three_point_power_fit_exponent"], fit_exponent, places=12
        )

        query_scale = review["full_shape_queries"] / review["measured_query_count"]
        page_scale = review["full_shape_pages_per_query"] / pages[-1]
        derived = review["derived_single_worker_days"]
        expected = {
            "lower_local_exponent": (
                seconds[-1] * query_scale * page_scale ** min(local_exponents) / 86400
            ),
            "three_point_power_fit": (
                math.exp(fit_intercept)
                * review["full_shape_pages_per_query"] ** fit_exponent
                * query_scale
                / 86400
            ),
            "quadratic_log_complexity": (
                seconds[-1]
                * query_scale
                * page_scale**2
                * math.log(review["full_shape_pages_per_query"])
                / math.log(pages[-1])
                / 86400
            ),
            "upper_local_exponent": (
                seconds[-1] * query_scale * page_scale ** max(local_exponents) / 86400
            ),
        }
        for name, value in expected.items():
            self.assertAlmostEqual(derived[name], value, places=12, msg=name)
        self.assertEqual(review["estimate_status"], "derived_not_measured")
        self.assertEqual(
            review["recommendation"],
            "no_go_current_monolithic_single_worker_full_w7",
        )
        self.assertFalse(review["execution_authorized"])

    def test_records_sharded_wrapper_and_authorized_calibration(self) -> None:
        authorization = self.protocol["authorization"]["sharded_wrapper_preparation"]
        self.assertEqual(
            authorization["scope"],
            "local_query_sharded_resumable_wrapper_preparation_only",
        )
        self.assertEqual(
            authorization["approval_text"], SHARDED_PREPARATION_APPROVAL_TEXT
        )
        self.assertFalse(authorization["execution_authorized"])
        hardening = self.protocol["authorization"]["review_hardening"]
        self.assertEqual(
            hardening["scope"],
            "local_review_hardening_code_protocol_docs_and_tests_only",
        )
        self.assertEqual(hardening["approval_text"], REVIEW_HARDENING_APPROVAL_TEXT)
        self.assertFalse(hardening["execution_authorized"])
        calibration_approval = self.protocol["authorization"][
            "full_page_calibration_execution"
        ]
        self.assertEqual(
            calibration_approval["scope"],
            "one_human_p1_02r_o1_full_page_synthetic_cpu_calibration",
        )
        self.assertEqual(
            calibration_approval["approval_text"],
            FULL_PAGE_CALIBRATION_APPROVAL_TEXT,
        )
        self.assertEqual(calibration_approval["execution_actor"], "human")
        self.assertEqual(
            calibration_approval["approved_parent_commit"],
            FULL_PAGE_CALIBRATION_APPROVAL_PARENT_COMMIT,
        )
        self.assertEqual(
            calibration_approval["execution_commit_rule"],
            EXECUTION_COMMIT_RULE,
        )
        self.assertEqual(
            calibration_approval["approval_commit_changed_paths"],
            FULL_PAGE_CALIBRATION_APPROVAL_COMMIT_PATHS,
        )
        self.assertEqual(calibration_approval["authorized_invocations"], 1)
        self.assertEqual(calibration_approval["consumed_invocations"], 0)
        self.assertEqual(calibration_approval["remaining_authorized_invocations"], 1)
        self.assertFalse(calibration_approval["automatic_retry_allowed"])

        scores = self.protocol["input_bundle"]["retrieval_scores"]
        wrapper = self.protocol["sharded_wrapper"]
        self.assertEqual(wrapper["grid"], "w7")
        self.assertEqual(wrapper["expected_queries"], scores["queries"])
        self.assertEqual(wrapper["expected_pages_per_query"], scores["pages_per_query"])
        self.assertEqual(wrapper["input_row_groups"], scores["row_groups"])
        self.assertEqual(wrapper["input_query_chunk_size"], 8)
        self.assertEqual(
            wrapper["checkpoint_write_mode"],
            "atomic_create_once_no_overwrite",
        )
        self.assertEqual(
            wrapper["checkpoint_envelope"],
            {
                "schema_version": 1,
                "canonical_json_sha256": "required",
                "run_identity_sha256": "required",
                "input_query_sha256": "required_per_query",
            },
        )
        self.assertEqual(
            wrapper["resume_policy"],
            "reuse_existing_only_after_exact_identity_and_content_hash_validation",
        )
        self.assertEqual(
            wrapper["absent_expected_checkpoint_action"],
            "compute_once_in_canonical_pass",
        )
        self.assertEqual(
            wrapper["invalid_existing_or_unexpected_checkpoint_action"],
            "fail_closed_no_overwrite",
        )
        self.assertTrue(
            wrapper["phases"]["global_profile"][
                "reduce_across_all_queries_before_query_oracle"
            ]
        )
        self.assertTrue(wrapper["phases"]["query_oracle"]["checkpoint_per_query"])
        self.assertEqual(wrapper["phases"]["query_oracle"]["qpaf_max_sweeps"], 2)
        self.assertTrue(
            wrapper["phases"]["finalization"]["bootstrap_once_after_canonical_merge"]
        )
        self.assertEqual(
            wrapper["exact_semantic_equivalence"],
            {
                "reference": "frozen_run_qpaf_oracle_w7",
                "rows": "exact",
                "summary": "exact",
                "subgroups": "exact",
                "numeric_tolerance": 0.0,
            },
        )
        self.assertEqual(wrapper["full_w7_future_command_cmd"], FULL_W7_COMMAND_CMD)
        self.assertFalse(wrapper["command_currently_authorized"])

        calibration = self.protocol["full_page_calibration"]
        self.assertEqual(calibration["query_index"], 570)
        self.assertEqual(calibration["pages_per_query"], 5385)
        self.assertEqual(calibration["bootstrap_resamples"], 100)
        self.assertEqual(calibration["max_workers"], 1)
        self.assertEqual(calibration["cpu_thread_limit"], 1)
        self.assertEqual(calibration["hard_timeout_seconds"], 2700)
        self.assertFalse(calibration["actual_relevance_loaded"])
        self.assertFalse(calibration["automatic_retry_allowed"])
        self.assertEqual(
            calibration["future_command_cmd"], FULL_PAGE_CALIBRATION_COMMAND_CMD
        )
        self.assertTrue(calibration["command_currently_authorized"])

    def test_freezes_current_w7_oracle_semantics_and_source_files(self) -> None:
        contract = self.protocol["implementation_contract"]
        self.assertEqual(contract["source_sha256_basis"], "utf8_lf_bytes")
        for source in contract["source_files"]:
            self.assertEqual(
                text_sha256(ROOT / source["path"]),
                source["sha256"],
                source["path"],
            )

        design = self.protocol["oracle_design"]
        np.testing.assert_allclose(
            np.asarray(design["profiles"], dtype=float), W7, atol=1e-12
        )
        self.assertEqual(
            design["channel_order"], ["bm25_score", "dense_score", "visual_score"]
        )
        self.assertEqual(
            design["qpaf_max_sweeps"],
            inspect.signature(_candidate_oracle).parameters["max_sweeps"].default,
        )
        self.assertEqual(design["strict_improvement_tolerance"], TOLERANCE)
        self.assertEqual(
            design["global_and_qarf_profile_tie_policy"],
            "retain_earliest_w7_profile",
        )
        self.assertEqual(
            design["qpaf_profile_tie_policy"],
            "retain_current_assignment_without_strict_improvement",
        )
        self.assertFalse(design["renormalize_at_oracle_runtime"])
        self.assertFalse(
            design["qrels_used_for_candidate_construction_or_score_normalization"]
        )

        bootstrap = self.protocol["bootstrap"]
        self.assertEqual(bootstrap["seed"], SEED)
        self.assertEqual(bootstrap["resamples"], 10_000)

    def test_records_disjoint_w7_screening_gates_without_automatic_progression(
        self,
    ) -> None:
        thresholds = PREREGISTERED_THRESHOLDS["qpaf"]
        gates = self.protocol["decision_gates"]
        stop = gates["stop_learned_qpaf"]["mean_delta_qpaf_vs_qarf_ndcg_at_10"]
        self.assertEqual(stop["operator"], "<")
        self.assertEqual(
            stop["threshold"], thresholds["no_go_confirmation_mean_delta_ndcg10_below"]
        )

        review = gates["eligible_for_separate_w66_protocol_review"]
        self.assertEqual(review["mean_delta_qpaf_vs_qarf_ndcg_at_10"]["operator"], ">=")
        self.assertEqual(
            review["mean_delta_qpaf_vs_qarf_ndcg_at_10"]["threshold"],
            thresholds["discovery_mean_delta_ndcg10_min"],
        )
        self.assertEqual(
            review["bootstrap_ci95_lower"], {"operator": ">", "threshold": 0.0}
        )
        self.assertEqual(
            review["top_5pct_gain_share"],
            {"operator": "<", "threshold": thresholds["no_go_top_5pct_gain_share_min"]},
        )
        self.assertEqual(
            review["effect"], "human_review_only_not_execution_authorization"
        )


if __name__ == "__main__":
    unittest.main()
