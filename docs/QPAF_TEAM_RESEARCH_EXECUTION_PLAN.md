# QPAF Team Research Execution Plan

**Plan date:** 2026-09-10
**Status:** Proposed operational plan; no dependency gate or execution authorization is changed by this document.
**Authoritative dependency source:** [`Tasks.md`](../Tasks.md). [`PROJECT_TRACKING.md`](../PROJECT_TRACKING.md) remains the stakeholder-facing status view, and [`Context.md`](../Context.md) remains the scientific contract.

This plan does not authorize training, Modal/GPU use, a new oracle invocation, or a retry.

## 1. What the team can claim now

The current evidence supports calling QPAF **promising**, not **good enough** or **validated**.

| Evidence level | What is verified | Claim allowed now? |
|---|---|---|
| Exploratory oracle headroom | On the frozen 24-query ViDoSeek subset, W7 QPAF-minus-QARF is `0.05001054981241935`, CI95 `[0.008343883145752686, 0.10192128410987107]`; W66 is `0.03206569322602797`, CI95 `[0.002888476746941956, 0.07116543024082586]` | Yes: “QPAF has promising oracle headroom on this bounded subset.” |
| Learned confirmation | No learned QPAF checkpoint, matched learned comparison, or confirmation result exists | No |
| Robustness | No three-seed learned benchmark exists | No |
| Efficiency | No learned-QPAF latency or CUDA-memory measurement exists | No |
| Generalization | No sealed external evaluation of a frozen learned checkpoint exists | No |

Use this precise current statement:

> On a frozen 24-query exploratory ViDoSeek subset, relevance-informed QPAF oracle search produced positive mean nDCG@10 headroom over QARF under both W7 and W66, with positive query-bootstrap lower bounds. This motivates learned-QPAF evaluation but does not establish learned, deployable, or generalizable improvement.

Do not currently write “QPAF outperforms QARF,” “QPAF is good enough,” or “QPAF is deployable” without the words **oracle**, **exploratory subset**, and **upper bound**.

## 2. Definition of “good enough”

The team may make the core learned-method claim only after all five conditions pass:

1. **Matched comparison:** learned QARF and learned QPAF use identical candidate rows, data split, 13 label-free features, loss, optimizer, early stopping, seed set, image, GPU class, and compute budget.
2. **Quality:** across seeds, QPAF-minus-QARF mean nDCG@10 is at least `0.01`, and the query-bootstrap 95% lower bound is greater than `0` on confirmation data. QPAF must also beat the strongest deployable baseline under the same evaluation protocol.
3. **Stability:** exactly three preregistered seeds (`20260820`, `20260821`, `20260822`) complete; no best-seed selection is allowed.
4. **Operational envelope:** no NaN/Inf; median added fusion latency is at most `10.0 ms/query`; peak learned-fusion CUDA allocation is below `1.50 GiB`; checkpoint reload reproduces fused scores within `1e-7`.
5. **Independent audit:** data/config/code/checkpoint hashes, per-query predictions, metrics, confidence intervals, and run manifests pass review by someone other than the run operator.

Passing these conditions supports: “Learned QPAF improves over the matched QARF baseline on the confirmation protocol.” A claim of **external generalization** additionally requires M6. A claim of **deployment readiness** still requires a separately defined downstream integration and production evaluation.

## 3. Team roles

These are responsibility hats; one person may hold multiple hats, but the experiment operator and independent verifier should be different people for accepted result runs.

| Code | Role | Primary responsibility |
|---|---|---|
| RL | Research lead | Own hypotheses, protocol amendments, gates, scope, and final claim language |
| DE | Data/protocol engineer | Own dataset splits, score bundles, feature inputs, schemas, hashes, and leakage checks |
| ME | Method engineer | Implement the 13-feature builder, QARF/QPAF gates, loss, serialization, and unit tests |
| EO | Experiment operator | Prepare reviewed commands; run only approved Modal/CPU jobs; preserve manifests and telemetry |
| IV | Independent verifier | Recompute rankings/metrics/CI, verify hashes and coverage, and issue PASS/FAIL review |
| RA | Research analyst/writer | Maintain tables, error analysis, ablation interpretation, limitations, and report text |

