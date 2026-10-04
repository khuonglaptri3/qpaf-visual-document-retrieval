# W66 synthetic resource calibration interruption review

**FAIL; THE ONE INVOCATION IS CONSUMED; NO CALIBRATION OR W66 RESULT EXISTS.** The approved `vidoseek_w66_resource_calibration_v1` attempt started from commit `90719a8cbbdf5cc8fe7c31020b3b60810c297b09` at `2026-09-09T08:29:35.312311+00:00`. It was stopped fail-closed after independent monitoring found a 1,296.325-second telemetry gap, violating the approved one-second sampling contract. No retry was launched.

The first command issued earlier failed its RAM admission check before an output directory or `_ATTEMPTED.json` existed, so it did not start or consume an attempt. The later admitted invocation created `_ATTEMPTED.json`; that marker records one consumed and zero remaining invocations.

## Cause and evidence

Telemetry is continuous except between `09:07:11.223434+00:00` and `09:28:47.547971+00:00`. Windows System log event 42 begins at the same instant and records a sleep transition caused by **Button or Lid**. Event 107 records the corresponding resume transition. `SetThreadExecutionState` can inhibit idle sleep but cannot certify continuity across an explicit lid/button action.

The parent/worker processes remained related by their recorded PID and creation-time identities after resume. Nevertheless, the approved contract says telemetry failure is an abort condition. Allowing the worker to finish would have produced a manifest that could not be certified against that contract, so the processes were stopped.

The console interruption terminated the process tree before the runner's exception handler could write `_INCOMPLETE.json`. This external review records that fact without adding or changing files inside the partial run directory.

## Independent integrity findings

- The resolved config exactly matches the approved config, and its canonical SHA-256 matches `_ATTEMPTED.json`.
- All 29 source snapshots match their pinned hashes; `tracked_changes.patch` is empty.
- OpenBLAS, Arrow CPU, and Arrow I/O pools were each verified at one thread.
- The real 24-query subset loaded 129,240 rows without the `relevance` column in 0.621 seconds.
- The run-plan, one 66-profile Global checkpoint, and its Global-selection checkpoint pass envelope, identity, metric, and hash-chain validation.
- No query checkpoint, calibration result, worker-complete marker, run manifest, actual-label W66 result, or scientific result exists.
- The partial directory has 42 files and 1,670,925 bytes. Its canonical artifact-hash-map SHA-256 is `535770dfbaf7722e16fd8758ace9ae38b63055f3a0ecdc542af77d6f1b104267`.
- Across 2,353 samples, peak parent-plus-worker private memory was 466,206,720 bytes, minimum host-free physical memory was 4,262,223,872 bytes, and maximum output was 1,670,379 bytes. Resource-size limits did not cause the failure.
- The last sample recorded 2,290.438 worker CPU-seconds. This is incomplete engineering timing, not a completed-query runtime and not a basis for a full-W66 timeout.

Synthetic Global metrics exist only inside the incomplete calibration checkpoint and must not be interpreted as retrieval quality. P1-02 remains blocked; P1-03, full exploratory-24 W66, training, and Modal/GPU remain unexecuted.

## Next gate

The current per-candidate implementation repeatedly rebuilds the same ranking state for every one of 65 alternative W66 profiles. The defensible next preparation is an exactly equivalent implementation that computes those candidate-invariant ranking quantities once, backed by equality tests for assignments, scores, metrics, update counts, ties, and checkpoint semantics. A new synthetic recovery calibration may then reuse only the validated Global evidence in a separate output namespace.

Preparation and tests do not authorize that recovery. Any new live attempt requires an explicit timeout, one-invocation/no-retry scope, actor, approval text/timestamp, clean commit provenance, fresh admission, and an automatic telemetry-cadence abort guard.
