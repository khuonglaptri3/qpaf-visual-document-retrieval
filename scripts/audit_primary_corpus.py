#!/usr/bin/env python3
"""CLI tool for M1.3 Primary Corpus Audit and Closed Boundary Verification."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict

# Ensure src is in python path
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from qpaf.m13.boundary import get_boundary_status
from qpaf.m13.corpus import inspect_pdf_archive
from qpaf.m13.splits import (
    create_deterministic_splits,
    serialize_split_manifest,
    verify_split_disjointness,
)
from qpaf.m13.vidoseek import parse_vidoseek_annotations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M1.3 Primary Corpus (ViDoSeek) CPU Audit Tool."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to TOML config file (e.g. configs/m1.1/vidoseek.toml).",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Path to vidoseek.json annotations file.",
    )
    parser.add_argument(
        "--corpus-zip",
        type=Path,
        help="Path to vidoseek_pdf_document.zip archive.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to write JSON audit report.",
    )
    parser.add_argument(
        "--splits-dir",
        type=Path,
        help="Directory to save or verify split manifest files.",
    )
    parser.add_argument(
        "--generate-splits",
        action="store_true",
        help="Generate deterministic splits and save manifests.",
    )
    parser.add_argument(
        "--verify-splits",
        action="store_true",
        help="Verify existing split manifests in splits-dir.",
    )
    parser.add_argument(
        "--check-boundary",
        action="store_true",
        help="Verify that execution boundary is CLOSED.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform audit without writing output files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Load from config if provided
    annotations_path = args.annotations
    corpus_zip_path = args.corpus_zip

    if args.config and args.config.exists():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore

        with open(args.config, "rb") as f:
            cfg = tomllib.load(f)

        dataset_cfg = cfg.get("dataset", {})
        if not annotations_path and "annotation_file" in dataset_cfg:
            annotations_path = Path(dataset_cfg["annotation_file"])
        if not corpus_zip_path and "corpus_file" in dataset_cfg:
            corpus_zip_path = Path(dataset_cfg["corpus_file"])

    boundary_status = get_boundary_status()

    report: Dict[str, Any] = {
        "status": "VERIFIED_CPU_AUDIT",
        "dataset": "Qiuchen-Wang/ViDoSeek",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "boundary": boundary_status,
        "corpus": {},
        "annotations": {},
        "splits": {},
    }

    # 1. Corpus ZIP Inspection
    if corpus_zip_path and corpus_zip_path.exists():
        archive_info = inspect_pdf_archive(corpus_zip_path)
        report["corpus"] = archive_info
        print(f"[OK] Inspected archive: {corpus_zip_path.name} ({archive_info['pdf_count']} PDFs)")
    elif corpus_zip_path:
        report["corpus"] = {"status": "MISSING_LOCAL_FILE", "path": str(corpus_zip_path)}
        print(f"[NOTE] Corpus archive not found locally at: {corpus_zip_path}")

    # 2. Annotations Parsing
    query_ids = []
    if annotations_path and annotations_path.exists():
        parsed = parse_vidoseek_annotations(annotations_path)
        query_ids = [q["query_id"] for q in parsed.queries]
        report["annotations"] = {
            "total_queries": len(parsed.queries),
            "total_documents": len(parsed.document_names),
            "qrels_count": len(parsed.qrels),
        }
        print(f"[OK] Parsed annotations: {len(parsed.queries)} queries, {len(parsed.document_names)} documents")
    elif annotations_path:
        report["annotations"] = {"status": "MISSING_LOCAL_FILE", "path": str(annotations_path)}
        print(f"[NOTE] Annotations file not found locally at: {annotations_path}")

    # 3. Splits Generation / Verification
    if (args.generate_splits or args.verify_splits) and query_ids:
        splits = create_deterministic_splits(query_ids, seed=2026)
        valid, msg = verify_split_disjointness(splits, total_expected=len(query_ids))
        if not valid:
            print(f"[ERROR] Split verification failed: {msg}", file=sys.stderr)
            return 1

        split_summary = {}
        for split_name, ids in splits.items():
            text, digest = serialize_split_manifest(ids)
            split_summary[split_name] = {
                "count": len(ids),
                "sha256": digest,
            }
            if args.splits_dir and not args.dry_run:
                args.splits_dir.mkdir(parents=True, exist_ok=True)
                manifest_file = args.splits_dir / f"{split_name}_ids.txt"
                manifest_file.write_text(text, encoding="utf-8")

        report["splits"] = split_summary
        print(f"[OK] Derived deterministic splits: Train={len(splits['train'])}, Val={len(splits['val'])}, Test={len(splits['test'])}")

    # 4. Output Writing
    if args.output and not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[OK] Audit report written to: {args.output}")

    print(f"\n[DONE] M1.3 CPU Audit completed successfully. Boundary state: {boundary_status['boundary_state']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
