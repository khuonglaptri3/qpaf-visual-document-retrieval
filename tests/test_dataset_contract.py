from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def test_dataset_metadata_is_frozen_with_modal_only_payloads() -> None:
    config = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
    assert config["policy"]["mode"] == "modal_only_materialization"
    assert config["policy"]["download_performed"] is True
    assert config["policy"]["local_download_performed"] is False
    assert config["policy"]["modal_materialization_approved"] is True
    assert len(config["datasets"]) == 3
    assert {item["key"] for item in config["datasets"]} == {
        "vidoseek",
        "vimdoc",
        "vidore_v3_finance_en",
    }
    assert {item["role"] for item in config["datasets"]} == {
        "discovery",
        "confirmation",
        "sealed_external_validation",
    }
    for dataset in config["datasets"]:
        assert HEX40.fullmatch(dataset["revision"])
        assert dataset["license"]
        assert dataset["download_status"] in {"not_downloaded", "materialized_on_modal"}
        assert dataset["local_dir"].startswith("/vol/datasets/")
        assert len(dataset["required_files"]) == dataset["remote_file_count"]


def test_metadata_manifest_reports_materialization_blockers() -> None:
    manifest = json.loads(
        (ROOT / "artifacts" / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] in {
        "BLOCKED_PENDING_DATA_DOWNLOAD",
        "BLOCKED_DATASET_PROTOCOL",
    }
    assert manifest["dataset_count"] == 3
    assert {item["key"] for item in manifest["datasets"]} == {
        "vidoseek",
        "vimdoc",
        "vidore_v3_finance_en",
    }
    assert any(item["missing_materialization_fields"] for item in manifest["datasets"])
    vimdoc = next(item for item in manifest["datasets"] if item["key"] == "vimdoc")
    assert vimdoc["qrels_contract"] == "blocked_page_level_binary_qrels_362_missing_page_assets"
    assert vimdoc["qrels_metadata"]["granularity"] == "page"
    assert vimdoc["qrels_metadata"]["relevance_mapping"] == "listed_page_is_binary_relevance_1"
    assert vimdoc["qrels_metadata"]["multi_page_queries_supported"] is True
    assert vimdoc["qrels_metadata"]["remote_query_count"] == 10_904
    assert vimdoc["protocol_status"] == "approved_label_free_sha256_query_id_sample"
    assert vimdoc["confirmation_sample"]["sample_size"] == 2_000
    assert vimdoc["confirmation_sample"]["seed"] == 20_260_820
    assert vimdoc["confirmation_sample"]["allowed_fields"] == ["id"]
    assert "doc_ids" in vimdoc["confirmation_sample"]["forbidden_fields"]
    assert vimdoc["page_qrels_validation"]["unique_doc_ids_without_exact_page_asset"] == 362
    assert not any("page-level qrels eligibility is unresolved" in item for item in manifest["blockers"])
    assert not any("sample rule requires review" in item for item in manifest["blockers"])
