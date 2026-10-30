# F3 Objective Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute this existing experiment protocol task-by-task. Steps use checkbox syntax.

**Goal:** Run the existing F3 experiments and report measured results and missing inputs.
**Architecture:** Use the branch's unchanged CPU harness in a managed worktree; keep task evidence together.
**Tech Stack:** Python 3.11, torch 2.7.1 CPU, numpy 2.2.6, pandas 2.2.3, pyarrow 20.0.0.
**Spec:** [spec.md](spec.md)

## Global Constraints

- Existing F3 protocol only, 5 folds / 40 epochs / seed 20260820.
- No test or confirmation labels, cloud compute, hyperparameter sweep, harness changes, or remote writes.
- Read-only listing/downloading existing Modal cache through the configured account is allowed.
- All logs, JSON and validation under ../evidence/.
- A missing dataset remains explicitly incomplete.

## Review Focus

1. Input cache SHA-256 must equal the committed baseline.
2. Exactly 970 ViDoSeek / 2,000 ViMDoc dev IDs; no sealed labels.
3. Full results must not be smoke runs and must record a clean source commit.
4. Paired comparisons must share the exact query set and method.
5. LSE applies only to ViMDoc and is compared against the matching learned baseline.

## Task 1: Prepare and verify environment and inputs

**Files:** Create ../evidence/environment.json, input-validation.json, unit-tests.log; reuse existing source and tests.
**Interfaces:** Produce a verified Python executable and eligible dataset directories for Task 2.

- [ ] Create canonical spec/plan, provenance and local branch at pinned source; commit preparation.
- [ ] Diagnose existing broken torch import (torch_cpu.dll absent); create task-local environment with pinned CPU packages.
- [ ] Recover only required cached ViDoSeek score file and compare input hashes to committed baseline; locate ViMDoc cache.
- [ ] Run existing tests.test_lab and tests.test_lab_f3. Expected: no failure.
- [ ] Run both eligible loss variants with --limit 120 --epochs 2 --folds 2. Expected: finite results and smoke=true.

## Task 2: Full runs on eligible datasets

### Performance prerequisite (added after measuring the original implementation)

- [ ] RED: add output/gradient equivalence against the original dense formula, padding/multi-positive/invalid-query
  cases, and an intermediate-size resource bound that the old all-pairs formula fails.
- [ ] GREEN: compute only positive-unit ranks and scatter their DCG gains per query.
- [ ] Run selected tests and full unittest discovery; retain named failures and resolve environment gaps.
- [ ] Commit source/tests before real runs; rerun both smokes and compare with archived original 6-thread smoke.
- [ ] Reuse the completed baseline only if shared harness/baseline source and input hashes are identical.
- [ ] Preserve interrupted dense attempts separately; no incomplete metrics enter results.

**Files:** Create ../evidence/results/<dataset>-<variant>.json and execution logs.
**Interfaces:** Consume Task 1 inputs; produce full per-query scores for Task 3.

- [ ] Run baseline with unchanged default recipe. Expected: hashes equal reference and means within 5e-5; stop full variants for a mismatched dataset.
- [ ] Run f3_approxndcg and f3_topk_hard for ViDoSeek; repeat on ViMDoc if eligible, plus f3_lse_pool there.
- [ ] Verify full records, IDs, folds, recipe, finite scores, source_commit and tracked_changes.
- [ ] Preserve missing-input findings for any ineligible dataset.

## Task 3: Analyze and verify handoff

**Files:** Finalize ../README.md, ../evidence/workflow.md, comparisons.json, hashes.json and validation.json.
**Interfaces:** Consume Task 2 per-query JSON; produce a reproducible report.

- [ ] Recompute means and paired bootstrap comparisons against baseline; leave verdict n/a.
- [ ] Fresh review of evidence and report against spec; use requesting-code-review per executing-plans.
- [ ] Verify layout, local links, report index, hashes and git diff --check.
- [ ] Commit final local artifacts and report what ran, results and remaining work.

## Self-review

Existing design is reused by link; no new feature implementation is planned, so existing tests are verification,
not a retroactive RED→GREEN claim. Input validation gates all full runs. User explicitly requested immediate execution;
continue without asking again for routine execution decisions.
