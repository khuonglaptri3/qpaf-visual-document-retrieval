# QPAF-M1.5-A004 — ΔnDCG@10-weighted pairwise logistic loss

> **Protocol:** `QPAF-M1.5-v1` (scoped successor `m1.5-002`)
> **Date:** 2026-10-24
> **Requester:** Tấn Phát (Research Lead), M4.6 `revise_once`
> **Affected contract:** learned-training loss (A001), `[loss]` of the matched config
> **Effective loss ID:** `lambda_pairwise_logistic` / `query_mean` / `metric_cutoff = 10`
> **Status:** `PROPOSED / RESEARCH_LEAD_APPROVAL_PENDING / INDEPENDENT_REVIEW_PENDING`
> **Registry classification:** `governance` / `governance_record`

This file is the create-once record for amendment A004. Like A003 it is a
separate file, because `protocol_amendments.md` and `amendments_after_import.md`
are hash-bound and are not edited. A004 follows A001–A003 in the same ID
sequence. The design is
[`2026-10-24-m46-revise-once-design.md`](../../../../docs/superpowers/specs/2026-10-24-m46-revise-once-design.md).

## 1. Identity before implementation

Recorded before any A004 code or run exists, on branch
`feature/m4-6-revise-once` at `d7f4ba8ae47634864a5976970a741283b3b0eb3c`
(develop `d9b5c34` plus the M4.6 spec and plan).

| File | SHA-256 |
| --- | --- |
| `src/qpaf/m12/losses.py` (A001 loss) | `18debc316b02146c38c36a6b1021f0db5e3ba9be55ffdb4c8be153cd11ce5395` |
| `src/qpaf/m24/config.py` (accepts only the A001 loss) | `5d730b9cb1ba8971ae972729401013e0bb0ccce81310615e2a9088963eb53841` |
| `src/qpaf/m24/trainer.py` | `242fbcdc3a1cf44c81d29ef7be19aac256b29e5226f870cdf1cee889ff9df7d4` |
| `results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/inputs/shared_base.toml` | `3e58a867d11cebf72970cf0c141a90822cd7cbbdad65fb1e081cb14fa4889b58` |
| `evidence/M1_FINAL/02_protocol/amendments_after_import.md` (A001 row) | `6a7a0f6328e467c698771115affa58cac32b95ea889da1a91691661e4049dc49` |
| `evidence/revisions/m4.3-001/method_freeze.json` (QPAF-v1 freeze) | `4015c74b54f5ac3d2cbce54f8424c0e9329c009595e81ced5eab0039af7761cc` |
| `docs/superpowers/specs/2026-10-24-m46-revise-once-design.md` | `834c1afc6e8c7c35d99f0693466b3b8b314e8fef1fe5d7e666565fc3e560b6c4` |

## 2. Old and new values

**Old (A001, `pairwise_logistic` / `query_mean`):** for each query with at least
one positive and one negative active candidate, the mean of
`softplus(s_negative − s_positive)` over all positive–negative pairs; queries
are averaged with equal weight.

**New (`lambda_pairwise_logistic` / `query_mean` / `metric_cutoff = 10`):** for
each such query:

1. Rank active candidates by the current fused scores, detached, with
   `qpaf.m24.evaluator.rank` (score descending, page ID ascending).
2. Give position `p` (0-based) the discount `d(p) = 1/log2(p+2)` if `p < 10`,
   else `0`.
3. For positive `i` and negative `j`, `w_ij = |d(p_i) − d(p_j)|`. This is
   `|ΔnDCG@10|` for swapping them, times the query's IDCG, which cancels below.
4. Query loss `Σ w_ij · softplus(s_j − s_i) / Σ w_ij`. With both classes
   present some pair touches the top 10, so `Σ w_ij > 0`.
5. Average queries with equal weight, as before.

