import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from oracle_study import vidoseek_exploratory12 as pilot
from scripts import recover_vidoseek_exploratory12 as recovery
from test_vidoseek_exploratory12 import fixture_scores

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def historical_parent_execution_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep completed-parent validation bound to its recorded checkout."""
    recorded = pilot.read_json(ROOT / pilot.CONFIG_PATH)["base_git_commit"]
    monkeypatch.setattr(pilot, "git_head", lambda _root: recorded)


def test_live_recovery_pins_match_and_approved_attempt_is_consumed():
    config = recovery.read_json(ROOT / recovery.CONFIG_PATH)
    review = recovery.validate_config(ROOT, config)
    assert review["verified_query_checkpoints"] == 4
    assert config["authorization"]["execution_authorized"] is True
    attempt = recovery.read_json(ROOT / recovery.OUTPUT_PATH / "_ATTEMPTED.json")
    assert attempt["remaining_authorized_invocations"] == 0
    assert attempt["config_sha256"] == pilot.sharded._value_sha256(config)
    closed = recovery.read_json(
        ROOT
        / "runs/exploratory12_recovery_preparation_20260907/reviewed_closed_config.json"
    )
    with pytest.raises(PermissionError, match="pending"):
        recovery.require_approval(closed, "codex")


def test_closed_recovery_refuses_before_reads_or_writes(tmp_path, monkeypatch):
    config = recovery.read_json(ROOT / recovery.CONFIG_PATH)
    config["authorization"]["execution_authorized"] = False

    def forbidden(*args):
        pytest.fail("Closed recovery touched the inputs")

    monkeypatch.setattr(recovery, "validate_config", forbidden)
    with pytest.raises(PermissionError):
        recovery.run(tmp_path, config, "codex")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("new_queries", 7),
        ("total_wall_timeout_seconds", 43200),
        ("runner_sha256", "0" * 64),
        ("review_sha256", "0" * 64),
    ],
)
def test_recovery_drift_refuses(field, value):
    config = recovery.read_json(ROOT / recovery.CONFIG_PATH)
    config[field] = value
    with pytest.raises(ValueError, match="drift"):
        recovery.validate_config(ROOT, config)


@pytest.fixture
def interrupted_fixture(tmp_path, monkeypatch):
    """Build a genuine interrupted two-pass run on five tiny synthetic queries."""
    scores = fixture_scores()
    order = [("fixture", f"q{i}") for i in range(5)]
    monkeypatch.setattr(pilot, "QUERY_COUNT", 5)
    monkeypatch.setattr(pilot, "PAGES_PER_QUERY", 7)
    monkeypatch.setattr(pilot, "BOOTSTRAP_RESAMPLES", 100)
    monkeypatch.setattr(recovery, "INHERITED_QUERIES", 2)
    for name in pilot.safeguards.CPU_THREAD_ENV:
        monkeypatch.setenv(name, "1")
    parent = tmp_path / pilot.OUTPUT_PATH
    parent.mkdir(parents=True)
    scores.to_parquet(tmp_path / "scores.parquet", index=False)
    original = {"base_git_commit": "b" * 40, "environment": {"fixture": True}}
    recovery.write_json(parent / "resolved_config.json", original)
    proposal = {
        "selection": {"queries": [{"dataset": d, "query_id": q} for d, q in order]},
        "input": {"retrieval_scores_path": "scores.parquet"},
    }
    recovery.write_json(tmp_path / pilot.PROPOSAL_PATH, proposal)
    recovery.write_json(parent / "source_snapshot" / pilot.PROPOSAL_PATH, proposal)
    base = {
        "base_preflight": {
            "retrieval_score_sha256": "c" * 64,
            "retrieval_score_content_sha256": "d" * 64,
        }
    }
    identity = pilot.sharded.build_run_identity(
        protocol_id=pilot.PROTOCOL_ID,
        protocol_sha256=pilot.sharded._value_sha256(original),
        source_commit=original["base_git_commit"],
        retrieval_score_sha256="c" * 64,
        retrieval_score_content_sha256="d" * 64,
        query_order=order,
        pages_per_query=7,
        bootstrap_resamples=100,
    )
    expected_rows, expected_summary, _ = pilot.evaluate_subset(
        scores, order, identity, tmp_path / "uninterrupted", 7, 100
    )
    original_search = pilot.sharded._query_result_row

    def stop_third(frame, *args):
        if frame.query_id.iloc[0] == "q2":
            raise RuntimeError("fixture interruption")
        return original_search(frame, *args)

    monkeypatch.setattr(pilot.sharded, "_query_result_row", stop_third)
    with pytest.raises(RuntimeError, match="fixture interruption"):
        pilot.evaluate_subset(scores, order, identity, parent / "checkpoints", 7, 100)
    calls = []

    def count_new_search(frame, *args):
        query_id = frame.query_id.iloc[0]
        assert query_id not in {"q0", "q1"}, "Inherited query was recomputed"
        calls.append(query_id)
        return original_search(frame, *args)

    monkeypatch.setattr(pilot.sharded, "_query_result_row", count_new_search)
    monkeypatch.setattr(
        pilot.sharded,
        "_global_metrics",
        lambda *args: pytest.fail("Inherited Global metrics recomputed"),
    )
    monkeypatch.setattr(pilot, "preflight", lambda *args: base)
    monkeypatch.setattr(recovery, "preflight", lambda *args: base)
    review = {
        "artifact_sha256": recovery.inventory(parent),
        "run_identity_sha256": pilot.sharded._value_sha256(identity),
        "config_canonical_sha256": pilot.sharded._value_sha256(original),
    }
    monkeypatch.setattr(recovery, "validate_config", lambda *args: review)
    for relative in (recovery.SCRIPT_PATH, recovery.REVIEW_PATH):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture snapshot", encoding="utf-8")
    config = copy.deepcopy(recovery.read_json(ROOT / recovery.CONFIG_PATH))
    config["authorization"] = {
        "recovery_adopted": True,
        "execution_authorized": True,
        "approved_by": "user",
        "execution_actor": "codex",
        "approval_text": "synthetic fixture only",
        "approved_at": "fixture",
    }

    class InlineProcess:
        def __init__(self, target, args):
            self.target, self.args, self.exitcode = target, args, None

        def start(self):
            self.target(*self.args)
            self.exitcode = 0

        def join(self, timeout):
            pass

        def is_alive(self):
            return False

    monkeypatch.setattr(
        recovery.mp, "get_context", lambda *args: SimpleNamespace(Process=InlineProcess)
    )
    return SimpleNamespace(
        root=tmp_path,
        parent=parent,
        config=config,
        review=review,
        calls=calls,
        expected_rows=expected_rows,
        expected_summary=expected_summary,
    )


def test_recovery_matches_uninterrupted_without_recomputing_saved_work(
    interrupted_fixture,
):
    case = interrupted_fixture
    manifest_path = recovery.run(case.root, case.config, "codex")
    output = manifest_path.parent
    manifest = recovery.read_json(manifest_path)
    assert manifest["status"] == "COMPLETE"
    assert case.calls == ["q2", "q3", "q4"]
    assert recovery.read_json(output / "per_query.json")["rows"] == case.expected_rows
    assert recovery.read_json(output / "summary.json") == case.expected_summary
    assert recovery.inventory(case.parent) == case.review["artifact_sha256"]
    assert recovery.check_inherited(output)
    assert manifest["inherited_queries"] == 2 and manifest["new_queries"] == 3
    assert manifest["parent_run_identity_sha256"] == case.review["run_identity_sha256"]
    for name, digest in manifest["artifact_sha256"].items():
        assert recovery.sha256(output / name) == digest
    timings = recovery.read_json(output / "recovery_timings.json")["timings"]
    assert [t["checkpoint_reused"] for t in timings] == [True] * 7 + [False] * 3
    assert all(t["original_search_seconds"] is None for t in timings)
    with pytest.raises(FileExistsError):
        recovery.run(case.root, case.config, "codex")
    assert case.calls == ["q2", "q3", "q4"]


@pytest.mark.parametrize(
    "error", [TimeoutError("fixture timeout"), RuntimeError("fixture worker failed")]
)
def test_failed_recovery_consumes_attempt_and_refuses_retry(
    interrupted_fixture, monkeypatch, error
):
    case = interrupted_fixture

    def fail(process, remaining):
        assert 0 < remaining <= recovery.TIMEOUT_SECONDS
        raise error

    monkeypatch.setattr(pilot.safeguards, "complete_process_with_timeout", fail)
    with pytest.raises(type(error), match="fixture"):
        recovery.run(case.root, case.config, "codex")
    output = case.root / recovery.OUTPUT_PATH
    assert (
        recovery.read_json(output / "_INCOMPLETE.json")[
            "remaining_authorized_invocations"
        ]
        == 0
    )
    assert not (output / "run_manifest.json").exists()
    with pytest.raises(FileExistsError):
        recovery.run(case.root, case.config, "codex")
    assert recovery.inventory(case.parent) == case.review["artifact_sha256"]
    assert case.calls == []


def test_changed_parent_fails_before_search(interrupted_fixture):
    case = interrupted_fixture
    checkpoint = case.parent / "checkpoints/queries/000000.json"
    checkpoint.write_bytes(checkpoint.read_bytes() + b" ")
    with pytest.raises(ValueError, match="changed before copy"):
        recovery.run(case.root, case.config, "codex")
    assert case.calls == []


def test_corrupt_copied_checkpoint_fails_before_search(
    interrupted_fixture, monkeypatch
):
    case = interrupted_fixture
    copy_parent = recovery.copy_parent

    def corrupt(*args):
        copy_parent(*args)
        checkpoint = args[1] / "checkpoints/queries/000000.json"
        checkpoint.write_bytes(checkpoint.read_bytes() + b" ")

    monkeypatch.setattr(recovery, "copy_parent", corrupt)
    with pytest.raises(ValueError, match="Inherited checkpoint changed"):
        recovery.run(case.root, case.config, "codex")
    assert case.calls == []
    assert recovery.inventory(case.parent) == case.review["artifact_sha256"]


def test_missing_outputs_cannot_be_complete(interrupted_fixture, monkeypatch):
    case = interrupted_fixture
    monkeypatch.setattr(
        pilot.safeguards, "complete_process_with_timeout", lambda *args: None
    )
    with pytest.raises(RuntimeError, match="did not finish"):
        recovery.run(case.root, case.config, "codex")
    assert not (case.root / recovery.OUTPUT_PATH / "run_manifest.json").exists()


def test_wrong_actor_or_threads_refuse(interrupted_fixture, monkeypatch):
    case = interrupted_fixture
    with pytest.raises(PermissionError):
        recovery.run(case.root, case.config, "human")
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    with pytest.raises(RuntimeError, match="thread limits"):
        recovery.run(case.root, case.config, "codex")
    assert not (case.root / recovery.OUTPUT_PATH).exists()
