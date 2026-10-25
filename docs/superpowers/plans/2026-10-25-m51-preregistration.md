# M5.1 Preregistration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a verifiable R1 preregistration before remaining seed runs and TEST-172.

**Architecture:** A create-once structured record pins G2A and policy inputs. A read-only verifier checks its invariants; a concise Vietnamese README hands the plan to M5.2–M5.7 owners.

**Tech Stack:** Python standard library, JSON, unittest, Markdown.

**Spec:** `docs/superpowers/specs/2026-10-25-m51-preregistration-design.md`

## Global Constraints

- Do not read test/ViMDoc labels or execute training/evaluation.
- Preserve frozen M1.5 and M4.7 bytes.
- One M5.1 commit on `feature/m5-1-preregistration`.

## Review Focus

- Detect stale or tampered G2A freeze/confirmation hashes.
- Reject seed substitutions, missing matched methods or changed seed-specific parameters.
- Reject dropping any core item or changing the R7 once-only test boundary.
- Keep optional ablations diagnostic and validation-only.
- State that missing operational measurements restrict operational claims.

### Task 1: Record and verifier

**Files:** `scripts/preregister_m51.py`, `tests/test_m51_preregistration.py`, `evidence/revisions/m5.1-001/preregistration.json`.

- [x] Write tests for pinned inputs, matrix and drop-order invariants; observe failure first.
- [x] Implement a standalone create-once generator and read-only verifier.
- [x] Create the structured preregistration and verify its exact bytes.

### Task 2: Handoff and publication

**Files:** `evidence/revisions/m5.1-001/README.md` and optional owner confirmation if Thanh explicitly accepts.

- [x] Explain schedule, one-factor order, drop rule, claim limits and handoff in Vietnamese.
- [x] Run focused tests and verifier; review staged diff.
- [ ] Commit once, push the branch and prepare PR description.
