import csv
import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "evidence" / "M1_FINAL" / "04_experiment_registry"
REGISTRY_PATH = REGISTRY_DIR / "experiment_registry.csv"
TRACEABILITY_PATH = REGISTRY_DIR / "traceability_matrix.csv"
ISSUE_LOG_PATH = REGISTRY_DIR / "issue_log.csv"
M16_REVISION_DIR = ROOT / "evidence" / "revisions" / "m1.6-001"
M18_REVISION_DIR = ROOT / "evidence" / "revisions" / "m1.8-001"

HISTORICAL_REGISTRY_DIGESTS = {
    "QPAF-REG-20260927-0001": "b31fbb5bed6201783d229cdc3f60585d6d7a54be2256f63ba525984cd73b220a",
    "QPAF-REG-20260927-0002": "02bbc436c2b6c98fdbbe9e8193620a1f40883507ad548380dee31e951bf71a0b",
    "QPAF-REG-20260927-0003": "dbbf42be382a73336db81584aac18fb7a02e36c69fd33268010e7069287b24da",
    "QPAF-REG-20260927-0004": "7262c4c6fabdc8211abec0a58fb1d04c6f9f8c3b21496526499c8623aca45534",
    "QPAF-REG-20260927-0005": "d296c38611995e382d4e2542a429c7974a03fee56ac9e14352acc653cffd8752",
    "QPAF-REG-20260927-0006": "c90845b1a4b2099ced113aff481844840a2cc5e051f6cbb315c02852e9d19f4c",
    "QPAF-REG-20260927-0007": "4fb14b5fd5e069ae9f1cd685114a2c5c1575c408e2f6396d0e6f3fe42d4757f4",
    "QPAF-REG-20260927-0008": "30b9a9a53395b36e52ff15931692e1579cbbf52ae8ad75e12c4163926505f8ff",
    "QPAF-REG-20260927-0009": "dfb5839143085f1f186874ee2f31a58b8c7fa284477c9bd4c98e300d8ab35357",
}

HISTORICAL_TRACE_DIGESTS = {
    "M17-TRC-001": "e1837aecc9a7d82474d08c1f68e8c863196b563a5ef1ecbb2578735685e195b0",
    "M17-TRC-002": "70708fe0b207acd4dade55d198dad6866a6b0c3e5c5446c213621ca14dc0ac43",
    "M17-TRC-003": "07086dfc376799ac09d222ea2683bf831dab482cfa91c5e2160ff4f24402f2a3",
    "M17-TRC-004": "c9b3bd96eb64c4d111895ba87eef4bc26688b4637d21a08711ed312d4d3e6399",
    "M17-TRC-005": "9d4249a206a26cfde6805302136343351410367edfd31c296e6e917c596a539e",
    "M17-TRC-006": "7e88590b3bdc12e04758b028280da01c085be520bc07c7d9b6bc86f3d88a9e08",
    "M17-TRC-007": "8284b031f106e8b314d86e5af5fd5557189b463a68fd382b5808f33206300c6d",
    "M17-TRC-008": "fd5ad58abe7e71d65b3e944e0bacddfc5774a9fc2baf5849f4eea0f715daa105",
    "M17-TRC-009": "8169a4a49c55dad6bdbb28395cba7d5e3e8d6970ebf3187afbfd5d5fef2256b1",
}

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


