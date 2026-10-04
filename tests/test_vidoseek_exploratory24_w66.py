import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oracle_study.qpaf import run_qpaf_oracle
from scripts import run_vidoseek_exploratory24_w66 as study


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def prepared_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests validate bytes without requiring the final preparation commit yet."""
    monkeypatch.setattr(
        study.pilot.safeguards,
        "require_exact_git_execution_checkout",
        lambda *args, **kwargs: None,
    )


def synthetic_scores() -> pd.DataFrame:
    rng = np.random.default_rng(20260820)
    return pd.DataFrame(
        [
            {
                "dataset": "fixture",
                "query_id": f"q{query}",
                "page_id": f"p{page}",
                "source": "synthetic",
                "relevance": float(page == (query + 1) % 4),
                "bm25_score": rng.random(),
                "dense_score": rng.random(),
                "visual_score": rng.random(),
                "stage1_score": rng.random(),
                "branch_ranks": "{}",
            }
            for query in range(3)
            for page in range(4)
        ]
    )


def fixture_identity(order: list[tuple[str, str]]) -> dict:
    return study.build_run_identity(
        protocol_sha256="a" * 64,
        source_commit="b" * 40,
        retrieval_score_sha256="c" * 64,
        retrieval_score_content_sha256="d" * 64,
        query_order=order,
        pages_per_query=4,
        bootstrap_resamples=100,
    )


def test_live_config_is_closed_and_hash_pinned():
    config = study.read_json(ROOT / study.CONFIG_PATH)
    proposal = study.validate_config(ROOT, config)
    assert proposal["status"] == "PREPARED_RESOURCE_REVIEW_REQUIRED_EXECUTION_CLOSED"
    assert proposal["execution_authorized"] is False
    assert config["resource_budget_status"] == study.RESOURCE_BUDGET_STATUS
    assert config["total_wall_timeout_seconds"] == 0
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


def test_frozen_queries_and_w66_profiles_are_exact():
    queries = study.selected_queries(ROOT)
    profiles = study.get_profiles(study.GRID_NAME)
    assert len(queries) == 24
    assert study.canonical_query_hash(queries) == study.QUERY_LIST_SHA256
    assert profiles.shape == (66, 3)
    assert len(np.unique(profiles, axis=0)) == 66
    assert np.allclose(profiles.sum(axis=1), 1.0, rtol=0.0, atol=1e-12)
    assert study.pilot.sharded._value_sha256(profiles.tolist()) == study.PROFILES_SHA256


@pytest.mark.parametrize(
    "field,value",
    [
        ("grid", "w7"),
        ("profile_count", 7),
        ("queries", 12),
        ("pages_per_query", 512),
        ("bootstrap_resamples", 100),
        ("workers", 2),
        ("threads_per_library", 2),
        ("automatic_retries", 1),
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
        {"total_wall_timeout_seconds": 1},
        {"invocations": 1},
        {"resource_budget_status": "APPROVED_FOR_ONE_INVOCATION"},
    ],
)
def test_partial_resource_approval_is_rejected(updates):
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config.update(updates)
    with pytest.raises(ValueError, match="authorization/resource state drift"):
        study.validate_config(ROOT, config)


def test_source_and_environment_drift_are_rejected():
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config["source_sha256"][study.SCRIPT_PATH] = "0" * 64
    with pytest.raises(ValueError, match="source hash drift"):
        study.validate_config(ROOT, config)
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config["environment"]["python"] = "0.0.0"
    with pytest.raises(ValueError, match="environment drift"):
        study.validate_config(ROOT, config)


def test_closed_run_refuses_before_validation_input_or_writes(tmp_path, monkeypatch):
    config = study.read_json(ROOT / study.CONFIG_PATH)
    monkeypatch.setattr(
        study, "validate_config", lambda *args: pytest.fail("validation reached")
    )
    monkeypatch.setattr(
        study.pd, "read_parquet", lambda *args, **kwargs: pytest.fail("input read")
    )
    with pytest.raises(PermissionError, match="approval pending"):
        study.run(tmp_path, config, "codex")
    assert list(tmp_path.iterdir()) == []


def test_live_preflight_is_read_only_and_not_a_result():
    config = study.read_json(ROOT / study.CONFIG_PATH)
    evidence = study.preflight(ROOT, config)
    assert evidence["status"] == "PASS"
    assert evidence["queries"] == 24
    assert evidence["candidate_pairs"] == 129240
    assert evidence["profile_count"] == 66
    assert evidence["actual_relevance_loaded"] is False
    assert evidence["w66_oracle_executed"] is False
    assert evidence["scientific_result_produced"] is False
    assert evidence["execution_authorized"] is False
    assert evidence["attempt_exists"] is False


def test_synthetic_evaluation_matches_frozen_oracle(tmp_path):
    scores = synthetic_scores()
    order = [("fixture", f"q{index}") for index in range(3)]
    rows, summary, timings, stats = study.evaluate_subset(
        scores,
        order,
        fixture_identity(order),
        tmp_path / "checkpoints",
        4,
        100,
    )
    expected_rows, expected_summary, _ = run_qpaf_oracle(
        scores, grids=("w66",), n_bootstrap=100
    )
    assert rows == expected_rows
    assert summary["grids"] == expected_summary["grids"]
    assert summary["classification"] == study.CLASSIFICATION
    assert summary["phase1_decision"] == "NOT_APPLICABLE_EXPLORATORY_W66_SUBSET"
    assert summary["training_authorized"] is False
    assert len(timings) == 6
    assert stats == {
        "plan_reused": 0,
        "global_created": 3,
        "global_reused": 0,
        "selection_reused": 0,
        "query_created": 3,
        "query_reused": 0,
    }


def test_complete_resume_preserves_checkpoint_bytes(tmp_path):
    scores = synthetic_scores()
    order = [("fixture", f"q{index}") for index in range(3)]
    checkpoint_root = tmp_path / "checkpoints"
    identity = fixture_identity(order)
    first = study.evaluate_subset(scores, order, identity, checkpoint_root, 4, 100)
    before = {
        path: path.read_bytes() for path in checkpoint_root.rglob("*") if path.is_file()
    }
    second = study.evaluate_subset(scores, order, identity, checkpoint_root, 4, 100)
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


def test_tampered_checkpoint_fails_closed(tmp_path):
    scores = synthetic_scores()
    order = [("fixture", f"q{index}") for index in range(3)]
    checkpoint_root = tmp_path / "checkpoints"
    identity = fixture_identity(order)
    study.evaluate_subset(scores, order, identity, checkpoint_root, 4, 100)
    path = checkpoint_root / "global/000000.json"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["payload"]["query_id"] = "tampered"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ValueError, match="content hash mismatch"):
        study.evaluate_subset(scores, order, identity, checkpoint_root, 4, 100)


class DummyProcess:
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
    config["resource_budget_status"] = "APPROVED_FOR_ONE_INVOCATION"
    config["total_wall_timeout_seconds"] = 30
    config["invocations"] = 1
    config["authorization"] = {
        "protocol_adopted": True,
        "resource_budget_approved": True,
        "execution_authorized": True,
        "approved_by": "user",
        "execution_actor": "codex",
        "approval_text": "synthetic fixture only",
        "approved_at": "fixture",
    }
    for name in study.pilot.safeguards.CPU_THREAD_ENV:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(study, "validate_config", lambda *args: {})
    monkeypatch.setattr(study, "git_head", lambda *args: "e" * 40)
    monkeypatch.setattr(study.mp, "get_context", lambda *args: DummyContext())
    monkeypatch.setattr(study.subprocess, "run", lambda *args, **kwargs: None)
    return tmp_path, config


def write_worker_outputs(_root, _config, output, _identity):
    for name, value in {
        "preflight.json": {},
        "per_query.json": {"rows": [{} for _ in range(24)]},
        "summary.json": {},
        "timings.json": {},
        "checkpoint_stats.json": {},
    }.items():
        study.pilot.sharded._write_json_atomic_create_once(output / name, value)


def test_approved_synthetic_lifecycle_completes_once(approved_fixture, monkeypatch):
    root, config = approved_fixture
    monkeypatch.setattr(study, "worker", write_worker_outputs)

    def complete(process, remaining):
        assert 0 < remaining <= 30
        process.target(*process.args)

    monkeypatch.setattr(
        study.pilot.safeguards, "complete_process_with_timeout", complete
    )
    manifest = study.read_json(study.run(root, config, "codex"))
    assert manifest["status"] == "COMPLETE"
    assert manifest["grid"] == "w66"
    assert manifest["profile_count"] == 66
    assert manifest["exploratory_w66_executed"] is True
    assert manifest["formal_p1_03_executed"] is False
    assert manifest["phase1_decision"] == "NOT_APPLICABLE_EXPLORATORY_W66_SUBSET"
    assert manifest["remaining_authorized_invocations"] == 0
    with pytest.raises(FileExistsError):
        study.run(root, config, "codex")


@pytest.mark.parametrize("failure", ["worker", "missing_output"])
def test_failed_synthetic_lifecycle_is_incomplete_and_cannot_retry(
    approved_fixture, monkeypatch, failure
):
    root, config = approved_fixture
    if failure == "worker":
        monkeypatch.setattr(
            study,
            "worker",
            lambda *args: (_ for _ in ()).throw(RuntimeError("boom")),
        )
    else:
        monkeypatch.setattr(study, "worker", lambda *args: None)

    def complete(process, _remaining):
        process.target(*process.args)

    monkeypatch.setattr(
        study.pilot.safeguards, "complete_process_with_timeout", complete
    )
    with pytest.raises(RuntimeError):
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
    with pytest.raises(RuntimeError, match="one thread"):
        study.run(root, config, "codex")
    assert list(root.iterdir()) == []
