# Optimized exploratory-24 W66: resource and execution review

**AUTHORIZED FOR EXACTLY ONE CODEX INVOCATION; NOT YET EXECUTED.** The user approved this separately versioned protocol from preparation commit `aea9e31fb0ccf8eab65e4735e76ad950c25eb103` with a 7,200-second cap, one local CPU worker/thread, a five-second telemetry-gap limit, and zero retries. The authorization changes no scientific or resource parameter and does not authorize P1-03, training, Modal/GPU, or a P1-02 status change.

## Frozen scientific contract

| Item | Prepared contract |
| --- | --- |
| Protocol | `vidoseek_p1_02r_w66_exploratory24_optimized_v1` |
| Queries | Same 24 ordered ViDoSeek queries as exploratory-24 W7; no reselection |
| Query-list SHA-256 | `95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b` |
| Candidates | All 5,385 pages/query; 129,240 query-page pairs |
| Score bytes | `32b39da19e9507a0a5060157630cb40bf5c6bcf6464d88e4bb6136888473173b` |
| Grid | 66 simplex profiles; SHA-256 `c04139858954fd0a7f7baa5dad548f3675a41b8682e9798039508e4077da5973` |
| Global/QARF | Unchanged exhaustive W66 selection and tie-breaks |
| QPAF | QARF-initialized fixed-order coordinate ascent; strict `1e-12` improvement; at most two sweeps |
| Bootstrap | 10,000 query resamples; seed `20260820`; percentile CI95 |
| Classification | Exploratory subset oracle upper bound; not formal P1-03 or deployable performance |

The historical runner remains byte-unchanged. The new runner calls `candidate_oracle_exact_fast`, SHA-256 `3322b024fa689e0b08ba2e9d6cd08347b5e889cbd26980c4cd19a3a002d4c4e5`. Its run identity binds that implementation and uses new checkpoint kinds and a fresh output namespace, so historical W66 and calibration checkpoints cannot be mixed into this protocol.

## Exactness evidence

The optimized candidate search reuses candidate-invariant ranking state but preserves candidate order, profile order, tie handling, accepted-update rule, maximum sweeps, and serialized result fields. Deterministic tests compare it with the frozen oracle on W7/W66 random, tie-heavy, zero-relevance, bounded larger, complete-row, and checkpoint-replay fixtures.

The independently reviewed synthetic full-page recovery completed in 70.611111 seconds. Its optimized one-query search took 62.574621 seconds and matched immutable replay; all 49 manifest-bound artifacts, 33 source snapshots, four checkpoints, thread pools, and telemetry checks passed. This was engineering evidence with one synthetic relevant page, zero accepted updates, and one exercised sweep--not a retrieval result or a measurement of the actual-label 24-query study.

## Resource review

Scaling the measured one-sweep query search across 24 queries plus observed overhead gives a conditional 1,533.811-second illustration. Doubling the query-search component gives a conservative arithmetic illustration of 3,035.602 seconds. The actual-label two-sweep update path was not measured, so neither value is a runtime guarantee.

The prepared cost cap is 7,200 seconds: approximately 2.37 times the conservative illustration. A future approved attempt would use one local CPU worker, one thread for each numeric and Arrow pool, one-second telemetry, a five-second maximum wall/monotonic telemetry gap, Windows sleep inhibition, a 2-GiB process-tree private-memory limit, a 2-GiB free-memory abort threshold, a 5-GiB prestart disk threshold, a 100-MiB output limit, and zero automatic retries. Crossing any bound makes the consumed attempt incomplete; partial checkpoints or metrics are not a result.

The 7,200-second cap is approved for exactly one invocation as a bounded cost ceiling. It does not promise completion and authorizes no retry.

## Lifecycle and evidence gates

The approval must be recorded in a clean direct-child commit changing exactly this review, the config, and the focused test. A fresh preflight and admission check must pass from that exact commit before execution. Once admitted, the create-once `_ATTEMPTED.json` consumes the invocation. Existing output is rejected; any incomplete attempt is consumed and any recovery needs another versioned protocol and explicit approval.

Completion requires 24 Global checkpoints, one shared Global-selection checkpoint, 24 optimized query checkpoints, all output files, a complete hash manifest, and a separate independent review of input identity, checkpoint envelopes, query coverage, rankings, metrics, bootstrap values, resources, and Git provenance. Until then, no W66 comparison or result may be reported.

## Authorized command

```powershell
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
C:\Python313\python.exe scripts\run_vidoseek_exploratory24_w66_optimized.py run --actor codex
```

Authorization text recorded at `2026-09-09T17:40:40.9893617Z`: "Approve exactly one Codex local-CPU invocation of the optimized exploratory-24 W66 protocol from preparation commit aea9e31, with a 7,200-second cap, one worker/thread, five-second telemetry-gap limit, and zero retries. Prepare the allowlisted approval commit, rerun preflight, then execute and monitor it. Do not run P1-03, training, Modal/GPU, or change P1-02".

Run the command only after the exact approval commit and fresh preflight/admission checks pass. This approval does not authorize P1-03, training, Modal/GPU work, a retry, or a P1-02 status change.
