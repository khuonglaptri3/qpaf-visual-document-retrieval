# M5.5 CPU Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Execute the preregistered CPU part of M5.5 and leave an honest, reproducible GPU handoff.

**Architecture:** Add `qpaf.m55` beside the frozen M4.4 loader/evaluator. Authenticate fixed inputs and a CPU-only authorization, produce create-once artifacts, then verify them read-only. Keep resource measurement deferred.

**Tech Stack:** Python 3.11+, existing NumPy/pandas/PyArrow, unittest, existing matplotlib for supporting plots.

**Spec:** `docs/superpowers/specs/2026-10-27-m55-cpu-diagnostics-design.md`.

## Global Constraints

- No Modal request, GPU call, training, retriever rerun, test-label access or ViMDoc access.
- Validation only: 171 queries, 82,255 candidates, exact M4.2 cache and frozen evaluator.
- Eight fixed rows and their order/weights from the spec; no parameter fitting or baseline reselection.
- Z-score uses population standard deviation (`ddof=0`), zero-variance channel -> 0, negative scores retained.
- Preserve old evidence/source/checkpoint bytes; no overwrite/retry of a result namespace.
- R5-04 is `NOT_RUN_DEFERRED_MODAL_NETWORK_BLOCKED`; M5.5 is partial pending resource work/review.
- Record the user's CPU authorization faithfully; do not fabricate a Research Lead or reviewer signature.

## Review Focus

- A saved normalized cache with reordered/missing keys must be refused before metrics.
- New data carrying a test query in development qrels must be refused.
- A different source/config/authorization pin must never create a successful result.
- An existing output or failed attempt must never be overwritten by run or verify.
- A recipient with only 171 validation IDs must not be told that repetitions meet 1,000 distinct queries.

## Task 1: Reproducible CPU diagnostic executor

**Files:** Create `src/qpaf/m55/__init__.py`, `src/qpaf/m55/diagnostics.py`, `src/qpaf/m55/runner.py`, `scripts/run_m55_diagnostics.py`, `tests/test_m55_diagnostics.py`.

**Interfaces:**
- Consumes: frozen `qpaf.m44.common.load_context(root)`, `qpaf.m24.evaluator.evaluate/rank`, the saved normalized cache, M5.1/G2A/M5.2 authority records.
- Produces: `normalize_scores(raw_scores, method)`, fixed row scoring and `compute_diagnostics(records, saved_minmax)`; `execute(root, authorization, expected_sha256, run_id)`, `verify(root, output, expected_manifest_sha256)`, local `restore_inputs(root, archive)`; CLI subcommands `restore-inputs`, `run`, `verify`.

- [x] Write meaningful tests first: hand-derived min-max/z-score values; constant channels; negative scores; fixed drop-channel weights; label-independent scoring; malformed/nonfinite/misaligned rows; tie ordering and missing-positive denominator; reference parity; create-once run; tamper refusal; read-only replay; no network/GPU boundary.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_m55_diagnostics.py -v`.
  Expected: missing implementation fails before implementation is added.
- [x] Implement the smallest pipeline satisfying the spec, including authority/input/source validation and honest deferred-system status.
- [x] Run the focused tests and `.venv/bin/python -m unittest discover -s tests -q`.
  Expected: all software tests pass, historical skips reported, no live services called.
- [x] Commit only the implementation/tests and plan/spec/research records; record the source commit for authorization.

## Task 2: Authorized real-data run, report and cross-machine handoff

**Files:** Create `evidence/revisions/m5.5-001/authorization.json`, successor governance events and README; `results/m5.5/<run-id>/`; `Bao_cao_tien_do/M5_5_Khuong.md`; `docs/06_handover/m5.5-cpu-results-and-gpu-handoff.md`; update the documentation index.

**Interfaces:**
- Consumes: Task 1 CLI, exact downloaded M4.2 archive, pinned implementation commit and current user's CPU-only instruction.
- Produces: a manifest-bound real run, read-only verification, Vietnamese interpretation, supporting chart and a deferred R5-04 checklist.

- [x] Create and commit the explicit user CPU-only authorization with exact hashes/runtime/run ID and no cloud permission.
- [x] Execute `scripts/run_m55_diagnostics.py run` with its external authorization SHA-256.
  Expected: all eight rows cover 171 queries/82,255 candidates, the four reference rows match at `1e-12`, CPU technical success and overall partial/deferred status.
- [x] Execute `scripts/run_m55_diagnostics.py verify` with the printed manifest SHA-256.
  Expected: artifacts and replay match; all run bytes unchanged.
- [x] Write research interpretation and complete a handoff listing inputs, source/runtime, exact receiver commands and the unresolved counting/scope decision (base policy measured queries versus M3.6 distinct IDs). Include M3.6 only as historical context.
- [x] Independently verify hashes/access flags and unchanged frozen inputs/source; run `git diff --check`.
  Expected: PASS, no fabricated resource numbers, no old evidence changes.
- [x] Obtain one fresh whole-branch engineering review, fix material findings, and commit the results/report.
- [x] Keep work on `feature/m5-5-diagnostics`; do not merge the incomplete full milestone into develop.
