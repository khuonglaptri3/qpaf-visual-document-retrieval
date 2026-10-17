from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_adapter_import_is_model_load_free_and_revisions_are_pinned() -> None:
    path = ROOT / "scripts" / "colqwen25_retriever.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls = [node for node in tree.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)]
    assert top_level_calls == []
    assert source.count("revision=base_revision") == 1
    assert source.count("revision=adapter_revision") == 2
    assert "PeftModel.from_pretrained" in source
    assert "snapshot_download" in source
    assert '"additional_chat_templates/*"' in source
    assert "local_files_only=True" in source
    assert "torch_dtype=torch.bfloat16" in source


def test_adapter_scores_on_cpu_without_reloading_the_model() -> None:
    source = (ROOT / "scripts" / "colqwen25_retriever.py").read_text(encoding="utf-8")
    score_body = source.split("def get_scores", maxsplit=1)[1]
    assert 'device="cpu"' in score_body
    assert "from_pretrained" not in score_body
