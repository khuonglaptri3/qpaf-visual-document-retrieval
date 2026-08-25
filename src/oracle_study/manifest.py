from __future__ import annotations

import platform
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import yaml

from .constants import SEED
from .io import sha256_file


def _run(command: list[str], cwd: str | Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def capture_manifest(
    heaven_root: str | Path | None,
    dataset_files: list[str | Path],
    output: str | Path,
    checkpoint_revisions: dict[str, str] | None = None,
) -> dict:
    commit = _run(["git", "rev-parse", "HEAD"], heaven_root) if heaven_root else None
    gpu = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    manifest = {
        "seed": SEED,
        "heaven_commit": commit,
        "checkpoint_revisions": checkpoint_revisions or {},
        "python": sys.version,
        "platform": platform.platform(),
        "gpu": gpu,
        "packages": {
            name: _package_version(name)
            for name in ["numpy", "pandas", "pyarrow", "matplotlib", "PyYAML", "torch"]
        },
        "heaven_parameters": {
            "stage1_model": "dse",
            "stage2_model": "colqwen25",
            "reduction_factor": 15,
            "alpha": 0.1,
            "filter_ratio_stage1": 0.5,
            "k": 200,
            "filter_ratio_stage2": 0.25,
            "beta": 0.3,
        },
        "dataset_files": {
            str(Path(path)): sha256_file(path) for path in dataset_files if Path(path).is_file()
        },
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return manifest
