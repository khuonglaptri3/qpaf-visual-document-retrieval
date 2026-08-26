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


def test_dataset_manifest_reports_complete_materialization() -> None:
    manifest = json.loads(
        (ROOT / "artifacts" / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "PASS"
    assert manifest["download_performed"] is True
    assert manifest["dataset_count"] == 3
    assert {item["key"] for item in manifest["datasets"]} == {
        "vidoseek",
        "vimdoc",
        "vidore_v3_finance_en",
    }
    assert all(not item["missing_materialization_fields"] for item in manifest["datasets"])
    vimdoc = next(item for item in manifest["datasets"] if item["key"] == "vimdoc")
    assert vimdoc["qrels_contract"] == "heaven_aligned_document_level_binary_qrels"
    assert vimdoc["qrels_metadata"]["granularity"] == "document"
    assert vimdoc["qrels_metadata"]["document_id_transform"] == "remove_final_underscore_segment"
    assert vimdoc["qrels_metadata"]["relevance_mapping"] == "transformed_document_is_binary_relevance_1"
    assert vimdoc["qrels_metadata"]["multi_document_queries_supported"] is True
    assert vimdoc["qrels_metadata"]["remote_query_count"] == 10_904
    assert vimdoc["protocol_status"] == "approved_label_free_sha256_query_id_sample"
    assert vimdoc["confirmation_sample"]["sample_size"] == 2_000
    assert vimdoc["confirmation_sample"]["seed"] == 20_260_820
    assert vimdoc["confirmation_sample"]["allowed_fields"] == ["id"]
    assert "doc_ids" in vimdoc["confirmation_sample"]["forbidden_fields"]
    assert vimdoc["page_qrels_validation"]["unique_raw_ids_not_resolving_exactly_once"] == 362
    assert vimdoc["page_qrels_validation"]["status"] == "resolved_by_document_level_protocol"
    assert vimdoc["confirmation_evaluation"]["document_score_aggregation"] == "max_page_score"
    assert vimdoc["validation"]["all_qrels_documents_resolve_to_pages"] is True
    assert vimdoc["validation"]["page_asset_file_count"] == 76_347
    assert vimdoc["validation"]["unique_extension_stripped_page_id_count"] == 70_080
    assert vimdoc["validation"]["heaven_document_count"] == 1_247
    assert vimdoc["validation"]["confirmation_sample"]["selected_query_count"] == 2_000
    assert manifest["blockers"] == []
