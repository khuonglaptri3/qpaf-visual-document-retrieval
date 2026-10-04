# W66 resource-budget review

Reviewed 2026-09-09 at commit `592846a5ea8c680a66297144aca13a2ba8411f9d`.

**Decision: NO-GO for the full 24-query W66 invocation with the present evidence and resource controls.** Proceed with preparation of the single-query synthetic calibration below. No full-study timeout is recommended yet. The six-hour calibration cap is a proposed spending limit, not execution approval or a guarantee of completion.

This review adds only this document and its [machine-readable evidence](QPAF_W66_RESOURCE_BUDGET_REVIEW.json). The existing configuration, proposal, source, receipts and Git commit remain unchanged. It performs no W66 search and creates no execution output directory.

## Evidence and measured W7 runtime

The [parent W7 manifest](../runs/vidoseek_w7_exploratory24_v1/run_manifest.json) is COMPLETE; its SHA-256 is `0fcfbceee0e581240f241447abae1cb85cbb4f11cfee4f4d5343c2f81e06d9ee`. All 82 artifact hashes were rechecked, including the [timings](../runs/vidoseek_w7_exploratory24_v1/timings.json), per-query records and source snapshots. All 27 W66 source pins also match. The existing score file was hashed again: 248,445,561 bytes, SHA-256 `32b39da19e9507a0a5060157630cb40bf5c6bcf6464d88e4bb6136888473173b`.

| Recorded component | Seconds | Interpretation |
| --- | ---: | --- |
| Entire W7 invocation | 8,700.394 | About 2h 25m, 24 queries, 5,385 pages each |
| Sum of 24 Global-pass timers | 2.725 | Includes each checkpoint operation |
| Sum of 24 query-search timers | 8,688.940 | 99.87% of total elapsed time |
| Total minus the two timer sums | 8.729 | Unattributed remainder, not a separately measured bootstrap or I/O time |
| Query timer minimum / median / maximum | 244.316 / 296.743 / 691.207 | About 4.1 to 11.5 minutes per query |

The timer in [the shared W7 subset evaluator](../src/oracle_study/vidoseek_exploratory12.py) starts after frame filtering and validation and surrounds the yielded checkpoint operation. It therefore cannot separate QARF, QPAF, hashing and checkpoint writing. Input loading, frame preparation, summaries and process/finalization costs contribute to the remainder. There is no measured W7 peak process memory in these run artifacts, and the manifest does not identify the historical CPU model or thermal state.

From the unchanged search loop and the recorded accepted-update counts, 19 queries required one sweep and five required two: 29 query-sweeps total. The slowest query was audit index **1129**, with **zero accepted updates** and 691.207 seconds. Thus a slow query cannot be identified solely by whether its oracle improved the ranking. The JSON companion records all 24 timers and update counts.

## Workload and conditional scenarios

In [the candidate oracle](../src/oracle_study/qpaf.py), each alternative profile calls `_single_item_ndcg`. That helper re-sorts the current ranking, allocates position/order arrays and constructs a Python list of approximately 5,384 score/ID pairs. If the position changes, it also recomputes gain/discount information and sorts the relevance array. The small three-channel dot product is not the dominant structural cost.

For Q queries, N pages, P profiles and S sweeps, an approximate upper-order cost is `O(Q * S * (P-1) * N^2 * log(N))`; Python allocation and string comparisons affect constants. S is one or two, not a constant learned from W7. The implementation does not skip the candidate loop merely because nDCG is already at its ceiling.

| Work count | W7 | W66 |
| --- | ---: | ---: |
| Profiles | 7 | 66 |
| Alternatives per candidate per sweep | 6 | 65 |
| Global profile evaluations over 24 queries | 168 | 1,584 |
| QARF profile evaluations over 24 queries | 168 | 1,584 |
| Candidate alternative evaluations | 936,990, inferred for the observed 29 sweeps | 8,400,600 to 16,801,200 for one to two sweeps on every query |

The [W66 query-result function](../scripts/run_vidoseek_exploratory24_w66.py) recomputes the query-local profile search in its second pass; it does not reuse the first pass's profile metrics for that calculation. Its larger menu can alter initialization, accepted updates and second-sweep frequency. Finer-grid coordinate ascent does not guarantee a better QPAF local optimum, so runtime review must not assume improved retrieval outcomes.

For transparency, the following are conditional arithmetic scenarios, **not confidence intervals, measured W66 runtimes or safe limits**:

| Assumption | Derived duration |
| --- | ---: |
| Keep each query's W7 sweep count and per-alternative cost | 26.16 hours |
| Normalize each W7 query timer by its inferred sweep count; give all W66 queries one sweep | 21.76 hours |
| Same normalization; give all W66 queries two sweeps | 43.51 hours |
| Every query takes two sweeps at the slowest observed W7 one-sweep rate | 99.84 hours for the search component alone |

