# M1.1 Modal Oracle implementation plan

> **For agentic workers:** Use superpowers:executing-plans for inline implementation
> and a fresh final review. Track completion here and in the verification report.

**Goal:** A configurable, reproducible ViDoSeek Oracle pipeline running on Modal.

**Architecture:** Pure CPU metric/config/data contracts are separate from optional
model extraction and Modal orchestration. Stage receipts bind payloads to source,
config and input hashes. Existing reference results remain immutable.

**Tech Stack:** Python >=3.11, TOML, NumPy, Hugging Face, PDFium/Tesseract, PyTorch,
SentenceTransformers, ColPali Engine and Modal.

**Spec:** docs/superpowers/specs/2026-09-26-m11-modal-oracle-design.md

## Continuation checkpoint — 2026-09-26

Implementation and local verification are recorded in the
[follow-up report](../../../results/m1.1/implementation-check/2026-09-26-followup/README.md).
The final suite ran 44 tests (43 passed, one Windows symlink privilege skip).
All 29 M1.1 tests passed, as did a persisted synthetic fixture through the local
evaluator CLI, SDK construction, compile, dependency and diff checks. Follow-up
regressions caught missing export metadata and temporary Windows access denial
during atomic JSON replacement; both are fixed with retained before/after logs.

Initial implementation red-phase observations below have no retained evidence in
this continuation and remain unchecked. Independent review and the real Modal
run remain outstanding; software checks do not close M1.1 research acceptance.

## Global constraints

- Runtime/model/dataset/path choices live in configuration; secrets stay external.
- All PDF pages are candidates before label-free top-K selection.
- Only binary qrels are supported by the exact per-page Oracle.
- Existing historical reports and snapshots are preserved.
- Local tests cannot close the real-run or independent human QA requirements.

## Review focus

- Wrong page numbering or truncated candidate IDCG inflates metrics.
- Stale, incomplete, reordered or corrupted score caches must fail validation.
- Per-page Oracle is not a learned result; W7/W66 equality is expected here.
- Modal decorators must use the chosen config rather than defaults at import time.
- Exceptions must persist diagnostics and never publish a success receipt.

## Task 1 — Config, metric and Oracle contracts

- [ ] Add real failing tests: hand nDCG with relevant pages outside the pool;
  exhaustive binary Oracle; deterministic ties; W7/W66 equality; paired bootstrap;
  TOML overrides and invalid runtime/resource values.
- [ ] Run `python -m unittest discover -s tests -p test_m11_core.py -v` and observe
  missing implementation failures.
- [x] Implement `config.py`, `metrics.py`, `oracle.py` in `src/qpaf/m11/`.
  Interfaces: `load_config(path, overrides) -> dict`, `evaluate(scores, query_ids,
  page_ids, qrels, config) -> (rows, summary, selections)`.
- [x] Run the same tests, then the existing suite.

## Task 2 — Artifact and dataset contracts

- [ ] Test original `examples` JSON with literal one-based page mappings, duplicate
  and missing labels, malicious ZIP paths, and atomic/immutable stage output.
- [x] Implement `artifacts.py`, `dataset.py`: `prepare(config, output, logger)`;
  `StageRun(root, stage, config, inputs, source)` context manager records receipts
  only on success. Invalid input fails before any scorers consume it.
- [x] Test corruption detection and error logs against actual temporary files.

## Task 3 — Scoring and run outputs

- [x] Test real BM25 ordering and fixture score-cache import through the evaluator.
- [x] Implement `retrieval.py`, `pipeline.py`: `execute_stage(stage, config,
  workspace, run_id, source)` with prepare/BM25/dense/visual/oracle stages;
  lazy model imports, pinned revisions, complete score matrix and ID metadata.
- [x] Produce all required M1.1 reports from a synthetic integration fixture and
  verify their hashes. Label this software verification only.

## Task 4 — Modal and documentation

- [x] Test `--dry-run` with changed GPU/volume/paths; no Modal auth is needed.
- [x] Implement dynamic Modal launcher, config preset, pinned requirements and
  local cached-score evaluator. Add a stage selection flag and evidence fetch.
- [x] Document install/auth/run/resume/download and the research comparison limits.
- [x] Verify the Modal SDK can construct the App without starting paid compute.
- [x] Run the complete test suite, compile checks and diff checks. Save actual logs.
- [ ] Obtain final independent code review; fix material findings and retest.
- [x] Report real-run/human-QA status separately from software readiness.
