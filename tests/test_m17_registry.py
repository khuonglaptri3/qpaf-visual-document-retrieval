import csv
import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "evidence" / "M1_FINAL" / "04_experiment_registry"
REGISTRY_PATH = REGISTRY_DIR / "experiment_registry.csv"
TRACEABILITY_PATH = REGISTRY_DIR / "traceability_matrix.csv"
ISSUE_LOG_PATH = REGISTRY_DIR / "issue_log.csv"

REQUIRED_DRAFT_FILES = {
    "experiment_registry.csv",
    "experiment_naming_rules.md",
    "test_classification.md",
    "append_only_policy.md",
    "traceability_matrix.csv",
    "evidence_audit.md",
    "issue_log.csv",
}

EXPECTED_REGISTRY_COLUMNS = [
    "registry_event_id",
    "experiment_id",
    "run_id",
    "event_type",
    "recorded_at_utc",
    "run_window_utc",
    "task_id",
    "owner",
    "actor",
    "purpose",
    "experiment_class",
    "evidence_class",
    "registry_status",
    "source_status",
    "method",
    "protocol_ref",
    "git_commit",
    "data_ref",
    "split_ref",
    "split_id",
    "split_sha256",
    "candidate_definition",
    "config_ref",
    "seed",
    "seed_purpose",
    "command",
    "runtime",
    "hardware",
    "resource_cost_cap",
    "authorization_ref",
    "authorization_manifest_ref",
    "authorization_manifest_sha256",
    "attempt_retry",
    "retry_of",
    "failure_reason",
    "output_ref",
    "output_sha256",
    "metrics_ref",
    "primary_metric",
    "primary_metric_value",
    "verifier",
    "verification_command",
    "review_status",
    "result_claim_scope",
    "issue_ids",
    "supersedes_event_id",
    "notes",
]

ALLOWED_REGISTRY_STATUSES = {
    "PLANNED",
    "AUTHORIZED",
    "STARTED",
    "PASS",
    "FAIL",
    "BLOCKED",
    "KILLED",
    "NOT_RUN",
    "SUPERSEDED",
}

ALLOWED_EXPERIMENT_CLASSES = {
    "governance",
    "unit_test",
    "integration_test",
    "smoke_test",
    "engineering_probe",
    "calibration",
    "data_audit",
    "score_extraction",
    "oracle_upper_bound",
    "learned_training",
    "learned_evaluation",
    "ablation",
    "external_evaluation",
    "system_test",
}

ALLOWED_EVIDENCE_CLASSES = {
    "governance_record",
    "non_scientific",
    "engineering_evidence",
    "scientific_upper_bound",
    "scientific_result",
    "system_evidence",
}