The first three apply `65/6` to search work, `66/7` to Global time and keep the 8.729-second remainder. The normalized scenarios divide a whole query timer, including overhead, by one or two sweeps; that is a simplification. The last is a stress illustration, not a statistically justified worst case. Neither a recycled 12-hour W7 cap nor a newly asserted 48-hour cap is established by these data.

## CPU, memory and storage

The read-only host snapshot at `2026-09-09T03:34:03.5591980+00:00` shows an Intel i7-10510U, four cores/eight logical processors, 15.81 GiB visible RAM, 3.80 GiB free physical memory and 22.61 GiB free space on C:. These are current conditions, not historical W7 measurements or reserved capacity. One search worker cannot claim an eightfold speedup from the logical processor count; this path spends substantial time in serial Python work.

The worker [loads all 129,240 selected rows](../scripts/run_vidoseek_exploratory24_w66.py) into one pandas DataFrame before its two passes. It is query-sharded for checkpointing, but is not a streaming one-query input loader. Its call does not project columns: strings, branch ranks and stage1 scores are loaded alongside the three score channels and relevance.

The three float64 channels alone occupy 2.958 MiB for the subset and 0.123 MiB for one query. These are lower bounds only. Arrow decoding/buffering, pandas string columns, frame copies, hash serialization, Python tuple lists and the parent/worker interpreters add memory. The Parquet file has 143 row groups; the first contains 43,080 rows and 3,467,417 uncompressed bytes. A filtered query read may decode more rows than it returns. This review read metadata only and did not measure the full loader's peak memory.

The profile grid itself is only 66 x 3 x 8 = 1,584 numeric bytes. The shared [bootstrap implementation](../src/oracle_study/bootstrap.py) batches resampling in groups of 256 and retains 10,000 float estimates; it does not retain a full 10,000 x 24 sample matrix. Bootstrap is therefore unlikely to dominate memory, but its elapsed time must be recorded separately in calibration.

