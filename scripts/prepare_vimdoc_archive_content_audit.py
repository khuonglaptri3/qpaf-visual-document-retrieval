"""Validate the closed ViMDoc archive-audit package without opening the archive."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.run_vimdoc_archive_content_audit import (  # noqa: E402
    CONFIG_RELATIVE_PATH,
    package_preflight,
)

MANIFEST_RELATIVE_PATH = "docs/04_data_protocol/manifests/vimdoc_archive_content_audit_v1_preparation.json"


def verify_manifest(root: Path) -> int:
    manifest = json.loads((root / MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8"))
    if (
        manifest.get("package_id") != "vimdoc_archive_content_audit_v1_preparation"
        or manifest.get("status") != "PREPARED_LOCAL_REVIEW_EXECUTION_CLOSED"
        or manifest.get("authorization") != {
            "execution_authorized": False,
            "approved_invocations": 0,
            "approved_timeout_seconds": 0,
            "approved_retries": 0,
        }
    ):
        raise ValueError("Preparation manifest status/authorization drift")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Preparation manifest inventory is missing")
    for entry in entries:
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Preparation file missing: {entry['path']}")
        if path.stat().st_size != entry["bytes"]:
            raise ValueError(f"Preparation file size drift: {entry['path']}")
        from scripts.run_vimdoc_archive_content_audit import file_sha256

        if file_sha256(path) != entry["sha256"]:
            raise ValueError(f"Preparation file hash drift: {entry['path']}")
    return len(entries)


def main() -> int:
    root = ROOT
    try:
        report = package_preflight(root, root / CONFIG_RELATIVE_PATH)
        report["preparation_manifest_files_verified"] = verify_manifest(root)
    except (KeyError, OSError, TypeError, ValueError, PermissionError) as error:
        print(f"VIMDOC_ARCHIVE_AUDIT_PREPARATION_REFUSED: {error}")
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
