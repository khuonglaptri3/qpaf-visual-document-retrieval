from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def test_dataset_metadata_is_frozen_without_payload_downloads() -> None:
    config = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
    assert config["policy"]["mode"] == "metadata_only"
    assert config["policy"]["download_performed"] is False
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
        assert dataset["download_status"] == "not_downloaded"
        assert dataset["local_dir"].startswith("/vol/datasets/")
        assert len(dataset["required_files"]) == dataset["remote_file_count"]


def test_metadata_manifest_reports_materialization_blockers() -> None:
    manifest = json.loads(
        (ROOT / "artifacts" / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "BLOCKED_PENDING_DATA_DOWNLOAD"
    assert manifest["download_performed"] is False
    assert manifest["dataset_count"] == 3
    assert {item["key"] for item in manifest["datasets"]} == {
        "vidoseek",
        "vimdoc",
        "vidore_v3_finance_en",
    }
    assert all(item["missing_materialization_fields"] for item in manifest["datasets"])
    vimdoc = next(item for item in manifest["datasets"] if item["key"] == "vimdoc")
    assert vimdoc["qrels_contract"] == "page_level_binary_qrels_eligible_pending_materialization"
    assert vimdoc["qrels_metadata"]["granularity"] == "page"
    assert vimdoc["qrels_metadata"]["relevance_mapping"] == "listed_page_is_binary_relevance_1"
    assert vimdoc["qrels_metadata"]["multi_page_queries_supported"] is True
    assert vimdoc["qrels_metadata"]["remote_query_count"] == 10_904
    assert vimdoc["protocol_status"] == "blocked_confirmation_sample_rule_requires_review"
    assert not any("page-level qrels eligibility is unresolved" in item for item in manifest["blockers"])
