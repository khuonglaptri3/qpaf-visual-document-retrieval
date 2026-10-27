# M5.5 — CPU diagnostics and deferred GPU handoff

## Continuation on 2026-10-27

The owner requested continuation of PR #45. Preserve the approved CPU experiment
below and every historical source/authority/result byte. Diagnose and repair the
failing Ubuntu method-core CI check, verify the CPU delivery on this Windows
machine, and leave one current report with provenance and explicit unfinished work.
This continues an approved experiment. The user subsequently authorized Modal/GPU
and delegated protocol details within validation; the successor scope below now
authorizes preparing and running R5-04. Historical CPU authorization remains unchanged.

The canonical task bundle is `docs/reports/milestones/M5.5/`: exactly `README.md`,
`evidence/`, and `superpowers/`; the latter contains only `spec.md` and `plan.md`.
New logs, hashes and workflow belong in evidence, never in the old CPU run.
The CI fix needs a deterministic regression and fresh full-suite results.
Check planning links, report/index consistency, manifest hashes and checkout bytes.
Independent human acceptance and R5-04 cannot be inferred from green CI.

## Successor R5-04 protocol — authorized 2026-10-27

User instructions, recorded verbatim: `Cho phép chạy Modal/GPU để hoàn tất số đo M5.5`
and `Tự quyết chi tiết và triển khai trong phạm vi validation`.
This supersedes the old machine-specific Modal prohibition for this successor
activity only. No Research Lead or independent reviewer signature is inferred.

Approaches considered: validation-only repeated timed events preserves M5.1;
using >=1,000 distinct IDs would require expanding beyond its 171 validation IDs;
reusing M3.6 would not create a new M5.5 measurement. Select the first under the
owner's delegated decision. This is an explicit operational counting interpretation:
20 warm-up events followed by six complete passes over all 171 validation IDs,
1,026 timed events per method, 171 distinct IDs, with warm-up overlap disclosed.
Never describe these as >=1,000 distinct queries or as the M3.6 distinct-ID protocol.
Warm-up uses the first 20 IDs in the frozen validation order. Both methods and all
passes use the same order. Primary statistic: median over 171 per-query medians
across six passes; also report event p50/p95 and each pass separately.

Reuse the frozen seed-20260820 QARF/QPAF checkpoints and 13-feature eager FP64
batch-one fusion, with unchanged source/config/checkpoint hashes. Export only
validation query/page IDs, text, three raw scores and existing CPU reference
predictions. The GPU bundle must contain no qrels or train/test records. Verify
all 171/82,255 CPU-reference scores/weights at <=1e-7 before timing. Run each
method in its own fresh subprocess, fixed one-thread CPU behavior and TF32 off.

Adapt the reviewed M3.6 worker/launcher into new M5.5 scripts; do not edit the
historical worker, its authorization, results or frozen scientific source.
Record CPU feature construction, H2D, gate CUDA/wall, D2H and page ranking
separately; synchronize CUDA correctly. The online wall scope starts after saved
scores/text are in RAM and includes preprocessing, transfers, inference and ranking.
Cold start/checkpoint I/O is separate. Preserve raw timings. Gate median <=10ms
and peak learned-fusion CUDA allocated <1.50GiB under this explicitly recorded
validation-event interpretation; report CUDA reserved, process RSS and cgroup
memory independently. Do not describe CUDA allocation as total container RAM.

Use one Modal A10 container, two physical CPU cores, 5,120MiB RAM, 900s function
timeout, 120s startup timeout and 900s whole-app watchdog. One invocation, no
automatic retries, one create-once namespace. Operating budget target USD0.50;
at current listed rates, 900s allocated GPU/CPU/5GiB RAM is about USD0.309.
This is a bounded operating target, not a provider-enforced dollar cap. Keep
runtime image/build timeouts and app stop on watchdog. Pin the existing M3.6 OCI
base, Python3.13.7/Torch2.11.0+cu126 and numerical packages; bind resolved Modal
image ID before the sole remote call. Never reuse an M3.6 execution authorization.

