from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oracle_study.qpaf import run_qpaf_oracle
from scripts import run_vidoseek_exploratory24_w66 as frozen
from scripts import run_vidoseek_exploratory24_w66_optimized as study


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def prepared_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate prepared bytes before the final preparation commit exists."""
    monkeypatch.setattr(
        study.frozen.pilot.safeguards,
        "require_exact_git_execution_checkout",
        lambda *args, **kwargs: "fixture-commit",
    )


def synthetic_scores() -> pd.DataFrame:
    rng = np.random.default_rng(20260909)
    return pd.DataFrame(
        [
            {
                "dataset": "fixture",
                "query_id": f"q{query}",
                "page_id": f"p{page}",
                "source": "synthetic",
                "relevance": float((page + query) % 5 == 0),
                "bm25_score": rng.random(),
                "dense_score": rng.random(),
                "visual_score": rng.random(),
                "stage1_score": rng.random(),
                "branch_ranks": "{}",
            }
            for query in range(3)
            for page in range(8)
        ]
    )


def fixture_identity(order: list[tuple[str, str]]) -> dict:
    return study.build_run_identity(
        protocol_sha256="a" * 64,
        source_commit="b" * 40,
        retrieval_score_sha256="c" * 64,
        retrieval_score_content_sha256="d" * 64,
        query_order=order,
        pages_per_query=8,
        bootstrap_resamples=100,
    )


def test_live_config_is_closed_hash_pinned_and_resource_reviewed():
    config = study.read_json(ROOT / study.CONFIG_PATH)
    validated = study.validate_config(ROOT, config)
    proposal = validated["proposal"]
    calibration = validated["calibration"]
    assert proposal["status"] == study.PREPARATION_STATUS
    assert proposal["execution_authorized"] is False
    assert config["resource_budget_status"] == study.PREPARATION_STATUS
    assert config["proposed_wall_timeout_seconds"] == 7200
    assert config["approved_wall_timeout_seconds"] == 0
    assert config["invocations"] == 0
    assert config["authorization"] == {
        "protocol_adopted": False,
        "resource_budget_approved": False,
        "execution_authorized": False,
        "approved_by": None,
        "execution_actor": None,
        "approval_text": None,
        "approved_at": None,
    }
    assert (
        calibration["decision"] == "GO_PREPARE_EXACT_OPTIMIZED_FULL_W66_PROTOCOL_ONLY"
    )
    assert calibration["full_w66_execution_authorized"] is False


def test_frozen_queries_profiles_and_optimized_implementation_are_exact():
    queries = study.selected_queries(ROOT)
    profiles = study.get_profiles(study.GRID_NAME)
    assert len(queries) == 24
    assert frozen.canonical_query_hash(queries) == study.QUERY_LIST_SHA256
    assert profiles.shape == (66, 3)
    assert study.value_sha256(profiles.tolist()) == study.PROFILES_SHA256
    assert study.file_sha256(ROOT / study.OPTIMIZED_PATH) == study.OPTIMIZED_SHA256
    assert (
        study.file_sha256(ROOT / study.CALIBRATION_REVIEW_PATH)
        == study.CALIBRATION_REVIEW_SHA256
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("grid", "w7"),
        ("profile_count", 7),
        ("queries", 12),
        ("pages_per_query", 512),
        ("bootstrap_resamples", 100),
        ("proposed_wall_timeout_seconds", 3600),
        ("workers", 2),
        ("threads_per_library", 2),
        ("arrow_cpu_threads", 2),
        ("maximum_telemetry_gap_seconds", 10.0),
        ("automatic_retries", 1),
        ("previous_checkpoint_reuse_allowed", True),
    ],
)
def test_scope_drift_is_rejected(field, value):
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config[field] = value
    with pytest.raises(ValueError, match="scope drift"):
        study.validate_config(ROOT, config)


@pytest.mark.parametrize(
    "updates",
    [
        {"approved_wall_timeout_seconds": 7200},
        {"invocations": 1},
        {"resource_budget_status": study.APPROVED_STATUS},
    ],
)
def test_partial_approval_is_rejected(updates):
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config.update(updates)
    with pytest.raises(ValueError, match="authorization/resource state drift"):
        study.validate_config(ROOT, config)


def test_source_environment_and_calibration_drift_are_rejected():
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config["source_sha256"][study.SCRIPT_PATH] = "0" * 64
    with pytest.raises(ValueError, match="source hash drift"):
        study.validate_config(ROOT, config)
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config["environment"]["python"] = "0.0.0"
    with pytest.raises(ValueError, match="environment drift"):
        study.validate_config(ROOT, config)
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config["calibration_review_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="scope drift"):
        study.validate_config(ROOT, config)


def test_closed_run_refuses_before_validation_input_or_writes(tmp_path, monkeypatch):
    config = study.read_json(ROOT / study.CONFIG_PATH)
    monkeypatch.setattr(
        study, "validate_config", lambda *args: pytest.fail("validation reached")
    )
    monkeypatch.setattr(
        study.pq, "read_table", lambda *args, **kwargs: pytest.fail("input read")
    )
    with pytest.raises(PermissionError, match="approval pending"):
        study.run(tmp_path, config, "codex")
    assert list(tmp_path.iterdir()) == []


def test_live_preflight_is_read_only_and_does_not_create_attempt():
    config = study.read_json(ROOT / study.CONFIG_PATH)
    evidence = study.preflight(ROOT, config)
    assert evidence["status"] == "PASS"
    assert evidence["queries"] == 24
    assert evidence["candidate_pairs"] == 129240
    assert evidence["profile_count"] == 66
    assert evidence["actual_relevance_loaded"] is False
    assert evidence["w66_oracle_executed"] is False
    assert evidence["scientific_result_produced"] is False
    assert evidence["approved_wall_timeout_seconds"] == 0
    assert evidence["authorized_invocations"] == 0
    assert evidence["execution_authorized"] is False
    assert evidence["attempt_exists"] is False
    assert not (ROOT / study.OUTPUT_PATH).exists()


def test_optimized_integration_matches_frozen_oracle_exactly(tmp_path):
    scores = synthetic_scores()
    order = [("fixture", f"q{index}") for index in range(3)]
    rows, summary, timings, stats = study.evaluate_subset(
        scores,
        order,
        fixture_identity(order),
        tmp_path / "optimized",
        8,
        100,
    )
    expected_rows, expected_summary, _ = run_qpaf_oracle(
        scores, grids=("w66",), n_bootstrap=100
    )
    assert rows == expected_rows
    assert summary["grids"] == expected_summary["grids"]
    assert summary["candidate_oracle_implementation"] == "candidate_oracle_exact_fast"
    assert summary["phase1_decision"] == "NOT_APPLICABLE_EXPLORATORY_W66_SUBSET"
    assert len(timings) == 6
    assert stats == {
        "plan_reused": 0,
        "global_created": 3,
        "global_reused": 0,
        "selection_reused": 0,
        "query_created": 3,
        "query_reused": 0,
    }


def test_integration_calls_optimized_candidate_oracle(tmp_path, monkeypatch):
    calls = 0
    original = study.candidate_oracle_exact_fast

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(study, "candidate_oracle_exact_fast", counted)
    scores = synthetic_scores()
    order = [("fixture", f"q{index}") for index in range(3)]
    study.evaluate_subset(
        scores,
        order,
        fixture_identity(order),
        tmp_path / "optimized",
        8,
        100,
    )
    assert calls == 3


def test_complete_replay_preserves_checkpoint_bytes(tmp_path):
    scores = synthetic_scores()
    order = [("fixture", f"q{index}") for index in range(3)]
    checkpoint_root = tmp_path / "checkpoints"
    identity = fixture_identity(order)
    first = study.evaluate_subset(scores, order, identity, checkpoint_root, 8, 100)
    before = {
        path: path.read_bytes() for path in checkpoint_root.rglob("*") if path.is_file()
    }
    second = study.evaluate_subset(scores, order, identity, checkpoint_root, 8, 100)
    after = {
        path: path.read_bytes() for path in checkpoint_root.rglob("*") if path.is_file()
    }
    assert first[0] == second[0]
    assert first[1] == second[1]
    assert before == after
    assert second[3] == {
        "plan_reused": 1,
        "global_created": 0,
        "global_reused": 3,
        "selection_reused": 1,
        "query_created": 0,
        "query_reused": 3,
    }


def test_frozen_runner_checkpoints_are_rejected(tmp_path):
    scores = synthetic_scores()
    order = [("fixture", f"q{index}") for index in range(3)]
    checkpoint_root = tmp_path / "checkpoints"
    old_identity = frozen.build_run_identity(
        protocol_sha256="a" * 64,
        source_commit="b" * 40,
        retrieval_score_sha256="c" * 64,
        retrieval_score_content_sha256="d" * 64,
        query_order=order,
        pages_per_query=8,
        bootstrap_resamples=100,
    )
    frozen.evaluate_subset(scores, order, old_identity, checkpoint_root, 8, 100)
    with pytest.raises(ValueError, match="Expected w66_optimized_run_plan checkpoint"):
        study.evaluate_subset(
            scores,
            order,
            fixture_identity(order),
            checkpoint_root,
            8,
            100,
        )


def test_telemetry_cadence_checks_wall_and_monotonic_gaps():
    wall_gap, monotonic_gap = study.telemetry_gap_seconds(
        "2026-09-09T10:00:00+00:00",
        "2026-09-09T10:00:04+00:00",
        100.0,
        104.5,
    )
    assert wall_gap == 4.0
    assert monotonic_gap == 4.5
    study.enforce_telemetry_cadence(wall_gap, monotonic_gap, 5.0)
    with pytest.raises(RuntimeError, match="telemetry cadence exceeded"):
        study.enforce_telemetry_cadence(5.001, 1.0, 5.0)
    with pytest.raises(RuntimeError, match="telemetry cadence exceeded"):
        study.enforce_telemetry_cadence(1.0, 5.001, 5.0)


class DummyProcess:
    pid = 1234
    exitcode = 0

    def __init__(self, target, args):
        self.target = target
        self.args = args

    def is_alive(self):
        return False

    def terminate(self):
        pass

    def kill(self):
        pass

    def join(self, timeout=None):
        pass


class DummyContext:
    def Process(self, target, args):
        return DummyProcess(target, args)


@pytest.fixture
def approved_fixture(tmp_path, monkeypatch):
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config["source_sha256"] = {}
    config["resource_budget_status"] = study.APPROVED_STATUS
    config["approved_wall_timeout_seconds"] = study.PROPOSED_TIMEOUT_SECONDS
    config["invocations"] = 1
    config["authorization"] = {
        "protocol_adopted": True,
        "resource_budget_approved": True,
        "execution_authorized": True,
        "approved_by": "user",
        "execution_actor": "codex",
        "approval_text": "synthetic lifecycle fixture only",
        "approved_at": "fixture",
    }
    for name in study.frozen.pilot.safeguards.CPU_THREAD_ENV:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(
        study,
        "validate_config",
        lambda *args: {"live_commit": "e" * 40},
    )
    monkeypatch.setattr(study.mp, "get_context", lambda *args: DummyContext())
    monkeypatch.setattr(study.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        study,
        "host_snapshot",
        lambda _root, output: {
            "observed_at": "2026-09-09T00:00:00+00:00",
            "free_physical_bytes": 8_000_000_000,
            "total_physical_bytes": 16_000_000_000,
            "disk_free_bytes": 10_000_000_000,
            "output_exists": output.exists(),
        },
    )
    monkeypatch.setattr(
        study.resources,
        "process_identity",
        lambda *args: {"pid": 1, "create_time": 1.0},
    )
    monkeypatch.setattr(study.resources, "set_sleep_inhibition", lambda *args: True)
    sample = {
        "observed_at": "2026-09-09T00:00:00+00:00",
        "processes": [],
        "process_tree_private_bytes": 1,
        "free_physical_bytes": 8_000_000_000,
        "output_bytes": 1,
        "disk_free_bytes": 10_000_000_000,
    }
    monkeypatch.setattr(study.resources, "resource_sample", lambda *args: sample)
    return tmp_path, config


def write_worker_outputs(_root, _config, output, _parent_identity):
    per_query = {
        "classification": study.CLASSIFICATION,
        "rows": [{} for _ in range(24)],
    }
    summary = {"classification": study.CLASSIFICATION}
    for name, value in {
        "per_query.json": per_query,
        "summary.json": summary,
        "timings.json": {},
        "checkpoint_stats.json": {},
    }.items():
        study.frozen.pilot.sharded._write_json_atomic_create_once(output / name, value)
    study.frozen.pilot.sharded._write_json_atomic_create_once(
        output / "_WORKER_COMPLETE.json",
        {
            "status": "COMPLETE",
            "per_query_sha256": study.file_sha256(output / "per_query.json"),
            "summary_sha256": study.file_sha256(output / "summary.json"),
            "queries": 24,
        },
    )


def supervision_fixture():
    return {
        "samples": 2,
        "peak_process_tree_private_bytes": 1,
        "minimum_free_physical_bytes": 8_000_000_000,
        "maximum_observed_output_bytes": 1,
        "maximum_wall_gap_seconds": 1.0,
        "maximum_monotonic_gap_seconds": 1.0,
        "maximum_allowed_telemetry_gap_seconds": 5.0,
        "telemetry_cadence_passed": True,
        "worker_identity": {"pid": 1, "create_time": 1.0},
    }


def test_approved_synthetic_lifecycle_completes_once(approved_fixture, monkeypatch):
    root, config = approved_fixture
    monkeypatch.setattr(study, "worker", write_worker_outputs)

    def monitor(process, *_args):
        process.target(*process.args)
        return supervision_fixture()

    monkeypatch.setattr(study, "monitor_worker", monitor)
    manifest = study.read_json(study.run(root, config, "codex"))
    assert manifest["status"] == "COMPLETE"
    assert manifest["grid"] == "w66"
    assert manifest["profile_count"] == 66
    assert manifest["candidate_oracle_implementation"] == "candidate_oracle_exact_fast"
    assert manifest["exploratory_w66_executed"] is True
    assert manifest["formal_p1_03_executed"] is False
    assert manifest["remaining_authorized_invocations"] == 0
    with pytest.raises(FileExistsError):
        study.run(root, config, "codex")


def test_failed_synthetic_lifecycle_consumes_attempt(approved_fixture, monkeypatch):
    root, config = approved_fixture

    def fail(_process, *_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(study, "monitor_worker", fail)
    with pytest.raises(RuntimeError, match="boom"):
        study.run(root, config, "codex")
    output = root / study.OUTPUT_PATH
    assert (output / "_ATTEMPTED.json").is_file()
    assert (output / "_INCOMPLETE.json").is_file()
    assert not (output / "run_manifest.json").exists()
    with pytest.raises(FileExistsError):
        study.run(root, config, "codex")


def test_actor_and_thread_guards_refuse_before_attempt(approved_fixture, monkeypatch):
    root, config = approved_fixture
    with pytest.raises(PermissionError, match="approval pending"):
        study.run(root, config, "human")
    assert list(root.iterdir()) == []
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    with pytest.raises(RuntimeError, match="one numeric-library thread"):
        study.run(root, config, "codex")
    assert list(root.iterdir()) == []
