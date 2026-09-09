# W66 resource-calibration recovery result review

**PASS: completed engineering recovery; not a scientific retrieval result.** The single approved invocation of `vidoseek_w66_resource_calibration_recovery_v1` completed from approval commit `c94fb8edd9f8adf5eaf5089ce8fb0f71e72bc311`. The invocation is consumed, zero invocations remain, and no retry is authorized.

## Independently verified evidence

- The run manifest SHA-256 is `fa99a2ada9562348d2e65acb09634b0a637b26f52b1e5bf8771425295857b0af`.
- All 49 manifest-bound artifacts and all 33 source snapshots match their recorded hashes. The tracked Git patch is empty.
- The 129,240-row input projection was independently reloaded with the same nine columns and no `relevance` column. The selected 5,385-page synthetic query contains exactly one constructed relevant page.
- All four checkpoint envelopes and identities validate. Independent replay succeeded with `candidate_oracle_exact_fast` replaced by a function that raises if called, proving that replay did not rerun candidate search.
- Numeric libraries and Arrow CPU/I/O pools each used one thread. The run used no GPU or Modal resource.
- Telemetry contains 69 samples. Maximum wall and monotonic gaps were 1.075006 and 1.0695475 seconds, both below the five-second limit. Peak process-tree private memory was 442,408,960 bytes; minimum host-free memory was 5,373,321,216 bytes; maximum output was 487,694 bytes. All limits passed.

## Timing result

Total elapsed time was 70.611111 seconds. Input loading took 1.063986 seconds, one-query W66 Global evaluation 0.999335 seconds, optimized query-oracle search 62.574621 seconds, and immutable replay 0.069082 seconds.

The synthetic query produced zero accepted updates and therefore exercised one candidate sweep. Scaling its measured query-search time to 24 queries gives a conditional one-sweep illustration of 1,501.791 seconds. Doubling that query-search component gives a conservative arithmetic illustration of 3,003.582 seconds before full-run overhead. These are not measured 24-query runtimes, confidence intervals, or approved timeouts; the full-page two-sweep update path was not measured by this recovery.

## Decision and boundary

The recovery closes the engineering uncertainty sufficiently to prepare an exact-output optimized exploratory-24 W66 protocol. It does **not** authorize the existing scientific W66 runner, which still uses the frozen unoptimized candidate oracle. The optimized implementation must be integrated under a separately versioned, hash-pinned preparation with equivalence and checkpoint tests, followed by a separate resource/timeout review and explicit execution approval.

No actual-relevance W66 study, scientific result, formal P1-03 decision, training, Modal/GPU execution, or frozen P1-02 status change occurred. Recovery checkpoints remain ineligible for reuse in a scientific run.

Machine-readable review: `artifacts/vidoseek_w66_resource_calibration_recovery_review/review.json`.
