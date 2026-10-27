# M5.5 — Thanh's scoped review

**Decision:** `ACCEPTED_WITH_SCOPE_LIMIT`. Thanh explicitly accepted the validation-only
diagnostics and recovered GPU measurement in this working session. The technical
checks and exact artifact pins are in [`validation.json`](validation.json); Thanh's
answer is recorded in [`owner_confirmation.json`](owner_confirmation.json).

The CPU run contains eight diagnostic rows for 171 validation queries. Reaggregating
all 1,368 saved per-query nDCG@10 values reproduces the eight metric rows exactly.
The earlier exact-runtime CPU replay receipt reports PASS, but this review did not
repeat the full CPU input replay because the pinned Python 3.11.14 runtime and
external Parquet payload were not used here.

The GPU offline verifier was rerun without Modal and returned PASS. It found 171
distinct validation IDs, six passes and 1,026 timed events per method over 82,255
candidate pages. Decoding all 55 saved provider-log fragments reconstructed 54
chunks and exactly the committed GPU result. All 135 task-bundle manifest files
match their stored hashes and sizes; four authorized GPU source files match the
pinned source commit. The original A03 client `_FAILURE.json` remains preserved:
the result came from that same successful provider Call ID, with no new GPU run.

| Method | Median online fusion | Peak CUDA allocation |
| --- | ---: | ---: |
| QARF | 2.569362 ms/query | 0.032428265 GiB |
| QPAF | 2.4263995 ms/query | 0.032439709 GiB |

**Policy boundary:** the original metric policy requires at least 1,000 measured
queries. This validation run contains only 171 distinct IDs repeated six times.
Thanh accepts it as a validation diagnostic; it **does not establish the original
operational latency gate**. The online measurement excludes retriever extraction,
cold start, queue time and file I/O. CUDA allocation is not physical peak RAM.
No claim is made about held-out test performance or QPAF beating the baseline.

Review commands (read-only):

```powershell
python docs/reports/milestones/M5.5/evidence/verify_gpu_result.py --evidence-dir docs/reports/milestones/M5.5/evidence/gpu-attempt-003 --check-only
python -m unittest tests.test_m55_diagnostics tests.test_m55_gpu tests.test_m55_gpu_transport -q
```

The review used Python 3.13.7. The targeted tests ran 40 tests with no failures.
No GPU invocation, training or test-label access occurred during review.
