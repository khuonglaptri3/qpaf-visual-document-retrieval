from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dse_safetensors_verification_is_bitwise_and_pinned() -> None:
    source = (ROOT / "scripts" / "verify_dse_safetensors.py").read_text(
        encoding="utf-8"
    )

    assert 'weights_only=True' in source
    assert 'mmap=True' in source
    assert 'torch.equal(original_tensor, mirror_tensor)' in source
    assert '"status": "PASS" if passed else "FAIL"' in source
    assert 'raise RuntimeError("DSE safetensors mirror is not bitwise equivalent")' in source