No result enters a paper table until RL accepts an IV review. EO completion receipts alone are not sufficient.

## 4. Critical path and milestones

Target dates are planning targets, not runtime guarantees or execution approvals.

`G0 protocol decision → M1 features → M2 gates/loss → M3 training readiness → M4 matched one-seed confirmation → M5 three-seed benchmark → M6 ablation/CARF + sealed external validation → M7 reproducibility release`

| ID | Target | Owner | Deliverable | Exit gate |
|---|---|---|---|---|
| G0 | 2026-09-12 | RL + IV | Reviewed Phase 1 path/amendment resolving how the blocked P1-03 dependency will be handled | `proceed` opens the next approved task; `revise` loops through a new preregistration; `stop` terminates the QPAF path; without a decision all P2 execution remains blocked |
| M1 | 2026-09-18 | DE + ME | P2-01 deterministic 13-feature builder and focused tests | Feature contract passes; label permutation cannot change features; padded rows are zero; outputs are finite |
| M2 | 2026-09-22 | ME + IV | P2-02 linear QARF/QPAF gates, scorer, masked listwise loss, gradient and serialization tests | Zero initialization gives equal weights; gradcheck tolerance is met; masks and boundaries are finite |
| M3 | 2026-09-25 | DE + EO + IV | Frozen confirmation split/cache, matched QARF/QPAF configs, Modal contract tests, reviewed execution package | All hashes and manifests pass; no train/validation overlap; live training remains closed until separately approved |
| M4 | 2026-10-01 | ME + EO + IV | Seed `20260820` learned QARF baseline followed by matched learned QPAF confirmation | QPAF quality, finite-value, latency, memory, checkpoint-reload, and provenance gates pass; otherwise halt and report |
| M5 | 2026-10-07 | EO + IV + RA | Three-seed P3-01 benchmark and 10,000-resample comparisons | All three seeds exist for QARF/QPAF; QPAF-minus-QARF is at least `0.01` with CI lower bound above `0` for a positive core claim |
| M6 | 2026-10-14 | ME + EO + IV + RA | P3-02 ablations including CARF K=2/3/4, plus P3-03 sealed external evaluation | Each learned ablation changes one factor; CARF clusters are label-free and frozen before qrels; external test is untuned and independently audited |
| M7 | 2026-10-18 | RL + IV + RA | Final tables, limitations, manifests, commands, and reproducibility package | Every result cell is measured or marked not run; oracle and learned rows are separated; package hashes verify from a clean checkout |

Status update (2026-09-10): G0 adopted only the post-hoc local method-core continuation recorded in `artifacts/qpaf_posthoc_continuation_decision_v1.json`. M1 and M2 are locally complete with `14` focused tests passing; this does not pass formal P1-03 or authorize M3 execution, training, Modal/GPU, or a learned-performance claim.

## 5. Milestone execution details

### G0 — Resolve the scientific gate before method execution

P1-03 is formally `BLOCKED` because P1-02 did not pass under its frozen protocol. The exploratory-24 results cannot silently convert it to `PASS`.

RL must prepare one explicit, reviewable choice:

- authorize a formally scoped discovery/confirmation protocol that can support the intended claim;
- approve a preregistration amendment that limits what the learned study may claim; or
- stop/revise the QPAF path.

IV verifies that the decision names the exact datasets, queries, hashes, thresholds, actor, resource limits, and evidence boundary. Before G0 passes, the team may discuss interfaces and review existing code, but it must not start optimizer-bearing work or report P2 progress as unblocked.

### M1–M2 — Build the smallest testable method core

Implementation order is fixed:

1. DE/ME implement P2-01 features without importing relevance or qrels.
2. IV checks deterministic order, permutation behavior, padding, constant channels, and finite values.
3. ME implements one shared fusion/loss core with separate `LinearQARFGate` and `LinearQPAFGate` inputs.
4. IV runs analytical fixtures, autograd comparison, masking tests, and checkpoint round-trip tests.

No optimizer step, trained checkpoint, local training, CARF implementation, MLP gate, or extra feature is part of M1–M2.

### M3 — Freeze the matched experiment before training