Tests must reject changed input/source/checkpoint/runtime pins, non-validation
IDs or label-bearing payloads, missing/reordered/duplicate events, invalid/nonfinite
timings and an existing output namespace. Record any failed attempt without
overwriting or claiming completion. Finish with fresh-context engineering review,
artifact hashes and CI. Independent human acceptance remains a distinct pending step.

### Transport successor

The first input-plane `.remote()` attempt completed once on Modal (32.943s), but
the local `AttemptAwait` RPC exceeded its deadline and returned no raw result.
Provider history confirms success; ordinary FunctionCall.get cannot retrieve that
transient input-plane call. Preserve the entire failed client attempt and provider
history. The app is stopped. Make one manually initiated successor with the same
validation workload/checkpoints and bounded resources under the owner's existing
execution delegation. Use `function.spawn()` once, save its durable Call ID before
waiting, then `call.get(timeout=900)`; retrieval failure must never submit a second
input. Record the prior completed invocation rather than claiming only one was ever
executed. This changes transport/recoverability, not scoring or the timing workload.

The durable successor exposed the actual export error: returning more than the
SDK's 8KiB asynchronous inline limit invokes BlobCreate, forbidden in a restricted
Function. Preserve that attempt too. Keep `block_network=True` and
`restrict_modal_access=True`; after measuring, encode the full result as deterministic
gzip/base64 stdout chunks <=3,100bytes each. Return only small metadata (codec,
byte count, chunk count, SHA256) below8KiB. Fetch the existing call's logs read-only
and verify/reassemble every chunk before accepting the result. Missing/conflicting/
corrupt chunks or hash mismatch must fail. Probe this exact channel on a CPU-only
restricted Function before a third bounded GPU invocation. Measurement stages
exclude serialization/compression and log transfer.

Exact original CPU replay may use a bounded CPU-only Modal verifier that fetches
the public pinned Git commit/M4.2 archive, avoiding stalled Windows downloads.
It must enforce Python3.11.14/NumPy2.4.6/pandas3.1.0/PyArrow26.0.0 and run the
unchanged verifier under write/network/forbidden-import/test-qrels audit guards,
proving all original run bytes unchanged. This is verification, not another
scientific run or GPU workload; development-label input is never included in GPU.

