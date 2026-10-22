# M3.6: 5 GiB rerun, memory investigation, and handoff

**The requested 5 GiB rerun is complete. Integrity, latency, CUDA allocation,
and validation parity pass. Overall M3.6 technical acceptance remains BLOCKED
because an exact container/host CPU-memory peak is unavailable.** Human owner
acceptance, QA acceptance, and M3.7/G2 have not been recorded.

This report covers Khương's technical work, executed by Codex at the user's
request. It supplements the original [4 GiB report](../m3.6-003/README.md).
The old results and review records remain unchanged.

## Work completed

1. Independently audited the accepted M3.2 QARF and M3.4 QPAF pilots: replayed
   the M3.1 seal and M3.5 comparison; rehashed 16 receipt outputs per method;
   replayed 30/39 first-pass checks; checked 1,000 persisted steps across 20
   epochs per method; reloaded checkpoints in fresh processes. All 171
   validation queries and 82,255 scores per method reproduced exactly, with
   no ranking or metric changes. Historical individual gradient tensors were
   not persisted; this audit checks the persisted finite-state evidence.
2. Prepared a sourced label-free GPU protocol and hash-bound executor, then
   measured both frozen methods on NVIDIA A10G. Original latency/CUDA/parity
   gates passed, but process RSS exceeded the original configured 4 GiB limit.
3. At the user's new request, changed only CPU RAM request/limit to 5 GiB and
   added read-only process/cgroup diagnostics outside timed query intervals.
   Froze a new source commit, bundle, authorization, output namespace, and image
   binding; executed exactly one new invocation without automatic retries.
4. Identified the reported kernel as `4.19.0-gvisor`, recorded the actual
   cgroup mount/root and 5 GiB limit, and preserved missing peak/OOM interfaces.
5. Used a separate local Modal 1.6.2 observer to export provider metadata,
   memory statistics, and call outcomes for both completed apps. The benchmark
   SDK/runtime remained pinned at Modal 1.5.5; these queries ran no GPU compute.
6. Recomputed timing statistics independently with NumPy, checked coverage and
   parity, and obtained a separate read-only code/result review. The new suite
   ran 446 tests: **444 passed, two skipped**.

## New measured results

Run: `RUN-QPAF-M3_6-SYS-001-20261022T165637Z-A03`.
Source: `ade1a7122d9f64c82e2493c0c7955fe2b0a74ec2`.
App: `ap-8f30Xc6tkHWkwJSpGnRm8U`.
Image: `im-bFFCtQsQCpEMjFhsQV5QkJ`.

| Measurement | QARF | QPAF | Interpretation |
| --- | ---: | ---: | --- |
| Median full online fusion | 2.4863105 ms | 2.4471775 ms | <=10 ms: PASS |
| p95 across per-query medians | 2.5824954 ms | 2.5498479 ms | Descriptive statistic |
| Peak CUDA allocated | 0.03244019 GiB | 0.03245258 GiB | <1.50 GiB: PASS |
| Process `ru_maxrss` | 4.885990 GiB | 4.841656 GiB | Reported process high-water <5 GiB |
| Max CPU/GPU score difference | 4.44e-16 | 3.33e-16 | <=1e-7: PASS |
| Max CPU/GPU weight difference | 3.33e-16 | 7.77e-16 | <=1e-7: PASS |
| Validation ranking changes | 0 | 0 | Same validation ordering |
| Validation queries / candidates | 171 / 82,255 | 171 / 82,255 | Complete parity coverage |
| Warm-up / unique measured / passes | 20 / 1,122 / 3 | 20 / 1,122 / 3 | 3,366 timing rows each |

The original 4 GiB run had medians 3.043815/2.9618795 ms and process RSS
4.874313/4.856293 GiB. Both runs meet the same operational fusion gates. The new
run's lower latency does not establish a speedup caused by additional RAM:
separate instances, hardware scheduling, and instrumentation conditions may
differ. Neither a confirmation-quality claim nor a general QPAF speedup follows.

Both methods retained the same seven input files, including both checkpoints,
and 103 core Python source files. FP64 eager batch size 1, runtime/package pins,
candidate contract, query order, warm-ups, three passes, and thresholds are
unchanged. The held-out text/cached scores are used only for label-free timing;
no qrels were uploaded or deserialized, and no training or test quality
evaluation occurred. Timing covers CPU features, H2D, gate/fusion, D2H, and page
ranking; retriever extraction and file I/O are excluded. This page-level pilot
does not certify document-level ViMDoc pipeline latency.