**Thread-control gap:** in a fresh installed PyArrow 24.0.0 process, with OMP, MKL, OpenBLAS and NumExpr thread variables all set to 1, `cpu_count()` reports 1 while `io_thread_count()` reports 8. The W66 source has no explicit Arrow CPU/I/O pool setters. The installed `read_table` signature defaults to `use_threads=True` and `pre_buffer=True`; [Apache Arrow's documentation](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.read_table.html) confirms threaded reads and background I/O buffering. Actual simultaneous thread usage during this workload remains unmeasured. A one-thread resource claim needs explicit pool limits and verification in the spawned worker.

The existing W7 run contains 83 files totaling 431,397 bytes. W66 adds more profile metrics and potentially more changed-page assignments, so this is not an output-size bound. Disk capacity appears sufficient for a small calibration, but current free RAM is below the proposed 4-GiB start threshold. Recheck both immediately before any approved attempt.

## Checkpoints and failure exposure

The W66 design writes a run plan, 24 Global checkpoints, a shared Global selection and 24 query checkpoints: 50 checkpoint envelopes. Each query result depends on the sealed shared Global selection; that selection requires all 24 first-pass checkpoints. Input hashes, query order, source/protocol identity and the Global-selection hash protect reuse. W7 checkpoints cannot be substituted for W66 checkpoints.

A query checkpoint is written only after the entire candidate search returns. There is no intra-query or per-sweep recovery point; interruption can lose hours of work on the current query under the scenarios above. The normal command rejects an existing output directory even if usable checkpoints exist. Recovery is a separate workflow requiring reviewed authorization, not a supported automatic restart.

The [atomic writer](../src/oracle_study/vidoseek_p1_02r_sharded.py) flushes and fsyncs a temporary file, then creates a hard link to its final path. This avoids replacing a completed checkpoint. It still requires working filesystem/link support and must be tested in the intended output location. A crash can leave temporary files; inventory checks can refuse them, so cleanup must not be automatic or erase evidence.

The parent waits for the worker with a timeout, then terminates it and, if needed, kills it after a five-second wait. This protects a surviving parent, but provides no independent watchdog if the parent or controlling session dies. Validation before spawning and final hashing use elapsed-time checks rather than continuous deadline supervision; termination also has grace time. There is no process-memory limit, memory sampler, per-query timeout or within-query heartbeat in the current runner. Timings are written to the final JSON only after completion; stdout progress is emitted after each query.

Before a long run, resolve parent/child survival, persistent logs, deadlines, sleep/power continuity and memory supervision. An incomplete marker or surviving process is not completion evidence. A full result still requires all 24 checkpoints, a COMPLETE manifest and independent integrity/ranking/bootstrap review.

## Minimal calibration protocol proposed for preparation

Protocol ID: `vidoseek_w66_resource_calibration_v1`. Status: **DRAFT; harness not implemented; no invocation authorized**. This is a new engineering experiment; earlier consumed calibration permissions cannot be reused.

| Item | Proposed contract |
| --- | --- |
| Selection | Slowest recorded W7 query-search timer, ties by ascending audit index; choose 1129, query `05e2dbaf2d299e33a0e7bf92a434214c84381bf1_5` |
| Selection basis | Existing runtime evidence only; this is an engineering stress sample, not a representative retrieval sample |
| Input loading | Load the same 24 frozen queries and original columns except `relevance` to measure subset materialization; inspect only query 1129 for search |
| Synthetic labels | Sort its 5,385 unique page IDs ascending; assign relevance 1 at zero-based position 2692 and 0 elsewhere; forbid decoding the actual relevance column |
| Search | Exactly one full-page W66 query, existing profile order, metric/tie rules, strict improvement tolerance and maximum two sweeps; preserve normal early stop |
| Global/checkpoints | Single-query synthetic Global pass followed by its query checkpoint; identity explicitly records synthetic labels and single-query scope; never reuse these in the real study |
| Bootstrap probe | Separately time the existing bootstrap functions at 10,000 resamples, seed 20260820, on fixed 24-element synthetic inputs `v[i]=i/23` and denominator 1; report engineering time only |
| CPU | One worker; each numeric CPU pool and Arrow CPU/I/O pool explicitly set to 1 and queried inside the spawned process |
| Wall cost cap | 21,600 seconds including preparation, input, search, probes and finalization; independent supervision with bounded shutdown grace |
| Invocation / retry | One proposed invocation; zero currently authorized; zero automatic retries, extensions or recovery |
| Memory | Proposed combined parent+worker private-bytes cap 2 GiB; sample private bytes and working set every second; this sampled threshold is not an OS-enforced instantaneous ceiling |
| Admission / abort | Start only with at least 4 GiB free physical RAM and 5 GiB disk; abort if free physical RAM drops below 2 GiB, memory threshold is exceeded, telemetry fails, or the deadline is reached |
| Output budget | At most 100 MiB, enforced by the future harness; path `runs/vidoseek_w66_resource_calibration_v1` must be absent at admission |

The six-hour cap is a policy proposal. The slowest W7 one-sweep timer multiplied by `2 * 65/6` is 14,976 seconds. A discretionary 35% allowance plus 600 seconds gives 20,818 seconds, rounded up to 21,600. This arithmetic motivates a bounded stress attempt; the factors are not measured W66 overheads or a completion guarantee. The calibration does not forcibly execute a second sweep if the unchanged search stops after the first.

Preparation must first implement a separate closed harness, pin source/config/environment/input and synthetic-label rules, and verify the numeric/thread/timeout/memory/output/parent-death guards using tiny fixtures. It must verify immutable checkpoint replay without rerunning the search. A guard failure or mismatched pin prevents the attempt. The reviewed harness should provide persistent stage timestamps and process identity (PID plus start time), parent and worker CPU time, peak private bytes/working set, observed pool sizes, checkpoint hashes/counts, elapsed time per stage and completion/failure status. Failure consumes the sole approved attempt; preserve partial evidence without a complete-result claim.

Synthetic ranking values may exist inside calibration checkpoints for replay checks, but the engineering report must not interpret or pool them as W66 retrieval gains. Actual full-study query selection, labels and scientific contract remain frozen. This proposal creates no calibration directory and supplies no runnable approval command.

## How the calibration changes the decision

1. **Timeout, memory breach, orphaned worker, checkpoint failure or missing telemetry:** keep the full-study NO-GO; review the harness or compute design before proposing any new attempt.
2. **Verified completion within the resource budget:** classify as an engineering PASS and record which sweep path was actually exercised. Revisit the full-study timing scenarios and input-memory cost using the measured evidence.
3. **Remaining coverage gaps:** a single synthetic query cannot establish the worst real W66 query time, second-sweep frequency, 24-query Global behavior or sustained multi-day throttling. If those gaps prevent a defensible budget, propose a further bounded probe or a more efficient exactly equivalent implementation; do not promote six hours into a full-study cap.

Only after that review can a concrete full-study resource proposal be considered. A future preparation/approval commit must explicitly handle Git provenance: the current validator expects a direct child of `c7f3b48` with exactly the original 13 paths. Simply committing this report or toggling authorization in an ordinary new child will not satisfy that rule. This review leaves HEAD and the protected files unchanged and leaves the two review artifacts untracked.

The immediate next work item is **implement and fixture-test the separate closed calibration harness described above**. The scope of this review ends with the protocol; execution, resource approval, full W66, Modal/GPU, training and P1-03 remain closed.
