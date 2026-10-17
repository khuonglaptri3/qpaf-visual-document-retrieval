# Exploratory-24 page-level QPAF feasibility: execution review

**COMPLETED AND INDEPENDENTLY VERIFIED.** After reviewing this exact contract, the user replied “ok I approved”. The one authorized Codex CPU invocation completed in 8,700.394 seconds with no retry. See [the verified result](QPAF_EXPLORATORY24_RESULTS.md) and [complete manifest](../../../runs/vidoseek_w7_exploratory24_v1/run_manifest.json). The authorization is consumed.

## Why this is the next gate

The full-discovery fixed-profile audit independently verified Global/QARF mean nDCG@10 of 0.875138/0.908268 and a theoretical mean QPAF-over-QARF headroom bound of 0.091732. The bound exceeds the 0.03 review threshold, so page-level feasibility is not mathematically ruled out. It does not establish that the existing QPAF coordinate search can realize the bound.

A full 1,142-query page-level run remains too expensive and is not authorized. This separate 24-query study is the bounded representative option already declared before the fixed-profile audit completed.

## Frozen selection

The selection algorithm was declared in `docs/02_project_plan/QPAF_NEXT_EVALUATION_PROPOSAL.md` before the fixed-profile result was known:

1. Start with the frozen 1,142-query candidate-audit order.
2. Remove the 12 exact audit indices used by the completed exploratory-12 study, leaving 1,130 queries in original order.
3. Run Python 3.13 `random.Random(20260820).sample(range(1130), 24)`.
4. Sort those remainder positions and map them back to original audit indices.

The frozen audit indices are `[92, 141, 148, 398, 513, 640, 676, 686, 798, 803, 832, 842, 855, 889, 890, 892, 950, 992, 1034, 1067, 1082, 1084, 1093, 1129]`. The canonical query-list SHA-256 is `95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b`.

[The frozen proposal](vidoseek_w7_exploratory24_proposal.json) publishes all 24 IDs. Query selection used no relevance values, retrieval scores, fixed-audit per-query metrics, or page-level QPAF outcomes. The sample is disjoint from the original 12 exact queries. It is representative by the declared uniform rule; it is not a failure-focused sample.

## Exact proposed contract

| Item | Contract |
| --- | --- |
| Classification | Exploratory 24-query side study; not full W7 or a formal Phase 1 gate |
| Dataset | ViDoSeek discovery only |
| Queries | 24 fixed additional queries from the 1,130-query remainder |
| Candidates | All 5,385 pages/query; 129,240 query-page pairs |
| Inputs | Existing normalized BM25, dense and visual scores; byte SHA-256 `32b39d…3173b` |
| Grid | Exact existing W7 profiles |
| Global | One profile selected across these same 24 queries only |
| QARF | Existing relevance-informed query-level W7 selection |
| QPAF | Existing page-level coordinate ascent, fixed candidate order, at most two sweeps |
| Metrics | nDCG@10, Recall@1, Recall@3 and MRR@10 with existing page-ID tie-break |
| Uncertainty | Query bootstrap with 10,000 resamples and seed 20260820 |
| CPU | One local worker; one thread per numeric library |
| Time budget | 43,200 seconds (12 hours) from run-function entry |
| Attempts | One invocation; zero automatic retries |
| Output | `runs/vidoseek_w7_exploratory24_v1/`; must not exist before execution |
| Exclusions | Full W7/W66, training, new extraction, Modal/GPU, ViDoRe, P1-03 and formal phase decisions |

The 12-hour value is a cap, not a runtime promise. The exploratory-12 recovery computed eight absent queries in 6,023.918 seconds including validation and finalization. Linear scaling gives approximately 18,071.754 seconds (5.02 hours) for 24 queries, but observed query costs varied, so this estimate cannot guarantee completion.

## Implementation and verification

- [Guarded runner](../../../scripts/run_vidoseek_exploratory24.py) adds no new scientific search code. It calls the frozen query-sharded W7/QARF/QPAF implementation through the already-tested generic subset function.
- [Closed config](../../../configs/vidoseek_w7_exploratory24_v1.json) pins 25 source/evidence files, the environment, Git HEAD, query count, page count, bootstrap, resources, timeout and output directory.
- [Focused tests](../../../tests/test_vidoseek_exploratory24.py) cover deterministic disjoint selection, frozen-oracle fixture equivalence, source/scope/environment drift, closed approval, actor/thread guards, success manifests, timeout/failure evidence, missing outputs and no retry.
- [Read-only preflight](../../../artifacts/vidoseek_exploratory24_preparation/preflight.json) passed on the 6,149,670-row source bundle with 24 frozen queries and 129,240 selected pairs. It loaded no relevance and ran no page-level search.
- [Closed CLI check](../../../artifacts/vidoseek_exploratory24_preparation/closed_cli_refusal.json) refused before creating an output directory or attempt marker.

Focused tests passed 19 in 1.95 seconds. The final complete repository suite passed 232 in 19.62 seconds. Ruff check/format and `git diff --check` passed.

Prepared closed-state SHA-256 pins:

| File | SHA-256 |
| --- | --- |
| Proposal | `1f3d76ce5976a8568fac1119e7de5791af0550ddea8331641613ff7a91a086b2` |
| Runner | `7165db755bc9f53fec96489464113ae36274f666ea1d1180b33ab1953bca04e7` |
| Config | `401da348fc875ace578d3d0d1e09c49f0e5d446d3cb198543bd50c1b1bff3fd3` |
| Tests | `8d39d94d3066eef6c396014fd261d844dd6a06bc97ddcc9534f8d9698c94ada5` |

Base Git HEAD remains `99823b96c9afd52e11e7ddb001f5b74bf0a1e314`. The current worktree is intentionally uncommitted; the runner snapshots every pinned source byte and the tracked diff before starting the worker.

## Failure and completion rules

Approval, actor and thread checks run before source/input validation or writes. The output directory and `_ATTEMPTED.json` consume the only invocation before the worker reads selected relevance rows. Any existing output directory blocks every second launch.

The worker saves a hash-bound run plan, 24 Global checkpoints, one shared Global selection, and 24 query-level QARF/QPAF checkpoints. A timeout, worker failure, source/input drift, selection mismatch, invalid checkpoint, incomplete query coverage or missing final output writes `_INCOMPLETE.json` when possible and stops. No partial mean or scientific conclusion may be reported. Recovery or retry requires a separate reviewed amendment and approval.

Only `run_manifest.json` with `status=COMPLETE`, followed by an independent hash/ranking/metric/bootstrap review, permits reporting the result. The original 12-query and new 24-query results must remain separate because each selects Global over a different population.

## Exact command used

Run from the repository root with the pinned Python 3.13.7 environment:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
C:\Python313\python.exe scripts\run_vidoseek_exploratory24.py run --actor codex
```

The create-once output directory now refuses every second launch. The user does not need to run the command manually.

## Recorded approval scope

“Approve the prepared exploratory-24 page-level QPAF feasibility study: the 24 published additional ViDoSeek queries, all 5,385 pages/query, exact existing W7/Global/QARF/QPAF semantics, 10,000-resample bootstrap, one Codex local CPU invocation with one worker/thread, a 43,200-second cap and no automatic retry, followed by independent result verification and separate reporting from exploratory-12. Do not run full W7/W66, training, Modal/GPU, ViDoRe, P1-03, or change frozen P1-02 and formal phase gates.”

The user approved this exact scope with “ok I approved”. Every later execution step still requires a separate explicit human-approved amendment under the P1-02R-O1 stop condition in `Tasks.md`.
