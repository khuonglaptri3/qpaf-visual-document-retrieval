from __future__ import annotations

import hashlib
from pathlib import Path

import modal_app


ROOT = Path(__file__).resolve().parents[1]


def test_modal_image_uses_the_frozen_linux_lock() -> None:
    expected_lock_hash = hashlib.sha256((ROOT / "requirements-lock.txt").read_bytes()).hexdigest()
    assert modal_app.REQUESTED_GPU == "L4"
    assert modal_app.REQUIREMENTS_LOCK_SHA256 == expected_lock_hash
    assert modal_app.IMAGE_DEFINITION["requirements_lock_sha256"] == expected_lock_hash
    assert modal_app.IMAGE_DEFINITION["python"] == "3.11"
