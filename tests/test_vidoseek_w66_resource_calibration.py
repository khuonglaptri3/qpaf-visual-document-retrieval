import copy
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from scripts import calibrate_vidoseek_w66_resources as study


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def prepared_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        study.pilot.safeguards,
        "require_exact_git_execution_checkout",
        lambda *args, **kwargs: "e" * 40,
    )
    for name in study.pilot.safeguards.CPU_THREAD_ENV:
        monkeypatch.setenv(name, "1")


def live_config() -> dict:
    return study.read_json(ROOT / study.CONFIG_PATH)


def closed_config() -> dict:
    config = copy.deepcopy(live_config())
    config["resource_budget_status"] = study.PREPARATION_STATUS
    config["approved_wall_timeout_seconds"] = 0
    config["invocations"] = 0
    config["approval_git"]["approved_parent_commit"] = None
    config["authorization"] = {
        "protocol_adopted": False,
        "resource_budget_approved": False,
        "execution_authorized": False,
        "approved_by": None,
        "execution_actor": None,
        "approval_text": None,
        "approved_at": None,
    }
    return config


def approved_config() -> dict:
    config = copy.deepcopy(closed_config())
    config["resource_budget_status"] = study.APPROVED_STATUS
    config["approved_wall_timeout_seconds"] = study.PROPOSED_TIMEOUT_SECONDS
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


def synthetic_subset() -> tuple[pd.DataFrame, list[dict]]:
    queries = [
        {"dataset": "fixture", "query_id": "q0"},
        {
            "dataset": "Qiuchen-Wang/ViDoSeek",
            "query_id": study.CALIBRATION_QUERY_ID,
        },
    ]
    frame = pd.DataFrame(
        [
            {
                "dataset": query["dataset"],
                "query_id": query["query_id"],
                "page_id": f"p{page}",
                "source": "synthetic",
                "bm25_score": page / 4,
                "dense_score": (3 - page) / 4,
                "stage1_score": page / 8,
                "visual_score": (page + 1) / 5,
                "branch_ranks": "{}",
            }
            for query in queries
            for page in range(4)
        ],
        columns=study.LOAD_COLUMNS,
    )
    return frame, queries


def synthetic_query_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dataset": "Qiuchen-Wang/ViDoSeek",
                "query_id": study.CALIBRATION_QUERY_ID,
                "page_id": f"p{page}",
                "source": "synthetic",
                "relevance": float(page == 2),
                "bm25_score": page / 4,
                "dense_score": (3 - page) / 4,
                "stage1_score": page / 8,
                "visual_score": (page + 1) / 5,
                "branch_ranks": "{}",
            }
            for page in range(4)
        ]
    )


def test_live_config_records_exact_approved_scope_and_matches_review():
    config = live_config()
    validated = study.validate_config(ROOT, config)
    assert validated["state"] == "approved"
    assert config["resource_budget_status"] == study.APPROVED_STATUS
    assert config["approved_wall_timeout_seconds"] == study.PROPOSED_TIMEOUT_SECONDS
    assert config["invocations"] == 1
    assert config["authorization"] == {
        "protocol_adopted": True,
        "resource_budget_approved": True,
        "execution_authorized": True,
        "approved_by": "user",
        "execution_actor": "codex",
        "approval_text": "Ok I approved, you can do whatever it need to proceed w66 but precisely",
        "approved_at": "2026-09-09T08:23:12.8745123Z",
    }
    assert study.selected_queries(ROOT)[-1]["audit_index"] >= 0
    review = study.read_json(ROOT / study.RESOURCE_REVIEW_JSON)
    assert (
        review["decision"] == "NO_GO_FULL_W66_PENDING_CALIBRATION_AND_RESOURCE_GUARDS"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("grid", "w7"),
        ("profile_count", 7),
        ("calibration_audit_index", 0),
        ("pages_per_query", 512),
        ("bootstrap_resamples", 100),
        ("workers", 2),
        ("arrow_io_threads", 2),
        ("automatic_retries", 1),
        ("actual_relevance_column_allowed", True),
    ],
)
def test_scope_drift_is_rejected(field, value):
    config = closed_config()
    config[field] = value
    with pytest.raises(ValueError, match="scope drift"):
        study.validate_config(ROOT, config)


