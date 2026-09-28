"""Corpus inspector and fixture utilities for M1.3 CPU audit."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Dict, List, Union
import zipfile
import pypdfium2 as pdfium


def _document_record(filename: str, source_path: str, data: bytes) -> Dict[str, Any]:
    try:
        document = pdfium.PdfDocument(data)
        try:
            page_count = len(document)
            if page_count < 1:
                raise ValueError("PDF has no pages")
            for index in range(page_count):
                page = document[index]
                page.close()
        finally:
            document.close()
    except Exception as exc:
        raise ValueError(f"Unreadable PDF {source_path}: {exc}") from exc
    return {"filename": filename, "document_id": Path(filename).stem,
            "source_path": source_path, "file_sha256": hashlib.sha256(data).hexdigest(),
            "page_count": page_count, "size_bytes": len(data)}


def _inventory(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not documents:
        raise ValueError("Corpus contains no PDF documents")
    names, stems = set(), set()
    for document in documents:
        name, stem = document["filename"].casefold(), document["document_id"].casefold()
        if name in names or stem in stems:
            raise ValueError(f"Duplicate PDF filename or document ID: {document['filename']}")
        names.add(name)
        stems.add(stem)
    documents = sorted(documents, key=lambda item: item["filename"])
    return {"pdf_count": len(documents), "pdf_documents": [d["filename"] for d in documents],
            "total_pages": sum(d["page_count"] for d in documents),
            "doc_page_counts": {d["filename"]: d["page_count"] for d in documents},
            "documents": documents}


def _safe_member_name(name: str) -> None:
    parts = name.rstrip("/").split("/")
    if (not name or name.startswith("/") or "\\" in name or ":" in name
            or any(part in ("", ".", "..") for part in parts)
            or any(ord(char) < 32 for char in name)
            or any(part.endswith((" ", ".")) for part in parts)):
        raise ValueError(f"Unsafe archive member: {name!r}")


def inspect_pdf_archive(archive_path: Union[str, Path]) -> Dict[str, Any]:
    """Inspect a ZIP archive containing PDF documents and return metadata."""
    path = Path(archive_path)
    if not path.is_file():
        raise FileNotFoundError(f"Archive not found: {path}")

    # Compute SHA256 of the archive file
    hasher = hashlib.sha256()
    size_bytes = 0
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
            size_bytes += len(chunk)
    archive_hash = hasher.hexdigest()

    documents: List[Dict[str, Any]] = []
    total_members = 0

    with zipfile.ZipFile(path, "r") as zf:
        seen_members = set()
        for info in zf.infolist():
            total_members += 1
            filename = info.filename
            _safe_member_name(info.orig_filename)
            _safe_member_name(filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"Symlink archive member: {filename}")
            normalized = filename.rstrip("/").casefold()
            if normalized in seen_members:
                raise ValueError(f"Duplicate archive member: {filename}")
            seen_members.add(normalized)
            if not info.is_dir():
                data = zf.read(info)  # Also verifies CRC for non-PDF members.
                if filename.lower().endswith(".pdf") and not filename.startswith("__MACOSX/"):
                    documents.append(_document_record(PurePosixPath(filename).name, filename, data))

    return {
        "archive_path": str(path),
        "sha256": archive_hash,
        "size_bytes": size_bytes,
        "total_files": total_members,
        **_inventory(documents),
    }


def inspect_pdf_directory(dir_path: Union[str, Path]) -> Dict[str, Any]:
    """Read every PDF recursively; reject links and ambiguous document identities."""
    path = Path(dir_path)
    if not path.is_dir():
        raise NotADirectoryError(f"Directory not found: {path}")
    if path.is_symlink():
        raise ValueError(f"Symlink corpus directory: {path}")
    documents = []
    total_files = 0
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            item = Path(parent) / name
            if item.is_symlink() or (item.lstat().st_file_attributes & 1024 if hasattr(item.lstat(), "st_file_attributes") else False):
                raise ValueError(f"Symlink or reparse point in corpus: {item}")
        for name in files:
            total_files += 1
            if name.lower().endswith(".pdf"):
                item = Path(parent) / name
                documents.append(_document_record(name, str(item.resolve()), item.read_bytes()))
    inventory = _inventory(documents)
    identity = [{**d, "source_path": Path(d["source_path"]).relative_to(path.resolve()).as_posix()}
                for d in inventory["documents"]]
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"archive_path": None, "directory": str(path), "sha256": digest,
            "hash_kind": "document_inventory_sha256", "total_files": total_files,
            "size_bytes": sum(d["size_bytes"] for d in documents), **inventory}


def scan_pdf_directory(dir_path: Union[str, Path]) -> Dict[str, Any]:
    """Scan a local directory for PDF files."""
    path = Path(dir_path)
    if not path.is_dir():
        raise NotADirectoryError(f"Directory not found: {path}")

    pdf_names: List[str] = []
    empty_files: List[str] = []

    for file_path in path.iterdir():
        if file_path.is_file() and file_path.name.lower().endswith(".pdf"):
            pdf_names.append(file_path.name)
            if file_path.stat().st_size == 0:
                empty_files.append(file_path.name)

    return {
        "directory": str(path),
        "total_pdfs": len(pdf_names),
        "pdf_names": sorted(pdf_names),
        "empty_files": sorted(empty_files),
    }


def generate_synthetic_vidoseek_fixture(target_dir: Union[str, Path]) -> Dict[str, Path]:
    """Generate minimal synthetic ViDoSeek dataset for local testing."""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    json_path = target / "vidoseek.json"
    zip_path = target / "vidoseek_pdf_document.zip"

    # Synthetic annotations
    raw_data = {
        "examples": [
            {
                "uid": f"synth_q_{i:03d}",
                "query": f"Synthetic query number {i}?",
                "meta_info": {
                    "file_name": f"doc_{i % 3 + 1}.pdf",
                    "reference_page": [(i % 2) + 1],
                },
            }
            for i in range(1, 11)
        ]
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2)

    # Synthetic ZIP archive
    with zipfile.ZipFile(zip_path, "w") as zf:
        for doc_id in range(1, 4):
            document = pdfium.PdfDocument.new()
            output = io.BytesIO()
            try:
                for _ in range(2):
                    document.new_page(100, 100).close()
                document.save(output)
            finally:
                document.close()
            zf.writestr(f"doc_{doc_id}.pdf", output.getvalue())

    return {
        "json_path": json_path,
        "zip_path": zip_path,
    }
