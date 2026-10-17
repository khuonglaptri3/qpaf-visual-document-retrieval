import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oracle_study import vidoseek_exploratory12 as pilot
from oracle_study.qpaf import run_qpaf_oracle


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def historical_execution_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate the completed run against its recorded source commit."""
    recorded = pilot.read_json(ROOT / pilot.CONFIG_PATH)["base_git_commit"]
    monkeypatch.setattr(pilot, "git_head", lambda _root: recorded)


def fixture_scores() -> pd.DataFrame:
    rng = np.random.default_rng(20260820)
    return pd.DataFrame(
        [
            {
                "dataset": "fixture",
                "query_id": f"q{q}",
                "page_id": f"p{p}",
                "source": "single",
                "relevance": float(p in {q, (q + 2) % 7}),
                "bm25_score": rng.random(),
                "dense_score": rng.random(),
                "visual_score": rng.random(),
                "stage1_score": rng.random(),
                "branch_ranks": "{}",
            }
            for q in range(5)
            for p in range(7)
        ]
    )


def test_subset_matches_monolithic_on_selected_queries_only(tmp_path: Path) -> None:
    scores = fixture_scores()
    selected = scores.loc[scores.query_id.isin(["q1", "q3", "q4"])].copy()
    order = [("fixture", q) for q in ["q1", "q3", "q4"]]
    identity = pilot.sharded.build_run_identity(
        protocol_id="fixture_subset",
        protocol_sha256="a" * 64,
        source_commit="b" * 40,
        retrieval_score_sha256="c" * 64,
        retrieval_score_content_sha256="d" * 64,
        query_order=order,
        pages_per_query=7,
        bootstrap_resamples=100,
    )
    rows, summary, timings = pilot.evaluate_subset(
        selected, order, identity, tmp_path / "checkpoints", 7, 100
    )
    expected_rows, expected_summary, _ = run_qpaf_oracle(
        selected, grids=("w7",), n_bootstrap=100
    )
    assert rows == expected_rows
    assert summary["grids"] == expected_summary["grids"]
    assert "discovery_gate" not in summary
    assert summary["phase1_decision"] == "NOT_APPLICABLE_EXPLORATORY_SUBSET"
    assert summary["training_authorized"] is False
    assert len(timings) == 6
    assert [t["pass"] for t in timings] == ["global"] * 3 + ["query_oracle"] * 3
    assert all(t["elapsed_seconds_including_checkpoint"] > 0 for t in timings)
    assert all(sum(counts.values()) == 3 for counts in summary["win_tie_loss"].values())


def test_missing_candidates_rejected(tmp_path: Path) -> None:
    scores = fixture_scores().iloc[:6]
    with pytest.raises(ValueError, match="expected 7"):
        pilot.sharded._validate_query_frame(scores, ("fixture", "q0"), 7)


def test_live_config_source_hashes_and_consumed_approval_match() -> None:
    config = pilot.read_json(ROOT / pilot.CONFIG_PATH)
    proposal = pilot.validate_config(ROOT, config)
    assert proposal["execution_authorized"] is False  # Historical draft remains intact.
    assert config["authorization"]["execution_authorized"] is True
    attempt = pilot.read_json(ROOT / pilot.OUTPUT_PATH / "_ATTEMPTED.json")
    manifest = pilot.read_json(
        ROOT / "runs/vidoseek_exploratory12_recovery_v1/run_manifest.json"
    )
    assert attempt["remaining_authorized_invocations"] == 0
    assert attempt["config_sha256"] == pilot.sharded._value_sha256(config)
    assert manifest["source_commit"] == config["base_git_commit"]


def test_draft_run_refuses_before_validation_or_writes(
    tmp_path: Path, monkeypatch
) -> None:
    config = pilot.read_json(ROOT / pilot.CONFIG_PATH)
    config["authorization"]["execution_authorized"] = False

    def forbidden(*args):
        pytest.fail("Closed approval must be checked before source/input access")

    monkeypatch.setattr(pilot, "validate_config", forbidden)
    with pytest.raises(PermissionError):
        pilot.run(tmp_path, config, "codex")
    assert list(tmp_path.iterdir()) == []


def test_source_drift_refuses() -> None:
    config = pilot.read_json(ROOT / pilot.CONFIG_PATH)
    config["source_sha256"]["src/oracle_study/qpaf.py"] = "0" * 64
    with pytest.raises(ValueError, match="source hash drift"):
        pilot.validate_config(ROOT, config)


def test_protocol_drift_refuses() -> None:
    config = pilot.read_json(ROOT / pilot.CONFIG_PATH)
    config["queries"] = 11
    with pytest.raises(ValueError, match="protocol drift: queries"):
        pilot.validate_config(ROOT, config)


def test_frozen_query_list_hash() -> None:
    proposal = pilot.read_json(ROOT / pilot.PROPOSAL_PATH)
    encoded = json.dumps(
        proposal["selection"]["queries"],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    assert hashlib.sha256(encoded).hexdigest() == pilot.QUERY_LIST_SHA256


def approved_fixture(monkeypatch) -> dict:
    config = copy.deepcopy(pilot.read_json(ROOT / pilot.CONFIG_PATH))
    config["source_sha256"] = {}
    config["authorization"] = {
        "protocol_adopted": True,
        "execution_authorized": True,
        "approved_by": "user",
        "execution_actor": "human",
        "approval_text": "synthetic test fixture only",
        "approved_at": "fixture",
    }
    for name in pilot.safeguards.CPU_THREAD_ENV:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(pilot, "validate_config", lambda root, config: {})
    monkeypatch.setattr(pilot.subprocess, "run", lambda *args, **kwargs: None)
    return config


def test_wrong_actor_refuses_before_attempt(tmp_path: Path, monkeypatch) -> None:
    config = approved_fixture(monkeypatch)
    with pytest.raises(PermissionError):
        pilot.run(tmp_path, config, "codex")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "failure",
    [TimeoutError("fixture timeout"), RuntimeError("fixture preflight failed")],
)
def test_failed_attempt_is_incomplete_and_cannot_retry(
    tmp_path: Path, monkeypatch, failure
) -> None:
    config = approved_fixture(monkeypatch)
    calls = []

    def fail_worker(process, remaining):
        assert 0 < remaining <= pilot.TIMEOUT_SECONDS
        assert (tmp_path / pilot.OUTPUT_PATH / "_ATTEMPTED.json").is_file()
        calls.append(remaining)
        raise failure

    monkeypatch.setattr(pilot.safeguards, "complete_process_with_timeout", fail_worker)
    with pytest.raises(type(failure), match="fixture"):
        pilot.run(tmp_path, config, "human")
    output = tmp_path / pilot.OUTPUT_PATH
    assert (
        pilot.read_json(output / "_INCOMPLETE.json")["remaining_authorized_invocations"]
        == 0
    )
    assert not (output / "run_manifest.json").exists()
    with pytest.raises(FileExistsError):
        pilot.run(tmp_path, config, "human")
    assert len(calls) == 1


def test_missing_worker_outputs_cannot_be_complete(tmp_path: Path, monkeypatch) -> None:
    config = approved_fixture(monkeypatch)
    monkeypatch.setattr(
        pilot.safeguards, "complete_process_with_timeout", lambda *args: None
    )
    with pytest.raises(RuntimeError, match="did not finish"):
        pilot.run(tmp_path, config, "human")
    assert not (tmp_path / pilot.OUTPUT_PATH / "run_manifest.json").exists()
