from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml


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
    assert set(config["models"]) == {"bge_m3", "dse", "colqwen25"}
    assert all(HEX40.fullmatch(model["revision"]) for model in config["models"].values())


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
