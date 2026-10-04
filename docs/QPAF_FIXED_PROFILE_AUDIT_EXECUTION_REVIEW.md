# Fixed-profile discovery audit: execution review

**EXECUTION COMPLETE AND INDEPENDENTLY VERIFIED.** The user approved the reviewed scope on 2026-09-08. The single Codex CPU invocation completed in 561.485 seconds, and the independent review recomputed all seven profile metrics over all 6,149,670 pairs. See [the verified result](05_oracle_experiments/fixed_profile/QPAF_FIXED_PROFILE_AUDIT_RESULTS.md). The preparation-only text below is retained as the pre-execution contract.

## Purpose and scope

The completed exploratory-12 study had eleven Global ceiling cases and one improving query. This audit would measure the remaining theoretical headroom across all frozen discovery queries before committing to further page-specific search. See [the case study](QPAF_QUERY797_CASE_STUDY.md) and [the evaluation proposal](QPAF_NEXT_EVALUATION_PROPOSAL.md).

| Item | Prepared contract |
| --- | --- |
| Dataset | ViDoSeek discovery only: 1,142 queries, 5,385 pages/query, 6,149,670 pairs |
| Inputs | Existing P1-02R score bundle, candidate audit, extraction manifest and integrity review, all hash-pinned through the unchanged base protocol |
| Profiles | Exact existing W7 order; three single-channel profiles, three equal two-channel mixtures, one equal three-channel mixture |
| Global | One profile selected over the complete discovery population |
| QARF | One oracle profile per query, selected from the same seven profiles |
| Metrics | Existing nDCG@10, Recall@1, Recall@3 and MRR@10; no renormalization |
| Ties | Rank by descending score then ascending page ID; select profiles by nDCG@10, Recall@3, MRR@10 with existing 1e-12 tolerance; retain earliest profile on a tie |
| Resources | One local CPU worker, one thread per library, 1,800-second cap, one invocation, zero automatic retries |
| Arrow decoding | CPU and I/O pools explicitly limited to one; batch-to-pandas conversion and the full candidate-audit read disable threaded conversion |
| Input memory | Arrow batches of at most 5,385 rows; carry incomplete query rows across batches; evaluate one complete query at a time |
| Output directory | `runs/vidoseek_fixed_profile_audit_v1/`, which must not exist before the first authorized invocation |
| Explicit exclusions | QPAF coordinate search, W66, training, new extraction, Modal/GPU, ViDoRe access, and formal phase decisions |

The deterministic audit retains seed 20260820 as study metadata. It performs neither query sampling nor bootstrap resampling. It is not a multi-seed learned-model experiment.

## Implementation and verification

Final verification: **213 tests passed in 88.46 seconds**, including 31 focused audit tests. Ruff lint/format checks passed. The source-pinned read-only preflight passed for all 1,142 queries / 6,149,670 rows with `actual_relevance_loaded=false`, `execution_authorized=false`, and `attempt_exists=false`. All 43 original-run and 78 recovery-run artifact hashes still match, as do the original report and chart. The live CLI's closed-approval refusal was also checked without creating an attempt.

- [Runner](../scripts/audit_vidoseek_fixed_profiles.py): reuses the unchanged metric/profile/tie-break primitives; it never calls a QPAF or full-oracle runner.
- [Focused tests](../tests/test_vidoseek_fixed_profile_audit.py): synthetic equivalence to frozen Global/QARF selection, independent single-positive metric values, graded relevance, ties, row permutation, split row groups, corruption/coverage refusal, closed approval, actor/thread guards, consumed attempts, timeouts and preserved inputs.
- [Preparation verification receipt](../artifacts/vidoseek_fixed_profile_audit_preparation/verification_receipt.json): final test results, lint/format checks, exact source/config/test hashes and evidence-preservation checks.
- [Read-only preflight](../artifacts/vidoseek_fixed_profile_audit_preparation/preflight.json): input hash/metadata/provenance verification and ID-only query-order validation. It reads no relevance values, calculates no retrieval metrics and consumes no attempt.

No existing scientific source, score file, checkpoint, old approval config or old result report is edited. The new script is under `scripts/` so the frozen `src/oracle_study/` inventory stays intact. No dependency was added. The current working tree contains local, uncommitted changes; HEAD alone does not reproduce this prepared state. The runtime will snapshot every pinned source file and the tracked diff.

Prepared byte SHA-256 pins (closed state):

| File | SHA-256 |
| --- | --- |
| `configs/vidoseek_fixed_profile_audit_v1.json` | `53f59852512cc28c2ab5f03233db3cde6a68549691086532275af4c1ee6b7e27` |
| `scripts/audit_vidoseek_fixed_profiles.py` | `2eebbb6db9853eacedcfe143d5cac6910e116e6c469ed64d9cf0cbaab52b1e6f` |
| `tests/test_vidoseek_fixed_profile_audit.py` | `43cfd69845c07be51f83a33e1662a0e9279cd01075df2ce1b5825f888dd81fb3` |

