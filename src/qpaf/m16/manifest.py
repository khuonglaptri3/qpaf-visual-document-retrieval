"""Page manifest and alias normalization for M1.6 Collision Audit."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union


@dataclass
class PageRecord:
    document_id: str
    page_id: str
    page_number: int
    source_path: str
    file_sha256: str
    content_sha256: str
    split: str
    extraction_method: str
    review_status: str


@dataclass
class AliasRecord:
    alias_id: str
    canonical_page_id: str
    source_reference: str
    reason: str
    review_status: str


def format_canonical_page_id(document_id: str, page_number: int) -> str:
    """Format canonical page identifier: {doc_stem}_page_{page_number:04d}."""
    doc_stem = Path(document_id).stem
    return f"{doc_stem}_page_{int(page_number):04d}"


def build_page_manifest(
    raw_pages: Iterable[Dict[str, Any]],
    split_assignment: Optional[Dict[str, str]] = None,
    default_split: str = "unassigned",
    default_extraction_method: str = "direct_bytes",
    default_review_status: str = "pending_review",
) -> List[PageRecord]:
    """Construct a list of validated PageRecords from raw page data."""
    split_assignment = split_assignment or {}
    manifest: List[PageRecord] = []
    seen_ids = set()

    for raw in raw_pages:
        doc_id = str(raw["document_id"]).strip()
        page_num = int(raw["page_number"])
        page_id = raw.get("page_id") or format_canonical_page_id(doc_id, page_num)
        if not doc_id or page_num < 1 or page_id != format_canonical_page_id(doc_id, page_num):
            raise ValueError(f"Invalid canonical page identity: {page_id}")
        if page_id.casefold() in seen_ids:
            raise ValueError(f"Duplicate page ID: {page_id}")
        seen_ids.add(page_id.casefold())
        source_path = str(raw.get("source_path", ""))
        file_sha256 = str(raw.get("file_sha256", ""))

        if "content_sha256" in raw:
            content_sha256 = str(raw["content_sha256"])
        elif "content" in raw:
            content = raw["content"]
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            elif isinstance(content, (bytes, bytearray)):
                content_bytes = bytes(content)
            else:
                raise TypeError(f"Unsupported content type for page {page_id}: {type(content)}")
            content_sha256 = hashlib.sha256(content_bytes).hexdigest()
        else:
            raise KeyError(f"Page data for {page_id} must have 'content' or 'content_sha256'")

        split = raw.get("split") or split_assignment.get(doc_id, default_split)
        extraction_method = str(raw.get("extraction_method", default_extraction_method))
        review_status = str(raw.get("review_status", default_review_status))

        manifest.append(
            PageRecord(
                document_id=doc_id,
                page_id=page_id,
                page_number=page_num,
                source_path=source_path,
                file_sha256=file_sha256,
                content_sha256=content_sha256,
                split=split,
                extraction_method=extraction_method,
                review_status=review_status,
            )
        )

    return manifest


def normalize_alias_to_canonical(alias_candidate: str) -> Optional[Tuple[str, str]]:
    """Attempt to normalize an alias string to (canonical_page_id, reason).

    Supported patterns:
    - doc_p1 -> doc_page_0001 (reason: short_p_notation)
    - doc_1 -> doc_page_0001 (reason: underscore_index)
    - doc.pdf_page_1 -> doc_page_0001 (reason: extension_stripped_and_padded)
    - doc_page_0001 -> doc_page_0001 (reason: canonical_identity)
    """
    candidate = alias_candidate.strip()
    if not candidate:
        return None

    # Exact canonical format: stem_page_\d{4}
    m_canonical = re.fullmatch(r"^(.+)_page_(\d{4})$", candidate)
    if m_canonical:
        stem = Path(m_canonical.group(1)).stem
        return f"{stem}_page_{m_canonical.group(2)}", "canonical_identity"

    # Pattern: stem_page_\d+ (unpadded)
    m_unpadded = re.fullmatch(r"^(.+)_page_(\d+)$", candidate)
    if m_unpadded:
        stem = Path(m_unpadded.group(1)).stem
        num = int(m_unpadded.group(2))
        return format_canonical_page_id(stem, num), "zero_padded_page_index"

    # Pattern: stem_p\d+
    m_p = re.fullmatch(r"^(.+)_p(\d+)$", candidate)
    if m_p:
        stem = Path(m_p.group(1)).stem
        num = int(m_p.group(2))
        return format_canonical_page_id(stem, num), "short_p_notation"

    # Pattern: stem_\d+
    m_num = re.fullmatch(r"^(.+)_(\d+)$", candidate)
    if m_num:
        stem = Path(m_num.group(1)).stem
        num = int(m_num.group(2))
        return format_canonical_page_id(stem, num), "underscore_index"

    return None


def resolve_aliases(
    raw_aliases: Iterable[Tuple[str, str]],
    canonical_page_ids: Set[str],
    default_review_status: str = "pending_review",
) -> Tuple[Dict[str, str], List[AliasRecord]]:
    """Resolve alias references against known canonical page IDs.

    Returns:
        mapping: Dict mapping alias_id -> canonical_page_id
        records: List of AliasRecord for traceable audit export
    """
    mapping: Dict[str, str] = {}
    records: List[AliasRecord] = []
    seen_aliases: Set[str] = set()

    for alias_id, source_ref in raw_aliases:
        alias_id_clean = alias_id.strip()
        if not alias_id_clean or alias_id_clean in seen_aliases:
            continue
        seen_aliases.add(alias_id_clean)

        norm = normalize_alias_to_canonical(alias_id_clean)
        if norm is not None:
            canonical_target, reason = norm
            if canonical_target in canonical_page_ids:
                mapping[alias_id_clean] = canonical_target
                records.append(
                    AliasRecord(
                        alias_id=alias_id_clean,
                        canonical_page_id=canonical_target,
                        source_reference=source_ref,
                        reason=reason,
                        review_status=default_review_status,
                    )
                )
                continue
        records.append(AliasRecord(alias_id_clean, "", source_ref,
                                   "unknown_alias_or_target", "unresolved"))

    return mapping, records
