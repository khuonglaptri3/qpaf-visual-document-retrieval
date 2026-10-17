import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from oracle_study import qpaf
from oracle_study.metrics import RankingMetrics
from scripts import audit_vidoseek_fixed_profiles as audit

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def historical_execution_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate the completed audit against its recorded source commit."""
    recorded = audit.read_json(ROOT / audit.CONFIG_PATH)["base_git_commit"]
    monkeypatch.setattr(audit, "git_head", lambda _root: recorded)


def synthetic_scores():
    matrices = [
        [[1, 0.1, 0.3], [0.8, 0.9, 1], [0, 1, 0.1], [0.2, 0.2, 0.2]],
        [[0.7, 0.1, 0.9], [1, 0.3, 0.7], [0.1, 1, 1], [0, 0, 0]],
        [[0, 0, 0]] * 4,
    ]
    relevance = [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 2, 0]]
    return pd.DataFrame(
        [
            {
                "dataset": "Qiuchen-Wang/ViDoSeek",
                "query_id": f"q{q}",
                "page_id": f"p{p}",
                "source": "synthetic",
                "relevance": relevance[q][p],
                "bm25_score": values[0],
                "dense_score": values[1],
                "visual_score": values[2],
                "stage1_score": 0.0,
                "branch_ranks": "{}",
            }
            for q, matrix in enumerate(matrices)
            for p, values in enumerate(matrix)
        ]
    )


def test_live_config_source_pins_and_consumed_approval_match():
    config = audit.read_json(ROOT / audit.CONFIG_PATH)
    bundle = audit.validate_config(ROOT, config)
    assert bundle["retrieval_scores"]["rows"] == 6149670
    assert config["authorization"]["protocol_adopted"] is True
    assert config["authorization"]["execution_authorized"] is True
    output = ROOT / audit.OUTPUT_PATH
    attempt = audit.read_json(output / "_ATTEMPTED.json")
    manifest = audit.read_json(output / "run_manifest.json")
    assert attempt["remaining_authorized_invocations"] == 0
    assert attempt["config_sha256"] == audit.value_sha256(config)
    assert manifest["status"] == "COMPLETE"
    assert manifest["remaining_authorized_invocations"] == 0
    assert manifest["source_commit"] == config["base_git_commit"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("queries", 24),
        ("grid", "w66"),
        ("total_wall_timeout_seconds", 1801),
        ("automatic_retries", 1),
        ("workers", 2),
        ("qpaf_search_allowed", True),
        ("output_path", "runs/vidoseek_exploratory12_recovery_v1"),
        ("headroom_review_threshold", 0.01),
        ("training_allowed", True),
    ],
)
def test_scope_drift_rejected(field, value):
    config = audit.read_json(ROOT / audit.CONFIG_PATH)
    config[field] = value
    with pytest.raises(ValueError, match="scope drift"):
        audit.validate_config(ROOT, config)


def test_source_hash_and_environment_drift_rejected():
    config = audit.read_json(ROOT / audit.CONFIG_PATH)
    config["source_sha256"][audit.SCRIPT_PATH] = "0" * 64
    with pytest.raises(ValueError, match="source hash drift"):
        audit.validate_config(ROOT, config)
    config = audit.read_json(ROOT / audit.CONFIG_PATH)
    config["environment"]["python"] = "0.0.0"
    with pytest.raises(ValueError, match="environment drift"):
        audit.validate_config(ROOT, config)


def test_closed_run_refuses_before_input_access_or_writes(tmp_path, monkeypatch):
    config = audit.read_json(ROOT / audit.CONFIG_PATH)
    config["authorization"]["execution_authorized"] = False
    monkeypatch.setattr(
        audit, "validate_config", lambda *a: pytest.fail("Input accessed")
    )
    with pytest.raises(PermissionError, match="pending"):
        audit.run(tmp_path, config, "codex")
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def fixture_run(tmp_path, monkeypatch):
    config = audit.read_json(ROOT / audit.CONFIG_PATH)
    config.update(queries=3, pages_per_query=4, source_sha256={})
    config["authorization"] = {
        "protocol_adopted": True,
        "execution_authorized": True,
        "approved_by": "user",
        "execution_actor": "codex",
        "approval_text": "synthetic fixture only",
        "approved_at": "2026-09-07T00:00:00+00:00",
    }
    scores = synthetic_scores()
    # Deliberately split queries across Parquet row groups to exercise bounded streaming.
    scores.to_parquet(tmp_path / "scores.parquet", index=False, row_group_size=3)
    order = [("Qiuchen-Wang/ViDoSeek", f"q{q}") for q in range(3)]
    pd.DataFrame(
        [
            {
                "dataset": d,
                "query_id": q,
                "relevant_total": 2 if q == "q2" else 1,
                "relevant_selected": 2 if q == "q2" else 1,
                "coverage": 1.0,
                "candidate_count": 4,
            }
            for d, q in order
        ]
    ).to_parquet(tmp_path / "audit.parquet", index=False)
    bundle = {
        "retrieval_scores": {"path": "scores.parquet", "rows": 12},
        "candidate_audit": {"path": "audit.parquet"},
    }
    monkeypatch.setattr(audit, "validate_config", lambda *args: bundle)
    monkeypatch.setattr(
        audit.safeguards, "load_protocol", lambda *args: {"input_bundle": bundle}
    )
    monkeypatch.setattr(
        audit.safeguards, "protocol_bound_preflight", lambda *a, **kw: {"fixture": True}
    )
    for name in audit.safeguards.CPU_THREAD_ENV:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(
        audit.subprocess, "check_output", lambda *a, **kw: b"synthetic fixture diff"
    )

    class InlineProcess:
        def __init__(self, target, args):
            self.target, self.args, self.exitcode = target, args, None

        def start(self):
            self.target(*self.args)
            self.exitcode = 0

        def join(self, timeout=None):
            pass

        def is_alive(self):
            return False

    monkeypatch.setattr(
        audit.mp, "get_context", lambda *a: SimpleNamespace(Process=InlineProcess)
    )
    return tmp_path, config, scores, order


def test_preflight_reads_only_query_id_columns(fixture_run, monkeypatch):
    root, config, _, _ = fixture_run
    original = pd.read_parquet
    reads = []

    def read(path, *args, **kwargs):
        reads.append((Path(path).name, kwargs.get("columns")))
        assert kwargs["columns"] == ["dataset", "query_id"]
        return original(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", read)
    before = {p.name for p in root.iterdir()}
    result = audit.preflight(root, config)
    assert audit.pa.cpu_count() == audit.pa.io_thread_count() == 1
    assert result["actual_relevance_loaded"] is False
    assert result["scientific_result_produced"] is False
    assert reads == [("audit.parquet", ["dataset", "query_id"])]
    assert {p.name for p in root.iterdir()} == before


def test_streaming_and_selection_equal_frozen_reference(fixture_run, monkeypatch):
    root, config, _, order = fixture_run
    monkeypatch.setattr(
        qpaf, "_candidate_oracle", lambda *a, **k: pytest.fail("QPAF search called")
    )
    monkeypatch.setattr(
        qpaf, "run_qpaf_oracle", lambda *a, **k: pytest.fail("Full runner called")
    )
    frames = list(audit.iter_queries(root / "scores.parquet", order, 4))
    rows = [audit.profile_row(frame, i) for i, frame in enumerate(frames)]
    items = [audit.sharded._query_item(frame) for frame in frames]
    profiles = audit.get_profiles("w7")
    global_index, global_metrics = qpaf._global_oracle(items, profiles)
    for row, item in zip(rows, items):
        selected, _, metrics = qpaf._query_oracle(
            item["score_matrix"], item["relevance"], item["page_ids"], profiles
        )
        assert row["qarf_profile_index"] == selected
        assert row["profile_metrics"][selected] == audit.asdict(metrics)
    summary = audit.summarize(rows, config)
    assert summary["global_profile_index"] == global_index
    assert summary["global_metrics"] == audit.asdict(qpaf._mean_metrics(global_metrics))
    expected_bound = np.mean(
        [1 - r["profile_metrics"][r["qarf_profile_index"]]["ndcg10"] for r in rows]
    )
    assert summary["mean_qpaf_gain_upper_bound"] == expected_bound
    assert summary["qpaf_measured"] is False
    assert summary["phase1_decision"] == "NOT_APPLICABLE_FIXED_PROFILE_AUDIT"
    # All-zero score ties retain profile zero and sort page IDs deterministically.
    assert rows[2]["qarf_profile_index"] == 0
    assert rows[2]["profile_metrics"][0]["recall1"] == 0
    assert rows[2]["profile_metrics"][0]["mrr10"] == 0.5


def test_profile_tolerance_and_secondary_tie_breaks():
    a = RankingMetrics(0.5, 0.0, 0.5, 0.5)
    assert audit.select_profile([a, a]) == 0
    assert audit.select_profile([a, RankingMetrics(0.5 + 5e-13, 0.0, 0.6, 0.5)]) == 1
    assert (
        audit.select_profile([a, RankingMetrics(0.5, 1.0, 0.5, 0.5)]) == 0
    )  # Recall@1 is not a selection key.
    assert audit.select_profile([a, RankingMetrics(0.5, 0.0, 0.5, 0.6)]) == 1


def test_single_positive_closed_form_and_row_permutation():
    frame = synthetic_scores().iloc[:4].copy()
    row = audit.profile_row(frame, 0)
    # BM25 ranks the one positive first; dense ranks it fourth; visual ranks it second.
    assert [m["ndcg10"] for m in row["profile_metrics"][:3]] == pytest.approx(
        [1.0, 1 / np.log2(5), 1 / np.log2(3)]
    )
    shuffled = audit.profile_row(frame.sample(frac=1, random_state=3), 0)
    assert shuffled["profile_metrics"] == row["profile_metrics"]
    assert shuffled["input_query_sha256"] == row["input_query_sha256"]


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "missing",
        "extra",
        "wrong_order",
        "nonfinite",
        "range",
        "negative_relevance",
        "uncovered",
        "different_corpus",
    ],
)
def test_bad_query_inputs_fail_closed(fixture_run, mutation):
    root, _, frame, order = fixture_run
    if mutation == "duplicate":
        frame.loc[1, "page_id"] = "p0"
    elif mutation == "missing":
        frame = frame.iloc[:-1]
    elif mutation == "extra":
        frame = pd.concat([frame, frame.iloc[:4]])
    elif mutation == "wrong_order":
        frame.loc[:3, "query_id"] = "unexpected"
    elif mutation == "nonfinite":
        frame.loc[0, "bm25_score"] = np.nan
    elif mutation == "range":
        frame.loc[0, "dense_score"] = 1.5
    elif mutation == "negative_relevance":
        frame.loc[0, "relevance"] = -1
    elif mutation == "uncovered":
        frame.loc[:3, "relevance"] = 0
    elif mutation == "different_corpus":
        frame.loc[4, "page_id"] = "other"
    frame.to_parquet(root / "bad.parquet", index=False, row_group_size=3)
    with pytest.raises(ValueError):
        list(audit.iter_queries(root / "bad.parquet", order, 4))


def test_approved_fixture_completes_and_second_invocation_preserves_every_byte(
    fixture_run,
):
    root, config, _, _ = fixture_run
    inputs = {p.name: audit.sha256(p) for p in root.glob("*.parquet")}
    manifest_path = audit.run(root, config, "codex")
    manifest = audit.read_json(manifest_path)
    output = root / audit.OUTPUT_PATH
    assert manifest["queries"] == 3 and manifest["status"] == "COMPLETE"
    assert manifest["qpaf_search_executed"] is False
    for name, expected in manifest["artifact_sha256"].items():
        assert audit.sha256(output / name) == expected
    before = {
        p.relative_to(output).as_posix(): audit.sha256(p)
        for p in output.rglob("*")
        if p.is_file()
    }
    with pytest.raises(FileExistsError):
        audit.run(root, config, "codex")
    assert before == {
        p.relative_to(output).as_posix(): audit.sha256(p)
        for p in output.rglob("*")
        if p.is_file()
    }
    assert inputs == {p.name: audit.sha256(p) for p in root.glob("*.parquet")}


@pytest.mark.parametrize("failure", ["timeout", "preflight", "coverage"])
def test_failed_invocation_consumes_attempt_and_never_emits_manifest(
    fixture_run, monkeypatch, failure
):
    root, config, _, _ = fixture_run
    if failure == "timeout":

        def timeout(*args):
            raise TimeoutError("fixture timeout")

        monkeypatch.setattr(audit.safeguards, "complete_process_with_timeout", timeout)
    elif failure == "preflight":

        def corrupt(*args):
            raise ValueError("fixture hash mismatch")

        monkeypatch.setattr(audit, "preflight", corrupt)
    else:
        table = pd.read_parquet(root / "audit.parquet")
        table.loc[0, "relevant_total"] = 99
        table.to_parquet(root / "audit.parquet", index=False)
    with pytest.raises((ValueError, TimeoutError)):
        audit.run(root, config, "codex")
    output = root / audit.OUTPUT_PATH
    assert (
        audit.read_json(output / "_ATTEMPTED.json")["remaining_authorized_invocations"]
        == 0
    )
    assert (
        audit.read_json(output / "_INCOMPLETE.json")["completed_result_available"]
        is False
    )
    assert not (output / "run_manifest.json").exists()
    with pytest.raises(FileExistsError):
        audit.run(root, config, "codex")


def test_actor_and_threads_guard(fixture_run, monkeypatch):
    root, config, _, _ = fixture_run
    audit.pa.set_cpu_count(2)
    audit.pa.set_io_thread_count(2)
    audit.require_approval(config, "codex")
    assert audit.pa.cpu_count() == audit.pa.io_thread_count() == 1
    with pytest.raises(PermissionError):
        audit.run(root, config, "human")
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    with pytest.raises(RuntimeError, match="one thread"):
        audit.run(root, config, "codex")
    assert not (root / audit.OUTPUT_PATH).exists()


def test_checkpoint_corruption_and_partial_aggregate_refused(fixture_run):
    root, config, _, order = fixture_run
    audit.run(root, config, "codex")
    output = root / audit.OUTPUT_PATH
    rows = audit.read_checkpoints(output, config, order)
    with pytest.raises(ValueError, match="every query"):
        audit.summarize(rows[:-1], config)
    changed = copy.deepcopy(rows)
    changed[0]["profile_metrics"][0]["ndcg10"] = float("nan")
    with pytest.raises(ValueError, match="Invalid profile metric"):
        audit.summarize(changed, config)
    path = output / "checkpoints/000000.json"
    envelope = audit.read_json(path)
    envelope["payload"]["query_id"] = "tampered"
    path.write_text(audit.json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ValueError, match="content hash"):
        audit.read_checkpoints(output, config, order)