Sources checked for this successor: [Modal GPU guide](https://modal.com/docs/guide/gpu),
[Modal resource pricing](https://modal.com/pricing) and the repository's frozen
metric policy and M3.6 measurement implementation. The choices of six passes,
validation counting, resource bounds and reuse architecture are the implementing
agent's decisions under the user's explicit delegation.

## Authority and intent

Implement the already accepted M5.1 R5-01 through R5-03 on the frozen ViDoSeek
validation pool. Khương's current instruction explicitly requests M5.5 and
defers all Modal/GPU work because this machine cannot reach Modal. Record that
instruction verbatim in a CPU-only execution authorization; do not attribute
Research Lead approval or an independent human review that was not supplied.

The binding study specification is `evidence/revisions/m5.1-001/preregistration.json`,
its owner confirmation, and the confirmed G2A roster. This document implements
that existing specification; it does not change QPAF-v1 or the primary study.

## Exact experiment

Use the M4.2 bundle, manifest `4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86`.
There are 171 validation queries and 82,255 candidate rows. Read development
qrels through the existing validation-only loader. Reject test qrels in that
container and never materialize test records. Labels cannot affect scoring.

Eight rows, in this order:

| Row | Input | Weights BM25/BGE/ColQwen | Roster |
| --- | --- | --- | --- |
| `bm25` | saved min-max | 1/0/0 | R5-01 |
| `bge_m3` | saved min-max | 0/1/0 | R5-01 |
| `colqwen25` | saved min-max | 0/0/1 | R5-01 |
| `uniform_combsum` | saved min-max | 1/3 each | reference |
| `without_bm25` | saved min-max | 0/0.5/0.5 | R5-02 |
| `without_bge_m3` | saved min-max | 0.5/0/0.5 | R5-02 |
| `without_colqwen25` | saved min-max | 0.5/0.5/0 | R5-02 |
| `uniform_zscore` | per-query raw-score z-score | 1/3 each | R5-03 |

Z-score uses population standard deviation (`ddof=0`), with a zero-variance
channel mapped to zero. Preserve negative z-scores: no clipping or score shift.
Keep candidate rows/order fixed, including when dropping a channel. Validate
saved normalized keys and scores against raw-score min-max. Use the frozen
page evaluator and page-ID tie break. Report nDCG@10, R@1, R@3 and MRR@10.

Recompute the four existing singleton/uniform rows and compare all aggregate
and per-query metrics with the pinned M4.4 artifacts at tolerance `1e-12`.
Keep the selected `train_fitted_static` baseline as historical context; do not
refit it or promote the best diagnostic row. Descriptive paired deltas/W-T-L
against uniform min-max are permitted; no new confirmatory claim or seed selection.

## Execution and evidence

Add isolated `qpaf.m55` scoring and runner modules plus one CLI. Do not edit
frozen code, approved earlier authorizations, checkpoints or historical output.
Use a create-once output namespace and external authorization/manifest hashes.
Authorization pins the implementation commit/source bytes, authority files,
runtime and explicit CPU-only user instruction. Permit only its own committed
authorization file after the implementation commit before starting the run.

Restoration is local only from the exact GitHub M4.2 ZIP, SHA-256
`45e764f6bfe081063ea2488dbf5e26ffcaacf2e6f43ea3ad47f56a10c331d2d8`.
Verify archive bytes and every existing target; no overwrite or general archive
extraction. The archive has development labels and no test qrels.

Save aggregate/per-query metrics, top-10 rankings, paired contrasts, input and
source identities, reference parity, access boundaries, authorization, manifest,
attempt/completion markers and a report. A read-only verifier checks artifact
hashes and replays CPU calculations without changing files. A standalone chart
may be generated for the human report, separately hashed as supporting evidence.
CPU elapsed time is data-analysis wall time, not a learned-fusion latency result.

## Deferred R5-04

Make no Modal request, GPU call, retriever inference, model training or checkpoint
reload in this task. Record `NOT_RUN_DEFERRED_MODAL_NETWORK_BLOCKED` for R5-04.
Overall M5.5 remains partial and pending independent review, even if all CPU rows pass.

M3.6 measurements are historical reference only. Its measured pool includes
train/test label-free inputs under a separate authorization. R5 permits only
validation, whereas metric policy calls for 20 warm-ups and >=1,000 label-free
measured queries. The accepted M3.6 workload implements this with >=1,000
distinct measured IDs. The validation pool has only 171 IDs; repeating them
does not increase the distinct-ID count. Whether a new validation-only M5.5
benchmark may count repeated timed events must be explicitly reviewed rather
than silently equated with M3.6's distinct-ID protocol. A future machine needs an explicit reviewed
measurement-scope decision, a new M5.5 authorization, runtime/source/input pins,
one create-once invocation, and separate CPU/RAM/CUDA accounting. Do not reuse
an old M3.6 authorization or silently import its result as a new M5.5 result.

## Approach chosen

Reuse frozen cache, validation loader and evaluator; add a small diagnostics
layer. This minimizes changes and makes replay possible on CPU. Re-extracting
retriever scores would change the experiment and require unnecessary GPU work.
Running GPU measurements here conflicts with the user's explicit constraint.

## Completion criteria

- Meaningful normalization, scoring, boundary, authorization, tamper and replay tests pass.
- Real CPU execution covers every frozen validation query/candidate and matches M4.4 references.
- Independent engineering review and full software suite pass.
- Vietnamese report explains the results and exactly what remains for another machine.
- No full M5.5 completion, human acceptance or operational-gate PASS is inferred.
