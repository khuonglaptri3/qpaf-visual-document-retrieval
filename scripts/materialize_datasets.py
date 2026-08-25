from __future__ import annotations

import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def aggregate_sha256(values: dict[str, str]) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def select_query_ids(query_ids: Iterable[object], sample_size: int, seed: int) -> list[str]:
    normalized = [str(query_id) for query_id in query_ids]
    if len(normalized) != len(set(normalized)):
        raise ValueError("ViMDoc query IDs must be unique before sampling")
    if sample_size <= 0 or sample_size > len(normalized):
        raise ValueError("Sample size must be between 1 and the query count")

    ranked = sorted(
        normalized,
        key=lambda query_id: (
            hashlib.sha256(f"{seed}:{query_id}".encode("utf-8")).hexdigest(),
            query_id,
        ),
    )
    return ranked[:sample_size]


def _relative_files(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and ".cache" not in path.relative_to(root).parts
        and path.name != "_MATERIALIZED.json"
    )


def _hash_named_files(root: Path, relative_paths: list[str]) -> dict[str, str]:
    return {relative_path: sha256_file(root / relative_path) for relative_path in relative_paths}


def _vimdoc_checks(root: Path, dataset: dict[str, Any]) -> dict[str, Any]:
    import pyarrow.parquet as pq

    parquet_path = root / "data" / "ViMDoc-00000-of-00001.parquet"
    table = pq.read_table(parquet_path, columns=["id", "doc_ids"])
    query_ids = table.column("id").to_pylist()
    relevant_pages = table.column("doc_ids").to_pylist()
    if len(query_ids) != dataset["qrels_metadata"]["remote_query_count"]:
        raise ValueError("ViMDoc query count differs from frozen metadata")
    if any(not pages for pages in relevant_pages):
        raise ValueError("Every ViMDoc query must have at least one relevant page")

    required_page_ids = [str(page_id) for pages in relevant_pages for page_id in pages]
    page_counts: dict[str, int] = {}
    archive_member_names: list[str] = []
    archive_path = root / "ViMDoc_pages.tar.gz"
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive:
            if member.isfile():
                archive_member_names.append(member.name)
                page_id = Path(member.name).stem
                page_counts[page_id] = page_counts.get(page_id, 0) + 1
    unresolved = sorted({page_id for page_id in required_page_ids if page_counts.get(page_id) != 1})
    if unresolved:
        diagnostic_matches = {
            page_id: [
                member_name
                for member_name in archive_member_names
                if page_id.rsplit("_", maxsplit=1)[0] in member_name
            ][:3]
            for page_id in unresolved[:5]
        }
        raise ValueError(
            f"{len(unresolved)} ViMDoc doc_ids do not resolve to exactly one page asset; "
            f"first IDs and archive matches: {diagnostic_matches}"
        )

    protocol = dataset["confirmation_sample"]
    selected = select_query_ids(
        query_ids,
        sample_size=protocol["sample_size"],
        seed=protocol["seed"],
    )
    selected_sha256 = hashlib.sha256(("\n".join(selected) + "\n").encode("utf-8")).hexdigest()
    return {
        "query_count": len(query_ids),
        "relevance_pair_count": len(required_page_ids),
        "page_asset_count": len(page_counts),
        "all_doc_ids_resolve_once": True,
        "confirmation_sample": {
            **protocol,
            "selected_query_count": len(selected),
            "selected_query_ids": selected,
            "selected_query_ids_sha256": selected_sha256,
        },
    }


def materialize_dataset(
    config: dict[str, Any],
    dataset_key: str,
    *,
    token: str,
    function_call_id: str,
    source_commit: str,
    image_definition_sha256: str,
) -> dict[str, Any]:
    from huggingface_hub import snapshot_download

    datasets = {dataset["key"]: dataset for dataset in config["datasets"]}
    if dataset_key not in datasets:
        raise ValueError(f"Unknown dataset key: {dataset_key}")
    dataset = datasets[dataset_key]
    volume_root = Path(config["policy"]["volume_root"]).resolve()
    destination = Path(dataset["local_dir"]).resolve()
    if destination == volume_root or volume_root not in destination.parents:
        raise ValueError("Dataset destination must be a child of the configured Volume root")

    marker = destination / "_MATERIALIZED.json"
    if marker.exists():
        existing = json.loads(marker.read_text(encoding="utf-8"))
        if existing["revision"] != dataset["revision"]:
            raise ValueError("Existing materialization has a different revision")
        return existing
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite incomplete destination: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.partial-{function_call_id}"
    if temporary.exists():
        raise FileExistsError(f"Temporary materialization path already exists: {temporary}")

    snapshot_download(
        repo_id=dataset["id"],
        repo_type="dataset",
        revision=dataset["revision"],
        local_dir=temporary,
        allow_patterns=dataset["required_files"],
        token=token,
    )
    actual_files = _relative_files(temporary)
    expected_files = sorted(dataset["required_files"])
    if actual_files != expected_files:
        raise ValueError(
            f"Downloaded file inventory differs for {dataset_key}: "
            f"expected {expected_files}, got {actual_files}"
        )

    file_sha256 = _hash_named_files(temporary, actual_files)
    qrels_file_sha256 = {path: file_sha256[path] for path in dataset["qrels_files"]}
    split_file_sha256 = {path: file_sha256[path] for path in dataset["split_files"]}
    validation: dict[str, Any] = {}
    if dataset_key == "vimdoc":
        validation = _vimdoc_checks(temporary, dataset)

    record: dict[str, Any] = {
        "key": dataset["key"],
        "id": dataset["id"],
        "revision": dataset["revision"],
        "license": dataset["license"],
        "role": dataset["role"],
        "local_dir": dataset["local_dir"],
        "download_status": "materialized",
        "download_performed": True,
        "remote_file_count": dataset["remote_file_count"],
        "required_files": expected_files,
        "local_file_count": len(actual_files),
        "file_sha256": file_sha256,
        "local_file_sha256": aggregate_sha256(file_sha256),
        "qrels_sha256": aggregate_sha256(qrels_file_sha256),
        "split_sha256": aggregate_sha256(split_file_sha256),
        "qrels_contract": dataset["qrels_contract"],
        "missing_materialization_fields": [],
        "remote_metadata_verified": True,
        "materialized_at_utc": datetime.now(timezone.utc).isoformat(),
        "function_call_id": function_call_id,
        "source_commit": source_commit,
        "image_definition_sha256": image_definition_sha256,
        "validation": validation,
    }
    for optional_field in (
        "qrels_metadata",
        "protocol_status",
        "protocol_note",
        "confirmation_sample",
    ):
        if optional_field in dataset:
            record[optional_field] = dataset[optional_field]

    temporary_marker = temporary / marker.name
    temporary_marker.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return record
