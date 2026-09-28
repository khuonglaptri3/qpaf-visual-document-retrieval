"""Parser and validator for ViDoSeek dataset annotations and qrels."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union


@dataclass
class ViDoSeekParsedDataset:
    queries: List[Dict[str, str]]
    qrels: Dict[str, Dict[str, int]]
    document_names: Set[str]


def format_page_id(doc_name: str, page_num: int) -> str:
    """Format canonical page ID: {doc_stem}_page_{page_num:04d}."""
    stem = Path(doc_name).stem
    return f"{stem}_page_{page_num:04d}"


def page_to_document_id(page_id: str) -> str:
    """Extract document ID (stem) from canonical page ID."""
    if "_page_" in page_id:
        return page_id.rsplit("_page_", 1)[0]
    return page_id.rsplit("_", 1)[0]


def parse_vidoseek_annotations(
    data_or_path: Union[str, Path, Dict[str, Any]],
    doc_page_counts: Optional[Dict[str, int]] = None,
) -> ViDoSeekParsedDataset:
    """Parse ViDoSeek annotation format (vidoseek.json).

    Validates schema, query uniqueness, non-empty query texts, and reference page bounds.
    """
    if isinstance(data_or_path, (str, Path)):
        with open(data_or_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    elif isinstance(data_or_path, dict):
        raw = data_or_path
    else:
        raise TypeError("Expected file path or dictionary for vidoseek annotations")

    if "examples" not in raw or not isinstance(raw["examples"], list):
        raise ValueError("Annotations JSON must contain an 'examples' list")

    examples = raw["examples"]
    queries: List[Dict[str, str]] = []
    qrels: Dict[str, Dict[str, int]] = {}
    documents: Set[str] = set()
    seen_uids: Set[str] = set()

    for idx, ex in enumerate(examples):
        if not isinstance(ex, dict):
            raise ValueError(f"Example at index {idx} must be a dictionary")

        uid = ex.get("uid")
        if not isinstance(uid, str) or not uid.strip():
            raise ValueError(f"Missing or invalid query uid at index {idx}")
        if uid in seen_uids:
            raise ValueError(f"Duplicate query ID found: {uid}")
        seen_uids.add(uid)

        query_text = ex.get("query")
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError(f"Empty query text for query ID {uid}")

        meta = ex.get("meta_info")
        if not isinstance(meta, dict):
            raise ValueError(f"Missing meta_info for query ID {uid}")

        file_name = meta.get("file_name")
        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError(f"Missing file_name in meta_info for query ID {uid}")
        documents.add(file_name)

        ref_pages = meta.get("reference_page")
        if not isinstance(ref_pages, list) or not ref_pages:
            raise ValueError(f"Empty or missing reference_page list for query ID {uid}")

        query_qrels: Dict[str, int] = {}
        for p in ref_pages:
            if not isinstance(p, int) or p < 1:
                raise ValueError(f"Invalid one-based page number '{p}' for query ID {uid}")

            if doc_page_counts is not None and file_name in doc_page_counts:
                max_pages = doc_page_counts[file_name]
                if p > max_pages:
                    raise ValueError(
                        f"Page number {p} exceeds document page count {max_pages} for {file_name}"
                    )

            page_id = format_page_id(file_name, p)
            query_qrels[page_id] = 1

        queries.append({"query_id": uid, "text": query_text.strip()})
        qrels[uid] = query_qrels

    return ViDoSeekParsedDataset(
        queries=queries,
        qrels=qrels,
        document_names=documents,
    )