Base HEAD: `99823b96c9afd52e11e7ddb001f5b74bf0a1e314`. Input score SHA-256: `32b39da19e9507a0a5060157630cb40bf5c6bcf6464d88e4bb6136888473173b`. The full 1,142-query ID-order SHA-256 from ID-only preflight is `a59da8a89b9bc0ffcb4f4588c96c3a5a5256c9df95a3a707cbd5e98eb1944535`.

## Outputs and interpretation

Each query gets an immutable, config-bound checkpoint with its ID, source category, input-content hash, page/relevance counts, all seven profile metrics, selected QARF profile and profile-evaluation time. Checkpoints preserve partial work for inspection; there is no automatic resume or retry command.

After all 1,142 queries pass validation, the audit creates:

- `per_query.json`: every query's profile metrics, shared Global metrics, QARF metrics and remaining gain bound.
- `summary.json`: shared Global/profile/channel means, QARF mean, ceiling counts/fractions, source counts, mean bound and review advice.
- `preflight.json`, `resolved_config.json`, `source_snapshot/`, `tracked_changes.patch`, `_ATTEMPTED.json`, `_WORKER_COMPLETE.json`, and the final `run_manifest.json` with artifact hashes, input references, environment, actor, elapsed time and closed downstream boundaries.

For each query, the maximum possible QPAF improvement is bounded by `1 - nDCG@10(QARF)`. The mean of these quantities is reported as **an upper bound, not measured QPAF gain**. Ceiling counts use a 1e-12 tolerance. A bound below 0.03 yields `TARGET_UNATTAINABLE_REVIEW_DIRECTION`; otherwise it yields `HEADROOM_POSSIBLE_REVIEW_COMPUTE`. Neither label authorizes another experiment.

The fixed discovery population is fully enumerated, so no query-sampling confidence interval is added to this descriptive bound. Generalization beyond it remains untested. Global is selected on the same discovery labels, so it must remain labeled as oracle selection. Its scope differs from the earlier 12-query Global.

## Failure and completion rules

Approval and source/scope checks precede input-label access. Creation of the new output directory and `_ATTEMPTED.json` consumes the sole invocation before worker preflight. Any existing output directory rejects another run, even if it is empty or the preceding attempt failed.

The parent enforces the remaining 1,800-second deadline around the spawned worker; elapsed timing begins on entry to `run`, including preparation and finalization. Python imports before function entry are outside that timer. Termination/kill cleanup may add up to ten seconds. The cap is a budget, not a measured completion-time estimate.

Timeout, worker failure, hash drift, wrong query order, missing/duplicate pages, candidate-corpus mismatch, nonfinite/out-of-range scores, uncovered relevance, candidate-audit disagreement or incomplete checkpoint coverage stops the attempt. A handled failure writes `_INCOMPLETE.json` with zero remaining invocations; hard termination may leave only partial evidence. A summary or worker marker alone is not proof of successful completion.

Only a `run_manifest.json` with `status=COMPLETE`, followed by independent artifact/hash/selection/metric review, permits reporting the audit. Any incomplete aggregate remains unusable. Original attempts are never reset or modified.

## Exact commands

Run from the repository root with the pinned Python 3.13.7 environment (NumPy 2.4.4, pandas 3.0.2, PyArrow 24.0.0, PyYAML 6.0.3). On this machine the interpreter is `C:\Python313\python.exe`. CMD preparation:

```bat
set "PYTHONPATH=src"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "NUMEXPR_NUM_THREADS=1"
```

Read-only command, already checked during preparation:

```bat
C:\Python313\python.exe scripts\audit_vidoseek_fixed_profiles.py preflight
```

**Future execution command, not run and currently refused by the closed config:**

```bat
C:\Python313\python.exe scripts\audit_vidoseek_fixed_profiles.py run --actor codex
```

The user does not need to edit the config or run these commands manually. After explicit approval of this reviewed scope, Codex can record the actual approval and hashes separately, update only the new authorization block, recheck the prepared pins, and launch once. Any source/scope/resource drift requires renewed review before launch. Future execution authorization does not include a retry.

## Proposed approval text

“Approve the prepared fixed-profile discovery audit: all 1,142 ViDoSeek queries and 5,385 pages/query, seven fixed W7 profiles, one Codex local CPU invocation with one worker/thread, a 1,800-second cap, no automatic retries, followed by independent result verification and reporting. Do not run QPAF coordinate search, W66, training, Modal/GPU, or change frozen P1-02/P1-03 and formal phase gates.”

This was the historical proposed approval text. The actual approval is recorded in `runs/fixed_profile_audit_preparation_20260908/execution_approval.json`; the one invocation is complete and consumed. The requirement for any later execution amendment remains in [Tasks.md](../Tasks.md), P1-02R-O1 STOP/KILL CONDITION: “Every later execution step requires a separate explicit human-approved amendment.”
