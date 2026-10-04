# QPAF calibration review and proposed next experiment

Reviewed on 2026-09-06. **The CPU calibration passed. QPAF retrieval improvement remains unmeasured.**

Preparation update, 2026-09-07: a separate guarded 12-query runner, closed configuration, and fixture tests are now prepared. See [the execution review and exact proposed command](QPAF_EXPLORATORY12_EXECUTION_REVIEW.md). The proposal and the descriptions below remain the historical design snapshot; adoption and live execution are still pending.

## Verified result

| Item | Verified value |
| --- | --- |
| Worker duration | 752.7996488000001 seconds, approximately 12 minutes 33 seconds |
| Attempt-to-completion timestamps | 755.77775 seconds |
| Scope | One synthetic-relevance query, audit index 570, all 5,385 pages |
| Query ID | `031b7b7d18c37c9bc134212f6ccf7bac1f06e606_2` |
| Resources | CPU only; one worker; numerical libraries limited to one thread |
| Bootstrap | 100 resamples for this timing calibration |
| Worker timeout | 2,700 seconds |
| Source commit | `b252080d4ea32ea7b5b11450b54a7cb58f214990` |
| Consumed calibration attempts | 1; remaining 0; no retry |
| Scientific oracle / GPU / learned model run | None |

The [review JSON](../artifacts/vidoseek_p1_02r_full_page_calibration_review.json) records 11 passing checks, source/protocol identities, artifact byte hashes, and the runtime calculation. The [attempt marker](../artifacts/vidoseek_p1_02r_oracle_w7_v1_full_page_calibration/_ATTEMPTED.json) and [manifest](../artifacts/vidoseek_p1_02r_oracle_w7_v1_full_page_calibration/run_manifest.json) were imported byte-for-byte from the execution checkout; original files remain intact.

The executed YAML is preserved as a historical approval snapshot. Its pre-run `remaining_authorized_invocations: 1` does not override the immutable attempt marker, which records zero remaining and prevents another invocation. The marker exists in both checkouts, and the existing launcher refuses to proceed when either marker is present. No execution flag was reopened.

## Resource implication

If every real query cost exactly as much as this one synthetic query:

```text
752.7996488000001 seconds x 1,142 queries / 86,400 = 9.950199061685188 days
752.7996488000001 seconds x 12 queries / 3,600 = 2.5093321626666674 hours
```

These are illustrative linear projections, not measured full-run runtimes, confidence intervals, or promised completion times. Actual labels can change accepted coordinate updates and sweep duration. One synthetic query does not measure query-to-query variance. Full Global reduction, 10,000-resample final bootstrap, persistent checkpoint/final-output I/O, process startup, host contention, and sustained thermal behavior also differ.

Recommendation: do not start the full 1,142-query job merely to obtain the first improvement signal. Its current single-worker implementation is a substantial time commitment. Checkpointing improves recoverability; it does not by itself reduce the amount of computation.

## Proposed bounded discovery pilot — draft only

The complete machine-readable design and exact query IDs are in [the 12-query proposal](vidoseek_w7_exploratory12_proposal.json). **It is not approved, implemented, or runnable.** It requires a protocol decision because it changes the discovery query set and the scope used to select Global.

| Design choice | Proposed value |
| --- | --- |
| Dataset | Existing ViDoSeek P1-02R score bundle; no new extraction |
| Queries | 12 IDs selected before reading relevance or scores, using Python 3.13 `random.Random(20260820).sample(range(1142), 12)` and sorted audit indices |
| Frozen indices | 147, 396, 510, 682, 792, 797, 848, 880, 881, 940, 1023, 1081 |
| Candidate pool | All 5,385 pages per selected query; 64,620 pairs |
| Scores and normalization | Reuse the pinned normalized BM25, dense, and visual scores unchanged |
| Global | Select one W7 profile across these 12 queries, then freeze it before query-level results |
| QARF / QPAF | Reuse the frozen query-local search and two-sweep page-level coordinate ascent |
| Statistics | Per-query metrics/deltas, mean delta, exploratory 95% query-bootstrap CI with 10,000 resamples and seed 20260820, win/tie/loss counts, and all per-query timings |
| Resources | One CPU worker; one numerical-library thread; no GPU |
| Proposed total timeout | 21,600 seconds (6 hours), including input checks and finalization; proposed budget, not a runtime guarantee |
| Attempts | One; no automatic retry; any restart requires separate approval |
| Failure / timeout | Preserve evidence and mark incomplete; no replacement queries or mean presented as a completed 12-query result |

The 12-query count and six-hour limit are proposed budget choices, not sample-size or power guarantees. The selection read only dataset/query-ID columns from the candidate audit. No oracle or relevance-based selection was performed. The canonical query-list SHA-256 is `03b6480ae76d8de483106ae48e3c3a10da99cdad0812ffe1aa2c54687a2d7a64`.

This pilot's Global profile is selected on the 12-query exploratory set. It is **not** the Global profile selected across the full 1,142 queries, and its metrics must not be merged into or relabeled as the full W7 result. QPAF uses the existing heuristic coordinate search, not an exhaustive search over every page-profile assignment.

The main diagnostic is QPAF minus QARF nDCG@10: how much page-specific weighting adds beyond query-specific weighting. QARF minus Global provides the simpler alternative. Report all 12 queries and the size/distribution of gains; the ordering QPAF >= QARF >= Global alone follows from nested choices and is not evidence of useful improvement.

With only 12 queries, confidence intervals are exploratory and cannot establish broad benefit or rule it out. Do not apply the full-discovery phase gate to this subset, stop the entire research direction solely because of a weak subset, claim learned performance, or authorize training from it. The completed pilot would support a human decision about a larger run, search/runtime work, or a revised research scope. ViDoRe external-validation labels remain untouched.

## Required decision and implementation boundary

The next decision is whether to adopt this separately versioned exploratory protocol. Existing W7 guards remain false in `configs/vidoseek_p1_02r_oracle_w7_v1.yaml`; no full or subset oracle execution was authorized by calibration approval.

If the protocol is adopted, prepare the smallest separate guarded runner using the existing oracle primitives, fixture tests for exact semantics and no-retry/timeout behavior, fixed input/source/query-list hashes, and immutable outputs. Execution approval must then name the actor and exact reviewed invocation with its six-hour cap. No execution command is supplied for this unimplemented draft.

P1-02 remains BLOCKED; P1-03/W66 and learned QPAF remain unauthorized. The original scientific thresholds and task dependencies are unchanged.
