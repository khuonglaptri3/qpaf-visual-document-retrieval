# M4.2 active-primary baseline completion plan

> **For agentic workers:** execute inline with superpowers:executing-plans.

**Goal:** complete Khương's workbook M4.2 shared baseline input/settings
deliverable using the approved ViDoSeek primary and an actual train-only fit.

**Architecture:** preserve m4.2-001 as historical ViMDoc preparation. Add a
separate active-primary runner that validates the exact M3.1/M2.8 expanded
bundle, calls the frozen M2.5 static fitter, and creates an immutable M4.2
run and revision. All seven baseline contracts bind the same input identity.

**Tech Stack:** Python 3.13, existing M2.4/M2.5 code, PyArrow, NumPy, JSON/SHA-256.

**Spec:** workbook Milestones row 49; approved A002 in
evidence/M1_FINAL/02_protocol/amendments_after_import.md; M2.5 method document
and freeze; approved expanded M2.8/M3.1 input manifest; confirmed G2 GO.

## Global constraints

- Active primary: Qiuchen-Wang/ViDoSeek, revision e91a92b..., page evaluation.
- Exact split counts 799/171/172; fit only the 799 train IDs.
- Reuse the EXPANSION-001 pool used by M3, cap 600, not the original cache pool.
- M2.5 static grid denominator 10, 66 simplex weights, frozen train nDCG/ties.
- RRF k=60, 1-based channel ranks on common rescored union, no label fitting.
- No validation baseline selection, test/ViMDoc confirmation label access,
  learned model training, GPU/cloud job, or changed historical acceptance.
- All seven baseline contracts share scores/candidates/splits/evaluator; bind
  the already accepted M3.2 QARF best checkpoint and M3.3 acceptance.
- Create-once attempts, retry count zero; real fitting follows source commit.

## Review focus

- A002 active primary versus future ViMDoc confirmation remain distinguished.
- Every fit record/qrel is train-only; test qrels are hashed but never parsed.
- Expanded candidate union, score order and normalized cache are exact.
- Fitted weight/objective replays with the frozen M2.5 implementation.
- Input/source tamper, alternate roots and incomplete roster fail closed.

## Task 1: implement and verify real-data runner

Files: src/qpaf/m42/active_primary.py,
scripts/run_m42_active_primary.py, tests/test_m42_active_primary.py,
configs/m4.2/active_primary.json.

- [x] Write RED tests for common-input audit, train-only fitting, immutable
  output and tamper rejection using hand-derived small fixtures.
- [x] Implement input audit, normalized-cache/candidate replay, fitting and
  read-only verification; reuse M2.5 fitting/evaluator unchanged.
- [x] Test GREEN, independently review, fix substantial findings, commit source.

## Task 2: execute and hand off

- [x] Recover 16 accepted inputs from the M3.1 worktree; all original hashes match.
- [x] Recover accepted QARF best.pt (11,512 bytes), exact receipt hash matches.
- [x] Record user's M4.2 instruction as one CPU calibration invocation.
- [x] Execute real train-only fit and create source/input/output manifests.
- [x] Verify selected weights/metrics and complete shared baseline contracts.
- [x] Write m4.2-002 evidence and corrected report with source citations.
- [x] Run relevant checks and repository suite; preserve unrelated failures.
- [x] Commit reviewable result and report actual weights, train objective,
  identity/coverage, tests and downstream claim limits to the user.

## Ledger

- Root cause: previous work incorrectly treated future ViMDoc extraction as a
  prerequisite for all M4.2 work. Approved A002 and the active M2.5/M2.7/M3.1
  contract already authorize the ViDoSeek baseline bundle. This is a scope
  correction, not a new dataset amendment. Independent scope review agreed.
- Ruling: complete the active-primary deliverable; retain the M4.1 ViMDoc
  baseline obligation as separately pending. Never claim the former satisfies
  ViMDoc confirmation readiness or a scientific generalization result.
- Ruling: user identifies themself as Khương and explicitly requests completion;
  this authorizes the existing train-only CPU baseline calibration. No separate
  cloud or learned optimizer invocation is needed.
- Independent code review: one Important alternate-root provenance finding;
  reproduced RED and fixed by restricting execution/replay to the executing
  checkout. Added a RED→GREEN top-list/raw-score consistency check. Fourteen
  active-primary tests and 45 combined M4.2/M2.5/M4.1 checks pass.
- Read-only real-data preflight before fitting: 551,764 shared candidate rows,
  1,142 queries, 2,075 expansion rows, maximum 579 candidates/query, exact
  normalization replay (max absolute difference 0.0). No labels read by audit.
- Actual run source commit 363db3f: 799 train queries / 386,390 candidates;
  selected weights [0.0,0.1,0.9], train nDCG@10 0.8642244283102866, coverage 1.0,
  zero uncovered queries. All seven baseline contracts bind one shared input hash.
- Ruling: calibration completed and persisted _SUCCESS, but the final CLI JSON
  print exited 1 because Windows default charmap cannot encode the owner's name.
  Preserve original attempt; verify with Python -X utf8, without a new fit attempt.
  This reporting issue and original exit code are retained in execution_receipt.
- Read-only selected-objective verification PASS. Independent NumPy audit of
  the same 66-grid selected identical weights, objective difference 3.33e-16.
  The immutable calibration outputs were not changed by verification.
- 45/45 related checks PASS. Full suite: 894 passed, 29 failed, 2 skipped,
  310 subtests passed. Replayed every failing node on clean base with same
  environment: same 28 failing nodes, 29 failures. Six failures are PDFium
  version mismatch; 23 are historical source/environment drift.
- Complete delivery ZIP: 31,333,271 bytes / 24 files including ignored payloads;
  CRC checked, SHA-256 in m4.2-002/delivery.json. No sealed test qrels included.
