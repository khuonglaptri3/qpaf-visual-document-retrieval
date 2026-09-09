import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from oracle_study.metrics import evaluate_scores
from oracle_study.profiles import get_profiles
from scripts import recover_vidoseek_w66_resource_calibration as recovery


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def prepared_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        recovery.base.pilot.safeguards,
        "require_exact_git_execution_checkout",
        lambda *args, **kwargs: "e" * 40,
    )
    for name in recovery.base.pilot.safeguards.CPU_THREAD_ENV:
        monkeypatch.setenv(name, "1")


def live_config() -> dict:
    return recovery.read_json(ROOT / recovery.CONFIG_PATH)


def approved_config() -> dict:
    config = copy.deepcopy(live_config())
    config["resource_budget_status"] = recovery.APPROVED_STATUS
    config["approved_wall_timeout_seconds"] = recovery.PROPOSED_TIMEOUT_SECONDS
    config["invocations"] = 1
    config["approval_git"]["approved_parent_commit"] = "a" * 40
    config["authorization"] = {
        "protocol_adopted": True,
        "resource_budget_approved": True,
        "execution_authorized": True,
        "approved_by": "user",
        "execution_actor": "codex",
        "approval_text": "fixture approval only",
        "approved_at": "fixture",
    }
    return config


def synthetic_query_frame(size: int = 12) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dataset": "Qiuchen-Wang/ViDoSeek",
                "query_id": recovery.CALIBRATION_QUERY_ID,
                "page_id": f"p{page:04d}",
                "source": "synthetic",
                "relevance": float(page in {2, 7}),
                "bm25_score": ((page * 7) % size) / size,
                "dense_score": ((page * 5 + 1) % size) / size,
                "stage1_score": page / (size * 2),
                "visual_score": ((page * 3 + 2) % size) / size,
                "branch_ranks": "{}",
            }
            for page in range(size)
        ]
    )


def test_live_config_is_closed_and_matches_prepared_scope():
    config = live_config()
    validated = recovery.validate_config(ROOT, config)
    assert validated["state"] == "closed"
    assert config["resource_budget_status"] == recovery.PREPARATION_STATUS
    assert config["approved_wall_timeout_seconds"] == 0
    assert config["invocations"] == 0
    assert config["maximum_telemetry_gap_seconds"] == 5.0
    assert config["previous_checkpoint_reuse_allowed"] is False
    assert config["authorization"] == {
        "protocol_adopted": False,
        "resource_budget_approved": False,
        "execution_authorized": False,
        "approved_by": None,
        "execution_actor": None,
        "approval_text": None,
        "approved_at": None,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("grid", "w7"),
        ("profile_count", 7),
        ("calibration_audit_index", 0),
        ("pages_per_query", 512),
        ("proposed_wall_timeout_seconds", 1),
        ("workers", 2),
        ("maximum_telemetry_gap_seconds", 10.0),
        ("previous_checkpoint_reuse_allowed", True),
        ("automatic_retries", 1),
        ("actual_relevance_column_allowed", True),
    ],
)
def test_scope_drift_is_rejected(field, value):
    config = live_config()
    config[field] = value
    with pytest.raises(ValueError, match="scope drift"):
        recovery.validate_config(ROOT, config)


@pytest.mark.parametrize(
    "update",
    [
        {"approved_wall_timeout_seconds": 1},
        {"invocations": 1},
        {"resource_budget_status": recovery.APPROVED_STATUS},
    ],
)
def test_partial_approval_is_rejected(update):
    config = live_config()
    config.update(update)
    with pytest.raises(ValueError, match="authorization/resource state drift"):
        recovery.validate_config(ROOT, config)


def test_closed_run_refuses_before_validation_or_output(tmp_path, monkeypatch):
    called = False

    def validate(*args):
        nonlocal called
        called = True

    monkeypatch.setattr(recovery, "validate_config", validate)
    with pytest.raises(PermissionError, match="approval pending"):
        recovery.run(tmp_path, live_config(), "codex")
    assert called is False
    assert not (tmp_path / recovery.OUTPUT_PATH).exists()


