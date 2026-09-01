import hashlib
import inspect
import json
import unittest
from pathlib import Path

import numpy as np
import yaml

from oracle_study.constants import PREREGISTERED_THRESHOLDS, SCORE_COLUMNS, SEED
from oracle_study.profiles import W7
from oracle_study.qpaf import TOLERANCE, _candidate_oracle


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "vidoseek_p1_02r_oracle_w7_v1.yaml"
APPROVAL_TEXT = (
    "Approve creating and committing a separately versioned P1-02R post-hoc "
    "oracle/task-graph amendment using the verified local score bundle. Prepare "
    "the protocol and tests only. Do not execute oracle analysis, Modal/GPU work, "
    "or P1-03, and do not relabel frozen P1-02. Return the complete amendment diff "
    "and stop/go gates for review."
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

    def test_records_protocol_only_authorization_and_closed_execution(self) -> None:
        protocol = self.protocol
        self.assertEqual(protocol["protocol_id"], "vidoseek_p1_02r_oracle_w7_v1")
        self.assertEqual(protocol["task_id"], "P1-02R-O1")
        self.assertEqual(protocol["status"], "protocol_prepared_review_required")
        self.assertEqual(protocol["authorization"]["approval_text"], APPROVAL_TEXT)

        execution = protocol["execution"]
        self.assertTrue(execution)
        self.assertTrue(all(value is False for value in execution.values()))
        self.assertFalse(protocol["planned_outputs"]["produced"])
        self.assertFalse(
            protocol["execution_readiness"]["ready_for_execution_approval"]
        )
        self.assertEqual(
            protocol["execution_readiness"]["next_gate"],
            "review_protocol_diff_and_choose_preexecution_preparation",
        )

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