def row_digest(row):
    canonical = json.dumps(
        row,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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

    def test_post_merge_reconciliation_is_append_only_and_remains_fail_closed(self):
        _, registry_rows = read_csv(REGISTRY_PATH)
        _, trace_rows = read_csv(TRACEABILITY_PATH)
        _, issue_rows = read_csv(ISSUE_LOG_PATH)

        events = {row["registry_event_id"]: row for row in registry_rows}
        historical_events = {
            event_id: row_digest(events[event_id])
            for event_id in HISTORICAL_REGISTRY_DIGESTS
        }
        self.assertEqual(HISTORICAL_REGISTRY_DIGESTS, historical_events)

        reconciliation = {
            "QPAF-REG-20260928-0010": ("M1.4", "QPAF-REG-20260927-0003"),
            "QPAF-REG-20260928-0011": ("M1.5", "QPAF-REG-20260927-0004"),
            "QPAF-REG-20260928-0012": ("M1.6", "QPAF-REG-20260927-0005"),
            "QPAF-REG-20260928-0013": ("M1.8", "QPAF-REG-20260927-0007"),
            "QPAF-REG-20260928-0014": ("M1.7", "QPAF-REG-20260927-0006"),
        }
        self.assertGreaterEqual(len(registry_rows), 14)
        for event_id, (task_id, superseded_id) in reconciliation.items():
            row = events[event_id]
            self.assertEqual(task_id, row["task_id"])
            self.assertEqual(superseded_id, row["supersedes_event_id"])
            self.assertEqual("BLOCKED", row["registry_status"], row)
            self.assertNotIn(row["event_type"], {"AUTHORIZED", "STARTED"})

        for event_id in (
            "QPAF-REG-20260928-0010",
            "QPAF-REG-20260928-0012",
            "QPAF-REG-20260928-0013",
        ):
            self.assertEqual("NOT_RECORDED", events[event_id]["command"])

        self.assertEqual(
            "AMENDMENTS_REVIEWED_PARTIAL_NO_SIGNOFF",
            events["QPAF-REG-20260928-0011"]["review_status"],
        )
        m16_issues = split_issue_ids(events["QPAF-REG-20260928-0012"]["issue_ids"])
        self.assertIn("M17-ISS-013", m16_issues)
        self.assertIn("M17-ISS-014", m16_issues)
        self.assertEqual(
            "PACKAGE_HASH_VERIFIED_THRESHOLDS_PROVISIONAL",
            events["QPAF-REG-20260928-0013"]["review_status"],
        )

        trace_ids = [row["trace_id"] for row in trace_rows]
        self.assertEqual(len(trace_ids), len(set(trace_ids)))
        traces = {row["trace_id"]: row for row in trace_rows}
        historical_traces = {
            trace_id: row_digest(traces[trace_id]) for trace_id in HISTORICAL_TRACE_DIGESTS
        }
        self.assertEqual(HISTORICAL_TRACE_DIGESTS, historical_traces)

        self.assertTrue(
            {f"M17-TRC-{number:03d}" for number in range(10, 15)}.issubset(trace_ids)
        )

        issue_ids = {row["issue_id"] for row in issue_rows}
        self.assertTrue(
            {f"M17-ISS-{number:03d}" for number in range(11, 17)}.issubset(issue_ids)
        )

    def test_m16_evidence_integrity_failures_are_explicitly_blocked(self):
        manifest_fields, manifest_rows = read_csv(M16_REVISION_DIR / "hash_manifest.csv")
        self.assertEqual(["path", "size_bytes", "sha256"], manifest_fields)

        mismatches = []
        for row in manifest_rows:
            path = ROOT / row["path"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != row["sha256"]:
                mismatches.append(path.name)
        self.assertEqual(
            ["alias_manifest.csv", "duplicate_report.csv", "page_manifest.csv"],
            sorted(mismatches),
        )

        _, pages = read_csv(M16_REVISION_DIR / "page_manifest.csv")
        missing_sources = {
            row["source_path"] for row in pages if not (ROOT / row["source_path"]).exists()
        }
        self.assertEqual(5, len(missing_sources))

        _, issue_rows = read_csv(ISSUE_LOG_PATH)
        issues = {row["issue_id"]: row for row in issue_rows}
        self.assertIn("hash", issues["M17-ISS-013"]["finding"].lower())
        self.assertIn("source", issues["M17-ISS-014"]["finding"].lower())
        self.assertEqual("BLOCKED", issues["M17-ISS-013"]["status"])
        self.assertEqual("BLOCKED", issues["M17-ISS-014"]["status"])

    def test_m18_manifest_binds_all_four_payloads_by_size_and_hash(self):
        fields, rows = read_csv(M18_REVISION_DIR / "hash_manifest.csv")
        self.assertEqual(["path", "size_bytes", "sha256"], fields)
        self.assertEqual(4, len(rows))

        for row in rows:
            path = M18_REVISION_DIR / row["path"]
            payload = path.read_bytes()
            self.assertEqual(int(row["size_bytes"]), len(payload), path)
            self.assertEqual(row["sha256"], hashlib.sha256(payload).hexdigest(), path)


if __name__ == "__main__":
    unittest.main()