## Memory findings and remaining limitation

The 23 snapshots locate the reported RSS increase primarily at PyTorch import
(about 3.93 GiB), payload loading, checkpoint loading, and validation parity.
They identify gVisor and the correct cgroup v1 memory mount. Every observed
`memory.limit_in_bytes` is **5,368,709,120 bytes**. The largest recorded current
cgroup sample is **4.738094 GiB**; that is a sampled current value, not a peak.
`VmHWM`, `smaps_rollup`, `memory.max_usage_in_bytes`, and `memory.oom_control`
are unavailable in this environment.

Modal's separate provider export records one successful input, zero failed
inputs, one container, and zero container errors. Container memory sample
percentiles are p50 **0.867619 GiB**, p90 **0.894916 GiB**, and p99
**0.894920 GiB**. The time-series export exposes one-minute averages. These
figures differ substantially from gVisor process RSS and support an accounting
scope difference. The [gVisor resource model](https://gvisor.dev/docs/architecture_guide/resources/)
documents approximate in-sandbox memory statistics; the observed backend now
supports that explanation. It does not determine the exact cause or magnitude
of the original 4 GiB discrepancy.

**Averages, p99, current samples, and successful completion are not an exact
container peak.** Neither the original run's physical RAM <4 GiB nor a continuous
physical RAM <5 GiB claim is certified. The pre-execution interpretation remains
unchanged; no metric has been relabeled to close the issue. See
[issue update](telemetry_issue_update.json), [provider receipt](provider_telemetry_receipt.json),
and [technical review](technical_review.json).

## Source and reproducibility

| Source | Responsibility |
| --- | --- |
| [audit_m36_integrity.py](../../../scripts/audit_m36_integrity.py) | Seal/receipt replay, persisted-state checks, fresh-process CPU validation |
| [prepare_m36_gpu_review.py](../../../scripts/prepare_m36_gpu_review.py) | Fixed label-free workload and review package |
| [run_m36_gpu.py](../../../scripts/run_m36_gpu.py) | Allowlisted bundle, Modal resources, authorization, binding, watchdog, create-once results |
| [m36_gpu_worker.py](../../../scripts/m36_gpu_worker.py) | Frozen eager inference, validation parity, synchronized query timing, CUDA peak |
| [m36_memory_telemetry.py](../../../scripts/m36_memory_telemetry.py) | Read-only process/cgroup diagnostics with explicit units and missing data |
| [test_m36_memory.py](../../../tests/test_m36_memory.py) | Unit conversion, mount-root mapping, missing peaks, scope and limit checks |
| [post_run_check.py](post_run_check.py) | Offline binding/input/source checks and independent timing arithmetic |

```powershell
python -X utf8 evidence/revisions/m3.6-004/post_run_check.py
```

The verifier reads existing artifacts and prints a receipt; it does not execute
GPU work. [Execution request](execution_request.json) records the historical
create-once invocation, not permission to rerun it. The independent reviewer
checked all 112 bundle files, 6,732 timing rows, 23 snapshots, and unchanged
original results. See [verification](offline_verification.json) and
[review receipt](independent_review.json). The full-suite raw log is retained
with the new results; original Windows log encoding is preserved.

## Next work and owners

| Owner | Next responsibility | Completion condition |
| --- | --- | --- |
| Khương — Technical / Data Owner | Obtain provider/host peak and its accounting definition for A02/A03, or document the unsupported measurement for explicit QA/protocol review | Traceable reconciliation or an explicit reviewed policy decision; no automatic extra GPU run |
| Thanh — Experiment Governance / QA | Independently audit source/input/checkpoint/runtime/result bindings and provider metric meanings; append the appropriate registry verification | Evidence supports technical closure and QA acceptance |
| Tấn Phát — Research Lead / Protocol Owner | Decide any proposed measurement-policy exception; review M3.7/G2 after prerequisites; prepare M3.8/R3 | Technical/QA inputs and explicit gate decision |

Roles are grounded in [M3.1 handoff](../../../docs/GUILDLINE_OVERVIEWS_PROPOSAL/M3_1_HANDOFF.md)
and the [team timeline](../../../docs/GUILDLINE_OVERVIEWS_PROPOSAL/TIMELINE_fixed.md).
All three observed apps are stopped. No remaining-seed, confirmation, test-label,
or G2 execution has been authorized by this report.
