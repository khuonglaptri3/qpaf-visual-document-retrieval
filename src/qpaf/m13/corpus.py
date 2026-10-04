"""Corpus inspector and fixture utilities for M1.3 CPU audit."""
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Union
import zipfile


def inspect_pdf_archive(archive_path: Union[str, Path]) -> Dict[str, Any]:
    """Inspect a ZIP archive containing PDF documents and return metadata."""
    path = Path(archive_path)
    if not path.exists():
        raise FileNotFoundError(f"Archive not found: {path}")

    # Compute SHA256 of the archive file
    hasher = hashlib.sha256()
    size_bytes = 0
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
            size_bytes += len(chunk)
    archive_hash = hasher.hexdigest()

    pdf_docs: List[str] = []
    total_members = 0

    with zipfile.ZipFile(path, "r") as zf:
        for info in zf.infolist():
            total_members += 1
            filename = info.filename
            if filename.lower().endswith(".pdf") and not filename.startswith("__MACOSX"):
                pdf_docs.append(Path(filename).name)

    return {
        "archive_path": str(path),
        "sha256": archive_hash,
        "size_bytes": size_bytes,
        "total_files": total_members,
        "pdf_count": len(pdf_docs),
        "pdf_documents": sorted(pdf_docs),
    }


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
            zf.writestr(f"doc_{doc_id}.pdf", b"%PDF-1.4 synthetic mock document content")

    return {
        "json_path": json_path,
        "zip_path": zip_path,
    }