@pytest.mark.parametrize(
    "update",
    [
        {"approved_wall_timeout_seconds": 1},
        {"invocations": 1},
        {"resource_budget_status": study.APPROVED_STATUS},
    ],
)
def test_partial_approval_is_rejected(update):
    config = closed_config()
    config.update(update)
    with pytest.raises(ValueError, match="authorization/resource state drift"):
        study.validate_config(ROOT, config)


def test_closed_run_refuses_before_validation_or_output(tmp_path, monkeypatch):
    called = False

    def validate(*args):
        nonlocal called
        called = True

    monkeypatch.setattr(study, "validate_config", validate)
    with pytest.raises(PermissionError, match="approval pending"):
        study.run(tmp_path, closed_config(), "codex")
    assert called is False
    assert not (tmp_path / study.OUTPUT_PATH).exists()


def test_approved_actor_and_numeric_thread_guard(monkeypatch):
    config = approved_config()
    study.require_approval(config, "codex")
    with pytest.raises(PermissionError):
        study.require_approval(config, "human")
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "2")
    with pytest.raises(RuntimeError, match="one numeric-library thread"):
        study.require_approval(config, "codex")


def test_loaded_subset_adds_only_deterministic_synthetic_label(monkeypatch):
    frame, queries = synthetic_subset()
    monkeypatch.setattr(study, "PAGES_PER_QUERY", 4)
    monkeypatch.setattr(study, "LOAD_QUERY_COUNT", 2)
    monkeypatch.setattr(study, "LOAD_PAIR_COUNT", 8)
    monkeypatch.setattr(study, "SYNTHETIC_RELEVANT_INDEX", 2)
    result = study.validate_loaded_subset(frame, queries)
    assert "relevance" not in frame
    assert result.relevance.tolist() == [0.0, 0.0, 1.0, 0.0]
    assert result.page_id.tolist() == ["p0", "p1", "p2", "p3"]


def test_loaded_subset_rejects_decoded_relevance(monkeypatch):
    frame, queries = synthetic_subset()
    frame["relevance"] = 1.0
    monkeypatch.setattr(study, "PAGES_PER_QUERY", 4)
    monkeypatch.setattr(study, "LOAD_QUERY_COUNT", 2)
    monkeypatch.setattr(study, "LOAD_PAIR_COUNT", 8)
    with pytest.raises(ValueError, match="unexpected score column"):
        study.validate_loaded_subset(frame, queries)


def test_checkpoint_replay_does_not_rerun_search(tmp_path, monkeypatch):
    calls = 0
    original = study.w66.query_result_row

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(study.w66, "query_result_row", counted)
    result = study.run_checkpointed_search(
        synthetic_query_frame(), {"fixture": True}, tmp_path / "checkpoints"
    )
    assert calls == 1
    assert result["checkpoint_count"] == 4
    assert result["checkpoint_replay_verified_without_search"] is True
    assert (tmp_path / "checkpoints/global/000000.json").is_file()
    assert (tmp_path / "checkpoints/global_selection.json").is_file()
    assert (tmp_path / "checkpoints/queries/000000.json").is_file()


def test_bootstrap_probe_is_fixed_and_deterministic():
    first = study.run_bootstrap_probe()
    second = study.run_bootstrap_probe()
    for key in ("sample_size", "resamples", "seed", "mean_ci", "ratio_ci"):
        assert first[key] == second[key]
    assert first["mean_ci"] == first["ratio_ci"]


def test_worker_thread_pools_are_explicitly_one():
    state = study.set_worker_thread_limits()
    assert state["arrow_cpu_threads"] == state["arrow_io_threads"] == 1
    assert all(pool["num_threads"] == 1 for pool in state["numeric_pools"])


def test_parent_identity_rejects_pid_reuse():
    identity = study.process_identity(os.getpid())
    assert study.parent_identity_alive(identity)
    identity["create_time"] += 100
    assert not study.parent_identity_alive(identity)


