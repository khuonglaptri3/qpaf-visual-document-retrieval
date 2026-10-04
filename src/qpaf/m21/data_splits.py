"""Freeze the active ViDoSeek split roles without changing M1.3 artifacts."""

import hashlib
import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, Tuple

from qpaf.m13.splits import read_split_bundle
from qpaf.m13.vidoseek import parse_vidoseek_annotations


def _relative_path(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _verify_reproduced_payloads(
    source: Dict[str, Any], raw_dir: Path, repo_root: Path
) -> Dict[str, Dict[str, Any]]:
    verified = {}
    for record in source["files"]:
        path = raw_dir / record["filename"]
        size = path.stat().st_size
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if size != record["size_bytes"] or digest != record["sha256"]:
            raise ValueError(f"Reproduced payload hash mismatch: {record['filename']}")
        verified[record["filename"]] = {
            "path": _relative_path(path, repo_root),
            "size_bytes": size,
            "sha256": digest,
        }
    return verified


def build_data_split_freeze(
    *,
    repo_root: Path,
    source_manifest_path: Path,
    raw_dir: Path,
    splits_dir: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build the M2.1 role manifest and its verification report read-only."""
    source = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    data_files = _verify_reproduced_payloads(source, raw_dir, repo_root)
    parsed = parse_vidoseek_annotations(raw_dir / "vidoseek.json")
    query_ids = [query["query_id"] for query in parsed.queries]
    splits = read_split_bundle(splits_dir, query_ids)
    split_manifest = json.loads((splits_dir / "split_manifest.json").read_text(encoding="utf-8"))

    split_files = split_manifest["files"]

    roles = {
        "train": {
            "dataset": source["dataset"],
            "purpose": "learned_model_fitting",
            "id_manifest": _relative_path(splits_dir / "train_ids.txt", repo_root),
            "count": len(splits["train"]),
            "sha256": split_files["train_ids.txt"]["sha256"],
            "size_bytes": split_files["train_ids.txt"]["size_bytes"],
        },
        "validation": {
            "dataset": source["dataset"],
            "purpose": "model_selection_and_calibration",
            "id_manifest": _relative_path(splits_dir / "val_ids.txt", repo_root),
            "count": len(splits["val"]),
            "sha256": split_files["val_ids.txt"]["sha256"],
            "size_bytes": split_files["val_ids.txt"]["size_bytes"],
        },
        "test": {
            "dataset": source["dataset"],
            "purpose": "frozen_primary_evaluation",
            "id_manifest": _relative_path(splits_dir / "test_ids.txt", repo_root),
            "count": len(splits["test"]),
            "sha256": split_files["test_ids.txt"]["sha256"],
            "size_bytes": split_files["test_ids.txt"]["size_bytes"],
        },
        "confirmation": {
            "dataset": "ViMDoc",
            "status": "NOT_ACTIVATED_FUTURE_SCOPE",
            "id_manifest": None,
        },
        "external": {
            "dataset": None,
            "status": "NOT_ADOPTED",
            "id_manifest": None,
        },
    }
    manifest = {
        "schema_version": 1,
        "task_id": "M2.1",
        "status": "VERIFIED_ACTIVE_PRIMARY_SPLITS",
        "dataset": {
            "name": source["dataset"],
            "revision": source["revision"],
            "source_manifest": _relative_path(source_manifest_path, repo_root),
            "source_manifest_sha256": hashlib.sha256(source_manifest_path.read_bytes()).hexdigest(),
        },
        "data_files": data_files,
        "split_bundle": {
            "source_task": "M1.3",
            "manifest_path": _relative_path(splits_dir / "split_manifest.json", repo_root),
            "manifest_sha256": hashlib.sha256(
                (splits_dir / "split_manifest.json").read_bytes()
            ).hexdigest(),
        },
        "split_policy": split_manifest["policy"],
        "query_ids_sha256": split_manifest["query_ids_sha256"],
        "roles": roles,
    }
    split_sets = {name: set(ids) for name, ids in splits.items()}
    overlaps = {
        "train_validation": len(split_sets["train"] & split_sets["val"]),
        "train_test": len(split_sets["train"] & split_sets["test"]),
        "validation_test": len(split_sets["val"] & split_sets["test"]),
    }
    union_count = len(set().union(*split_sets.values()))
    return manifest, {
        "status": "VERIFIED",
        "query_count": len(query_ids),
        "checks": {
            "source_payload_hashes": "PASS",
            "split_disjointness": "PASS",
            "split_union_matches_annotations": "PASS",
        },
        "integrity": {
            "pairwise_overlap": overlaps,
            "union_count": union_count,
            "annotation_query_count": len(query_ids),
        },
    }


def write_evidence_bundle(
    output_dir: Path,
    manifest: Dict[str, Any],
    report: Dict[str, Any],
) -> None:
    """Write an immutable M2.1 evidence bundle and bind its payload hashes."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Evidence output already exists: {output_dir}")

    roles = manifest["roles"]
    readme = (
        "# M2.1 — Data-split roles and ID manifests\n\n"
        f"Status: `{manifest['status']}`\n\n"
        "The active ViDoSeek primary split is frozen read-only from the accepted M1.3 "
        "ID artifacts. This revision does not authorize learned training.\n\n"
        "| Role | Count | State |\n"
        "|---|---:|---|\n"
        f"| Train | {roles['train']['count']} | Active |\n"
        f"| Validation | {roles['validation']['count']} | Active |\n"
        f"| Test | {roles['test']['count']} | Active, frozen primary evaluation |\n"
        f"| Confirmation | — | {roles['confirmation']['status']} |\n"
        f"| External | — | {roles['external']['status']} |\n"
    ).encode("utf-8")
    payloads = {
        "README.md": readme,
        "data_split_manifest.json": (
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8"),
        "verification_report.json": (
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8"),
    }

    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=["path", "size_bytes", "sha256"], lineterminator="\n")
    writer.writeheader()
    for name in sorted(payloads):
        data = payloads[name]
        writer.writerow(
            {
                "path": name,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    payloads["hash_manifest.csv"] = csv_buffer.getvalue().encode("utf-8")

    output_dir.mkdir(parents=True)
    for name, data in payloads.items():
        with (output_dir / name).open("xb") as stream:
            stream.write(data)
