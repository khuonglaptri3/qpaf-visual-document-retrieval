from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dse_adapter_loads_pinned_weights_directly_on_device() -> None:
    source = (ROOT / "scripts" / "dse_qwen2_retriever.py").read_text(encoding="utf-8")

    assert "class DSEQwen2DirectRetriever(DSEQwen2Retriever)" in source
    assert "torch_dtype=torch.bfloat16" in source
    assert "device_map=str(self.device)" in source
    assert "low_cpu_mem_usage=True" in source
    assert ".to(self.device)" not in source