def test_admission_and_resource_limits_are_fail_closed(tmp_path):
    config = closed_config()
    snapshot = {
        "output_exists": False,
        "free_physical_bytes": config["prestart_free_physical_bytes_min"],
        "disk_free_bytes": config["prestart_disk_free_bytes_min"],
    }
    study.enforce_admission(snapshot, config)
    for field, value, error in (
        ("output_exists", True, FileExistsError),
        (
            "free_physical_bytes",
            config["prestart_free_physical_bytes_min"] - 1,
            RuntimeError,
        ),
        (
            "disk_free_bytes",
            config["prestart_disk_free_bytes_min"] - 1,
            RuntimeError,
        ),
    ):
        changed = dict(snapshot)
        changed[field] = value
        with pytest.raises(error):
            study.enforce_admission(changed, config)

    sample = {
        "process_tree_private_bytes": config["process_tree_private_bytes_limit"],
        "free_physical_bytes": config["abort_free_physical_bytes_below"],
        "output_bytes": config["output_byte_limit"],
    }
    study.enforce_resource_sample(sample, config)
    for field in sample:
        changed = dict(sample)
        changed[field] += 1 if field != "free_physical_bytes" else -1
        with pytest.raises((MemoryError, RuntimeError)):
            study.enforce_resource_sample(changed, config)


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
        study,
        "validate_config",
        lambda *args: {"state": "approved", "live_commit": "e" * 40},
    )
    monkeypatch.setattr(
        study,
        "host_snapshot",
        lambda _root, output: {
            "observed_at": "fixture",
            "free_physical_bytes": study.PRESTART_FREE_PHYSICAL_BYTES_MIN,
            "total_physical_bytes": study.PRESTART_FREE_PHYSICAL_BYTES_MIN * 2,
            "disk_free_bytes": study.PRESTART_DISK_FREE_BYTES_MIN,
            "output_exists": output.exists(),
        },
    )
    monkeypatch.setattr(study, "set_sleep_inhibition", lambda enabled: True)
    monkeypatch.setattr(study.mp, "get_context", lambda method: DummyContext())
    monkeypatch.setattr(study.subprocess, "run", lambda *args, **kwargs: None)
    sample = {
        "observed_at": "fixture",
        "processes": [],
        "process_tree_private_bytes": 1,
        "free_physical_bytes": study.ABORT_FREE_PHYSICAL_BYTES_BELOW,
        "output_bytes": 1,
        "disk_free_bytes": study.PRESTART_DISK_FREE_BYTES_MIN,
    }
    monkeypatch.setattr(study, "resource_sample", lambda *args: sample)

    def monitor(_process, _root, output, _config, _deadline):
        if failure:
            raise TimeoutError("fixture timeout")
        result = {
            "status": "COMPLETE",
            "actual_relevance_loaded": False,
            "scientific_result_produced": False,
            "search": {"checkpoint_replay_verified_without_search": True},
        }
        study.pilot.sharded._write_json_atomic_create_once(
            output / "calibration_result.json", result
        )
        study.pilot.sharded._write_json_atomic_create_once(
            output / "_WORKER_COMPLETE.json",
            {
                "status": "COMPLETE",
                "calibration_result_sha256": study.file_sha256(
                    output / "calibration_result.json"
                ),
            },
        )
        return {
            "samples": 1,
            "peak_process_tree_private_bytes": 1,
            "minimum_free_physical_bytes": study.ABORT_FREE_PHYSICAL_BYTES_BELOW,
            "maximum_observed_output_bytes": 1,
            "worker_identity": {"pid": 1, "create_time": 1.0},
        }

    monkeypatch.setattr(study, "monitor_worker", monitor)
    return config


def test_approved_fixture_completes_and_refuses_second_invocation(
    tmp_path, monkeypatch
):
    config = patch_run_boundaries(tmp_path, monkeypatch)
    manifest_path = study.run(tmp_path, config, "codex")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "COMPLETE"
    assert manifest["engineering_calibration_completed"] is True
    assert manifest["actual_relevance_loaded"] is False
    assert manifest["scientific_result_produced"] is False
    with pytest.raises(FileExistsError):
        study.run(tmp_path, config, "codex")


def test_failed_fixture_consumes_attempt_and_writes_incomplete(tmp_path, monkeypatch):
    config = patch_run_boundaries(tmp_path, monkeypatch, failure=True)
    with pytest.raises(TimeoutError, match="fixture timeout"):
        study.run(tmp_path, config, "codex")
    output = tmp_path / study.OUTPUT_PATH
    assert (output / "_ATTEMPTED.json").is_file()
    assert (
        study.read_json(output / "_INCOMPLETE.json")["remaining_authorized_invocations"]
        == 0
    )
    assert not (output / "run_manifest.json").exists()
