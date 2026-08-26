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


def heaven_document_id(page_id: object) -> str:
    normalized = str(page_id)
    document_id, separator, page_suffix = normalized.rpartition("_")
    if not separator or not document_id or not page_suffix:
        raise ValueError(f"Invalid HEAVEN page identifier: {normalized}")
    return document_id


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
    relevant_page_ids = table.column("doc_ids").to_pylist()
    if len(query_ids) != dataset["qrels_metadata"]["remote_query_count"]:
        raise ValueError("ViMDoc query count differs from frozen metadata")
    if any(not pages for pages in relevant_page_ids):
        raise ValueError("Every ViMDoc query must have at least one relevant document")

    required_page_ids = [str(page_id) for pages in relevant_page_ids for page_id in pages]
    page_counts: dict[str, int] = {}
    document_page_counts: dict[str, int] = {}
    image_file_count = 0
    archive_path = root / "ViMDoc_pages.tar.gz"
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive:
            if member.isfile() and Path(member.name).suffix.lower() in {".jpg", ".jpeg", ".png"}:
                image_file_count += 1
                page_id = Path(member.name).stem
                page_counts[page_id] = page_counts.get(page_id, 0) + 1
                document_id = heaven_document_id(page_id)
                document_page_counts[document_id] = document_page_counts.get(document_id, 0) + 1

    metadata = dataset["qrels_metadata"]
    if image_file_count != metadata["expected_page_asset_file_count"]:
        raise ValueError(
            f"ViMDoc image-file count {image_file_count} differs from frozen "
            f"{metadata['expected_page_asset_file_count']}"
        )
    if len(page_counts) != metadata["expected_unique_extension_stripped_page_id_count"]:
        raise ValueError(
            f"ViMDoc unique page-ID count {len(page_counts)} differs from frozen "
            f"{metadata['expected_unique_extension_stripped_page_id_count']}"
        )
    if len(document_page_counts) != metadata["expected_heaven_document_count"]:
        raise ValueError(
            f"ViMDoc HEAVEN document count {len(document_page_counts)} differs from frozen "
            f"{metadata['expected_heaven_document_count']}"
        )

    raw_ids_not_resolving_exactly_once = sorted(
        {page_id for page_id in required_page_ids if page_counts.get(page_id) != 1}
    )
    if (
        len(raw_ids_not_resolving_exactly_once)
        != metadata["expected_raw_ids_not_resolving_exactly_once"]
    ):
        raise ValueError("ViMDoc raw page-ID mismatch count differs from the frozen audit")

    relevant_documents = [
        sorted({heaven_document_id(page_id) for page_id in pages})
        for pages in relevant_page_ids
    ]
    unresolved_documents = sorted(
        {
            document_id
            for documents in relevant_documents
            for document_id in documents
            if document_page_counts.get(document_id, 0) < 1
        }
    )
    if unresolved_documents:
        raise ValueError(
            f"{len(unresolved_documents)} ViMDoc qrels documents have no page assets; "
            f"first IDs: {unresolved_documents[:5]}"
        )

    canonical_qrels = sorted(
        (str(query_id), document_id, 1)
        for query_id, documents in zip(query_ids, relevant_documents, strict=True)
        for document_id in documents
    )
    document_qrels_sha256 = hashlib.sha256(
        "".join(
            f"{query_id}\t{document_id}\t{relevance}\n"
            for query_id, document_id, relevance in canonical_qrels
        ).encode("utf-8")
    ).hexdigest()

    protocol = dataset["confirmation_sample"]
    selected = select_query_ids(
        query_ids,
        sample_size=protocol["sample_size"],
        seed=protocol["seed"],
    )
    selected_sha256 = hashlib.sha256(("\n".join(selected) + "\n").encode("utf-8")).hexdigest()
    return {
        "query_count": len(query_ids),
        "raw_relevance_id_count": len(required_page_ids),
        "document_relevance_pair_count": len(canonical_qrels),
        "page_asset_file_count": image_file_count,
        "unique_extension_stripped_page_id_count": len(page_counts),
        "duplicate_extension_stripped_page_asset_count": image_file_count - len(page_counts),
        "heaven_document_count": len(document_page_counts),
        "dataset_card_document_count": metadata["dataset_card_document_count"],
        "raw_ids_not_resolving_exactly_once_count": len(
            raw_ids_not_resolving_exactly_once
        ),
        "raw_ids_not_resolving_exactly_once_sample": raw_ids_not_resolving_exactly_once[:20],
        "all_qrels_documents_resolve_to_pages": True,
        "document_qrels_sha256": document_qrels_sha256,
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
        if existing["qrels_contract"] != dataset["qrels_contract"]:
            validation = existing.get("validation", {})
            if not (
                dataset_key == "vimdoc"
                and dataset["qrels_contract"] == "heaven_aligned_document_level_binary_qrels"
                and validation.get("all_qrels_documents_resolve_to_pages") is True
            ):
                raise ValueError("Existing materialization has a different qrels contract")
            existing["qrels_contract"] = dataset["qrels_contract"]
            for field in ("qrels_metadata", "confirmation_evaluation", "page_qrels_validation"):
                existing[field] = dataset[field]
            existing["protocol_metadata_refreshed_at_utc"] = datetime.now(timezone.utc).isoformat()
            marker.write_text(
                json.dumps(existing, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
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
    source_qrels_sha256 = aggregate_sha256(qrels_file_sha256)
    qrels_sha256 = validation.get("document_qrels_sha256", source_qrels_sha256)

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
        "qrels_sha256": qrels_sha256,
        "qrels_source_file_sha256": source_qrels_sha256,
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
        "confirmation_evaluation",
        "page_qrels_validation",
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
