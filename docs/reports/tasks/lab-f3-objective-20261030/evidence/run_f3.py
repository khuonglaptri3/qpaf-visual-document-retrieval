"""Reproduce the existing F3 protocol; execution evidence only, no harness changes."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).resolve().parent
BUNDLE = ROOT / "results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle"
RESULTS = EVIDENCE / "results" / "vidoseek"
ENV = dict(os.environ, OMP_NUM_THREADS="6", MKL_NUM_THREADS="6", PYTHONUNBUFFERED="1",
           PYTHONIOENCODING="utf-8")


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def run(name, command):
    stamp = datetime.now(timezone.utc).isoformat()
    print(f"{stamp} START {name}", flush=True)
    save(EVIDENCE / "run-state.json", {"stage": name, "status": "running", "started_utc": stamp,
                                      "command": command, "pid": os.getpid()})
    with (EVIDENCE / f"{name}.log").open("w", encoding="utf-8") as log:
        log.write("command: " + subprocess.list2cmdline(command) + "\n")
        log.flush()
        result = subprocess.run(command, cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        save(EVIDENCE / "run-state.json", {"stage": name, "status": "failed",
                                          "exit_code": result.returncode, "command": command})
        raise RuntimeError(f"{name} failed, exit {result.returncode}; see {name}.log")
    print(f"{datetime.now(timezone.utc).isoformat()} PASS {name}", flush=True)


def validate_record(path, reference, *, smoke=False):
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["schema"] == "qpaf-lab-v1"
    assert record["dataset"] == "vidoseek" and record["smoke"] is smoke
    assert record["tracked_changes"] is False
    if record["variant"] == "baseline":
        # Baseline predates the equivalent F3-only optimization; none of its code may change.
        shared = ["src/qpaf/lab/data.py", "src/qpaf/lab/model.py", "src/qpaf/lab/train.py",
                  "src/qpaf/lab/compare.py", "src/qpaf/lab/variants/baseline.py",
                  "src/qpaf/lab/variants/__init__.py", "scripts/run_lab.py"]
        subprocess.run(["git", "diff", "--exit-code", record["source_commit"], "HEAD", "--", *shared],
                       cwd=ROOT, check=True, stdout=subprocess.PIPE)
    else:
        assert record["source_commit"] == git("rev-parse", "HEAD")
    assert record["inputs_sha256"] == reference["inputs_sha256"]
    assert record["folds"] == (2 if smoke else 5)
    assert record["queries"] == (120 if smoke else 970)
    assert record["seeds"] == [20260820]
    assert record["granularities"] == ["query", "page"]
    if not smoke:
        assert record["recipe"] == reference["recipe"]
        assert record["fold_sizes"] == reference["fold_sizes"]
        assert record["fold_anchors"] == reference["fold_anchors"]
        for method in ("static", "qarf", "qpaf"):
            assert set(record["per_query"][method]) == set(reference["per_query"][method])
    return record


def main():
    os.chdir(ROOT)
    assert git("branch", "--show-current") == "feature/lab-f3-objective"
    assert not git("status", "--porcelain", "--untracked-files=no"), "tracked tree must be clean"
    source = git("rev-parse", "HEAD")
    reference = json.loads((ROOT / "results/lab/vidoseek/vidoseek-baseline.json").read_text(encoding="utf-8"))
    checks = {}
    for name, expected in reference["inputs_sha256"].items():
        actual = sha(BUNDLE / name)
        checks[name] = {"sha256": actual, "expected": expected, "matches": actual == expected}
        assert actual == expected, f"input mismatch: {name}"
    save(EVIDENCE / "input-validation.json", {"dataset": "vidoseek", "files": checks,
          "vimdoc": {"status": "missing", "required": ["candidate_scores.parquet", "queries.jsonl", "dev_qrels.json"]},
          "sealed_labels_opened_by_runner": False})
    save(EVIDENCE / "environment.json", {"python": sys.version, "executable": sys.executable,
          "packages": {n: importlib.metadata.version(n) for n in ("torch", "numpy", "pandas", "pyarrow")},
          "source_commit": source, "environment": {k: ENV[k] for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS")},
          "platform": sys.platform, "baseline_reused_from_threads": 2,
          "partial_attempt": "attempt-threads2/full-f3_approxndcg.log (incomplete, excluded)"})
    run("unit-tests", [sys.executable, "-m", "unittest", "tests.test_lab", "tests.test_lab_f3", "-v"])
    for variant in ("f3_approxndcg", "f3_topk_hard"):
        output = EVIDENCE / "smoke" / f"vidoseek-{variant}.json"
        run("smoke-" + variant, [sys.executable, "-u", "scripts/run_lab.py", "--dataset", "vidoseek",
            "--data", str(BUNDLE), "--variant", variant, "--limit", "120", "--epochs", "2",
            "--folds", "2", "--output", str(output)])
        smoke_record = validate_record(output, reference, smoke=True)
        archived = EVIDENCE / "attempt-threads6/smoke" / output.name
        original = json.loads(archived.read_text(encoding="utf-8"))
        assert smoke_record["per_query"] == original["per_query"], "optimized smoke changed rankings"
        assert smoke_record["mean"] == original["mean"], "optimized smoke changed means"
    baseline_path = RESULTS / "vidoseek-baseline.json"
    if baseline_path.is_file():
        validate_record(baseline_path, reference)
        print("REUSE full-baseline: same clean source, input hashes, recipe, exact reference means; "
              "original 2-thread environment in attempt-threads2/environment.json", flush=True)
    else:
        run("full-baseline", [sys.executable, "-u", "scripts/run_lab.py", "--dataset", "vidoseek",
            "--data", str(BUNDLE), "--variant", "baseline", "--output", str(baseline_path)])
    baseline = validate_record(baseline_path, reference)
    gaps = {m: abs(baseline["mean"][m] - reference["mean"][m]) for m in reference["mean"]}
    save(EVIDENCE / "baseline-validation.json", {"gaps": gaps, "tolerance": 5e-5,
          "matches": max(gaps.values()) <= 5e-5, "reference_source_commit": reference["source_commit"]})
    assert max(gaps.values()) <= 5e-5, "baseline mismatch: full F3 variants must not run"
    for variant in ("f3_approxndcg", "f3_topk_hard"):
        output = RESULTS / f"vidoseek-{variant}.json"
        run("full-" + variant, [sys.executable, "-u", "scripts/run_lab.py", "--dataset", "vidoseek",
            "--data", str(BUNDLE), "--variant", variant, "--output", str(output)])
        validate_record(output, reference)
    run("comparison", [sys.executable, "scripts/compare_lab.py", "--results", str(EVIDENCE / "results"),
        "--output", str(EVIDENCE / "SUMMARY_f3.md")])
    sys.path.insert(0, str(ROOT / "src"))
    import numpy as np
    from qpaf.lab.compare import paired
    comparisons = {}
    for variant in ("baseline", "f3_approxndcg", "f3_topk_hard"):
        record = validate_record(RESULTS / f"vidoseek-{variant}.json", reference)
        for method in ("static", "qarf", "qpaf"):
            values = list(record["per_query"][method].values())
            assert np.isfinite(values).all()
            assert all(0 <= v <= 1 + 1e-12 for v in values)
            assert abs(float(np.mean(values)) - record["mean"][method]) < 1e-12
        if variant != "baseline":
            comparisons[variant] = {m: paired(record["per_query"][m], baseline["per_query"][m])
                                     for m in ("qarf", "qpaf")}
    save(EVIDENCE / "comparisons.json", comparisons)
    save(EVIDENCE / "run-state.json", {"status": "eligible_runs_complete", "source_commit": source,
          "completed_utc": datetime.now(timezone.utc).isoformat(),
          "remaining": "ViMDoc missing cache; no f3_lse_pool run; final report and review pending"})
    print("Eligible ViDoSeek runs complete; ViMDoc remains missing.", flush=True)


if __name__ == "__main__":
    main()
