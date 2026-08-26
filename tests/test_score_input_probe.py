from __future__ import annotations

import json
import tarfile
import zipfile
from pathlib import Path

import pandas as pd

from scripts.probe_score_inputs import _adapter_readiness, inspect_path


def test_probe_reports_schema_without_payload_values(tmp_path: Path) -> None:
    parquet_path = tmp_path / "rows.parquet"
    pd.DataFrame({"query_id": ["secret"], "score": [1.0]}).to_parquet(parquet_path)
    detail = inspect_path(parquet_path)
    assert detail["kind"] == "parquet"
    assert detail["rows"] == 1
    assert [column["name"] for column in detail["columns"]] == ["query_id", "score"]
    assert "secret" not in json.dumps(detail)


def test_probe_reports_json_shape_only(tmp_path: Path) -> None:
    path = tmp_path / "rows.json"
    path.write_text(json.dumps([{"query": "secret", "doc_ids": ["hidden"]}]), encoding="utf-8")
    detail = inspect_path(path)
    assert detail["item_keys"] == ["doc_ids", "query"]
    assert "secret" not in json.dumps(detail)
    assert "hidden" not in json.dumps(detail)


def test_probe_reports_archive_inventory_without_extracting(tmp_path: Path) -> None:
    zip_path = tmp_path / "pages.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("a/page.png", b"image")
    assert inspect_path(zip_path)["suffix_counts"] == {".png": 1}

    tar_path = tmp_path / "pages.tar.gz"
    payload = tmp_path / "page.jpg"
    payload.write_bytes(b"image")
    with tarfile.open(tar_path, "w:gz") as archive:
        archive.add(payload, arcname="b/page.jpg")
    assert inspect_path(tar_path)["suffix_counts"] == {".jpg": 1}


def test_readiness_allows_only_declared_vidore_adapter() -> None:
    retrievers = {"imports": {"local_colqwen25_adapter": {"status": "available"}}}
    files = {
        "corpus/part.parquet": {
            "columns": [
                {"name": "corpus_id"},
                {"name": "image"},
                {"name": "markdown"},
            ]
        }
    }
    assert _adapter_readiness("vidore_v3_finance_en", files, retrievers) == {
        "status": "ready_for_gpu_smoke",
        "blockers": [],
    }
    assert _adapter_readiness("vidoseek", {}, retrievers)["status"] == "blocked"
    assert _adapter_readiness("vimdoc", {}, retrievers)["status"] == "blocked"
