#!/usr/bin/env python3
"""Read PDFs and qrels for the M1.3 CPU audit; preserve existing evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import tomllib
import zipfile

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from qpaf.m13.boundary import get_boundary_status
from qpaf.m13.corpus import inspect_pdf_archive, inspect_pdf_directory
from qpaf.m13.splits import create_deterministic_splits, read_split_bundle, write_split_bundle, serialize_split_manifest
from qpaf.m13.vidoseek import parse_vidoseek_annotations


def parse_args():
    parser = argparse.ArgumentParser(description="M1.3 Primary Corpus (ViDoSeek) CPU Audit Tool.")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--annotations", type=Path)
    corpus = parser.add_mutually_exclusive_group()
    corpus.add_argument("--corpus-zip", type=Path)
    corpus.add_argument("--corpus-dir", type=Path)
    parser.add_argument("--output", type=Path, help="Create a new report; never overwrite an existing report.")
    parser.add_argument("--splits-dir", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--generate-splits", action="store_true")
    mode.add_argument("--verify-splits", action="store_true", help="Read and verify existing splits without changing them.")
    parser.add_argument("--check-boundary", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Audit without writing files.")
    return parser.parse_args()


def _provenance(args):
    sources = [Path(__file__), *sorted((repo_root / "src/qpaf/m13").glob("*.py"))]
    hashes = {p.relative_to(repo_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root,
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=repo_root,
                                    capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return {"command": [sys.executable, *sys.argv], "cwd": str(Path.cwd()),
            "source_commit": commit, "source_tree_dirty": dirty, "source_hashes": hashes,
            "environment": {"python": sys.version, "platform": platform.platform(),
                            "pypdfium2": importlib.metadata.version("pypdfium2")},
            "config": None if not args.config else {"path": str(args.config),
                "sha256": hashlib.sha256(args.config.read_bytes()).hexdigest()}}


def audit(args):
    annotations_path, archive_path, directory_path = args.annotations, args.corpus_zip, args.corpus_dir
    if args.config:
        cfg = tomllib.loads(args.config.read_text(encoding="utf-8"))
        dataset = cfg.get("dataset", {})
        if annotations_path is None and dataset.get("annotation_file"):
            annotations_path = Path(dataset["annotation_file"])
        if archive_path is None and directory_path is None and dataset.get("corpus_file"):
            archive_path = Path(dataset["corpus_file"])
    if annotations_path is None or (archive_path is None and directory_path is None):
        raise ValueError("Both annotations and a PDF corpus are required for a CPU audit")
    if not annotations_path.is_file():
        raise FileNotFoundError(f"Annotations not found: {annotations_path}")
    if (args.generate_splits or args.verify_splits) and args.splits_dir is None:
        raise ValueError("--splits-dir is required for split generation or verification")
    corpus = inspect_pdf_archive(archive_path) if archive_path is not None else inspect_pdf_directory(directory_path)
    parsed = parse_vidoseek_annotations(annotations_path, corpus["doc_page_counts"])
    query_ids = [query["query_id"] for query in parsed.queries]
    splits = {}
    if args.verify_splits:
        splits = read_split_bundle(args.splits_dir, query_ids)
    elif args.generate_splits:
        splits = create_deterministic_splits(query_ids)

    # Preflight all existing output paths before creating any artifacts.
    if args.output and not args.dry_run and (args.output.exists() or args.output.is_symlink()):
        raise FileExistsError(f"Report already exists; select a new output path: {args.output}")
    report = {
        "status": "VERIFIED_CPU_AUDIT", "dataset": "Qiuchen-Wang/ViDoSeek",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "boundary": get_boundary_status(),
        "corpus": corpus,
        "annotations": {"path": str(annotations_path), "sha256": hashlib.sha256(annotations_path.read_bytes()).hexdigest(),
                        "size_bytes": annotations_path.stat().st_size, "total_queries": len(parsed.queries),
                        "total_documents": len(parsed.document_names), "qrels_count": len(parsed.qrels)},
        "queries": parsed.queries, "qrels": parsed.qrels,
        "splits": {name: {"count": len(ids), "sha256": serialize_split_manifest(ids)[1], "ids": ids}
                   for name, ids in splits.items()},
        "split_mode": "verified" if args.verify_splits else "generated" if args.generate_splits else "not_requested",
        "provenance": _provenance(args),
    }
    if args.generate_splits and not args.dry_run:
        write_split_bundle(args.splits_dir, query_ids)
    if args.output and not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            stream.write((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"[OK] VERIFIED_CPU_AUDIT: {corpus['pdf_count']} PDFs, {corpus['total_pages']} pages, {len(query_ids)} queries")
    return 0


def main():
    args = parse_args()
    try:
        return audit(args)
    except (OSError, ValueError, TypeError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"[ERROR] FAILED_CPU_AUDIT: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
