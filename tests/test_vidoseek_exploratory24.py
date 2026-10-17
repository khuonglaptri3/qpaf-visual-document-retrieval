import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oracle_study.qpaf import run_qpaf_oracle
from scripts import run_vidoseek_exploratory24 as study


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_INDICES = [
    92,
    141,
    148,
    398,
    513,
    640,
    676,
    686,
    798,
    803,
    832,
    842,
    855,
    889,
    890,
    892,
    950,
    992,
    1034,
    1067,
    1082,
    1084,
    1093,
    1129,
]


@pytest.fixture(autouse=True)
def historical_execution_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate the completed run against its recorded source commit."""
    recorded = study.read_json(ROOT / study.CONFIG_PATH)["base_git_commit"]
    monkeypatch.setattr(study, "git_head", lambda _root: recorded)


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


def test_live_config_records_consumed_authorization_and_source_pins():
    config = study.read_json(ROOT / study.CONFIG_PATH)
    proposal = study.validate_config(ROOT, config)
    assert proposal["status"] == "FROZEN_SELECTION_EXECUTION_CLOSED"
    assert proposal["execution_authorized"] is False
    assert config["authorization"]["protocol_adopted"] is True
    assert config["authorization"]["execution_authorized"] is True
    assert config["authorization"]["approved_by"] == "user"
    assert config["authorization"]["execution_actor"] == "codex"
    manifest = study.read_json(ROOT / study.OUTPUT_PATH / "run_manifest.json")
    assert manifest["status"] == "COMPLETE"
    assert manifest["remaining_authorized_invocations"] == 0
    assert manifest["source_commit"] == config["base_git_commit"]


def test_frozen_selection_is_deterministic_and_excludes_original12():
    proposal = study.read_json(ROOT / study.PROPOSAL_PATH)
    selected = study.selected_queries(ROOT, proposal)
    assert [query["audit_index"] for query in selected] == EXPECTED_INDICES
    assert study.canonical_query_hash(selected) == study.QUERY_LIST_SHA256
    original = study.read_json(ROOT / study.ORIGINAL_PROPOSAL_PATH)
    original_indices = {
        query["audit_index"] for query in original["selection"]["queries"]
    }
    assert not original_indices.intersection(EXPECTED_INDICES)
    assert len({query["query_id"] for query in selected}) == 24


@pytest.mark.parametrize(
    "field,value",
    [
        ("queries", 12),
        ("pages_per_query", 512),
        ("total_wall_timeout_seconds", 21600),
        ("bootstrap_resamples", 100),
        ("workers", 2),
        ("threads_per_library", 2),
        ("invocations", 2),
        ("automatic_retries", 1),
        ("output_path", "runs/vidoseek_w7_exploratory12_v1"),
    ],
)
def test_scope_drift_rejected(field, value):
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config[field] = value
    with pytest.raises(ValueError, match="scope drift"):
        study.validate_config(ROOT, config)


def test_source_and_environment_drift_rejected():
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config["source_sha256"][study.SCRIPT_PATH] = "0" * 64
    with pytest.raises(ValueError, match="source hash drift"):
        study.validate_config(ROOT, config)
    config = study.read_json(ROOT / study.CONFIG_PATH)
    config["environment"]["python"] = "0.0.0"
    with pytest.raises(ValueError, match="environment drift"):
        study.validate_config(ROOT, config)


def test_closed_run_refuses_before_input_access_or_writes(tmp_path, monkeypatch):
    config = copy.deepcopy(study.read_json(ROOT / study.CONFIG_PATH))
    config["authorization"]["execution_authorized"] = False
    monkeypatch.setattr(
        study, "validate_config", lambda *args: pytest.fail("Input accessed")
    )
    with pytest.raises(PermissionError, match="pending"):
        study.run(tmp_path, config, "codex")
    assert list(tmp_path.iterdir()) == []


def test_worker_matches_existing_frozen_oracle_semantics(tmp_path, monkeypatch):
    scores = synthetic_scores()
    order = [("fixture", f"q{index}") for index in range(3)]
    proposal = {
        "selection": {
            "queries": [
                {"audit_index": index, "dataset": dataset, "query_id": query_id}
                for index, (dataset, query_id) in enumerate(order)
            ]
        },
        "input": {"retrieval_scores_path": "fixture.parquet"},
    }
    monkeypatch.setattr(study, "QUERY_COUNT", 3)
    monkeypatch.setattr(study, "PAGES_PER_QUERY", 4)
    monkeypatch.setattr(study, "BOOTSTRAP_RESAMPLES", 100)
    monkeypatch.setattr(
        study,
        "preflight",
        lambda *args: {
            "base_preflight": {
                "retrieval_score_sha256": "a" * 64,
                "retrieval_score_content_sha256": "b" * 64,
            }
        },
    )
    monkeypatch.setattr(study, "read_json", lambda *args: proposal)
    monkeypatch.setattr(study.pd, "read_parquet", lambda *args, **kwargs: scores)
    output = tmp_path / "output"
    output.mkdir()
    config = {"base_git_commit": "c" * 40}
    study.worker(tmp_path, config, output, "d" * 64)

    rows = json.loads((output / "per_query.json").read_text())["rows"]
    summary = json.loads((output / "summary.json").read_text())
    timings = json.loads((output / "timings.json").read_text())["timings"]
    expected_rows, expected_summary, _ = run_qpaf_oracle(
        scores, grids=("w7",), n_bootstrap=100
    )
    assert rows == expected_rows
    assert summary["grids"] == expected_summary["grids"]
    assert summary["classification"] == study.CLASSIFICATION
    assert summary["phase1_decision"] == "NOT_APPLICABLE_EXPLORATORY_SUBSET"
    assert summary["training_authorized"] is False
    assert len(timings) == 6


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
    config = copy.deepcopy(study.read_json(ROOT / study.CONFIG_PATH))
    config["source_sha256"] = {}
    config["authorization"] = {
        "protocol_adopted": True,
        "execution_authorized": True,
        "approved_by": "user",
        "execution_actor": "codex",
        "approval_text": "synthetic fixture only",
        "approved_at": "fixture",
    }
    for name in study.pilot.safeguards.CPU_THREAD_ENV:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(study, "validate_config", lambda *args: {})
    monkeypatch.setattr(study.mp, "get_context", lambda *args: DummyContext())
    monkeypatch.setattr(study.subprocess, "run", lambda *args, **kwargs: None)
    return tmp_path, config


def write_worker_outputs(_root, _config, output, _identity):
    for name, value in {
        "per_query.json": {"rows": [{} for _ in range(24)]},
        "summary.json": {},
        "timings.json": {},
        "preflight.json": {},
    }.items():
        study.pilot.sharded._write_json_atomic_create_once(output / name, value)


def test_approved_fixture_completes_once_and_hashes_outputs(
    approved_fixture, monkeypatch
):
    root, config = approved_fixture
    monkeypatch.setattr(study, "worker", write_worker_outputs)

    def complete(process, remaining):
        assert 0 < remaining <= study.TIMEOUT_SECONDS
        process.target(*process.args)

    monkeypatch.setattr(
        study.pilot.safeguards, "complete_process_with_timeout", complete
    )
    manifest_path = study.run(root, config, "codex")
    manifest = study.read_json(manifest_path)
    assert manifest["status"] == "COMPLETE"
    assert manifest["queries"] == 24
    assert manifest["remaining_authorized_invocations"] == 0
    assert set(manifest["artifact_sha256"]) == {
        "_ATTEMPTED.json",
        "per_query.json",
        "preflight.json",
        "resolved_config.json",
        "summary.json",
        "timings.json",
        "tracked_changes.patch",
    }
    with pytest.raises(FileExistsError):
        study.run(root, config, "codex")


@pytest.mark.parametrize("failure", [TimeoutError("fixture"), RuntimeError("fixture")])
def test_failure_is_incomplete_and_cannot_retry(approved_fixture, monkeypatch, failure):
    root, config = approved_fixture
    monkeypatch.setattr(
        study.pilot.safeguards,
        "complete_process_with_timeout",
        lambda *args: (_ for _ in ()).throw(failure),
    )
    with pytest.raises(type(failure), match="fixture"):
        study.run(root, config, "codex")
    output = root / study.OUTPUT_PATH
    incomplete = study.read_json(output / "_INCOMPLETE.json")
    assert incomplete["remaining_authorized_invocations"] == 0
    assert incomplete["completed_result_available"] is False
    assert not (output / "run_manifest.json").exists()
    with pytest.raises(FileExistsError):
        study.run(root, config, "codex")


def test_missing_worker_outputs_cannot_be_complete(approved_fixture, monkeypatch):
    root, config = approved_fixture
    monkeypatch.setattr(
        study.pilot.safeguards, "complete_process_with_timeout", lambda *args: None
    )
    with pytest.raises(RuntimeError, match="did not finish"):
        study.run(root, config, "codex")
    assert not (root / study.OUTPUT_PATH / "run_manifest.json").exists()


def test_wrong_actor_and_thread_settings_refuse_before_attempt(
    approved_fixture, monkeypatch
):
    root, config = approved_fixture
    config["authorization"]["execution_actor"] = "human"
    with pytest.raises(PermissionError):
        study.run(root, config, "codex")
    assert list(root.iterdir()) == []

    config["authorization"]["execution_actor"] = "codex"
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    with pytest.raises(RuntimeError, match="one thread"):
        study.run(root, config, "codex")
    assert list(root.iterdir()) == []
