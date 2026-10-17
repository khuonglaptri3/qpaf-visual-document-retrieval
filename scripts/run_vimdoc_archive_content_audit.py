"""Core for a future, separately approved ViMDoc archive content audit.

The audit is CPU-only and read-only with respect to the dataset archive. It
writes a create-once evidence directory only after explicit authorization.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Callable, Iterable

from scripts import validate_vimdoc_ocr_page_identity as identity


CONFIG_RELATIVE_PATH = "configs/vimdoc_archive_content_audit_v1.json"
CLOSED_AUTHORIZATION = {
    "execution_authorized": False,
    "approved_actor": None,
    "required_source_commit": None,
    "approved_invocations": 0,
    "approved_retries": 0,
    "approved_timeout_seconds": 0,
}


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def value_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def safe_relative(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("Configured paths must be nonempty POSIX-relative strings")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Configured path escapes its declared root")
    return target


def validate_sources(project_root: Path, config: dict) -> None:
    declared = config.get("source_files")
    if not isinstance(declared, dict) or not declared:
        raise ValueError("Source-file hashes are required")
    for relative, expected in declared.items():
        path = safe_relative(project_root, relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise ValueError(f"Source/input hash drift: {relative}")


def package_preflight(project_root: Path, config_path: Path) -> dict:
    project_root, config_path = project_root.resolve(), config_path.resolve()
    if not config_path.is_relative_to(project_root) or not config_path.is_file():
        raise ValueError("Config must be a file inside the project root")
    config = read_json(config_path)
    if config.get("status") != "PREPARED_LOCAL_REVIEW_EXECUTION_CLOSED":
        raise ValueError("Audit package status is not closed preparation")
    if json.dumps(config.get("authorization"), sort_keys=True) != json.dumps(CLOSED_AUTHORIZATION, sort_keys=True):
        raise PermissionError("Execution authorization must remain closed during preparation")
    resources = config["resources"]
    if resources != {
        "cpu_physical_cores": 1.0,
        "memory_mb": 4096,
        "gpu": None,
        "timeout_seconds": 21600,
        "retries": 0,
        "region": None,
        "max_output_bytes": 134217728,
        "minimum_free_volume_bytes": 1073741824,
    }:
        raise ValueError("Resource contract drift")
    if config["modal"]["secret_names"] != [] or config["modal"]["network_required"] is not False:
        raise ValueError("The content audit must require neither secrets nor network")
    price = config["pricing_snapshot"]
    computed = 21600 * (1.0 * price["cpu_usd_per_core_second"] + 4 * price["memory_usd_per_gib_second"])
    if abs(computed - price["maximum_reserved_compute_usd_at_timeout"]) > 1e-12:
        raise ValueError("Pricing arithmetic drift")
    if price["review_budget_usd"] < computed:
        raise ValueError("Review budget is below the reserved-resource estimate")
    validate_sources(project_root, config)
    receipt = read_json(project_root / config["input"]["materialization_receipt"])
    if receipt["revision"] != config["input"]["dataset_revision"]:
        raise ValueError("Dataset revision differs from materialization receipt")
    if receipt["file_sha256"]["ViMDoc_pages.tar.gz"] != config["input"]["archive_sha256"]:
        raise ValueError("Archive hash differs from materialization receipt")
    return {
        "status": "PASS_LOCAL_PACKAGE_ONLY",
        "config_sha256": file_sha256(config_path),
        "source_files_verified": len(config["source_files"]),
        "execution_authorized": False,
        "approved_invocations": 0,
        "modal_called": False,
        "archive_opened": False,
        "ocr_executed": False,
        "extraction_executed": False,
        "training_executed": False,
        "proposed_resources": resources,
        "maximum_reserved_compute_usd_at_timeout": computed,
        "pricing_must_be_refreshed_before_approval": True,
    }


def execution_guard(config: dict, actor: str, source_commit: str) -> None:
    authorization = config.get("authorization", {})
    if (
        authorization.get("execution_authorized") is not True
        or authorization.get("approved_invocations") != 1
        or authorization.get("approved_retries") != 0
        or authorization.get("approved_timeout_seconds") != config["resources"]["timeout_seconds"]
        or authorization.get("approved_actor") != actor
        or authorization.get("required_source_commit") != source_commit
    ):
        raise PermissionError("Separate exact audit execution approval is pending; no attempt consumed")


def write_json_x(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def write_jsonl_x(path: Path, rows: Iterable[dict]) -> tuple[str, int, int]:
    digest, size, count = hashlib.sha256(), 0, 0
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            line = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            stream.write(line)
            encoded = line.encode("utf-8")
            digest.update(encoded)
            size += len(encoded)
            count += 1
        stream.flush()
        os.fsync(stream.fileno())
    return digest.hexdigest(), size, count


def output_inventory(output: Path, excluded: set[str]) -> dict[str, dict[str, object]]:
    inventory = {}
    for path in sorted(output.rglob("*")):
        if path.is_file():
            relative = path.relative_to(output).as_posix()
            if relative not in excluded:
                inventory[relative] = {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
    return inventory


def verify_jsonl(path: Path, expected_sha256: str, expected_rows: int) -> None:
    if file_sha256(path) != expected_sha256:
        raise ValueError(f"Persisted JSONL byte hash mismatch: {path.name}")
    with path.open("rb") as stream:
        observed_rows = sum(1 for line in stream if line.strip())
    if observed_rows != expected_rows:
        raise ValueError(f"Persisted JSONL row-count mismatch: {path.name}")


def copy_sources(project_root: Path, output: Path, source_files: dict[str, str]) -> None:
    for relative, expected in sorted(source_files.items()):
        source = safe_relative(project_root, relative)
        destination = output / "source_snapshot" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        if file_sha256(destination) != expected:
            raise ValueError(f"Source snapshot hash drift: {relative}")


def audit_summary(report: dict) -> dict:
    return {key: value for key, value in report.items() if key not in {"assets", "pages"}}


def process_peak_rss_bytes() -> int | None:
    try:
        import resource  # Linux runtime; unavailable in the Windows local test environment.
    except ImportError:
        return None
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def run_audit(
    project_root: Path,
    volume_root: Path,
    config_path: Path,
    expected_config_sha256: str,
    actor: str,
    source_commit: str,
    function_call_id: str,
    commit: Callable[[], None],
) -> dict:
    project_root, volume_root, config_path = (
        project_root.resolve(), volume_root.resolve(), config_path.resolve()
    )
    if file_sha256(config_path) != expected_config_sha256:
        raise ValueError("Caller config SHA-256 mismatch")
    config = read_json(config_path)
    execution_guard(config, actor, source_commit)
    validate_sources(project_root, config)
    archive = safe_relative(volume_root, config["input"]["archive_relative_path"])
    output = safe_relative(volume_root, config["output"]["directory_relative_path"])
    if not archive.is_file():
        raise FileNotFoundError("Frozen ViMDoc archive is absent")
    if output.exists():
        raise FileExistsError("Create-once audit output already exists; retry is forbidden")
    if shutil.disk_usage(output.parent if output.parent.exists() else volume_root).free < config["resources"]["minimum_free_volume_bytes"]:
        raise RuntimeError("Insufficient free Volume space for bounded audit evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    started_wall, started_perf = time.time(), time.perf_counter()
    attempt = {
        "schema_version": 1,
        "package_id": config["package_id"],
        "status": "STARTED_DATA_INTEGRITY_ONLY",
        "function_call_id": function_call_id,
        "actor": actor,
        "source_commit": source_commit,
        "config_sha256": expected_config_sha256,
        "archive_relative_path": config["input"]["archive_relative_path"],
        "archive_expected_sha256": config["input"]["archive_sha256"],
        "started_unix_seconds": started_wall,
        "consumed_invocations": 1,
        "remaining_authorized_invocations": 0,
        "retries_allowed": 0,
        "classification": "read_only_source_archive_content_audit_not_scientific_result",
    }
    write_json_x(output / "_ATTEMPTED.json", attempt)
    commit()
    stage = "source_snapshot"
    try:
        copy_sources(project_root, output, config["source_files"])
        stage = "archive_hash_and_content_scan"
        report = identity.inspect_tar(archive)
        stage = "raw_asset_evidence"
        asset_hash, asset_bytes, asset_count = write_jsonl_x(
            output / "asset_inventory.jsonl", report["assets"]
        )
        write_json_x(output / "audit_summary.json", audit_summary(report))
        stage = "frozen_identity_contract"
        checked = identity.enforce_frozen_identity_contract(
            report, read_json(project_root / config["input"]["identity_spec"])
        )
        stage = "canonical_page_evidence"
        page_hash, page_bytes, page_count = write_jsonl_x(
            output / "canonical_pages.jsonl", checked["pages"]
        )
        if asset_hash != checked["asset_inventory_sha256"] or page_hash != checked["canonical_pages_sha256"]:
            raise ValueError("Persisted JSONL hashes differ from in-memory canonical audit")
        if asset_count != checked["asset_count"] or page_count != checked["canonical_page_count"]:
            raise ValueError("Persisted JSONL row counts differ from audit counts")
        verify_jsonl(output / "asset_inventory.jsonl", asset_hash, asset_count)
        verify_jsonl(output / "canonical_pages.jsonl", page_hash, page_count)
        stage = "output_bounds"
        current_inventory = output_inventory(output, {"run_manifest.json", "_SUCCESS.json"})
        current_bytes = sum(int(item["bytes"]) for item in current_inventory.values())
        if current_bytes > config["resources"]["max_output_bytes"]:
            raise RuntimeError("Audit evidence exceeds the frozen output-size cap")
        elapsed = time.perf_counter() - started_perf
        peak_rss_bytes = process_peak_rss_bytes()
        manifest = {
            "schema_version": 1,
            "package_id": config["package_id"],
            "status": "COMPLETE",
            "classification": "DATA_INTEGRITY_ONLY_NO_OCR_NO_EXTRACTION_NO_TRAINING",
            "function_call_id": function_call_id,
            "source_commit": source_commit,
            "config_sha256": expected_config_sha256,
            "archive_sha256": checked["archive_sha256"],
            "archive_bytes": checked["archive_bytes"],
            "asset_count": checked["asset_count"],
            "canonical_page_count": checked["canonical_page_count"],
            "document_count": checked["document_count"],
            "extra_assets_sharing_page_id": checked["extra_assets_sharing_page_id"],
            "different_content_collision_count": 0,
            "asset_inventory_sha256": asset_hash,
            "canonical_pages_sha256": page_hash,
            "asset_inventory_bytes": asset_bytes,
            "canonical_pages_bytes": page_bytes,
            "elapsed_seconds": elapsed,
            "peak_process_rss_bytes": peak_rss_bytes,
            "requested_resources": config["resources"],
            "artifact_inventory": current_inventory,
            "scientific_metrics_computed": False,
            "ocr_executed": False,
            "retriever_extraction_executed": False,
            "optimizer_steps": 0,
        }
        write_json_x(output / "run_manifest.json", manifest)
        success = {
            "status": "SUCCESS",
            "package_id": config["package_id"],
            "run_manifest_sha256": file_sha256(output / "run_manifest.json"),
            "asset_inventory_sha256": asset_hash,
            "canonical_pages_sha256": page_hash,
            "remaining_authorized_invocations": 0,
        }
        write_json_x(output / "_SUCCESS.json", success)
        commit()
        return manifest
    except BaseException as error:
        failure = {
            "schema_version": 1,
            "package_id": config["package_id"],
            "status": "FAILED_ATTEMPT_CONSUMED_NO_RETRY",
            "stage": stage,
            "error_type": type(error).__name__,
            "error_message": str(error)[:1000],
            "elapsed_seconds": time.perf_counter() - started_perf,
            "remaining_authorized_invocations": 0,
            "success_marker_written": False,
        }
        try:
            write_json_x(output / "_FAILED.json", failure)
            commit()
        finally:
            raise
