# M4.2 baseline freeze implementation plan

> **For agentic workers:** use superpowers:executing-plans inline. User requested
> execution and a final report before directing the next step.

**Goal:** produce a source-grounded, tested M4.2 baseline preparation and an
honest audit of what is still required to freeze real ViMDoc inputs.

**Architecture:** separate standard-library document baselines from historical
page baselines; bind M4.1 inputs and the new implementation in an immutable
revision manifest. Keep real execution readiness separate from software PASS.

**Tech Stack:** Python 3.13, unittest/pytest, JSON, SHA-256.

**Spec:** ../specs/2026-10-23-m42-baseline-freeze-design.md

## Global constraints

- M4.1 train/validation/confirmation counts: 1600/400/8904.
- Candidate cap 600, min-max epsilon 1e-15, RRF k=60, seven required baselines.
- Static 66-point simplex grid, denominator 10, document nDCG@10, tie 1e-12.
- Preserve historical bytes and keep confirmation access closed.
- No real cache, fitted weights or owner acceptance may be invented.

## Review focus

- Document versus page objective, IDCG including missing positives.
- Validation/confirmation contamination or label-bearing score columns.
- Constant channels, float overflow, deterministic ties.
- Byte-level split/policy drift and manifest omissions.
- Fixture success incorrectly reported as real scientific readiness.

## Task 1: document baseline reference

Files: src/qpaf/m42/__init__.py, baselines.py, tests/test_m42_baselines.py,
configs/m4.2/freeze.json.

- [x] Write hand-calculated document/RRF/normalization and train-only guard tests.
- [x] Run tests and observe missing implementation failure (12 failures).
- [x] Implement score_pages, document_ranking, document_ndcg_at_10,
  audit_train_inputs and fit_static_on_train without torch or remote imports.
- [x] Run focused tests. Expected: all pass (12/12 before review).

## Task 2: reproducible freeze, evidence and report

Files: scripts/freeze_m42_baselines.py, tests/test_m42_freeze.py,
evidence/revisions/m4.2-001/{README.md,manifest.json,verification.json},
Bao_cao_tien_do/M4_2_Khuong.md.

- [x] Write drift, missing-inventory, read-only and CLI overwrite tests; observe RED (7 failures).
- [x] Implement build_manifest/verify and a create-once CLI, checking M4.1 and G2.
- [x] Record primary internet sources and exact project decision provenance.
- [x] Generate revision; verify from disk. Expected: technical PASS, real-input
  readiness BLOCKED with explicit missing hashes.
- [x] Run focused and repository tests; record actual counts/failures.
- [x] Review complete diff independently; fix substantive findings and reverify.
- [x] Report artifacts, tests, sources and unresolved real-input requirements.

## Execution ledger

- Ruling: execute the requested existing milestone directly, using the current
  project protocol as the spec; user asked for completed work before further
  directions. No new research method is proposed.
- Ruling: the root checkout contains unrelated deletions; use ignored
  .worktrees/m4-2-baseline-freeze on feature/m4-2-baseline-freeze from develop.
- Baseline Anaconda Python 3.14 unittest run: 394 tests, 14 failures, 46 errors,
  40 skips, including missing torch. A separate Python 3.13 test environment is
  being prepared; this initial run is environment evidence, not a regression.
- Task 1 and Task 2 focused implementation: 19/19 tests passed before review.
- Final independent review: three Important findings, no Critical/Minor.
  All three reproduced RED, then fixed: scalar/unordered qrels; exact v1
  configuration pin; fixture source matching inventoried source. 22/22 tests
  passed after fixes. No deferred minors.
- Ruling: unavailable caches/GPU/scientific performance were outside the
  code review's evidence scope; keep real readiness BLOCKED and acceptance
  PENDING. Cost of treating them as passed would be an unsupported result.
- Ruling: preserve the historical M2.5 page implementation; use its grid with
  the M4.1 document objective in a new module. ViMDoc adoption remains pending
  reviewed real execution. A changed adopted grid would need a new revision.
- Broader ViMDoc/M4.1/M4.2 check: 49 passed, 5 historical preparation failures,
  37 subtests passed on Python 3.14. All five fail on old configs/datasets.yaml
  manifest drift; involved source/config/test/manifest bytes exactly match base.
- Final focused verification: 25/25 M4.1/M4.2 tests passed. Revision m4.2-001
  created once and replayed: 27 hash-bound files, exact IDs, technical PASS,
  real inputs BLOCKED, no owner acceptance or scientific metrics claimed.
- Full Python 3.13 pytest: 878 passed, 30 failed, 3 skipped, 303 subtests
  passed in 318s. Replayed every failing node in a clean base checkout under
  the SAME environment: 30 failed, 1 passed; same 29 unique failing nodes.
  Logs and base-comparison.json are in results/m4.2/verification.
- Full-suite classification: seven failures are missing huggingface_hub in
  this local environment; the other 23 concern historical hash/environment
  drift. Both classes reproduce on the clean base; full suite is NOT green.
- Ruling: keep this as reviewable preparation on the named local branch;
  no integration while full-suite baseline failures and real-input gaps remain.
  Cost of claiming completion otherwise would hide missing experiment evidence.
