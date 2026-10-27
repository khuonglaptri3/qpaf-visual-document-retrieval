# M5.5 PR #45 Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this continuation task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair unfinished PR checks, verify the existing CPU result, and produce a precise current handoff.

**Architecture:** Keep the approved diagnostic executor and immutable evidence untouched. Confine a reproduced Git maintenance race to temporary test fixtures. Replay in the original numerical environment and record successor evidence.

**Tech Stack:** Python 3.11.14, unittest, Git, NumPy/pandas/PyArrow, GitHub Actions.

**Spec:** [spec.md](spec.md). The original completed CPU plan is in Git at starting commit `1bdb491ec3b74f578c31dda5ba796d1d375ac586`, path `docs/superpowers/plans/2026-10-27-m55-cpu-diagnostics.md`.

## Global Constraints

- The user superseded the Modal/GPU prohibition and delegated details within validation; use the successor R5-04 protocol in the spec.
- No training, retriever rerun, test-label access, ViMDoc access or method change.
- Preserve all existing M5.5 run/evidence and pinned source/authority bytes.
- Do not infer independent human acceptance or full M5.5 completion from CI.
- Use exactly the mandatory task layout specified by the owner.

## Review Focus

- Aggressive/global Git maintenance must not race fixture cleanup.
- Git subprocess failures must propagate; do not hide cleanup errors with blanket retries.
- A fix must not invalidate historical M5.5 source/authority hashes.
- Do not weaken exact Python/numerical replay pins to fit this machine.
- Moving planning files must preserve report and index links.

## Task 1: Reproduce and repair the CI fixture race

**Files:** `tests/test_m34_supervisor.py`; other affected fixtures only if justified; new task `evidence/` logs.

**Interfaces:** Consumes real temporary Git repositories and fixture `git(root, *args)`; produces commits without detached maintenance racing cleanup.

- [ ] Capture the CI traceback and inspect repeated fixture commits.
- [ ] Force real automatic maintenance; prove a worker outlives the helper and save a deterministic failing regression.
- [ ] Apply the smallest fixture-only change, preserving Git error propagation.
- [ ] Run regression/supervisor tests and full unittest suite; record every skip/failure, then commit.

## Task 2: Verify the unchanged CPU delivery

**Files:** new task `evidence/` receipts only; original `results/m5.5/` stays read-only.

**Interfaces:** Existing CLI `verify`, external manifest `f141871d5adbd90c11fad5084d6c08a599009e3bd0bbbe5f60513e8eebff03be`, exact Python 3.11.14 / NumPy 2.4.6 / pandas 3.1.0 / PyArrow 26.0.0.

- [ ] Prepare isolated CPU environment; restore pinned M4.2 inputs, checking original hashes first.
- [ ] Run existing read-only verifier; expect 171 queries, 82,255 candidates, PASS. Compare all run/source/authority bytes before/after.
- [ ] Record environment, commands, hashes and access limits; never rerun the original scientific namespace.

## Task 3: Validation-only R5-04 GPU execution

**Files:** new `scripts/m55_gpu_worker.py`, `scripts/run_m55_gpu.py`, `tests/test_m55_gpu.py`; successor authorization/workload/receipts under task `evidence/`; new `results/m5.5/RUN-QPAF-M5_5-SYS-001-*/`.

**Interfaces:** `make_workload(ids)` produces 20 warm-up events and six passes over 171 distinct IDs; `validate_payload(workload, records)` refuses non-validation/label-bearing rows; `summarize(rows, measured_ids, peak)` checks 1,026 ordered events. Launcher exports pinned M4.2 validation score/text/ID data and seed-1 reference predictions, then runs one bounded Modal invocation with isolated method subprocesses.

- [ ] Write failing tests for exact workload/counts, payload boundaries, ordered coverage, nonfinite/stage-invalid timings, inclusive 10ms/exclusive 1.5GiB gates and bundle/authorization tampering.
- [ ] Adapt the frozen M3.6 worker and launcher into new files; preserve their measurement stages, telemetry and source/runtime checks. Add validation-only export, explicit six-pass counts and one new external authorization pin.
- [ ] Run focused tests/full suite and fresh pre-execution code review; fix material issues before remote invocation.
- [ ] Commit source, prepare/hash the label-free bundle, record the user's exact GPU/delegation text in a new M5.5 authorization; pin command, checkpoints, runtime/image, workload and limits.
- [ ] Run one A10/2-core/5GiB invocation, no automatic retry, 900s watchdog; preserve success/failure bytes. Verify 171-query parity, 1,026 events per method, raw timings and independently recomputed summaries.
- [ ] Record new R5-04 engineering result and its counting interpretation; do not change historical CPU deferred receipts or invent independent human acceptance.

## Task 4: Final report, review and PR continuation

**Files:** bundle `README.md`, `evidence/workflow.md`, evidence manifest; documentation indexes and existing progress/handoff links as needed.

**Interfaces:** Consumes Tasks 1-2 evidence; produces a current linked report and updated existing PR branch.

- [ ] Obtain fresh-context review and address material findings with RED-to-GREEN verification.
- [ ] Validate bundle layout, local links, hashes, historical bytes and `git diff --check`.
- [ ] Finalize Vietnamese report with actual checks and explicit R5-04/human-review status.
- [ ] Commit and push to the existing PR head; verify remote SHA and CI. Do not merge or fabricate acceptance.
