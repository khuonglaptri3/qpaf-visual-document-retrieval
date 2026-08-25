from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not_installed"


def _git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def build_manifest(
    config_path: Path,
    lock_path: Path,
    modal_probe_path: Path,
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    modal_probe = json.loads(modal_probe_path.read_text(encoding="utf-8"))
    lock_sha256 = _sha256(lock_path)
    if modal_probe.get("requirements_lock_sha256") != lock_sha256:
        raise ValueError("Modal probe was not produced from the current dependency lock")

    local_packages = {
        name: _package_version(name)
        for name in ["modal", "torch", "numpy", "pandas", "pyarrow", "PyYAML", "pytest"]
    }
    return {
        "schema_version": 1,
        "status": "environment_frozen_dataset_materialization_pending",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": _git_output("rev-parse", "HEAD"),
        "working_tree_clean": not bool(_git_output("status", "--porcelain")),
        "environment_config_sha256": _sha256(config_path),
        "requirements_lock_sha256": lock_sha256,
        "local": {
            "python": sys.version,
            "platform": platform.platform(),
            "packages": local_packages,
            "training_allowed": False,
            "score_extraction_allowed": False,
        },
        "modal": modal_probe,
        "models": config["models"],
        "bm25": config["bm25"],
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/environment.yaml"))
    parser.add_argument("--lock", type=Path, default=Path("requirements-lock.txt"))
    parser.add_argument(
        "--modal-probe",
        type=Path,
        default=Path("artifacts/modal_environment_probe.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/environment_manifest.json"),
    )
    args = parser.parse_args()
    _write_json_atomic(
        args.output,
        build_manifest(args.config, args.lock, args.modal_probe),
    )


if __name__ == "__main__":
    main()