def read_csv(path: Path):
    if not path.is_file():
        raise AssertionError(f"Required CSV is missing: {path.relative_to(ROOT)}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def split_issue_ids(raw: str):
    if raw == "NA":
        return set()
    return {item.strip() for item in raw.split(";") if item.strip()}


class M17RegistryDraftTests(unittest.TestCase):
    def test_required_draft_artifacts_exist_without_final_signoff(self):
        present = {path.name for path in REGISTRY_DIR.iterdir() if path.is_file()}
        self.assertTrue(
            REQUIRED_DRAFT_FILES.issubset(present),
            f"Missing M1.7 Draft artifacts: {sorted(REQUIRED_DRAFT_FILES - present)}",
        )
        self.assertNotIn(
            "qa_signoff.md",
            present,
            "Draft package must not contain a Final-G1 QA sign-off",
        )

    def test_registry_schema_and_controlled_vocabularies_are_valid(self):
        fieldnames, rows = read_csv(REGISTRY_PATH)
        self.assertEqual(EXPECTED_REGISTRY_COLUMNS, fieldnames)
        self.assertGreaterEqual(len(rows), 9)

        event_ids = [row["registry_event_id"] for row in rows]
        self.assertEqual(len(event_ids), len(set(event_ids)))

        for row in rows:
            self.assertTrue(all(value not in ("", None) for value in row.values()), row)
            self.assertRegex(row["registry_event_id"], r"^QPAF-REG-\d{8}-\d{4}$")
            self.assertRegex(row["experiment_id"], r"^QPAF-M1_[0-9]+-[A-Z]{3}-\d{3}$")
            self.assertIn(row["registry_status"], ALLOWED_REGISTRY_STATUSES)
            self.assertIn(row["experiment_class"], ALLOWED_EXPERIMENT_CLASSES)
            self.assertIn(row["evidence_class"], ALLOWED_EVIDENCE_CLASSES)
            self.assertNotIn(row["event_type"], {"AUTHORIZED", "STARTED"})
            self.assertNotIn(row["registry_status"], {"AUTHORIZED", "STARTED"})
            if any(
                marker in {"UNKNOWN", "NOT_RECORDED", "PENDING"}
                for marker in row.values()
            ):
                self.assertNotEqual("NA", row["issue_ids"], row)

    def test_every_registry_issue_reference_resolves_to_an_open_issue(self):
        _, registry_rows = read_csv(REGISTRY_PATH)
        issue_fields, issue_rows = read_csv(ISSUE_LOG_PATH)
        self.assertEqual(
            [
                "issue_id",
                "opened_at_utc",
                "severity",
                "owner",
                "related_task",
                "related_experiment_id",
                "finding",
                "evidence",
                "status",
                "closure_criterion",
                "blocks",
                "reviewer",
            ],
            issue_fields,
        )
        issue_ids = {row["issue_id"] for row in issue_rows}
        self.assertEqual(len(issue_rows), len(issue_ids))
        self.assertTrue(
            all(value not in ("", None) for row in issue_rows for value in row.values())
        )

        referenced = set()
        for row in registry_rows:
            referenced.update(split_issue_ids(row["issue_ids"]))
        self.assertEqual(set(), referenced - issue_ids)
        self.assertTrue(
            {row["related_experiment_id"] for row in issue_rows}.issubset(
                {row["experiment_id"] for row in registry_rows}
            )
        )

    def test_traceability_covers_every_registered_experiment_and_real_paths_exist(self):
        _, registry_rows = read_csv(REGISTRY_PATH)
        trace_fields, trace_rows = read_csv(TRACEABILITY_PATH)
        self.assertEqual(
            [
                "trace_id",
                "experiment_id",
                "task_id",
                "method_ref",
                "config_ref",
                "git_commit",
                "data_ref",
                "data_hash",
                "output_ref",
                "output_hash",
                "verification_ref",
                "claim_scope",
                "trace_status",
                "issue_ids",
                "reviewer_note",
            ],
            trace_fields,
        )
        self.assertEqual(
            {row["experiment_id"] for row in registry_rows},
            {row["experiment_id"] for row in trace_rows},
        )

        sentinels = {"NA", "PENDING", "UNKNOWN", "NOT_RECORDED"}
        for row in trace_rows:
            self.assertTrue(all(value not in ("", None) for value in row.values()), row)
            for column in (
                "method_ref",
                "config_ref",
                "data_ref",
                "output_ref",
                "verification_ref",
            ):
                value = row[column]
                if value not in sentinels:
                    self.assertTrue((ROOT / value).exists(), f"Missing {column}: {value}")
            for column in ("data_hash", "output_hash"):
                value = row[column]
                if value not in sentinels:
                    self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", value), row)
                    path_column = "data_ref" if column == "data_hash" else "output_ref"
                    actual = hashlib.sha256((ROOT / row[path_column]).read_bytes()).hexdigest()
                    self.assertEqual(actual, value, row)

    def test_claim_boundaries_do_not_promote_oracle_or_software_checks(self):
        _, rows = read_csv(REGISTRY_PATH)
        oracle_rows = [row for row in rows if row["experiment_class"] == "oracle_upper_bound"]
        self.assertGreaterEqual(len(oracle_rows), 1)
        for row in oracle_rows:
            self.assertEqual("scientific_upper_bound", row["evidence_class"])
            self.assertEqual("oracle_upper_bound", row["result_claim_scope"])
            self.assertEqual("nDCG@10", row["primary_metric"])

        m12_rows = [row for row in rows if row["task_id"] == "M1.2"]
        self.assertGreaterEqual(len(m12_rows), 1)
        latest_m12 = max(m12_rows, key=lambda row: row["registry_event_id"])
        self.assertNotEqual("scientific_result", latest_m12["evidence_class"])
        self.assertNotEqual("learned_evaluation", latest_m12["experiment_class"])


if __name__ == "__main__":
    unittest.main()