The QARF/QPAF comparison package must freeze:

- confirmation train/validation query IDs and data hashes;
- candidate depth, normalization, page-to-document mapping, and metrics;
- the same 13 features and loss;
- optimizer, learning rate, batch size, early stopping, gradient clip, seed, image, GPU class, timeout, and budget;
- output paths, append-only ledger behavior, checkpoint schema, telemetry, and failure markers.

IV compares the two resolved configs semantically and permits only the declared gate-granularity difference. RL reviews the exact live commands. Preparing this package does not authorize a Modal run.

### M4 — Run QARF first, then QPAF

EO runs the learned QARF baseline first because QPAF has no interpretable claim without it. After QARF passes checkpoint/provenance review, EO may run the matched QPAF job only under a separate explicit authorization.

Stop immediately on data-hash drift, query overlap, missing manifest fields, NaN/Inf, peak CUDA allocation at or above `1.50 GiB`, or QPAF validation gain below `0.01`. Do not tune thresholds or silently retry after observing the result.

### M5 — Establish robustness

Repeat the frozen protocol for seeds `20260821` and `20260822`; do not select the best seed. RA reports each seed, mean/std, per-query deltas, win/tie/loss, and 10,000-resample query-bootstrap intervals. IV recomputes the primary comparisons from saved predictions.

M5 determines the core conclusion:

| Observed result | Conclusion |
|---|---|
| Quality and operational gates pass | Learned QPAF is good enough for the stated confirmation protocol |
| Oracle headroom exists but learned QPAF does not beat QARF | The available headroom was not learned; prefer QARF and report a negative QPAF result |
| Quality passes but latency or memory fails | Research quality result only; not operationally good enough |
| Seed variance or CI fails | Inconclusive; do not claim improvement |

### M6 — Explain the result and test generalization

CARF belongs here as an **oracle granularity ablation**, not as a co-primary learned method. DE freezes label-free clusters before any qrels join. IV verifies deterministic K=2/3/4 assignments and the qrels-leakage boundary. RA uses the QARF→CARF→QPAF pattern to discuss whether page-level flexibility is necessary.

Other ablations change one factor at a time. The sealed external evaluation uses frozen checkpoints and hyperparameters; no external qrels may influence model selection. A confirmation-only success must be reported as dataset-specific if external evidence is neutral or negative.

### M7 — Release only auditable claims

The final package must map every table number to a dataset hash, code commit, resolved config, seed, run ID, prediction artifact, and independent-review record. Tables must visually separate deployable learned methods from relevance-informed oracle upper bounds.

## 6. Team cadence and handoffs

- **Monday:** RL confirms the active milestone, scope, owner, dependency state, and stop conditions.
- **Daily:** each owner records `done / next / blocked / evidence path`; metrics without an artifact path are treated as unverified.
- **Before a live run:** EO presents the exact command, actor, commit, config hash, data hash, timeout, resource limits, invocation count, and retry rule for review.
- **After a live run:** EO freezes outputs; IV performs an independent reconstruction before RA updates any result table.
- **Friday:** RL runs a gate review and records exactly one state: `PASS`, `BLOCKED`, or `KILLED`.

Every handoff must contain: purpose, inputs, outputs, exact command, environment, hashes, tests, measured result or failure, boundaries, and next authorized action.

## 7. Immediate team action

G0's local-only continuation and the P2-01/P2-02 method core are complete. On 2026-09-10 the user explicitly approved **M3 local preparation only**. The initial hash-bound review package is in `docs/VIMDOC_M3_LOCAL_PACKAGE.md` and `configs/vimdoc_m3_local_v1.json`. It has a read-only preflight and matched config/synthetic tests, not a live extractor or trainer. OCR, duplicate asset identity, proposed split/hyperparameters, baseline/held-out protocol and runtime/resource contracts remain unresolved; M3 execution readiness is `BLOCKED`. The historical score-input probe is not a fresh remote-state check, and no real ViMDoc score cache was verified by this preparation.

Modal/GPU score extraction, optimizer steps, P2-03/P2-04 execution, and any learned-improvement claim remain closed until the exact resource and execution package receives separate approval. CARF remains deferred to M6/P3-02.
