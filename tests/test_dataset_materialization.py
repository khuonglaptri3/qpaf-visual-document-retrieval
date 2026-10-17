from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.materialize_datasets import (
    _vimdoc_checks,
    aggregate_sha256,
    heaven_document_id,
    materialize_dataset,
    select_query_ids,
)
from scripts.verify_datasets import merge_materializations


ROOT = Path(__file__).resolve().parents[1]


def test_vimdoc_sample_is_deterministic_and_query_id_only() -> None:
    query_ids = ["q3", "q1", "q4", "q2"]
    selected = select_query_ids(query_ids, sample_size=2, seed=20260820)
    expected = sorted(
        query_ids,
        key=lambda query_id: (
            hashlib.sha256(f"20260820:{query_id}".encode("utf-8")).hexdigest(),
            query_id,
        ),
    )[:2]
    assert selected == expected
    assert select_query_ids(reversed(query_ids), sample_size=2, seed=20260820) == expected


def test_vimdoc_sample_rejects_duplicate_or_invalid_query_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        select_query_ids(["q1", "q1"], sample_size=1, seed=20260820)
    with pytest.raises(ValueError, match="Sample size"):
        select_query_ids(["q1"], sample_size=2, seed=20260820)


def test_heaven_document_id_removes_only_the_final_segment() -> None:
    assert heaven_document_id("IBM_Annual_Report_2010_page_131") == "IBM_Annual_Report_2010_page"
    assert heaven_document_id("05-03-18-political-release_10") == "05-03-18-political-release"
    with pytest.raises(ValueError, match="Invalid HEAVEN"):
        heaven_document_id("missing-separator")


def test_vimdoc_validation_uses_document_mapping_not_exact_page_qrels(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pq.write_table(
        pa.table({"id": ["q1"], "doc_ids": [["report_9"]]}),
        data_dir / "ViMDoc-00000-of-00001.parquet",
    )
    with tarfile.open(tmp_path / "ViMDoc_pages.tar.gz", mode="w:gz") as archive:
        for name in ("pages/report_1.jpg", "pages/report_2.jpg", "pages/README.txt"):
            payload = b"fixture"
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))

    dataset = {
        "qrels_metadata": {
            "remote_query_count": 1,
            "expected_page_asset_file_count": 2,
            "dataset_card_document_count": 1,
            "expected_heaven_document_count": 1,
            "expected_raw_ids_not_resolving_exactly_once": 1,
            "expected_unique_extension_stripped_page_id_count": 2,
        },
        "confirmation_sample": {"sample_size": 1, "seed": 20260820},
    }
    validation = _vimdoc_checks(tmp_path, dataset)
    assert validation["all_qrels_documents_resolve_to_pages"] is True
    assert validation["raw_ids_not_resolving_exactly_once_count"] == 1
    assert validation["document_relevance_pair_count"] == 1
    assert len(validation["document_qrels_sha256"]) == 64


def test_aggregate_hash_is_independent_of_mapping_order() -> None:
    left = aggregate_sha256({"b": "2", "a": "1"})
    right = aggregate_sha256({"a": "1", "b": "2"})
    assert left == right
    assert len(left) == 64


def test_merge_materializations_requires_all_three_records_for_pass() -> None:
    config = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
    records = []
    for dataset in config["datasets"]:
        records.append(
            {
                "key": dataset["key"],
                "revision": dataset["revision"],
                "download_performed": True,
                "missing_materialization_fields": [],
            }
        )
    manifest = merge_materializations(config, records)
    assert manifest["status"] == "PASS"
    assert manifest["download_performed"] is True
    assert manifest["blockers"] == []
    assert json.loads(json.dumps(manifest))["dataset_count"] == 3


def test_merge_materializations_preserves_unapproved_protocol_blocker() -> None:
    config = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
    config["datasets"][1]["page_qrels_validation"]["status"] = "blocked"
    config["datasets"][1]["page_qrels_validation"][
        "interpretation"
    ] = "frozen ViMDoc is not eligible as exact page-level qrels"
    records = [
        {
            "key": dataset["key"],
            "revision": dataset["revision"],
            "download_performed": True,
            "missing_materialization_fields": [],
        }
        for dataset in config["datasets"]
    ]
    manifest = merge_materializations(config, records)
    assert manifest["status"] == "BLOCKED_DATASET_PROTOCOL"
    assert any("exact page-level qrels" in blocker for blocker in manifest["blockers"])


def test_materialization_atomically_moves_snapshot_and_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "datasets" / "tiny" / ("a" * 40)
    config: dict[str, Any] = {
        "policy": {"volume_root": str(tmp_path / "datasets")},
        "datasets": [
            {
                "key": "tiny",
                "id": "owner/tiny",
                "revision": "a" * 40,
                "license": "apache-2.0",
                "role": "discovery",
                "local_dir": str(destination),
                "remote_file_count": 2,
                "required_files": ["queries.json", "qrels.json"],
                "qrels_files": ["qrels.json"],
                "split_files": ["queries.json", "qrels.json"],
                "qrels_contract": "fixture",
            }
        ],
    }

    def fake_snapshot_download(**kwargs: Any) -> str:
        local_dir = Path(kwargs["local_dir"])
        local_dir.mkdir(parents=True)
        (local_dir / "queries.json").write_text("[]\n", encoding="utf-8")
        (local_dir / "qrels.json").write_text("{}\n", encoding="utf-8")
        return str(local_dir)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)
    record = materialize_dataset(
        config,
        "tiny",
        token="test-token",
        function_call_id="fc-test",
        source_commit="b" * 40,
        image_definition_sha256="c" * 64,
    )

    assert record["download_status"] == "materialized"
    assert destination.is_dir()
    assert (destination / "_MATERIALIZED.json").is_file()
    assert not (destination.parent / f".{destination.name}.partial-fc-test").exists()


def test_validated_vimdoc_marker_can_finalize_approved_contract(tmp_path: Path) -> None:
    destination = tmp_path / "datasets" / "vimdoc" / ("a" * 40)
    destination.mkdir(parents=True)
    marker = destination / "_MATERIALIZED.json"
    marker.write_text(
        json.dumps(
            {
                "revision": "a" * 40,
                "qrels_contract": "heaven_aligned_document_level_binary_qrels_pending_materialization",
                "validation": {"all_qrels_documents_resolve_to_pages": True},
            }
        ),
        encoding="utf-8",
    )
    dataset = {
        "key": "vimdoc",
        "revision": "a" * 40,
        "qrels_contract": "heaven_aligned_document_level_binary_qrels",
        "qrels_metadata": {"granularity": "document"},
        "confirmation_evaluation": {"unit": "document"},
        "page_qrels_validation": {"status": "resolved_by_document_level_protocol"},
        "local_dir": str(destination),
    }
    config = {
        "policy": {"volume_root": str(tmp_path / "datasets")},
        "datasets": [dataset],
    }
    refreshed = materialize_dataset(
        config,
        "vimdoc",
        token="test-token",
        function_call_id="fc-refresh",
        source_commit="b" * 40,
        image_definition_sha256="c" * 64,
    )
    assert refreshed["qrels_contract"] == "heaven_aligned_document_level_binary_qrels"
    assert json.loads(marker.read_text(encoding="utf-8"))["qrels_metadata"]["granularity"] == "document"
