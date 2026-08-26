from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from scripts import capture_environment


ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def test_environment_config_freezes_compatible_retriever_stack() -> None:
    config = yaml.safe_load((ROOT / "configs" / "environment.yaml").read_text(encoding="utf-8"))
    packages = config["packages"]
    assert packages["torch"] == "2.7.1"
    assert packages["torchvision"] == "0.22.1"
    assert packages["colpali-engine"] == "0.3.12"
    assert packages["transformers"] == "4.53.3"
    assert config["modal"]["python"] == "3.11"
    assert config["modal"]["default_gpu"] == "L4"
    assert config["modal"]["score_extraction_gpu"] == "A100-40GB"
    assert config["modal"]["score_extraction_cpu"] == 4.0
    assert config["modal"]["score_extraction_memory_mb"] == 32_768
    assert set(config["models"]) == {"bge_m3", "dse", "colqwen25"}
    assert all(HEX40.fullmatch(model["revision"]) for model in config["models"].values())
    assert config["models"]["colqwen25"]["base_id"] == "vidore/colqwen2.5-base"
    assert HEX40.fullmatch(config["models"]["colqwen25"]["base_revision"])
    assert config["models"]["dse"]["safetensors_id"] == (
        "ielabgroup/dse-qwen2-2b-mrl-v1-safetensor"
    )
    assert HEX40.fullmatch(config["models"]["dse"]["safetensors_revision"])


def test_linux_lock_is_fully_pinned_and_hashed() -> None:
    lock_path = ROOT / "requirements-lock.txt"
    lock_text = lock_path.read_text(encoding="utf-8")
    requirement_lines = [
        line for line in lock_text.splitlines() if line and not line.startswith((" ", "#", "--"))
    ]
    assert len(requirement_lines) >= 100
    assert all("==" in line for line in requirement_lines)
    assert "torch==2.7.1" in lock_text
    assert "colpali-engine==0.3.12" in lock_text
    assert "transformers==4.53.3" in lock_text
    assert "--hash=sha256:" in lock_text
    assert len(hashlib.sha256(lock_path.read_bytes()).hexdigest()) == 64


def test_environment_manifest_requires_passed_dataset_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "environment.yaml"
    config_path.write_text("models: {}\nbm25: {}\n", encoding="utf-8")
    lock_path = tmp_path / "requirements-lock.txt"
    lock_path.write_text("fixture==1.0\n", encoding="utf-8")
    lock_sha256 = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    probe_path = tmp_path / "modal_environment_probe.json"
    probe_path.write_text(
        json.dumps({"requirements_lock_sha256": lock_sha256, "source_commit": "a" * 40}),
        encoding="utf-8",
    )
    dataset_path = tmp_path / "dataset_manifest.json"
    dataset_path.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    monkeypatch.setattr(
        capture_environment,
        "_git_output",
        lambda *args: "a" * 40 if args == ("rev-parse", "HEAD") else "",
    )

    manifest = capture_environment.build_manifest(
        config_path,
        lock_path,
        probe_path,
        dataset_path,
        tmp_path / "environment_manifest.json",
    )
    assert manifest["status"] == "PASS"
    assert manifest["working_tree_clean_except_generated_probe"] is True
    assert manifest["dataset_manifest_sha256"] == hashlib.sha256(
        dataset_path.read_bytes()
    ).hexdigest()