def test_optimized_query_row_exactly_matches_frozen_row():
    frame = synthetic_query_frame()
    profiles = get_profiles("w66")
    item = recovery.base.pilot.sharded._query_item(frame)
    global_metrics = evaluate_scores(
        item["score_matrix"] @ profiles[0], item["relevance"], item["page_ids"]
    )
    expected = recovery.w66.query_result_row(frame, profiles, 0, global_metrics)
    observed = recovery.query_result_row_optimized(frame, profiles, 0, global_metrics)
    assert observed == expected


def test_checkpoint_replay_does_not_rerun_optimized_search(tmp_path, monkeypatch):
    calls = 0
    original = recovery.query_result_row_optimized

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(recovery, "query_result_row_optimized", counted)
    result = recovery.run_checkpointed_search(
        synthetic_query_frame(), {"fixture": True}, tmp_path / "checkpoints"
    )
    assert calls == 1
    assert result["previous_checkpoint_reused"] is False
    assert result["checkpoint_count"] == 4
    assert result["checkpoint_replay_verified_without_search"] is True
    assert (tmp_path / "checkpoints/global/000000.json").is_file()
    assert (tmp_path / "checkpoints/global_selection.json").is_file()
    assert (tmp_path / "checkpoints/queries/000000.json").is_file()


def test_telemetry_cadence_checks_wall_and_monotonic_gaps():
    wall_gap, monotonic_gap = recovery.telemetry_gap_seconds(
        "2026-09-09T00:00:00+00:00",
        "2026-09-09T00:00:04.900000+00:00",
        10.0,
        14.9,
    )
    recovery.enforce_telemetry_cadence(wall_gap, monotonic_gap, 5.0)
    with pytest.raises(RuntimeError, match="cadence exceeded"):
        recovery.enforce_telemetry_cadence(5.001, 1.0, 5.0)
    with pytest.raises(RuntimeError, match="cadence exceeded"):
        recovery.enforce_telemetry_cadence(1.0, 5.001, 5.0)
    with pytest.raises(RuntimeError, match="clock moved backwards"):
        recovery.telemetry_gap_seconds(
            "2026-09-09T00:00:01+00:00",
            "2026-09-09T00:00:00+00:00",
            1.0,
            2.0,
        )


class CadenceProcess:
    pid = 123
    exitcode = 0

    def __init__(self):
        self.alive = [True, False]

    def start(self):
        return None

    def is_alive(self):
        return self.alive.pop(0)

    def join(self, timeout=None):
        return None


