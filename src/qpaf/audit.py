"""Create immutable M1.4 inventory snapshots; never infer research acceptance."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys


FIELDS = ("path", "category", "size_bytes", "sha256", "status", "note")
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".cache", ".codex", ".agents", ".superpowers", ".worktrees", "evidence",
    "build", "dist", "node_modules",
}
INFRASTRUCTURE = {
    "src/qpaf/audit.py", "src/qpaf/__init__.py", "scripts/audit_repository.py",
}


def is_link(path):
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def digest_file(path):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError("File changed during hashing")
    return after.st_size, digest.hexdigest()


def category_for(relative):
    first = relative.parts[0].lower()
    if relative.name.lower() in {"readme.md", ".gitkeep"}:
        return "documentation"
    if relative.as_posix() in INFRASTRUCTURE:
        return "infrastructure"
    if first == "src" and relative.suffix == ".py":
        return "source"
    if first == "data":
        return "data"
    if first == "configs":
        return "config"
    if first in {"runs", "results", "artifacts", "checkpoints"}:
        return "run"
    return "documentation" if relative.suffix.lower() in {".md", ".xlsx"} else "infrastructure"


def collect_files(root, output):
    rows, excluded, errors = [], [], []

    def walk_error(error):
        errors.append(str(error))

    for current, directories, filenames in os.walk(root, followlinks=False, onerror=walk_error):
        current = Path(current)
        kept = []
        for name in sorted(directories):
            path = current / name
            if name.lower() in SKIP_DIRS or name.endswith(".egg-info") or is_link(path) or path == output:
                excluded.append(path.relative_to(root).as_posix() + "/")
            else:
                kept.append(name)
        directories[:] = kept
        for name in sorted(filenames):
            path = current / name
            relative = path.relative_to(root)
            lower = name.lower()
            if (is_link(path) or lower in {".env", ".ds_store", "thumbs.db"}
                    or (lower.startswith(".env.") and lower != ".env.example")
                    or path.suffix.lower() in {".pem", ".key", ".p12", ".pyc", ".pyo"}):
                excluded.append(relative.as_posix())
                continue
            category = category_for(relative)
            row = dict.fromkeys(FIELDS, "")
            row.update(path=relative.as_posix(), category=category, status="OBSERVED")
            if category in {"source", "data", "config"}:
                row["status"] = "UNREVIEWED"
            elif category == "run":
                row.update(status="PROVENANCE_UNVERIFIED", note="Observed output; run/config/commit/data links require review")
            try:
                row["size_bytes"], row["sha256"] = digest_file(path)
            except OSError as error:
                row.update(status="ERROR", note=str(error))
                errors.append(f"{relative.as_posix()}: {error}")
            rows.append(row)
    return sorted(rows, key=lambda row: row["path"]), sorted(excluded), errors


def git_snapshot(root):
    values = {}
    commands = {
        "commit": ["rev-parse", "HEAD"],
        "branch": ["branch", "--show-current"],
        "worktree_status": ["status", "--porcelain=v1", "--untracked-files=all"],
    }
    for key, arguments in commands.items():
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *arguments], capture_output=True,
                encoding="utf-8", errors="replace", timeout=30,
            )
            values[key] = result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"
        except (OSError, subprocess.TimeoutExpired):
            values[key] = "UNAVAILABLE"
    return values


def write_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_audit(root, output):
    if not output.is_relative_to(root) or output == root:
        raise ValueError("Output must be a new directory inside the audit root")
    if output.exists():
        raise ValueError("Output already exists; choose a new snapshot namespace")
    rows, excluded, errors = collect_files(root, output)
    git = git_snapshot(root)
    generated = datetime.now(timezone.utc).isoformat()
    counts = {name: sum(row["category"] == name for row in rows)
              for name in ("source", "data", "config", "run", "documentation", "infrastructure")}
    gaps = []
    for name, code in (("source", "RESEARCH_CODE_MISSING"), ("data", "DATA_MISSING"),
                       ("config", "CONFIG_MISSING"), ("run", "RUNS_MISSING")):
        if not counts[name]:
            gaps.append((code, f"No {name} assets observed in the audited scope. Request the real location or record that none exist."))
    if any(value == "UNAVAILABLE" for value in git.values()):
        gaps.append(("GIT_STATE_UNAVAILABLE", "Git revision/branch/status could not be read; check repository access."))
    gaps.extend(("INPUT_READ_ERROR", error) for error in errors)
    gaps.append(("PROVENANCE_REVIEW_REQUIRED", "Khương and independent QA must review source/data/config/run/output links. Inventory generation is not M1.4 acceptance."))
    metadata = {
        "schema_version": 1, "task": "M1.4", "owner": "Trần Đình Khương",
        "planned_date": "2026-09-23", "generated_at_utc": generated,
        "status": "PARTIAL", "file_count": len(rows), "counts": counts,
        "git": git, "excluded_entries": excluded, "read_errors": errors,
        "gaps": [{"id": code, "detail": detail} for code, detail in gaps],
        "scope": "Local filesystem inventory; generated evidence, links and configured exclusions are omitted. No external assets were inspected.",
    }
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "repo_inventory.csv", rows)
    write_csv(output / "hash_manifest.csv", rows)
    for name, category in (("data_inventory.csv", "data"), ("config_inventory.csv", "config"), ("run_inventory.csv", "run")):
        write_csv(output / name, [row for row in rows if row["category"] == category])
    snapshot = [f"generated_at_utc: {generated}", "planned_date: 2026-09-23"]
    snapshot += [f"{key}: {value or '(clean/empty)'}" for key, value in git.items()]
    (output / "git_snapshot.txt").write_text("\n".join(snapshot) + "\n", encoding="utf-8", newline="\n")
    gap_text = ["# M1.4 gap log", "", "Status: PARTIAL", f"Observed at: {generated}",
                "", "Only this checkout was inspected. Missing local assets do not prove that the team has no assets elsewhere.", ""]
    gap_text += [f"- **{code}** — {detail}" for code, detail in gaps]
    gap_text += ["", "Next: provide research source, corpus/split/qrels manifests, experiment configs and historical run locations; create a new audit snapshot after review."]
    (output / "gap_log.md").write_text("\n".join(gap_text) + "\n", encoding="utf-8", newline="\n")
    (output / "audit_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return metadata


def verify_manifest(root, manifest):
    failures, seen = [], set()
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"path", "sha256", "size_bytes"}.issubset(reader.fieldnames or []):
            raise ValueError("Manifest is missing required columns: path, sha256, size_bytes")
        for row in reader:
            raw = row.get("path") or ""
            relative = PurePosixPath(raw)
            if (not raw or relative.is_absolute() or ".." in relative.parts
                    or "\\" in raw or PureWindowsPath(raw).drive):
                failures.append(f"Unsafe manifest path: {raw}")
                continue
            path = root.joinpath(*relative.parts)
            parents = [root.joinpath(*relative.parts[:i]) for i in range(1, len(relative.parts) + 1)]
            if any(is_link(parent) for parent in parents) or not path.resolve().is_relative_to(root):
                failures.append(f"Unsafe linked manifest path: {raw}")
                continue
            if raw in seen:
                failures.append(f"Duplicate manifest path: {raw}")
                continue
            seen.add(raw)
            try:
                expected_hash = row.get("sha256") or ""
                if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                    raise ValueError("Invalid SHA-256")
                size, digest = digest_file(path)
                if digest != expected_hash or size != int(row.get("size_bytes") or "-1"):
                    failures.append(f"Content mismatch: {raw}")
            except (OSError, ValueError) as error:
                failures.append(f"{raw}: {error}")
    if not seen and not failures:
        failures.append("Manifest is empty; no hashes verified")
    return failures, len(seen)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="New evidence directory, relative to root or absolute")
    mode.add_argument("--verify", type=Path, help="Existing hash_manifest.csv")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if not root.is_dir():
            raise ValueError("Audit root must be an existing directory")
        value = args.output if args.output is not None else args.verify
        path = (root / value).resolve()
        if args.verify is not None:
            failures, count = verify_manifest(root, path)
            if failures:
                print("\n".join(failures), file=sys.stderr)
                return 1
            print(f"Verified {count} file hashes. Research acceptance is a separate review.")
            return 0
        result = build_audit(root, path)
        print(json.dumps({"output": str(path), "files": result["file_count"], "status": result["status"], "gaps": len(result["gaps"])}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, csv.Error) as error:
        print(f"Audit error: {error}", file=sys.stderr)
        return 1