| Unchanged | Value |
| --- | --- |
| Features, gate | `qpaf13_v1`, linear, temperature 1.0 |
| Optimizer | Adam, learning rate 0.01, weight decay 0, gradient clip 5.0 |
| Budget | batch size 16, 20 epochs |
| Selection | max validation nDCG@10, earlier epoch on ties |
| Runtime | float64 CPU, 1 thread, deterministic algorithms |
| Seed | `20260820` (then `20260821`/`20260822` in M5) |

## 3. Why the change is needed and why no-change is invalid

A read-only probe on the 799 train queries (no training) found that the A001
loss ranks fusion weights against the primary metric:

- On the 66-point static grid, the A001 minimum is BM25-only `[1, 0, 0]`
  (loss 0.41520), which has the lowest train nDCG@10 (0.7290, rank 66/66). The
  nDCG-best point `[0, 0.1, 0.9]` ranks 48/66 by loss.
- Spearman(loss, train nDCG@10) = +0.537.
- Learned QARF converges to that minimum (epoch-20 weights ≈
  `[0.9985, 0.0006, 0.0008]`, loss 0.41524). QPAF also averages BM25 weight 0.949.

Fused scores lie in [0, 1], so the softplus works near its linear range and the
A001 loss behaves like a mean margin over all up-to-600 candidates. nDCG@10
only rewards the top of the list. Keeping A001 means the next seeds and the
confirmation test measure a method trained for the wrong ranking; the M4.4
validation table already shows QPAF below `train_fitted_static`
(−0.005134, CI95 [−0.013457, +0.002783]).

Rejected alternatives: the original masked listwise loss needs a new
temperature to be top-focused (a tuned hyperparameter); tuning learning rate,
epochs or gate temperature on validation is result shopping.

## 4. Post-hoc status and controls

**This amendment is post hoc.** It is proposed on 2026-10-24 after the M4.4
validation table, the M4.5 audit and the train probe were seen. Controls:

- One loss, fixed above before implementation. No variant (other cutoff,
  scale, temperature or loss family) will be tried or selected.
- A train-only alignment gate is preregistered in the design before it runs:
  Spearman(loss, train nDCG@10) `<= −0.5` and the minimum-loss grid point within
  `0.01` of the grid's best train nDCG@10. Failing either stops the revision
  without training.
- Stop rule: one revision only. G2 (frozen criteria, unchanged) decides QPAF-v2
  vs QARF-v2; a non-`GO` result leads to `negative_qpaf_result`.

## 5. Leakage, fairness, statistics and claim impact

- **Leakage:** labels enter only the training loss, as under A001. Pair weights
  use train labels and the model's own scores; no validation, test or
  confirmation label is read by training or the gate.
- **Matched comparison:** QARF and QPAF use the identical loss, config and
  seed. `gate_granularity` remains the only intended difference.
- **Statistics:** unchanged (paired 10,000-bootstrap CI, W/T/L, concentration).
- **Claim boundary:** results under A004 must state the loss ID. QPAF-v1 and
  its M4.3–M4.5 records stay reported as the pre-revision result.

## 6. Affected runs

| Run / record | Effect |
| --- | --- |
| M3.2 QARF-v1, M3.4 QPAF-v1 | Preserved unchanged and still reported. |
| M4.3 freeze, M4.4 table, M4.5 audit | Preserved; they describe v1. |
| New `QPAF-M4_6-MTH-001` (QARF-v2), `-002` (QPAF-v2) | Mandatory if the gate passes; new namespace and separate authorization. |
| G2 replay on v2 | Mandatory before M4.7. |
| Seeds `20260821`/`20260822` (M5) | Must use the v2 config if v2 is adopted. |

## 7. Approval

| Role | Name | State | Evidence |
| --- | --- | --- | --- |
| Research Lead | Tấn Phát | `PENDING` | Approval of this amendment must be the Research Lead's own words. The M4.6 direction confirmation does not approve A004. |
| Independent reviewer | Thanh | `PENDING` | Required by the amendment procedure step 6 before any v2 training run. |
