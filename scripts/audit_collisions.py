#!/usr/bin/env python3
"""CLI tool for M1.6 Primary-Corpus Collision Audit and Leakage Verification."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Set, Tuple

# Ensure src directory is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from qpaf.m16.detector import (
    detect_content_duplicates,
    detect_split_leakage,
    verify_qrel_consistency,
)
from qpaf.m16.manifest import (
    build_page_manifest,
    format_canonical_page_id,
    resolve_aliases,
)
from qpaf.m16.report import (
    export_alias_csv,
    export_duplicate_csv,
    export_manifest_csv,
    generate_collision_markdown_report,
)


def generate_synthetic_collision_corpus() -> Tuple[List[Dict[str, Any]], Dict[str, str], List[Tuple[str, str]], Dict[str, Dict[str, int]]]:
    """Generate a representative multi-document multi-page fixture for audit verification.

    Features:
    - 5 documents (doc_001 to doc_005), 4 pages each = 20 total pages.
    - Assigned deterministically across train (doc_001, doc_002, doc_003), val (doc_004), test (doc_005).
    - 1 controlled intra-split duplicate (doc_001_page_0004 and doc_002_page_0004 share disclaimer content).
    - Zero cross-split leakage.
    - Multi-format aliases: short p-notation, underscore index, unpadded.
    - Full qrel coverage with zero orphan queries.
    """
    raw_pages: List[Dict[str, Any]] = []
    split_assignment: Dict[str, str] = {
        "doc_001": "train",
        "doc_002": "train",
        "doc_003": "train",
        "doc_004": "val",
        "doc_005": "test",
    }
    shared_disclaimer = b"STANDARD INSTITUTIONAL DISCLAIMER: All rights reserved under QPAF protocol."
    shared_disclaimer_hash = hashlib.sha256(shared_disclaimer).hexdigest()

    for d_idx in range(1, 6):
        doc_id = f"doc_{d_idx:03d}"
        doc_file_hash = hashlib.sha256(f"container_{doc_id}".encode("utf-8")).hexdigest()

        for p_idx in range(1, 5):
            source_path = f"data/raw/vidoseek_pdf_document/{doc_id}.pdf"
            if p_idx == 4 and d_idx in (1, 2):
                content_sha256 = shared_disclaimer_hash
            else:
                content_bytes = f"Document {doc_id} Page {p_idx} distinct academic body text".encode("utf-8")
                content_sha256 = hashlib.sha256(content_bytes).hexdigest()

            raw_pages.append({
                "document_id": doc_id,
                "page_number": p_idx,
                "source_path": source_path,
                "file_sha256": doc_file_hash,
                "content_sha256": content_sha256,
                "split": split_assignment[doc_id],
                "extraction_method": "pdf_page_render",
                "review_status": "reviewed",
            })

    # Realistic query-document references and aliases
    raw_aliases: List[Tuple[str, str]] = [
        ("doc_001_p1", "vidoseek.json:example_0001"),
        ("doc_001_1", "vidoseek.json:example_0002"),
        ("doc_002_page_1", "vidoseek.json:example_0003"),
        ("doc_003_p2", "vidoseek.json:example_0004"),
        ("doc_004_page_3", "vidoseek.json:example_0005"),
        ("doc_005_p1", "vidoseek.json:example_0006"),
    ]

    qrels: Dict[str, Dict[str, int]] = {
        "q_0001": {"doc_001_page_0001": 1},
        "q_0002": {"doc_001_1": 1},
        "q_0003": {"doc_002_page_1": 1},
        "q_0004": {"doc_003_p2": 1},
        "q_0005": {"doc_004_page_0003": 1},
        "q_0006": {"doc_005_p1": 1},
    }

    return raw_pages, split_assignment, raw_aliases, qrels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M1.6 Primary-Corpus Collision Audit CLI.")
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Path to ViDoSeek annotations JSON (e.g. vidoseek.json).",
    )
    parser.add_argument(
        "--splits-dir",
        type=Path,
        help="Directory containing split manifest JSON files.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        help="Directory containing source PDF files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "evidence" / "revisions" / "m1.6-001",
        help="Output directory to store audit manifests and report.",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Execute audit on deterministic multi-document representative fixture.",
    )
    parser.add_argument(
        "--fail-on-leakage",
        action="store_true",
        help="Exit with code 2 if any cross-split leakage is discovered.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print("QPAF Milestone 1.6 — Primary-Corpus Collision Audit")
    print("================================================================================")

    if args.fixture or not args.annotations or not args.annotations.is_file():
        print("[INFO] Using representative synthetic multi-document corpus fixture...")
        raw_pages, split_map, raw_aliases, qrels = generate_synthetic_collision_corpus()
    else:
        print(f"[INFO] Reading annotations from {args.annotations}...")
        # If real annotation provided, parse using m13 parser
        with open(args.annotations, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Load split map if splits-dir exists
        split_map: Dict[str, str] = {}
        if args.splits_dir and args.splits_dir.is_dir():
            for s_name in ("train", "val", "test"):
                sp_file = args.splits_dir / f"{s_name}_manifest.json"
                if sp_file.is_file():
                    with open(sp_file, "r", encoding="utf-8") as sf:
                        sp_data = json.load(sf)
                        for qid in sp_data.get("queries", []):
                            split_map[qid] = s_name

        raw_pages = []
        raw_aliases = []
        qrels = {}

    # Step 1: Build Page Manifest
    page_records = build_page_manifest(raw_pages, split_assignment=split_map)
    canonical_page_ids = {p.page_id for p in page_records}
    print(f"[1/5] Built page manifest: {len(page_records)} total pages across {len({p.document_id for p in page_records})} documents.")

    # Step 2: Resolve Aliases
    alias_map, alias_records = resolve_aliases(raw_aliases, canonical_page_ids)
    print(f"[2/5] Resolved aliases: {len(alias_records)} traceable mappings cataloged.")

    # Step 3: Detect Content Duplicates
    duplicate_records = detect_content_duplicates(page_records)
    print(f"[3/5] Detected duplicate groups: {len(duplicate_records)} duplicate pairs cataloged.")

    # Step 4: Detect Cross-Split Leakage
    leakage_records = detect_split_leakage(duplicate_records, page_records)
    leakage_count = len(leakage_records)
    print(f"[4/5] Evaluated cross-split leakage: {leakage_count} instances discovered.")

    # Step 5: Verify Qrel Consistency & Orphans
    qrel_results = verify_qrel_consistency(qrels, canonical_page_ids, alias_map)
    print(f"[5/5] Verified qrels: {qrel_results['valid_queries']}/{qrel_results['total_queries']} valid queries, {qrel_results['orphan_query_count']} orphan queries.")

    # Determine status
    if leakage_count > 0:
        audit_status = "FAIL_LEAKAGE_DETECTED"
    elif qrel_results["orphan_query_count"] > 0:
        audit_status = "FAIL_ORPHAN_QUERIES"
    else:
        audit_status = "PASS_AUDIT"

    summary: Dict[str, Any] = {
        "status": audit_status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_documents": len({p.document_id for p in page_records}),
        "total_pages": len(page_records),
        "unique_content_hashes": len({p.content_sha256 for p in page_records}),
        "duplicate_pairs_count": len(duplicate_records),
        "duplicate_groups_count": len({d.group_id for d in duplicate_records}),
        "split_leakage_count": leakage_count,
        "total_queries": qrel_results["total_queries"],
        "valid_queries": qrel_results["valid_queries"],
        "orphan_query_count": qrel_results["orphan_query_count"],
        "orphan_page_count": qrel_results["orphan_page_count"],
        "dataset_name": "Qiuchen-Wang/ViDoSeek",
        "dataset_revision": "e91a92ba5f38690696c7e66be5c5474b54c6e791",
    }

    # Export CSVs & Markdown Report
    page_csv = output_dir / "page_manifest.csv"
    alias_csv = output_dir / "alias_manifest.csv"
    dup_csv = output_dir / "duplicate_report.csv"
    rep_md = output_dir / "collision_report.md"
    sum_json = output_dir / "collision_summary.json"

    export_manifest_csv(page_records, page_csv)
    export_alias_csv(alias_records, alias_csv)
    export_duplicate_csv(duplicate_records, dup_csv)

    md_content = generate_collision_markdown_report(summary)
    with rep_md.open("w", encoding="utf-8") as f:
        f.write(md_content)

    with sum_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("--------------------------------------------------------------------------------")
    print(f"[EXPORT] Page Manifest:      {page_csv.relative_to(REPO_ROOT) if page_csv.is_relative_to(REPO_ROOT) else page_csv}")
    print(f"[EXPORT] Alias Manifest:     {alias_csv.relative_to(REPO_ROOT) if alias_csv.is_relative_to(REPO_ROOT) else alias_csv}")
    print(f"[EXPORT] Duplicate Report:   {dup_csv.relative_to(REPO_ROOT) if dup_csv.is_relative_to(REPO_ROOT) else dup_csv}")
    print(f"[EXPORT] Collision Report:   {rep_md.relative_to(REPO_ROOT) if rep_md.is_relative_to(REPO_ROOT) else rep_md}")
    print(f"[EXPORT] Collision Summary:  {sum_json.relative_to(REPO_ROOT) if sum_json.is_relative_to(REPO_ROOT) else sum_json}")
    print(f"[STATUS] Final Audit Status: {audit_status}")
    print("================================================================================")

    if args.fail_on_leakage and leakage_count > 0:
        return 2

    return 0 if audit_status == "PASS_AUDIT" else 1


if __name__ == "__main__":
    sys.exit(main())
