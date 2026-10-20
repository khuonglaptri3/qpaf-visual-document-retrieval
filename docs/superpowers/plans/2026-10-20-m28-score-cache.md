# M2.8 Real Score Cache Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the GPU orchestration;
> independent bundle implementation may be delegated under dispatching-parallel-agents.

**Goal:** Produce and verify a real, shared ViDoSeek retrieval cache using Modal GPU.
**Architecture:** Pinned preflight -> durable GPU encoding/scoring -> label-free
candidate freeze -> separate qrels/coverage -> verified M2.4/M2.5 handover.
**Tech Stack:** Python 3.11, Modal 1.5.5, pinned M2.2 CUDA stack, NumPy, Parquet.
**Spec:** docs/superpowers/specs/2026-10-20-m28-score-cache-design.md

## Global Constraints

Keep frozen dataset/split/model/OCR identities, top-200/channel and <=600 union.
CUDA inference and scoring; no CPU fallback or synthetic research result.
Keep labels out of candidate construction; raw trainer cache has exactly 5 columns.
Keep M2.7 evidence unchanged; use new result/revision paths and exact hashes.

## Review Focus

- Missing/nonfinite channel scores must fail, never be filled with zero.
- Resume must reject stale/corrupt/source-mismatched shards.
- Candidate freeze must predate qrels access; retain uncovered queries.
- All empty-text/failure-fallback pages must remain visual candidates.
- Collection and verification must detect incomplete cloud runs/artifact tampering.

## Tasks

- [x] 1. Write failing tests for candidate freeze, normalization and coverage;
  implement `m28/bundle.py`, pass tests and M2.4/M2.5 raw-row compatibility.
- [x] 2. Write failing tests for verified preflight and durable shard handling;
  implement config/preflight/worker/CLI with deterministic source/config binding.
- [x] 3. Run targeted checks, then launch real A10 execution, monitor and collect
  complete raw scores/embedding indexes/resource and GPU evidence.
- [x] 4. Build/freeze candidates, then audit coverage/export qrels; replay all
  schemas/hashes/numerics independently and publish append-only evidence.
- [x] 5. Remove confirmed OCR HTML exports with exact deletion inventory.
- [x] 6. Review final diff, run required regression checks, report measured
  outcomes and any genuine coverage/operational limitation.

## Execution ledger

- Preflight baseline: local `.venv` PyTorch import fails with existing WinError126
  (`shm.dll`). Use the functioning base Python for cache/Parquet tests and verify
  Torch-dependent checks in the pinned cloud CUDA runtime. Do not modify M2.7.
- User already authorized execution of the concrete M2.8 scope in conversation;
  no merge/push/publication to GitHub is part of this request.
- Task 1/2: 29 targeted M2.8 tests pass; compileall and diff --check pass. Bundle
  implementation was delegated independently; fresh review found four closure
  issues (query/split binding, collected checksums, latest resume tracking,
  read-only verify), each reproduced RED and fixed GREEN. Reviewer confirmed
  all four resolved with four focused CLI regression tests.
- Task 3 complete: real run `RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01`,
  Modal app `ap-HNWFiUPRZS12OoWYOBr138`, call
  `fc-01M5CWA5A503AXSS1NKZNP0G4Q`, output Volume `qpaf-m28-score-cache`.
  Actual GPU NVIDIA A10, CUDA12.6, PyTorch2.7.1+cu126. All three stages PASS;
  worker completed2026-10-20T16:15:49.671479Z, wall5490.35s. Collected and
  checksummed281 files/251435113bytes;129 embedding receipts cover all pages
  and queries. GPU encoding/scoring used no relevance labels.
- Ruling: preserve the exact launched GPU source before fixing CLI-only closure
  defects. Snapshot `source_snapshot.zip` contains all151 original source files,
  SHA256 `b085a150a8161e0fd725cf1d5b876747c3912ba9d8f2ef9928290d95bc8b91d7`.
  Finalizer identity is recorded separately in handover; GPU worker unchanged.
- Task5 complete: user clarified deletion belongs to results/m2.3, not M2.4.
  Deleted10 HTML exports, kept both source/evidence templates, logged every
  path/size/SHA256 in results/m2.8/verification/ocr-review-html-removal.json.
- A local terminal-result deserialization error exposed the existing Windows
  Torch DLL failure through a TorchVersion return value. GPU JSON artifacts
  were complete and unaffected. Added a narrow, identity/freshness-checked
  JSON fallback for status/resume;5 regression tests reproduced RED then GREEN,
  all34 M2.8 tests pass, fresh review passes, actual status now returns COMPLETE.
  No additional GPU invocation or scientific worker edit was needed.
- Task 4 complete: 549,689 candidates and 685,200 top-list rows frozen at
  2026-10-20T16:21:49.185938Z, before relevance mapping/coverage construction.

- Final result: GPU COMPLETE / CACHE VERIFIED / BLOCKED_COVERAGE. Macro recall
  0.999124343257443, one uncovered TRAIN query; validation/test coverage 1.0.
  Positive ranks 271/273/769 are outside all frozen top-200 lists. Independent
  full artifact replay confirms a legitimate retriever miss, not corruption.
- Read-only full closure replay PASS, 16 bundle files unchanged; M2.4 portable
  split loader PASS. Cloud closure upload/readback PASS for 32 files and
  31,921,646 bytes, plus its separately read-back receipt. No overwrite used.
- Published immutable evidence/revisions/m2.8-001 and the measured report.
  All implementation/execution/diagnostic/report tasks in this plan are closed;
  M2.8's scientific acceptance remains BLOCKED. Named human M2.10/D1 review and
  a documented amendment/new run are needed before changing the frozen policy.
