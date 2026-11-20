"""Controller evidence: fresh local clones before push, remote refs after push.

Does not merge, push, download weights, import models, or submit cloud jobs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).resolve().parent
MAIN = Path("C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project")
OWNERS = {
    "phat": "research/jev-phat-data-infra",
    "thanh": "research/jev-thanh-baselines",
    "khuong": "research/jev-khuong-model",
}


def run(argv, cwd=ROOT):
    result = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", errors="replace",
                            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    record = {"command": [str(x) for x in argv], "returncode": result.returncode,
              "stdout": result.stdout, "stderr": result.stderr}
    if result.returncode:
        raise RuntimeError(json.dumps(record, ensure_ascii=True))
    return record


def git(*args, cwd=ROOT):
    return run(["git", *args], cwd)["stdout"].strip()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main_state(before):
    state = {
        "branch": git("branch", "--show-current", cwd=MAIN),
        "head": git("rev-parse", "HEAD", cwd=MAIN),
        "index_sha256": hashlib.sha256((MAIN / ".git/index").read_bytes()).hexdigest(),
        "staged_diff_empty": not git("diff", "--cached", "--name-only", cwd=MAIN),
    }
    state["index_bytes_unchanged"] = state["index_sha256"] == before["index_sha256"]
    if not (state["branch"] == before["branch"] and state["head"] == before["head"]
            and state["index_bytes_unchanged"] and state["staged_diff_empty"]):
        raise RuntimeError(f"Main checkout preservation failed: {state}")
    return state


def clone_smoke(owner, branch, python):
    with tempfile.TemporaryDirectory(prefix=f"jev-delivery-{owner}-", ignore_cleanup_errors=True) as folder:
        temp = Path(folder)
        clone = temp / "clone"
        clone_log = run(["git", "clone", "--quiet", "--depth", "1", "--single-branch",
                         "--branch", branch, ROOT.as_uri(), clone])
        base_fetch = run(["git", "fetch", "--quiet", "--depth", "1", ROOT.as_uri(),
                          "842176c5b707298672629738390a09e222f47e86"], cwd=clone)
        commit = git("rev-parse", "HEAD", cwd=clone)
        output = temp / "demo"
        command = [python, "-I", "-S", clone / f"scripts/run_jev_{owner}.py", "--out", output]
        smoke = run(command, cwd=temp)
        artifacts = {
            p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob("*")) if p.is_file()
        }
        if owner == "phat":
            pairs = read(output / "prepared/pairs.json")
            cache = read(output / "prepared/base_scores.json")
            assert pairs["synthetic"] is True and len(pairs["pairs"]) == 2
            assert cache["manifest"]["synthetic"] is True
            assert cache["pairs_sha256"] == artifacts["prepared/pairs.json"]
            assert read(output / "prepared/manifest.json")["partition"] == "train"
        elif owner == "thanh":
            baseline, evaluation = (read(output / f"{name}.json") for name in ("baseline", "evaluation"))
            assert baseline["synthetic"] is True and evaluation["synthetic"] is True
            assert evaluation["mean"]["mrr@10"] - baseline["mean"]["mrr@10"] == 0.5
            assert read(output / "comparison.json")["synthetic"] is True
            assert "comparison.csv" in artifacts
        else:
            manifest = read(output / "train.jsonl.manifest.json")
            assert manifest["synthetic"] is True and manifest["records"] == 2
            assert manifest["data_sha256"] == artifacts["train.jsonl"]
            for init in ("kev", "base"):
                plan = read(output / f"{init}-plan.json")
                assert plan["init"] == init and plan["export"] == manifest
                assert not (output / f"{init}-checkpoint").exists()
        validation = run([python, "-I", "-S", clone / "docs/reports/tasks/jev-runnable-team-kit-20261120/evidence/finalize_artifacts.py"], cwd=temp)
        assert read(clone / "docs/reports/tasks/jev-runnable-team-kit-20261120/evidence/validation.json")["passed"] is True
        owner_hashes = read(clone / f"docs/reports/tasks/jev-{ {'phat':'phat-data-infra','thanh':'thanh-baselines','khuong':'khuong-model'}[owner]}-20261120/evidence/hashes.json")
        assert all(hashlib.sha256((clone / item["path"]).read_bytes()).hexdigest() == item["sha256"]
                   for item in owner_hashes["files"])
        return {"returncode": 0, "commit": commit, "synthetic": True,
                "artifacts_verified": True, "artifacts_sha256": artifacts,
                "python_version": run([python, "--version"])["stdout"].strip(),
                "clone": clone_log, "pinned_base_fetch": base_fetch,
                "smoke": smoke, "bundle_validation": validation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepush", "published"), required=True)
    parser.add_argument("--shared-commit", required=True)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--prepush-proof", type=Path, default=EVIDENCE / "delivery-prepush.json")
    parser.add_argument("--out", type=Path, help="optional evidence destination outside the tested checkout")
    args = parser.parse_args()
    before = read(EVIDENCE / "delivery-before.json")
    if args.phase == "prepush":
        registry = {"schema": 1, "published": False, "shared_commit": args.shared_commit,
                    "full_data_model_quality_verified": False, "branches": []}
        for owner, branch in OWNERS.items():
            commit = git("rev-parse", branch)
            git("merge-base", "--is-ancestor", args.shared_commit, commit)
            git("merge-base", "--is-ancestor", before["remote_refs"][f"refs/heads/{branch}"], commit)
            proof = clone_smoke(owner, branch, args.python)
            assert proof["commit"] == commit
            registry["branches"].append({"owner": owner, "branch": branch, "commit": commit,
                "url": f"https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/tree/{branch}",
                "fresh_clone": proof})
    else:
        registry = read(args.prepush_proof)
        assert registry["shared_commit"] == args.shared_commit
        remote = dict(line.split()[::-1] for line in git("ls-remote", "--heads", "origin", "research/jev-*").splitlines())
        for branch in registry["branches"]:
            branch["remote_sha"] = remote.get(f"refs/heads/{branch['branch']}")
            branch["matched"] = branch["commit"] == branch["remote_sha"] == git("rev-parse", branch["branch"])
            assert branch["matched"], branch
        registry["published"] = True
    registry["main_checkout"] = main_state(before["main_checkout"])
    destination = args.out or EVIDENCE / ("delivery-prepush.json" if args.phase == "prepush" else "delivery.json")
    destination.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"path": str(destination), "published": registry["published"],
                      "branches": [{k: b[k] for k in ("owner", "branch", "commit")} for b in registry["branches"]],
                      "main_checkout": registry["main_checkout"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
