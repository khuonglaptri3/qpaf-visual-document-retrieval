"""Validate the delivered kit and record byte hashes; no model or network calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[5]
TASK = Path(__file__).resolve().parents[1]
BASE = "842176c5b707298672629738390a09e222f47e86"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8")


def delivered_files() -> list[Path]:
    paths = set(git("ls-files", "--cached", "--others", "--exclude-standard").splitlines())
    prefixes = (
        "src/qpaf/jev/", "configs/jev/", "requirements/jev-",
        "tests/test_jev", "scripts/run_jev", "scripts/modal_jev", "scripts/train_jev",
        "docs/reports/tasks/jev-",
    )
    return sorted(
        ROOT / p for p in paths
        if (p.startswith(prefixes) or p in ("README.md", "docs/README.md"))
        and not p.endswith("/evidence/hashes.json")
        and not p.endswith("-review-package.md")
        and (ROOT / p).is_file()
    )


def validate() -> dict:
    checks = []

    def check(name: str, ok: bool, detail=None):
        checks.append({"name": name, "passed": bool(ok), "detail": detail})

    bundles = sorted((ROOT / "docs/reports/tasks").glob("jev-*"))
    for bundle in bundles:
        rel = bundle.relative_to(ROOT).as_posix()
        check(f"{rel}: root layout", {p.name for p in bundle.iterdir()} == {"README.md", "evidence", "superpowers"})
        check(f"{rel}: planning layout", {p.name for p in (bundle / "superpowers").iterdir()} == {"spec.md", "plan.md"})
        check(f"{rel}: provenance", (bundle / "evidence/workflow.md").is_file())
        current = (bundle / "README.md").read_text(encoding="utf-8")
        check(f"{rel}: report links", all(x in current for x in ("superpowers/spec.md", "superpowers/plan.md", "evidence/")))
    broken = []
    immutable_archives = []
    for path in delivered_files():
        if path.suffix != ".md" or "upstream-kev" in path.parts:
            continue
        # Upstream source snapshots are evidence, not authored navigation.
        if path.name.endswith("-review-package.md"):
            continue
        if path.parent.name == "evidence" and path.stem.endswith("-bootstrap-before-runtime-20261120"):
            # Byte-exact historical documents retain links relative to their original location.
            immutable_archives.append(path.relative_to(ROOT).as_posix())
            continue
        for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = target.split("#", 1)[0].strip("<>")
            if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            resolved = (path.parent / unquote(target)).resolve()
            generated = {TASK / "evidence/validation.json", TASK / "evidence/hashes.json"}
            if resolved not in generated and not resolved.exists():
                broken.append({"file": path.relative_to(ROOT).as_posix(), "target": target})
    check("delivered Markdown local links", not broken, broken)
    old_changes = git("diff", "--name-only", BASE, "--", "src/qpaf/lab", "src/qpaf/f9", "results", "evidence").splitlines()
    check("frozen source/results/evidence preserved", not old_changes, old_changes)
    diff_check = subprocess.run(["git", "diff", "--check", BASE], cwd=ROOT, capture_output=True, text=True)
    check("delivery diff whitespace", diff_check.returncode == 0, diff_check.stdout + diff_check.stderr)
    return {"schema": 1, "passed": all(c["passed"] for c in checks), "checks": checks,
            "excluded_immutable_snapshot_links": immutable_archives}


def inventory_record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def verify_inventory(path: Path) -> list[str]:
    try:
        manifest = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        return [f"cannot read hash inventory: {exc}"]
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        return ["hash inventory requires a files list"]
    expected = {p.relative_to(ROOT).as_posix(): p for p in delivered_files()}
    records, errors = {}, []
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            errors.append("invalid hash inventory entry")
            continue
        name = entry["path"]
        if name in records:
            errors.append(f"duplicate path: {name}")
        records[name] = entry
    errors.extend(f"missing path: {name}" for name in sorted(expected.keys() - records.keys()))
    errors.extend(f"unexpected path: {name}" for name in sorted(records.keys() - expected.keys()))
    if errors:
        return errors
    for name, source in expected.items():
        try:
            actual = inventory_record(source)
        except OSError as exc:
            errors.append(f"{name}: {exc}")
            continue
        record = records[name]
        if type(record.get("bytes")) is not int or record["bytes"] != actual["bytes"]:
            errors.append(f"size mismatch: {name}")
        if record.get("sha256") != actual["sha256"]:
            errors.append(f"SHA-256 mismatch: {name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write validation and hash evidence after checks")
    args = parser.parse_args()
    result = validate()
    if args.write:
        (TASK / "evidence/validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        manifest = {
            "algorithm": "SHA-256",
            "scope": "delivered Jev code/configs/tests/task bundles and entry documentation",
            "excludes": ["evidence/hashes.json manifests", "ignored review-package scratch", "ignored generated runs/checkpoints/logs"],
            "files": [inventory_record(p) for p in delivered_files()],
        }
        (TASK / "evidence/hashes.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    else:
        mismatches = verify_inventory(TASK / "evidence/hashes.json")
        result["hash_mismatches"] = mismatches
        result["passed"] = result["passed"] and not mismatches
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
