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
        help="Directory containing verified M1.3 *_ids.txt and split_manifest.json.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        help="Directory containing source PDF files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
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
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")

    print("================================================================================")
    print("QPAF Milestone 1.6 — Primary-Corpus Collision Audit")
    print("================================================================================")

    inventory, overlap = {}, {}
    if args.fixture:
        if args.annotations or args.corpus_dir or args.splits_dir:
            raise ValueError('--fixture cannot be mixed with real inputs')
        print('[INFO] Explicit synthetic fixture; this is not a real corpus audit.')
        raw_pages, split_map, raw_aliases, qrels = generate_synthetic_collision_corpus()
        for row in raw_pages:
            row['review_status'] = 'synthetic_not_reviewed'
    else:
        if not all((args.annotations, args.corpus_dir, args.splits_dir)):
            raise ValueError('Real audit requires --annotations, --corpus-dir and --splits-dir; fixture requires --fixture')
        from qpaf.m16.real_corpus import load_real_corpus
        raw_pages, split_map, raw_aliases, qrels, inventory, overlap = load_real_corpus(
            args.corpus_dir, args.annotations, args.splits_dir)
    if not raw_pages or not qrels:
        raise ValueError('Cannot audit empty pages or qrels')

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
    unresolved_aliases = sum(r.review_status == 'unresolved' for r in alias_records)
    overlap_count = len(overlap.get('overlapping_content', []))
    if unresolved_aliases:
        audit_status = 'FAIL_UNRESOLVED_ALIASES'
    elif overlap_count or overlap.get('cross_split_exact_query_groups'):
        audit_status = 'REVIEW_REQUIRED_OVERLAP'
    elif leakage_count > 0:
        audit_status = "FAIL_LEAKAGE_DETECTED"
    elif qrel_results["orphan_query_count"] > 0:
        audit_status = "FAIL_ORPHAN_QUERIES"
    else:
        audit_status = "PASS_AUDIT"

    summary: Dict[str, Any] = {
        "status": audit_status,
        "evidence_kind": "synthetic_fixture" if args.fixture else "real_corpus_cpu_audit",
        "independent_review": "PENDING",
        "unresolved_alias_count": unresolved_aliases,
        "document_overlap_count": len(overlap.get('overlapping_documents', {})),
        "content_overlap_count": overlap_count,
        "missing_target_count": qrel_results['missing_target_count'],
        "content_hash_method": "synthetic" if args.fixture else "pdfium_rgb_72dpi_v1",

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

    output_dir.mkdir(parents=True, exist_ok=False)
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

    import platform
    import subprocess
    from qpaf.m11.artifacts import digest
    def save(name, value):
        (output_dir/name).write_bytes((json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode('utf-8'))
    save('input_inventory.json', inventory)
    save('overlap_report.json', overlap)
    save('qrel_validation.json', qrel_results)
    source_paths = [Path(__file__), *sorted((SRC_DIR/'qpaf'/'m16').glob('*.py')),
                    *sorted((SRC_DIR/'qpaf'/'m13').glob('*.py'))]
    save('provenance.json', {
        'command': sys.argv, 'python': sys.version, 'platform': platform.platform(),
        'git_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=REPO_ROOT, text=True).strip(),
        'source_sha256': {p.relative_to(REPO_ROOT).as_posix():digest(p) for p in source_paths},
        'inputs': {} if args.fixture else {
            str(args.annotations):digest(args.annotations),
            **{str(p):digest(p) for p in sorted(args.splits_dir.iterdir()) if p.is_file()}},
    })
    save('hash_manifest.json', {p.name:{'sha256':digest(p), 'size_bytes':p.stat().st_size}
                               for p in sorted(output_dir.iterdir()) if p.is_file()})
    if args.fail_on_leakage and (leakage_count > 0 or overlap_count > 0):
        return 2

    return 0 if audit_status == "PASS_AUDIT" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(f'[ERROR] {exc}', file=sys.stderr)
        sys.exit(1)