def test_monitor_flushes_offending_gap_before_abort(tmp_path, monkeypatch):
    samples = iter(
        [
            {
                "observed_at": "2026-09-09T00:00:00+00:00",
                "processes": [],
                "process_tree_private_bytes": 1,
                "free_physical_bytes": recovery.ABORT_FREE_PHYSICAL_BYTES_BELOW,
                "output_bytes": 1,
                "disk_free_bytes": recovery.PRESTART_DISK_FREE_BYTES_MIN,
            },
            {
                "observed_at": "2026-09-09T00:00:10+00:00",
                "processes": [],
                "process_tree_private_bytes": 1,
                "free_physical_bytes": recovery.ABORT_FREE_PHYSICAL_BYTES_BELOW,
                "output_bytes": 1,
                "disk_free_bytes": recovery.PRESTART_DISK_FREE_BYTES_MIN,
            },
        ]
    )
    monotonic = iter([0.0, 1.0, 10.0])
    monkeypatch.setattr(recovery.base, "process_identity", lambda pid: {"pid": pid})
    monkeypatch.setattr(recovery.base, "resource_sample", lambda *args: next(samples))
    monkeypatch.setattr(recovery.time, "monotonic", lambda: next(monotonic))
    monkeypatch.setattr(
        recovery.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(available=recovery.PRESTART_FREE_PHYSICAL_BYTES_MIN),
    )
    with pytest.raises(RuntimeError, match="cadence exceeded"):
        recovery.monitor_worker(
            CadenceProcess(), tmp_path, tmp_path / "output", live_config(), 100.0
        )
    telemetry = (
        (tmp_path / "output" / "resource_telemetry.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(telemetry) == 2
    assert json.loads(telemetry[-1])["observed_at"].endswith("10+00:00")


class DummyProcess:
    def is_alive(self):
        return False


class DummyContext:
    def Process(self, target, args):
        return DummyProcess()


def patch_run_boundaries(tmp_path, monkeypatch, failure=False):
    config = approved_config()
    config["source_sha256"] = {}
    monkeypatch.setattr(
        recovery,
        "validate_config",
        lambda *args: {"state": "approved", "live_commit": "e" * 40},
    )
    monkeypatch.setattr(
        recovery.base,
        "host_snapshot",
        lambda _root, output: {
            "observed_at": "fixture",
            "free_physical_bytes": recovery.PRESTART_FREE_PHYSICAL_BYTES_MIN,
            "total_physical_bytes": recovery.PRESTART_FREE_PHYSICAL_BYTES_MIN * 2,
            "disk_free_bytes": recovery.PRESTART_DISK_FREE_BYTES_MIN,
            "output_exists": output.exists(),
        },
    )
    monkeypatch.setattr(recovery.base, "set_sleep_inhibition", lambda enabled: True)
    monkeypatch.setattr(recovery.mp, "get_context", lambda method: DummyContext())
    monkeypatch.setattr(recovery.subprocess, "run", lambda *args, **kwargs: None)
    sample = {
        "observed_at": "fixture",
        "processes": [],
        "process_tree_private_bytes": 1,
        "free_physical_bytes": recovery.ABORT_FREE_PHYSICAL_BYTES_BELOW,
        "output_bytes": 1,
        "disk_free_bytes": recovery.PRESTART_DISK_FREE_BYTES_MIN,
    }
    monkeypatch.setattr(recovery.base, "resource_sample", lambda *args: sample)

    def monitor(_process, _root, output, _config, _deadline):
        if failure:
            raise TimeoutError("fixture timeout")
        result = {
            "status": "COMPLETE",
            "actual_relevance_loaded": False,
            "scientific_result_produced": False,
            "search": {
                "checkpoint_replay_verified_without_search": True,
                "previous_checkpoint_reused": False,
            },
        }
        recovery.base.pilot.sharded._write_json_atomic_create_once(
            output / "calibration_result.json", result
        )
        recovery.base.pilot.sharded._write_json_atomic_create_once(
            output / "_WORKER_COMPLETE.json",
            {
                "status": "COMPLETE",
                "calibration_result_sha256": recovery.file_sha256(
                    output / "calibration_result.json"
                ),
            },
        )
        return {
            "samples": 1,
            "peak_process_tree_private_bytes": 1,
            "minimum_free_physical_bytes": recovery.ABORT_FREE_PHYSICAL_BYTES_BELOW,
            "maximum_observed_output_bytes": 1,
            "maximum_wall_gap_seconds": 0.0,
            "maximum_monotonic_gap_seconds": 0.0,
            "maximum_allowed_telemetry_gap_seconds": 5.0,
            "telemetry_cadence_passed": True,
            "worker_identity": {"pid": 1, "create_time": 1.0},
        }

    monkeypatch.setattr(recovery, "monitor_worker", monitor)
    return config


def test_approved_fixture_completes_and_refuses_second_invocation(
    tmp_path, monkeypatch
):
    config = patch_run_boundaries(tmp_path, monkeypatch)
    manifest_path = recovery.run(tmp_path, config, "codex")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "COMPLETE"
    assert manifest["engineering_calibration_recovery_completed"] is True
    assert manifest["previous_checkpoint_reused"] is False
    assert manifest["actual_relevance_loaded"] is False
    assert manifest["scientific_result_produced"] is False
    with pytest.raises(FileExistsError):
        recovery.run(tmp_path, config, "codex")


def test_failed_fixture_consumes_attempt_and_writes_incomplete(tmp_path, monkeypatch):
    config = patch_run_boundaries(tmp_path, monkeypatch, failure=True)
    with pytest.raises(TimeoutError, match="fixture timeout"):
        recovery.run(tmp_path, config, "codex")
    output = tmp_path / recovery.OUTPUT_PATH
    assert (output / "_ATTEMPTED.json").is_file()
    assert (
        recovery.read_json(output / "_INCOMPLETE.json")[
            "remaining_authorized_invocations"
        ]
        == 0
    )
    assert not (output / "run_manifest.json").exists()
