#!/usr/bin/env python3
"""Create the read-only M2.1 data-role and split-freeze evidence bundle."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qpaf.m21.data_splits import build_data_split_freeze, write_evidence_bundle


def _provenance():
    source_files = [Path(__file__), ROOT / "src/qpaf/m21/data_splits.py"]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    tracked_status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "tracked_tree_dirty": bool(tracked_status),
        "python": sys.version,
        "command": [sys.executable, *sys.argv],
        "source_hashes": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=ROOT / "data/manifests/vidoseek-e91a92b-location.json",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=ROOT / "data/raw/vidoseek-e91a92b",
    )
    parser.add_argument(
        "--splits-dir",
        type=Path,
        default=ROOT / "evidence/revisions/m1.3-001/splits",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "evidence/revisions/m2.1-001",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        manifest, report = build_data_split_freeze(
            repo_root=args.repo_root,
            source_manifest_path=args.source_manifest,
            raw_dir=args.raw_dir,
            splits_dir=args.splits_dir,
        )
        report["provenance"] = _provenance()
        write_evidence_bundle(args.output_dir, manifest, report)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"[ERROR] M2.1 freeze failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"[OK] M2.1 split freeze: {report['query_count']} queries; "
        f"evidence={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
