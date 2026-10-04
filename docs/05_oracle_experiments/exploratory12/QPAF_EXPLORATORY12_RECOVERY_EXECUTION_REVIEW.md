# Exploratory-12 recovery execution review

Execution update (2026-09-07): the user approved the exact prepared scope with "OK now continue". Codex launched the one permitted recovery invocation at 10:02 UTC. See [the current run status](QPAF_EXPLORATORY12_RECOVERY_RUN_STATUS.md). The preparation/closed statements below are the historical pre-approval review, whose hash is retained in the approval record.

Prepared 2026-09-07. **Recovery implementation and focused tests complete; live execution disabled.** No recovery output directory or attempt exists. The original experiment remains incomplete at four of twelve query results.

## Prepared changes and verification

- [Recovery launcher](../../../scripts/recover_vidoseek_exploratory12.py): validates the pinned interruption audit and exact original inventory; copies evidence into a new directory; reuses the original checkpoint science identity; runs the unchanged worker under a separately approved attempt marker and deadline.
- [Closed configuration](../../../configs/vidoseek_exploratory12_recovery_v1.json): both approval flags are false; actor, approver, text, and timestamp are unset. Original config/source/approval snapshots remain unchanged.
- [Recovery tests](../../../tests/test_exploratory12_recovery.py): verify exact equivalence to an uninterrupted synthetic run, no recomputation of inherited work, parent preservation, manifest hashes, corruption/drift refusal, actor/thread guards, timeout, incomplete outputs, and no retry.
- [Original pilot tests](../../../tests/test_vidoseek_exploratory12.py): lifecycle checks now reflect its consumed approval; the draft refusal test closes its own in-memory fixture. No original scientific code changed.

Focused tests: `24 passed in 24.13s`. Ruff lint/format passed. The read-only recovery preflight returned `PASS`: four inherited and eight missing query checkpoints; pinned 6,149,670-row score bundle, 1,142-query audit, 5,385 pages/query, coverage 1.0. It loaded no relevance labels or oracle search. See [the verification receipt](../../../runs/exploratory12_recovery_preparation_20260907/verification_receipt.json) for full-suite and final boundary checks.

The launcher lives in `scripts/`, preserving the pinned `src/oracle_study/` source inventory. No new dependency is required.

## Exact proposed scope

| Item | Recovery contract |
| --- | --- |
| Original run | `runs/vidoseek_w7_exploratory12_v1/`; preserve every byte |
| New run | `runs/vidoseek_exploratory12_recovery_v1/`; must not already exist |
| Reused | All 12 Global checkpoints, shared Global selection, four query checkpoints at positions 0–3 |
| Computed | Only positions 4–11: audit indices 792, 797, 848, 880, 881, 940, 1023, 1081 |
| Candidate pool | All 5,385 pages per query; same 12 frozen queries |
| Science | Original W7 profiles, two-sweep search, metrics, tie-breaks, seed 20260820, and 10,000-resample bootstrap |
| Actor | Codex, after new approval |
| CPU | One local worker; OMP/MKL/OpenBLAS/NumExpr each limited to one thread |
| New time budget | Additional 21,600 seconds (six hours), requiring separate approval |
| Attempts | One recovery invocation, zero automatic retries; any existing recovery directory blocks another attempt |
| Completion | All 12 results, complete manifest, then independent verification and comparison report |

The deadline starts on entering the recovery run function and includes validation, copying, worker startup/preflight/search, and finalization. Interpreter imports occur before the timer; timeout cleanup may take a short additional interval. Six hours is a cap, not a runtime prediction, and does not reuse or reset the original allowance.

`timings.json` measures this recovery invocation. `recovery_timings.json` explicitly labels inherited checkpoint validation versus new query computation. Original search durations are null because the original in-memory timing list was not finalized; its progress log/timestamps remain available as separate evidence. Reading a reused checkpoint must not be presented as the original search duration.

## Provenance

- Git base: `99823b96c9afd52e11e7ddb001f5b74bf0a1e314`. The prepared implementation and local payload remain uncommitted; a fresh checkout of that commit alone does not reproduce this prepared state.
- Closed recovery config byte SHA-256: `4cc5a2a7075df16cc607bdcf5f3f9850805991c90e621e2134dce15133e1c1c5`.
- Runner SHA-256: `6adb19f82ebb1037bcabc5bfd1174e95fe6c4728320febe0097cda5b88f49c09`.
- Pinned interruption audit SHA-256: `e69f464ed2f9d2a53c2707a30d68338c6e589c98c78cebb20780ae486149fc5f`.
- Inherited checkpoint identity SHA-256: `1b4e382fc32114aff97e1123c6a390a29037ab2a071d42aa419011c2897193a9`.

The new run copies the entire verified original run into `parent_snapshot/` and separately captures the recovery runner, audit, and approved recovery config. The new manifest binds its own authorization/config to the unchanged parent checkpoint science identity. Inherited checkpoints retain their real original hashes. Parent files are copied, never moved or hard-linked.

## Commands and human decision

The user does not need to edit files, copy checkpoints, or run terminal commands. Codex can record the actual approval, verify pins, launch once with CPU limits, and review the output.

Read-only preflight in Command Prompt:

```bat
set "PYTHONPATH=src"
C:\Python313\python.exe scripts\recover_vidoseek_exploratory12.py preflight
```

Future execution **only after separate approval is recorded**:

```bat
set "PYTHONPATH=src"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "NUMEXPR_NUM_THREADS=1"
C:\Python313\python.exe scripts\recover_vidoseek_exploratory12.py run --actor codex
```

Record actual user approval text, timestamp, approver, and actor in the separate recovery config, opening only its recovery-adoption and execution flags. Record both the reviewed closed-config hash and resulting approved-config hash in launch evidence. Leave the original pilot config unchanged. The current run command refuses before validation or output creation.

Proposed approval wording (not evidence of approval):

> Approve one Codex recovery invocation using the prepared launcher: reuse the four verified query results, compute the remaining eight, preserve the original run, use one CPU worker/thread with an additional six-hour cap and no automatic retry, then verify all twelve results and produce the comparison report.

The reason for this decision is the existing `Tasks.md` amendment: original invocation **once, with no retry**. Its immutable attempt marker records zero remaining invocations. Preparation does not reopen it.

## Completion and failure review

Handled failure/timeout records `_INCOMPLETE.json`; hard process/machine termination may leave no failure receipt. Without a complete manifest there is no completed comparison. Preserve all evidence and do not retry automatically. Check process identity/start time and checkpoint count rather than PID alone.

After completion, independently verify all 12 IDs, candidate counts, saved ranking metrics, bootstrap, inventory hashes, consumed recovery marker, parent lineage, inherited checkpoint equality, and exploratory-only decision marker. Adapt the existing original-run review to the recovery manifest's separate identities and labeled timings; it must not be used unchanged. Then produce the complete Global/QARF/QPAF comparison and chart.

Full W7/W66, formal Phase 1 decisions, P1-03, training, Modal/GPU, and frozen P1-02 remain outside this recovery. Outputs are exploratory oracle upper bounds, not learned/deployable performance.
