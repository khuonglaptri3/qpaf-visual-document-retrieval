"""Duplicate detection, split leakage analysis, and qrel consistency verification."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from qpaf.m16.manifest import PageRecord


@dataclass
class DuplicateRecord:
    group_id: str
    collision_type: str
    left_page_id: str
    right_page_id: str
    content_sha256: str
    split_leakage: bool
    resolution: str
    review_status: str


def detect_content_duplicates(
    manifest: Iterable[PageRecord],
    default_review_status: str = "reviewed",
) -> List[DuplicateRecord]:
    """Cluster pages with identical content_sha256 and detect pairwise collisions."""
    content_groups: Dict[str, List[PageRecord]] = defaultdict(list)
    for p in manifest:
        content_groups[p.content_sha256].append(p)

    duplicates: List[DuplicateRecord] = []
    group_idx = 1

    for content_hash, pages in sorted(content_groups.items()):
        if len(pages) < 2:
            continue

        gid = f"DUP-{group_idx:04d}"
        group_idx += 1

        # Compare pairs in canonical sorted order
        sorted_pages = sorted(pages, key=lambda p: (p.document_id, p.page_number, p.page_id))
        for i in range(len(sorted_pages)):
            for j in range(i + 1, len(sorted_pages)):
                left = sorted_pages[i]
                right = sorted_pages[j]

                # Determine collision type for identical content
                collision_type = "EXACT_CONTENT_DUPLICATE"

                # Check split leakage: different non-unassigned splits
                is_leakage = (
                    left.split != right.split
                    and left.split not in ("unassigned", "shared")
                    and right.split not in ("unassigned", "shared")
                )

                resolution = "split_leakage_blocker" if is_leakage else "intra_split_duplicate"

                duplicates.append(
                    DuplicateRecord(
                        group_id=gid,
                        collision_type=collision_type,
                        left_page_id=left.page_id,
                        right_page_id=right.page_id,
                        content_sha256=content_hash,
                        split_leakage=is_leakage,
                        resolution=resolution,
                        review_status=default_review_status,
                    )
                )

    return duplicates


def detect_split_leakage(
    duplicate_records: Iterable[DuplicateRecord],
    manifest: Optional[Iterable[PageRecord]] = None,
) -> List[DuplicateRecord]:
    """Identify duplicate records that represent cross-split leakage."""
    page_to_split: Dict[str, str] = {}
    if manifest:
        for p in manifest:
            page_to_split[p.page_id] = p.split

    leakage_records: List[DuplicateRecord] = []
    for dup in duplicate_records:
        if page_to_split:
            left_split = page_to_split.get(dup.left_page_id, "")
            right_split = page_to_split.get(dup.right_page_id, "")
            is_leakage = (
                left_split != right_split
                and left_split not in ("", "unassigned", "shared")
                and right_split not in ("", "unassigned", "shared")
            )
        else:
            is_leakage = dup.split_leakage

        if is_leakage:
            dup.split_leakage = True
            dup.resolution = "split_leakage_blocker"
            leakage_records.append(dup)

    return leakage_records


def verify_qrel_consistency(
    qrels: Dict[str, Dict[str, int]],
    canonical_page_ids: Set[str],
    alias_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Verify that all queries and relevance references match canonical pages."""
    alias_mapping = alias_mapping or {}
    total_queries = len(qrels)
    valid_queries = 0
    orphan_queries: List[str] = []
    referenced_canonical_pages: Set[str] = set()

    for qid, rel_map in sorted(qrels.items()):
        query_has_valid_target = False
        for raw_page_id, score in rel_map.items():
            if score <= 0:
                continue
            canonical_id = alias_mapping.get(raw_page_id, raw_page_id)
            if canonical_id in canonical_page_ids:
                query_has_valid_target = True
                referenced_canonical_pages.add(canonical_id)

        if query_has_valid_target:
            valid_queries += 1
        else:
            orphan_queries.append(qid)

    unreferenced_pages = sorted(canonical_page_ids - referenced_canonical_pages)

    return {
        "total_queries": total_queries,
        "valid_queries": valid_queries,
        "orphan_queries": orphan_queries,
        "orphan_query_count": len(orphan_queries),
        "referenced_page_count": len(referenced_canonical_pages),
        "unreferenced_pages": unreferenced_pages,
        "orphan_page_count": len(unreferenced_pages),
    }
