from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bge_adapter_preserves_frozen_dense_semantics() -> None:
    source = (ROOT / "scripts" / "bge_m3_dense_retriever.py").read_text(encoding="utf-8")
    assert "last_hidden_state[:, 0]" in source
    assert "torch.nn.functional.normalize" in source
    assert "max_length=512" in source
    assert "max_length=8192" in source
    assert "torch.einsum" in source


def test_bge_adapter_avoids_incompatible_flagembedding_loader() -> None:
    source = (ROOT / "scripts" / "bge_m3_dense_retriever.py").read_text(encoding="utf-8")
    assert "FlagEmbedding" not in source
    assert "torch_dtype=torch.float16" in source
    assert "local_files_only=True" in source
