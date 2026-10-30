"""Validate research artifacts without changing source code or rerunning experiments."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse

TASK = Path(__file__).resolve().parents[1]
ROOT = TASK.parents[3]
EVIDENCE = TASK / "evidence"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-hashes", action="store_true")
    args = parser.parse_args()
    if args.verify_hashes:
        saved = json.loads((EVIDENCE / "hashes.json").read_text(encoding="utf-8"))
        for rel, expected in saved["files"].items():
            assert sha(TASK / rel) == expected, rel
        print(f"PASS: {len(saved['files'])} research artifact hashes")
        return
    assert {p.name for p in TASK.iterdir()} == {"README.md", "superpowers", "evidence"}
    assert {p.name for p in (TASK / "superpowers").iterdir()} == {"spec.md", "plan.md"}
    future = {EVIDENCE / "validation.json", EVIDENCE / "hashes.json"}
    links = []
    for path in TASK.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = link.split("#")[0]
            if not target or "://" in target:
                continue
            resolved = (path.parent / target).resolve()
            assert resolved.exists() or resolved in future, (str(path), target)
            links.append(resolved)
    sources = json.loads((EVIDENCE / "sources.json").read_text(encoding="utf-8"))["sources"]
    assert len(sources) == 21
    assert len({s["id"] for s in sources}) == len(sources)
    primary_hosts = {"arxiv.org", "huggingface.co", "github.com", "www.mdpi.com", "aclanthology.org"}
    assert all(urlparse(s["url"]).hostname in primary_hosts for s in sources)
    local = json.loads((EVIDENCE / "local-evidence.json").read_text(encoding="utf-8"))
    for rel, expected in local["source_sha256"].items():
        assert sha(ROOT / rel) == expected, rel
    grid = local["summary"]["w66"]
    assert grid["queries"] == 171
    assert grid["paired_gaps"]["qpaf_minus_qarf"]["wins"] == 20
    assert grid["paired_gaps"]["qpaf_minus_qarf"]["ties"] == 151
    assert abs(grid["means"]["qpaf"] - 0.9401249762124373) < 1e-12
    toy = json.loads((EVIDENCE / "toy-example.json").read_text(encoding="utf-8"))
    assert toy["constraints_incompatible"] and toy["adaptive_ndcg10"] == 1
    assert abs(toy["best_static_ndcg10_on_three_items"] - 0.9197207891481876) < 1e-12
    f3 = ROOT / "docs/reports/tasks/lab-f3-objective-20261030"
    old = json.loads((f3 / "evidence/hashes.json").read_text(encoding="utf-8"))
    for rel, expected in old["files"].items():
        assert sha(f3 / rel) == expected, "previous F3 evidence changed: " + rel
    changed = subprocess.check_output(["git", "diff", "--name-only", "--", "src", "scripts", "tests", "configs"],
                                      cwd=ROOT, text=True).strip()
    assert not changed, "production source changed"
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    assert "reports/tasks/adaptive-fusion-opportunity-study-20261031/README.md" in index
    validation = {"status": "PASS", "primary_source_cards": len(sources), "local_links_checked": len(links),
                  "local_source_hashes_checked": len(local["source_sha256"]),
                  "prior_f3_hashes_unchanged": len(old["files"]), "production_edits": False,
                  "new_experiments_run": False, "scope": "research and proposed experiments only"}
    (EVIDENCE / "validation.json").write_bytes((json.dumps(validation, indent=2) + "\n").encode("utf-8"))
    manifest = {p.relative_to(TASK).as_posix(): sha(p) for p in sorted(TASK.rglob("*"))
                if p.is_file() and p.name != "hashes.json" and "__pycache__" not in p.parts}
    (EVIDENCE / "hashes.json").write_bytes(
        (json.dumps({"algorithm": "sha256", "files": manifest}, indent=2) + "\n").encode("utf-8"))
    assert all(p.exists() for p in links)
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
