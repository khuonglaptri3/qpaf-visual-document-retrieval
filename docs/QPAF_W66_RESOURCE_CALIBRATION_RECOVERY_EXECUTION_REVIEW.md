# W66 synthetic resource calibration recovery: preparation and execution review

**PREPARED; EXECUTION CLOSED.** The prior `vidoseek_w66_resource_calibration_v1` invocation is consumed and produced no calibration or W66 result. This separate protocol prepares one fresh engineering calibration in a new output namespace. It does not reuse or modify the partial run, authorize the 24-query W66 study, or change the blocked P1-02/P1-03 boundary.

## Why this recovery is materially different

The interrupted implementation rebuilt identical ranking state for each of 65 alternative profiles for every candidate. `candidate_oracle_exact_fast` computes that candidate-invariant state once while preserving the same fixed candidate order, profile order, strict `1e-12` improvement threshold, two-sweep limit, ascending-page-ID tie break, accepted-update sequence, and exact serialized result fields.

Exact-equality tests cover W7 and W66, random sizes and seeds, score/page-ID ties, zero relevance, and a bounded larger W66 fixture. A separate 512-page, one-thread benchmark produced exactly equal assignments, scores, metrics and accepted-update count: 53.405 seconds for the frozen implementation and 1.471 seconds for the optimized implementation (36.296x). Quadratic page-count scaling gives a conditional 162.764-second core-search illustration at 5,385 pages; it is not measured full-page timing or a completion guarantee. The proposed 3,600-second cap is a cost ceiling with about 22.1x margin over that illustration and also covers input loading, Global evaluation, checkpointing, replay, bootstrap, supervision and finalization.

## Frozen recovery contract

| Item | Prepared contract |
| --- | --- |
| Prior output | Read-only provenance only; no file or checkpoint is reused or modified |
| Input | Same 24-query, 129,240-row non-label projection; selected 5,385-page query at audit index 1129 |
| Synthetic label | Sort page IDs ascending; relevance 1 at zero-based index 2692, otherwise 0 |
| Search | Fresh one-query W66 Global pass plus exact-output optimized QPAF candidate search, at most two sweeps |
| Bootstrap | Existing mean and ratio functions, fixed 24-element synthetic input, 10,000 resamples, seed 20260820 |
| CPU | Local CPU, one worker, one numeric thread, Arrow CPU/I/O pools each fixed and checked at 1 |
| Cost cap | Proposed 3,600 seconds; not a completion guarantee |
| Memory | Parent-plus-worker private bytes at most 2 GiB; abort below 2 GiB host-free memory |
| Admission | At least 4 GiB free physical memory, 5 GiB free disk, and absent recovery namespace |
| Telemetry | One-second target; automatically abort when wall or monotonic gap exceeds 5 seconds |
| Output | At most 100 MiB in `runs/vidoseek_w66_resource_calibration_recovery_v1/` |
| Attempts | Currently zero; if separately approved, exactly one invocation and zero retries |

The worker still loads the real score bundle through an explicit projection that excludes `relevance`, validates all 129,240 rows, and creates the deterministic synthetic label only after validation. Fresh run-plan, Global, Global-selection and optimized query checkpoints are hash-sealed and replayed without search. They remain ineligible for a scientific W66 run.

The telemetry guard now checks both UTC wall-clock and monotonic intervals. The sample that exposes a gap is flushed before the guard raises, after which the parent terminates the worker and writes `_INCOMPLETE.json`. The check is also applied after worker exit, so completion during a sleep gap cannot be accepted.

## Commands and approval boundary

Read-only preflight after the preparation commit:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
C:\Python313\python.exe scripts\recover_vidoseek_w66_resource_calibration.py preflight
```

The following command is **not authorized**:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
C:\Python313\python.exe scripts\recover_vidoseek_w66_resource_calibration.py run --actor codex
```

A live recovery requires a new explicit user approval bound to protocol `vidoseek_w66_resource_calibration_recovery_v1`, actor `codex`, one local invocation, a 3,600-second total cap, one worker/thread, the existing memory/disk/output limits, a five-second maximum telemetry gap, and zero retries. Approval must be recorded in a clean direct-child commit changing only the config, this review, and the focused test. Preparation or test execution does not consume or imply that approval.

Even a completed recovery would be engineering evidence only. It must be independently reviewed before setting a full exploratory-24 W66 timeout or deciding whether that separate scientific run is feasible.
