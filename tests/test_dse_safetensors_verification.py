from __future__ import annotations

from pathlib import Path

import torch
from safetensors.torch import load_file

from scripts.verify_dse_safetensors import (
    EXPECTED_DTYPE,
    EXPECTED_KEYS,
    _state_comparison,
    _tensor_bitwise_equal,
    _tied_weights_equal,
    write_safetensors_preserving_keys,
)


ROOT = Path(__file__).resolve().parents[1]


def test_dse_safetensors_conversion_is_bitwise_and_pinned() -> None:
    source = (ROOT / "scripts" / "verify_dse_safetensors.py").read_text(
        encoding="utf-8"
    )

    assert 'weights_only=True' in source
    assert 'mmap=True' in source
    assert '"conversion": "torch_load_bf16_clone_all_keys_safetensors_save_file"' in source
    assert '"comparison": "all_keys_shape_dtype_bitwise_equal"' in source
    assert '"status": "PASS" if passed else "FAIL"' in source
    assert EXPECTED_KEYS == 730
    assert EXPECTED_DTYPE == "torch.bfloat16"
    assert "safetensors_id" not in source


def test_conversion_retains_all_keys_and_tied_values(tmp_path: Path) -> None:
    embedding = torch.arange(12, dtype=torch.bfloat16).reshape(3, 4)
    original = {
        "model.embed_tokens.weight": embedding,
        "lm_head.weight": embedding,
        "model.layer.weight": torch.ones((2, 2), dtype=torch.bfloat16),
    }
    destination = tmp_path / "model.safetensors"

    write_safetensors_preserving_keys(original, destination)
    converted = load_file(destination, device="cpu")
    comparison = _state_comparison(original, converted)

    assert comparison["original_keys"] == 3
    assert comparison["safetensors_keys"] == 3
    assert comparison["exactly_matched_keys"] == 3
    assert _tied_weights_equal(converted) is True


def test_bitwise_check_distinguishes_signed_zero() -> None:
    positive_zero = torch.tensor([0.0], dtype=torch.bfloat16)
    negative_zero = torch.tensor([-0.0], dtype=torch.bfloat16)

    assert torch.equal(positive_zero, negative_zero) is True
    assert _tensor_bitwise_equal(positive_zero, negative_zero) is False
