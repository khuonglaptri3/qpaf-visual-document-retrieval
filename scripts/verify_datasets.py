from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _hub_metadata(dataset_id: str) -> dict[str, Any]:
    url = f"https://huggingface.co/api/datasets/{dataset_id}"
    request = urllib.request.Request(url, headers={"User-Agent": "qpaf-metadata-verifier/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def verify_metadata(config: dict[str, Any], refresh_remote: bool) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for dataset in config["datasets"]:
        required_files = sorted(dataset["required_files"])
        record: dict[str, Any] = {
            "key": dataset["key"],
            "id": dataset["id"],
            "revision": dataset["revision"],
            "license": dataset["license"],
            "role": dataset["role"],
            "local_dir": dataset["local_dir"],
            "download_status": "not_downloaded",
            "download_performed": False,
            "remote_file_count": dataset["remote_file_count"],
            "required_files": required_files,
            "qrels_contract": dataset["qrels_contract"],
            "missing_materialization_fields": [
                "local_file_count",
                "local_file_sha256",
                "qrels_sha256",
                "split_sha256",
            ],
        }
        for optional_field in (
            "qrels_metadata",
            "protocol_status",
            "protocol_note",
            "confirmation_sample",
            "page_qrels_validation",
        ):
            if optional_field in dataset:
                record[optional_field] = dataset[optional_field]
        if refresh_remote:
            remote = _hub_metadata(dataset["id"])
            remote_files = sorted(item["rfilename"] for item in remote.get("siblings", []))
            remote_license = remote.get("cardData", {}).get("license")
            if remote.get("sha") != dataset["revision"]:
                raise ValueError(f"Revision drift for {dataset['id']}")
            if remote_license != dataset["license"]:
                raise ValueError(f"License drift for {dataset['id']}")
            if remote_files != required_files:
                raise ValueError(f"Remote file inventory drift for {dataset['id']}")
            record["remote_metadata_verified"] = True
        else:
            record["remote_metadata_verified"] = False
        records.append(record)

    return {
        "schema_version": 1,
        "status": "BLOCKED_PENDING_DATA_DOWNLOAD",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "download_performed": False,
        "dataset_count": len(records),
        "datasets": records,
        "blockers": [
            "Dataset payloads were intentionally not downloaded.",
            "File counts, file SHA-256 values, split hashes, and qrels hashes are unavailable.",
        ],
    }


def merge_materializations(
    config: dict[str, Any],
    materialization_records: list[dict[str, Any]],
) -> dict[str, Any]:
    records_by_key = {record["key"]: record for record in materialization_records}
    expected_keys = [dataset["key"] for dataset in config["datasets"]]
    unexpected = sorted(set(records_by_key) - set(expected_keys))
    if unexpected:
        raise ValueError(f"Unexpected materialization records: {unexpected}")

    metadata_manifest = verify_metadata(config, refresh_remote=False)
    merged_records: list[dict[str, Any]] = []
    for metadata_record in metadata_manifest["datasets"]:
        materialized = records_by_key.get(metadata_record["key"])
        if materialized is None:
            merged_records.append(metadata_record)
            continue
        if materialized["revision"] != metadata_record["revision"]:
            raise ValueError(f"Revision mismatch for {metadata_record['key']}")
        merged_records.append(materialized)

    missing = [key for key in expected_keys if key not in records_by_key]
    protocol_blockers = [
        f"{dataset['key']}: {dataset['page_qrels_validation']['interpretation']}"
        for dataset in config["datasets"]
        if dataset.get("page_qrels_validation", {}).get("status") == "blocked"
    ]
    complete = not missing and not protocol_blockers
    if protocol_blockers:
        status = "BLOCKED_DATASET_PROTOCOL"
    elif missing:
        status = "BLOCKED_PENDING_DATA_DOWNLOAD"
    else:
        status = "PASS"
    return {
        "schema_version": 1,
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "download_performed": bool(materialization_records),
        "dataset_count": len(merged_records),
        "datasets": merged_records,
        "blockers": protocol_blockers
        + [f"Missing Modal materialization: {key}" for key in missing],
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/datasets.yaml"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/dataset_manifest.json"),
    )
    parser.add_argument("--refresh-remote", action="store_true")
    parser.add_argument(
        "--materialization-result",
        type=Path,
        action="append",
        default=[],
    )
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if args.materialization_result:
        records = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in args.materialization_result
        ]
        manifest = merge_materializations(config, records)
    else:
        manifest = verify_metadata(config, refresh_remote=args.refresh_remote)
    _write_json_atomic(args.output, manifest)


if __name__ == "__main__":
    main()
