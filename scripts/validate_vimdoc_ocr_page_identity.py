"""Read-only ViMDoc page-identity and OCR-manifest validator.

The tool never performs OCR, imports an OCR/GPU library, or writes output. It
audits a supplied tar archive or validates supplied JSON manifests to stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
from typing import BinaryIO, Iterable


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PROTOCOL_PATH = Path(__file__).resolve().parents[1] / "configs/vimdoc_ocr_page_identity_v1.json"
ASSET_FIELDS = {
    "asset_path", "page_id", "document_id", "page_number", "asset_sha256", "asset_bytes"
}
PAGE_FIELDS = {
    "page_id", "document_id", "page_number", "canonical_asset_path",
    "asset_sha256", "asset_bytes", "alias_asset_paths"
}
OCR_FIELDS = {
    "page_id", "canonical_asset_path", "asset_sha256", "status", "text",
    "text_sha256", "character_count"
}


def utf8_key(value: str) -> bytes:
    return value.encode("utf-8")


def sha256_stream(stream: BinaryIO) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
        size += len(block)
    return digest.hexdigest(), size


def sha256_path(path: Path) -> tuple[str, int]:
    with path.open("rb") as stream:
        return sha256_stream(stream)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json_sha256(rows: Iterable[dict]) -> str:
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    return sha256_text(payload)


def page_identity(asset_path: str) -> tuple[str, str, int]:
    if not isinstance(asset_path, str) or not asset_path or "\x00" in asset_path or "\\" in asset_path:
        raise ValueError("Asset path must be a nonempty safe POSIX string")
    path = PurePosixPath(asset_path)
    if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "pages":
        raise ValueError("Image assets must use exactly pages/<filename>")
    if asset_path != "/".join(path.parts):
        raise ValueError("Asset paths must already be canonical POSIX paths")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Dot or empty path segments are forbidden")
    extension = path.suffix.lower()
    if extension not in IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image extension")
    page_id = path.name[:-len(path.suffix)]
    document_id, separator, page_number = page_id.rpartition("_")
    if not page_id or not separator or not document_id or not page_number.isascii() or not page_number.isdecimal():
        raise ValueError("Page ID must end in a nonempty ASCII-decimal underscore suffix")
    return page_id, document_id, int(page_number)


def asset_row(asset_path: str, asset_sha256: str, asset_bytes: int) -> dict:
    page_id, document_id, page_number = page_identity(asset_path)
    if not isinstance(asset_sha256, str) or len(asset_sha256) != 64:
        raise ValueError("Asset SHA-256 must be 64 lowercase hexadecimal characters")
    try:
        int(asset_sha256, 16)
    except ValueError as error:
        raise ValueError("Asset SHA-256 must be 64 lowercase hexadecimal characters") from error
    if asset_sha256 != asset_sha256.lower():
        raise ValueError("Asset SHA-256 must use lowercase hexadecimal")
    if type(asset_bytes) is not int or asset_bytes <= 0:
        raise ValueError("Image assets must contain at least one byte")
    return {"asset_path": asset_path, "page_id": page_id, "document_id": document_id,
            "page_number": page_number, "asset_sha256": asset_sha256, "asset_bytes": asset_bytes}


def resolve_assets(assets: list[dict]) -> dict:
    if not assets:
        raise ValueError("At least one image asset is required")
    seen_paths, normalized = set(), []
    for raw in assets:
        if not isinstance(raw, dict) or set(raw) != ASSET_FIELDS:
            raise ValueError("Asset row schema mismatch")
        expected = asset_row(raw["asset_path"], raw["asset_sha256"], raw["asset_bytes"])
        if raw != expected:
            raise ValueError("Asset row identity fields are inconsistent")
        if raw["asset_path"] in seen_paths:
            raise ValueError("Duplicate archive member path")
        seen_paths.add(raw["asset_path"])
        normalized.append(raw)
    normalized.sort(key=lambda row: utf8_key(row["asset_path"]))
    groups: dict[str, list[dict]] = {}
    for row in normalized:
        groups.setdefault(row["page_id"], []).append(row)
    pages, conflicts = [], []
    for page_id in sorted(groups, key=utf8_key):
        group = groups[page_id]
        hashes = sorted({row["asset_sha256"] for row in group})
        paths = sorted((row["asset_path"] for row in group), key=utf8_key)
        if len(hashes) != 1:
            conflicts.append({"page_id": page_id, "asset_paths": paths, "asset_sha256": hashes})
            continue
        canonical = min(group, key=lambda row: utf8_key(row["asset_path"]))
        pages.append({"page_id": page_id, "document_id": canonical["document_id"],
                      "page_number": canonical["page_number"],
                      "canonical_asset_path": canonical["asset_path"],
                      "asset_sha256": canonical["asset_sha256"], "asset_bytes": canonical["asset_bytes"],
                      "alias_asset_paths": paths})
    by_hash: dict[str, list[str]] = {}
    for page in pages:
        by_hash.setdefault(page["asset_sha256"], []).append(page["page_id"])
    cross_page_duplicates = [
        {"asset_sha256": digest, "page_ids": sorted(ids, key=utf8_key)}
        for digest, ids in sorted(by_hash.items()) if len(ids) > 1
    ]
    documents = {page["document_id"] for page in pages}
    return {
        "status": "PASS" if not conflicts else "BLOCKED_DIFFERENT_CONTENT_PAGE_ID_COLLISION",
        "ready_for_ocr": not conflicts,
        "asset_count": len(normalized),
        "page_id_count": len(groups),
        "extra_assets_sharing_page_id": len(normalized) - len(groups),
        "canonical_page_count": len(pages),
        "document_count": len(documents),
        "different_content_collision_count": len(conflicts),
        "different_content_collisions": conflicts,
        "cross_page_duplicate_content_group_count": len(cross_page_duplicates),
        "cross_page_duplicate_content_groups": cross_page_duplicates,
        "asset_inventory_sha256": canonical_json_sha256(normalized),
        "canonical_pages_sha256": canonical_json_sha256(pages) if pages else None,
        "assets": normalized,
        "pages": pages,
    }


def inspect_tar(archive_path: Path) -> dict:
    assets = []
    archive_sha256, archive_bytes = sha256_path(archive_path)
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            suffix = PurePosixPath(member.name).suffix.lower()
            if suffix not in IMAGE_EXTENSIONS:
                continue
            if not member.isfile() or member.issym() or member.islnk():
                raise ValueError("Image archive members must be regular files")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Unable to read image archive member")
            with stream:
                digest, size = sha256_stream(stream)
            assets.append(asset_row(member.name, digest, size))
    report = resolve_assets(assets)
    report["archive_sha256"] = archive_sha256
    report["archive_bytes"] = archive_bytes
    return report


def enforce_frozen_identity_contract(report: dict, protocol: dict) -> dict:
    source, contract = protocol["source_alignment"], protocol["asset_identity"]
    expected = {
        "archive_sha256": source["dataset_archive_sha256"],
        "asset_count": contract["expected_asset_files"],
        "page_id_count": contract["expected_unique_page_ids_before_content_audit"],
        "extra_assets_sharing_page_id": contract["expected_extra_assets_sharing_page_id"],
        "document_count": contract["expected_document_ids"],
    }
    mismatches = {key: {"expected": value, "observed": report.get(key)}
                  for key, value in expected.items() if report.get(key) != value}
    if mismatches:
        raise ValueError(f"Frozen archive identity mismatch: {mismatches}")
    if report.get("status") != "PASS" or report.get("different_content_collision_count") != 0:
        raise ValueError("Different-content page-ID collisions block OCR")
    result = dict(report)
    result["frozen_counts_verified"] = True
    return result


def normalize_ocr_text(text: str) -> str:
    if not isinstance(text, str) or "\x00" in text:
        raise ValueError("OCR text must be a NUL-free string")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def validate_ocr_rows(identity: dict, rows: list[dict]) -> dict:
    if identity.get("status") != "PASS" or identity.get("ready_for_ocr") is not True:
        raise ValueError("Page-identity audit must pass before OCR validation")
    pages = identity.get("pages")
    if not isinstance(pages, list) or any(not isinstance(p, dict) or set(p) != PAGE_FIELDS for p in pages):
        raise ValueError("Canonical page schema mismatch")
    expected = {page["page_id"]: page for page in pages}
    observed, empty = {}, 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != OCR_FIELDS:
            raise ValueError("OCR row schema mismatch")
        page_id = row["page_id"]
        if page_id in observed:
            raise ValueError("Duplicate OCR page ID")
        page = expected.get(page_id)
        if page is None:
            raise ValueError("Unexpected OCR page ID")
        if row["canonical_asset_path"] != page["canonical_asset_path"] or row["asset_sha256"] != page["asset_sha256"]:
            raise ValueError("OCR row does not bind to the canonical asset")
        text = normalize_ocr_text(row["text"])
        if text != row["text"] or row["text_sha256"] != sha256_text(text):
            raise ValueError("OCR text is not normalized or its hash is wrong")
        if type(row["character_count"]) is not int or row["character_count"] != len(text):
            raise ValueError("OCR character count mismatch")
        status = "SUCCESS_EMPTY" if text == "" else "SUCCESS_NONEMPTY"
        if row["status"] != status:
            raise ValueError("OCR status does not match text; errors cannot masquerade as empty text")
        empty += text == ""
        observed[page_id] = row
    missing = sorted(set(expected) - set(observed), key=utf8_key)
    if missing:
        raise ValueError("Missing OCR page IDs")
    ordered = sorted(rows, key=lambda row: utf8_key(row["page_id"]))
    if rows != ordered:
        raise ValueError("OCR rows must use UTF-8-byte ascending page-ID order")
    return {"status": "PASS", "ocr_row_count": len(rows), "empty_text_count": empty,
            "nonempty_text_count": len(rows) - empty, "ocr_jsonl_sha256": canonical_json_sha256(rows)}


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect-tar", type=Path)
    group.add_argument("--validate-ocr", type=Path, metavar="OCR_JSONL")
    parser.add_argument("--identity", type=Path, help="Identity JSON required with --validate-ocr")
    args = parser.parse_args()
    try:
        if args.inspect_tar:
            if args.identity is not None:
                raise ValueError("--identity applies only to --validate-ocr")
            report = enforce_frozen_identity_contract(inspect_tar(args.inspect_tar), read_json(PROTOCOL_PATH))
        else:
            if args.identity is None:
                raise ValueError("--identity is required with --validate-ocr")
            report = validate_ocr_rows(read_json(args.identity), read_jsonl(args.validate_ocr))
    except (OSError, tarfile.TarError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"VIMDOC_OCR_IDENTITY_REFUSED: {error}\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0 if report.get("status") == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
