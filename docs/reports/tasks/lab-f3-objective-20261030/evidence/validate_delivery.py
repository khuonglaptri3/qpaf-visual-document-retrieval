"""Verify task artifacts and recorded result provenance after experiment execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

EVIDENCE = Path(__file__).resolve().parent
TASK = EVIDENCE.parent
ROOT = EVIDENCE.parents[4]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-hashes", action="store_true")
    args = parser.parse_args()
    if args.verify_hashes:
        saved = json.loads((EVIDENCE / "hashes.json").read_text(encoding="utf-8"))
        for name, expected in saved["files"].items():
            assert digest(TASK / name) == expected, name
        print(f"PASS: {len(saved['files'])} recorded hashes")
        return
    assert {p.name for p in TASK.iterdir()} == {"README.md", "evidence", "superpowers"}
    assert {p.name for p in (TASK / "superpowers").iterdir()} == {"spec.md", "plan.md"}
    links = []
    for path in TASK.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = target.split("#")[0]
            if not target or "://" in target:
                continue
            resolved = path.parent / target
            assert resolved.exists(), f"broken link {path}: {target}"
            links.append(str(resolved.resolve()))
    index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    assert "reports/tasks/lab-f3-objective-20261030/README.md" in index
    reference = json.loads((ROOT / "results/lab/vidoseek/vidoseek-baseline.json").read_text(encoding="utf-8"))
    records = {}
    sources = {}
    for variant in ("baseline", "f3_approxndcg", "f3_topk_hard"):
        path = EVIDENCE / "results/vidoseek" / f"vidoseek-{variant}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["schema"] == "qpaf-lab-v1"
        assert record["queries"] == 970 and record["folds"] == 5
        assert record["seeds"] == [20260820]
        assert record["recipe"] == reference["recipe"]
        assert record["inputs_sha256"] == reference["inputs_sha256"]
        assert not record["smoke"] and not record["tracked_changes"]
        sources[variant] = record["source_commit"]
        for method, values in record["per_query"].items():
            assert set(values) == set(reference["per_query"][method])
            assert all(0 <= v <= 1 + 1e-12 for v in values.values())
            assert abs(sum(values.values()) / len(values) - record["mean"][method]) < 1e-12
        records[variant] = record
    baseline = records["baseline"]
    assert max(abs(baseline["mean"][m] - reference["mean"][m]) for m in baseline["mean"]) <= 5e-5
    comparisons = json.loads((EVIDENCE / "comparisons.json").read_text(encoding="utf-8"))
    for variant, methods in comparisons.items():
        for method, comparison in methods.items():
            scores = records[variant]["per_query"][method]
            diffs = [scores[q] - baseline["per_query"][method][q] for q in scores]
            assert abs(sum(diffs) / 970 - comparison["delta"]) < 1e-12
            assert comparison["wins"] == sum(v > 1e-12 for v in diffs)
            assert comparison["losses"] == sum(v < -1e-12 for v in diffs)
            assert comparison["ties"] == sum(abs(v) <= 1e-12 for v in diffs)
            assert comparison["wins"] + comparison["ties"] + comparison["losses"] == 970
            assert comparison["ci95"][0] <= comparison["ci95"][1]
    tests = (EVIDENCE / "unit-tests.log").read_text(encoding="utf-8")
    assert "Ran 20 tests" in tests and tests.rstrip().endswith("OK")
    suite = (EVIDENCE / "full-suite.log").read_text(encoding="utf-8")
    assert "Ran 802 tests" in suite and suite.rstrip().endswith("OK (skipped=6)")
    assert sources["f3_approxndcg"] == sources["f3_topk_hard"]
    for variant in ("f3_approxndcg", "f3_topk_hard"):
        subprocess.run(["git", "diff", "--exit-code", sources[variant], "HEAD", "--", "src", "scripts", "tests"],
                       cwd=ROOT, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    code_diff = subprocess.check_output(
        ["git", "diff", "2f15eb19b1a224f5768a5cfaa28692fb06e55b95", "--",
         "src", "scripts", "tests", ":!src/qpaf/lab/variants/f3_approxndcg.py", ":!tests/test_lab_f3.py"],
        cwd=ROOT, text=True)
    assert not code_diff, "source changed beyond the approved F3 performance fix and its tests"
    validation = {"status": "PASS", "full_records": len(records), "queries_per_record": 970,
                  "unit_tests": 20, "source_commits": sources, "local_links_checked": len(links),
                  "full_suite_tests": 802, "full_suite_skipped": 6,
                  "harness_unchanged": True, "overall_scope": "partial: ViMDoc cache unavailable"}
    (EVIDENCE / "validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    files = {p.relative_to(TASK).as_posix(): digest(p) for p in sorted(TASK.rglob("*"))
             if p.is_file() and p.name != "hashes.json" and "__pycache__" not in p.parts}
    (EVIDENCE / "hashes.json").write_text(json.dumps({"algorithm": "sha256", "files": files}, indent=2) + "\n",
                                         encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
