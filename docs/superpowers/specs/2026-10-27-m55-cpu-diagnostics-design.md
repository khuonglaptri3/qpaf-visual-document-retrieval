# M5.5 — CPU diagnostics and deferred GPU handoff

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
