from __future__ import annotations

import ast
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/run_vimdoc_archive_content_audit.py"
SPEC = importlib.util.spec_from_file_location("vimdoc_archive_audit", RUNNER_PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
IDENTITY = audit.identity
CONFIG_PATH = ROOT / audit.CONFIG_RELATIVE_PATH


def make_tar(path: Path, entries: list[tuple[str, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as archive:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def make_approved_fixture(tmp_path: Path, conflicting: bool = False):
    project, volume = tmp_path / "project", tmp_path / "volume"
    base = json.loads(CONFIG_PATH.read_text())
    for relative in base["source_files"]:
        destination = project / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    archive_path = volume / "datasets/vimdoc/fixture/ViMDoc_pages.tar.gz"
    entries = [("pages/doc_1.jpg", b"same"),
               ("pages/doc_1.png", b"different" if conflicting else b"same"),
               ("pages/doc_2.png", b"two")]
    make_tar(archive_path, entries)
    identity_path = project / "configs/vimdoc_ocr_page_identity_v1.json"
    identity_config = json.loads(identity_path.read_text())
    identity_config["source_alignment"]["dataset_archive_sha256"] = audit.file_sha256(archive_path)
    identity_config["asset_identity"].update({
        "expected_asset_files": 3,
        "expected_unique_page_ids_before_content_audit": 2,
        "expected_extra_assets_sharing_page_id": 1,
        "expected_document_ids": 1,
    })
    identity_path.write_text(json.dumps(identity_config), encoding="utf-8")
    config = copy.deepcopy(base)
    config["input"].update({
        "dataset_revision": "fixture",
        "archive_relative_path": "datasets/vimdoc/fixture/ViMDoc_pages.tar.gz",
        "archive_sha256": audit.file_sha256(archive_path),
        "materialization_receipt": "artifacts/receipt.json",
    })
    config["output"]["directory_relative_path"] = "audits/fixture"
    config["authorization"] = {
        "execution_authorized": True,
        "approved_actor": "codex",
        "required_source_commit": "fixturecommit",
        "approved_invocations": 1,
        "approved_retries": 0,
        "approved_timeout_seconds": 21600,
    }
    config["source_files"] = {
        relative: audit.file_sha256(project / relative) for relative in config["source_files"]
    }
    config_path = project / audit.CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return project, volume, config_path, archive_path


def run_fixture(project: Path, volume: Path, config_path: Path, commits: list[int]):
    return audit.run_audit(
        project, volume, config_path, audit.file_sha256(config_path), "codex",
        "fixturecommit", "fc-fixture", lambda: commits.append(1)
    )


def test_closed_local_package_preflight_is_read_only_and_exact():
    before = {path: audit.file_sha256(ROOT / path)
              for path in json.loads(CONFIG_PATH.read_text())["source_files"]}
    result = audit.package_preflight(ROOT, CONFIG_PATH)
    assert result["status"] == "PASS_LOCAL_PACKAGE_ONLY"
    assert result["source_files_verified"] == 5
    assert result["execution_authorized"] is False
    assert result["approved_invocations"] == 0
    assert result["modal_called"] is False and result["archive_opened"] is False
    assert result["ocr_executed"] is False and result["training_executed"] is False
    assert result["maximum_reserved_compute_usd_at_timeout"] == pytest.approx(0.474768)
    assert before == {path: audit.file_sha256(ROOT / path) for path in before}


def test_closed_config_refuses_execution_before_output(tmp_path):
    config = json.loads(CONFIG_PATH.read_text())
    with pytest.raises(PermissionError, match="approval is pending"):
        audit.execution_guard(config, "codex", "fixturecommit")
    assert list(tmp_path.iterdir()) == []


def test_success_writes_auditable_create_once_evidence_and_preserves_archive(tmp_path):
    project, volume, config_path, archive_path = make_approved_fixture(tmp_path)
    original_hash = audit.file_sha256(archive_path)
    commits = []
    manifest = run_fixture(project, volume, config_path, commits)
    output = volume / "audits/fixture"
    assert manifest["status"] == "COMPLETE"
    assert manifest["classification"] == "DATA_INTEGRITY_ONLY_NO_OCR_NO_EXTRACTION_NO_TRAINING"
    assert manifest["asset_count"] == 3 and manifest["canonical_page_count"] == 2
    assert manifest["different_content_collision_count"] == 0
    assert manifest["scientific_metrics_computed"] is False
    assert manifest["ocr_executed"] is False and manifest["optimizer_steps"] == 0
    assert commits == [1, 1]
    assert audit.file_sha256(archive_path) == original_hash
    assert (output / "_SUCCESS.json").is_file() and not (output / "_FAILED.json").exists()
    assert len((output / "asset_inventory.jsonl").read_text().splitlines()) == 3
    assert len((output / "canonical_pages.jsonl").read_text().splitlines()) == 2
    success = audit.read_json(output / "_SUCCESS.json")
    assert success["run_manifest_sha256"] == audit.file_sha256(output / "run_manifest.json")
    for relative, item in manifest["artifact_inventory"].items():
        path = output / relative
        assert path.stat().st_size == item["bytes"] and audit.file_sha256(path) == item["sha256"]
    with pytest.raises(FileExistsError, match="retry is forbidden"):
        run_fixture(project, volume, config_path, commits)


def test_different_content_collision_consumes_attempt_and_never_succeeds(tmp_path):
    project, volume, config_path, archive_path = make_approved_fixture(tmp_path, conflicting=True)
    before = audit.file_sha256(archive_path)
    commits = []
    with pytest.raises(ValueError, match="collisions block OCR"):
        run_fixture(project, volume, config_path, commits)
    output = volume / "audits/fixture"
    assert commits == [1, 1]
    assert (output / "_ATTEMPTED.json").is_file() and (output / "_FAILED.json").is_file()
    assert not (output / "_SUCCESS.json").exists() and not (output / "run_manifest.json").exists()
    failure = audit.read_json(output / "_FAILED.json")
    assert failure["status"] == "FAILED_ATTEMPT_CONSUMED_NO_RETRY"
    assert failure["remaining_authorized_invocations"] == 0
    assert audit.file_sha256(archive_path) == before


def test_jsonl_reread_detects_hash_and_row_count_drift(tmp_path):
    path = tmp_path / "inventory.jsonl"
    path.write_bytes(b'{"row":1}\n{"row":2}\n')
    expected_hash = audit.file_sha256(path)
    audit.verify_jsonl(path, expected_hash, 2)
    with pytest.raises(ValueError, match="row-count mismatch"):
        audit.verify_jsonl(path, expected_hash, 1)
    path.write_bytes(path.read_bytes() + b'{"row":3}\n')
    with pytest.raises(ValueError, match="byte hash mismatch"):
        audit.verify_jsonl(path, expected_hash, 3)


@pytest.mark.parametrize("change", ["actor", "commit", "timeout", "retry", "invocations"])
def test_execution_guard_requires_exact_approval(change):
    config = json.loads(CONFIG_PATH.read_text())
    config["authorization"] = {
        "execution_authorized": True, "approved_actor": "codex",
        "required_source_commit": "commit", "approved_invocations": 1,
        "approved_retries": 0, "approved_timeout_seconds": 21600,
    }
    actor, commit = "codex", "commit"
    if change == "actor":
        actor = "other"
    elif change == "commit":
        commit = "other"
    elif change == "timeout":
        config["authorization"]["approved_timeout_seconds"] = 1
    elif change == "retry":
        config["authorization"]["approved_retries"] = 1
    elif change == "invocations":
        config["authorization"]["approved_invocations"] = 2
    with pytest.raises(PermissionError):
        audit.execution_guard(config, actor, commit)


def test_source_or_config_drift_fails_closed(tmp_path):
    config = json.loads(CONFIG_PATH.read_text())
    altered = copy.deepcopy(config)
    altered["authorization"]["execution_authorized"] = True
    altered["authorization"]["approved_invocations"] = 1
    altered["authorization"]["approved_timeout_seconds"] = 21600
    path = tmp_path / "config.json"
    path.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="inside the project root"):
        audit.package_preflight(ROOT, path)
    source = ROOT / next(iter(config["source_files"]))
    drifted = copy.deepcopy(config)
    drifted["source_files"][source.relative_to(ROOT).as_posix()] = "0" * 64
    path.write_text(json.dumps(drifted))
    with pytest.raises(ValueError, match="hash drift"):
        audit.validate_sources(ROOT, drifted)


def test_modal_wrapper_is_cpu_only_without_secret_remote_call_or_local_entrypoint():
    source = (ROOT / "vimdoc_archive_audit_modal.py").read_text()
    tree = ast.parse(source)
    assert "gpu=" not in source and "modal.Secret" not in source
    assert ".remote(" not in source and "@app.local_entrypoint" not in source
    assert "retries=resources[\"retries\"]" in source
    assert "cpu=resources[\"cpu_physical_cores\"]" in source
    assert "memory=resources[\"memory_mb\"]" in source
    assert "timeout=resources[\"timeout_seconds\"]" in source
    assert "create_if_missing=False" in source
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(isinstance(call.func, ast.Attribute) and call.func.attr in {"remote", "spawn"}
                   for call in calls)


def test_modal_wrapper_uses_posix_absolute_remote_paths_on_windows():
    source = (ROOT / "vimdoc_archive_audit_modal.py").read_text()
    tree = ast.parse(source)
    remote_roots = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Name)
            and target.id in {"REMOTE_ROOT", "VOLUME_ROOT"}
            and isinstance(node.value, ast.Constant)
        ):
            remote_roots[target.id] = node.value.value
    assert remote_roots == {"REMOTE_ROOT": "/root", "VOLUME_ROOT": "/vol"}
    assert "str(REMOTE_ROOT)" not in source and "str(VOLUME_ROOT)" not in source
    assert "volumes={VOLUME_ROOT: volume}" in source
    assert "Path(REMOTE_ROOT)" in source and "Path(VOLUME_ROOT)" in source


def test_preparation_cli_passes_without_modal_or_archive_access():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/prepare_vimdoc_archive_content_audit.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["status"] == "PASS_LOCAL_PACKAGE_ONLY"
    assert report["preparation_manifest_files_verified"] == 10
    assert report["modal_called"] is False and report["archive_opened"] is False
