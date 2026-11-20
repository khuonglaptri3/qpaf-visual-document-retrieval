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
    for path in delivered_files():
        if path.suffix != ".md" or "upstream-kev" in path.parts:
            continue
        # Upstream source snapshots are evidence, not authored navigation.
        if path.name.endswith("-review-package.md"):
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
    return {"schema": 1, "passed": all(c["passed"] for c in checks), "checks": checks}


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
            "files": [
                {"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in delivered_files()
            ],
        }
        (TASK / "evidence/hashes.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    else:
        manifest_path = TASK / "evidence/hashes.json"
        if manifest_path.is_file():
            mismatches = []
            for item in json.loads(manifest_path.read_text(encoding="utf-8"))["files"]:
                p = ROOT / item["path"]
                if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != item["sha256"]:
                    mismatches.append(item["path"])
            result["hash_mismatches"] = mismatches
            result["passed"] = result["passed"] and not mismatches
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
