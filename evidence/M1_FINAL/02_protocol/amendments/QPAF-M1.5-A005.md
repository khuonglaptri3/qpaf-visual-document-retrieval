# QPAF-M1.5-A005 — Static-anchored residual gate (QPAF-SA) confirmed on ViMDoc

> **Protocol:** `QPAF-M1.5-v1` (scoped successor `m1.5-002`)
> **Date:** 2026-10-28
> **Requester:** Tấn Phát (Research Lead), after G3 `LIMITED-CLAIM` (M5.9)
> **Affected contracts:** gate parameterization, training loss, checkpoint selection, held-out evaluation dataset
> **New method IDs:** `QPAF-SA-v2` (page-level) and matched `QARF-SA-v2` (query-level)
> **Status:** `PROPOSED / RESEARCH_LEAD_APPROVAL_PENDING / INDEPENDENT_REVIEW_PENDING`
> **Registry classification:** `governance` / `governance_record`

This file is the create-once record for amendment A005. Like A003 and A004, it is a
separate file, because `protocol_amendments.md` and `amendments_after_import.md` are
hash-bound and are not edited. It authorizes no run, data access or GPU use. Every
stage below needs its own authorization.

## 1. Identity before implementation

Recorded before any A005 code, probe or run exists, on branch `feature/a005-qpaf-sa`
at develop `1cecddb63a03b629bf89af4859f85eb23a2f59c5`.

| File | SHA-256 |
| --- | --- |
| `src/qpaf/m12/model.py` (`FusionGate`, v1 gate) | `05c0370343a14b70b1db37e3d2bf6fd852c4ea67f7a967af52fa0ff498adcc3e` |
| `src/qpaf/m12/losses.py` (A001 loss) | `18debc316b02146c38c36a6b1021f0db5e3ba9be55ffdb4c8be153cd11ce5395` |
| `src/qpaf/m24/config.py` | `5d730b9cb1ba8971ae972729401013e0bb0ccce81310615e2a9088963eb53841` |
| `src/qpaf/m24/trainer.py` | `242fbcdc3a1cf44c81d29ef7be19aac256b29e5226f870cdf1cee889ff9df7d4` |
| `results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/train_fit.json` (ViDoSeek static `[0, 0.1, 0.9]`) | `51e1bb020cf295d8492eea9a9bd55980ac9b944e487881e5e84d89913c78d785` |
| `evidence/revisions/m4.3-001/method_freeze.json` (QPAF-v1 freeze) | `4015c74b54f5ac3d2cbce54f8424c0e9329c009595e81ced5eab0039af7761cc` |
| `evidence/revisions/m4.1-001/manifest.json` (ViMDoc ID seal) | `03673b16ef666c6d8756939efebdbcc73ff1c61a5abcff6c743400e5da6c4668` |
| `configs/vimdoc_m3_local_v1.json` (ViMDoc preparation, not adopted) | `0a68c19688519822e4ac58afa51e08ca43ad6350d849f642bac23115bc64be9d` |
| `evidence/revisions/m5.9-001/decision.json` (G3) | `c87033bf935ded49cc3eea79b2de55d252a182662fb1e877a0871d79e531390c` |
| `evidence/revisions/m5.9-001/owner_confirmation.json` | `0586b151496206746f501f09af1b08fc3330d385ca76d435cb166c40101503b1` |
| `evidence/revisions/m5.10-001/decision.json` (G3A) | `a82cfc923fd9d17bc445e2b957a32287e9e4d08191943c5a2ae2b0f7a2e00698` |
| `evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A004.md` | `d83a596d5bd7e4e45e8535b6f74064cb4814b1c2b138c6467f33ee7bf35bbbfc` |

## 2. Old and new values

### 2.1 Gate

**Old (v1):** `w = softmax(Linear(x) / T)` per page, with `T = 1.0` and the 13 `qpaf13_v1`
features `x`. The linear layer starts from a random initialization, so nothing ties the
gate to a good fusion.

**New (SA):** `w = softmax((log(w̄ + ε) + Δθ(x)) / T)`, with:

- `w̄`: the train-fitted static weights for the dataset being trained.
- `ε = 1e-3`, fixed.
- `Δθ`: a 13→3 linear layer whose weight and bias are initialized to exactly zero.
- `T = 1.0`, as in v1.

At epoch 0 the gate returns `(w̄ + ε)/(1 + 3ε)` for every page. For ViDoSeek this is
`[0.000997, 0.100698, 0.898305]`. So training starts from the static baseline and only
learns per-page deviations from it.

`QARF-SA-v2` uses the same anchor and the same `Δθ`. Its only difference is that `Δθ`
reads the query-mean features, as in v1. `gate_granularity` therefore stays the only
intended difference in the matched comparison.

### 2.2 Loss

**Old (A001):** pairwise logistic on page scores, `query_mean`.

**New:** a multi-positive listwise softmax cross-entropy on the evaluation unit, with a
learned temperature:

1. Unit scores:
   - **ViMDoc:** `s_d = max` over the fused page scores of document `d`. This is the
     frozen M4.1 aggregation.
   - **ViDoSeek:** each page is its own unit.
2. Query loss: `−log( Σ_{d∈R} exp(s_d/τ) / Σ_{d∈C} exp(s_d/τ) )`. Here `R` is the
   relevant units in the train qrels and `C` is the query's active candidates.
3. `τ = exp(η)`. `η` is one learned scalar per model, initialized to `0` (`τ = 1`) and
   clamped to `[log 1e-3, 0]`.
4. Queries are averaged with equal weight.

A004 rejected the listwise loss because it "needs a new temperature to be top-focused
(a tuned hyperparameter)". A005 answers this by fitting `τ` on train labels together
with `Δθ`. Validation is never used to tune `τ`. Its initial value and bounds are fixed
above.

### 2.3 Checkpoint selection

**Old:** max validation nDCG@10 over epochs 1–20, earlier epoch on ties.

**New:** max validation nDCG@10 over epochs **0–20**, earlier epoch on ties. Epoch 0 is
the anchor itself, so a model that learns nothing useful falls back to the static
baseline on validation.

### 2.4 Held-out evaluation

**Old:** ViDoSeek TEST-172. It was opened once in R7 and is now spent.

**New:** the ViMDoc confirmation split sealed in M4.1. The M4.1 frozen document-level
contract applies unchanged:

- **Splits:** 1,600 train, 400 validation and 8,904 confirmation IDs.
- **Document mapping:** `remove_final_underscore_segment`, with `max_fused_page_score`
  as the document score.
- **Ranking and IDCG:** ties broken by ascending document ID; IDCG over all relevant
  documents.
- **Primary metric:** `mean_per_query_document_ndcg_at_10`.

### 2.5 Unchanged

| Unchanged | Value |
| --- | --- |
| Features | `qpaf13_v1` |
| Optimizer | Adam, learning rate 0.01, weight decay 0, gradient clip 5.0 (`η` included) |
| Budget | batch size 16, 20 epochs |
| Runtime | float64 CPU, 1 thread, deterministic algorithms |
| Seeds | `20260820`, `20260821`, `20260822`; only `training.seed` changes |
| Statistics | paired query bootstrap after seed averaging, 10,000 resamples, seed `20260820`, percentile CI95, W/T/L, top-5% gain share |
| Claim rules | `frozen_protocol.md` §5 items 1–9 and `statistical_policy.md` §6 |

`ε`, the initial value and bounds of `η`, and the selection range are fixed here
before implementation. No other value will be tried or selected.

## 3. Why the change is needed and why no-change is invalid

- **TEST-172.** QPAF-v1 does not exceed `train_fitted_static`: −0.006748, CI95
  [−0.019028, +0.005269], W/T/L 7/152/13 (M5.7). G3 is `LIMITED-CLAIM`.
- **Validation (M4.4).** The same gap was already visible: −0.005134, CI95
  [−0.013457, +0.002783].
- **Two causes, both found on train or validation only:**
  1. **The loss is misaligned with the metric.** On the ViDoSeek train grid the A001
     loss has Spearman(loss, nDCG@10) = +0.537, and its minimum is BM25-only (M4.6).
  2. **The gate has no anchor.** With a randomly initialized gate, a misaligned loss can
     pull the model below a static fusion the protocol treats as a baseline.
- **Room above the baseline.** On validation, the label-using per-page W66 oracle
  reaches 0.9401 against the static 0.8714.
- **Why no change is invalid.** The v1 result is final for ViDoSeek. Re-running v1
  cannot change it, and re-scoring anything on TEST-172 would be result shopping. A
  learned-fusion improvement can only be tested with a new method on a still-sealed
  held-out set.

**Rejected alternatives:**
- Tuning learning rate, epochs, `T` or `ε` on validation: result shopping.
- A second pairwise variant: A004 already failed its gate.
- Evaluating v2 on TEST-172 in any form: it is spent.
- Adding features: M5.6 shows the auxiliary feature groups move nDCG@10 by at most
  ±0.002, and new features would need their own amendment.

## 4. Post-hoc status and controls

**This amendment is post hoc.** It is proposed on 2026-10-28, after TEST-172 was opened
in R7 and after M5.7, G3 and G3A were seen. It is motivated by the negative TEST-172
result. Controls:

1. **No ViDoSeek TEST-172 access for A005.** No A005 model is ever scored on TEST-172,
   not even as an exploratory row. TEST-172 per-query results are not used for any
   design choice.
2. **One method, fixed above.** No alternative anchor, loss, `ε`, temperature schedule
   or selection rule will be tried. Stage failures stop the amendment; they do not
   trigger a redesign.
3. **Preregistered train-only alignment gate.** It runs twice: in Stage 0 on ViDoSeek
   train (799 queries, page unit) and in Stage 2 on ViMDoc train (1,600 queries,
   document unit).
   - For each point `w` of the 66-point static grid, compute the profile loss
     `L(w) = min over τ ∈ [1e-3, 1]` of the A005 loss. Use deterministic golden-section
     search, 60 iterations.
   - Pass needs both: Spearman(`L`, train nDCG@10) `<= −0.5`, and the grid point with
     the lowest `L` within `0.01` of the grid's best train nDCG@10.
   - These are the same thresholds A004 used and failed.
   - No validation, test or confirmation label is read.
4. **No-deviation stop rule.** If validation selects epoch 0 for at least two of the
   three `QPAF-SA-v2` seeds, record `NO_LEARNED_DEVIATION` and stop. The ViMDoc
   confirmation split is then not opened.
5. **One confirmation opening.** It happens after every Stage 1–4 record has an
   independent review, with one attempt and no automatic retry (M4.1 access gate). No
   method, seed, checkpoint or baseline choice is made after it.

## 5. Stages and stop rules

| Stage | Content | Data | Needs | Stops if |
| --- | --- | --- | --- | --- |
| 0 | ViDoSeek train-only alignment probe | ViDoSeek train qrels (799) | Research Lead authorization | gate fails |
| 1 | ViMDoc inputs: OCR text for BM25/BGE-M3 over 70,080 pages; BM25, BGE-M3, ColQwen2.5 scores; candidate pool; label-free cache receipt; verified document-qrels contract and evaluator hash; M4.1 document-overlap analysis | page images (17.5 GB archive), no confirmation labels | separate resource review and GPU authorization | inputs fail verification |
| 2 | ViMDoc train-only alignment probe | ViMDoc train qrels (1,600) | authorization | gate fails |
| 3 | ViMDoc deployable baselines: BM25, BGE-M3, ColQwen2.5, uniform CombSUM, RRF k60, `train_fitted_static` refit on ViMDoc train, learned QARF; co-strongest selected on validation (`baseline_policy.md`) | train + validation | authorization, independent review | — |
| 4 | Matched `QARF-SA-v2` / `QPAF-SA-v2` × 3 seeds; fresh-process reload ≤ 1e-7, finite outputs | train + validation | one authorization per run, QARF reviewed before matched QPAF | no-deviation rule |
| 5 | One sealed ViMDoc confirmation: 7 baselines, QARF-SA ×3, QPAF-SA ×3 | confirmation (8,904) | separate result-bearing authorization; all prior reviews | — |
| 6 | Three-seed aggregation and a gate decision with the frozen §5 criteria | Stage 5 outputs | independent review, Research Lead confirmation | — |

`w̄` for ViMDoc is the Stage 3 `train_fitted_static` refit on ViMDoc train only. The
ViDoSeek weights `[0, 0.1, 0.9]` are used only in Stage 0. Optional context rows (QPAF-v1
retrained on ViMDoc) may be added only by their own authorization, and they are dropped
first under schedule pressure.

## 6. Leakage, fairness, statistics and claim impact

**Leakage**
- Train qrels enter only the loss, the static anchor fit and the alignment probe.
- Validation qrels enter only checkpoint and baseline selection.
- Confirmation qrels are read once, in Stage 5.
- OCR, retriever scores and candidates are label-free.
- The confirmation split shares the 1,247-document corpus with train and validation by
  design. The M4.1 overlap analysis must be completed and reviewed before Stage 5.

**Fairness**
- `QPAF-SA-v2` contains the static baseline as its epoch-0 special case, and both use
  the same train data.
- The baseline is still refit and selected independently, so QPAF-SA never chooses its
  own comparator.
- QARF-SA and QPAF-SA share the anchor, loss, config and seeds.

**Statistics:** unchanged (§2.5), in document units on ViMDoc.

**Claims**
- A positive core claim needs every §5 item on ViMDoc confirmation, including item 4:
  QPAF-SA beats every co-strongest ViMDoc baseline, with seed-averaged CI95 lower bound
  `> 0`.
- Any result must state `QPAF-SA-v2 / A005 / ViMDoc`.
- QPAF-v1 and its ViDoSeek TEST-172 result stay reported unchanged as the
  pre-amendment negative result.
- The latency gate stays `NOT_ESTABLISHED` unless a separately authorized measurement
  meets the 1,000-query rule.

## 7. Affected runs

| Run / record | Effect |
| --- | --- |
| M3.2–M5.10 (QPAF-v1, R7, G3, G3A) | Preserved unchanged and still reported. |
| ViDoSeek TEST-172 | Closed to A005. No new scoring. |
| ViMDoc M4.1 seal | Reused unchanged. Its access gate still applies. |
| New A005 namespaces (`QPAF-A005-PRB-*`, `-INP-*`, `-BSL-*`, `-MTH-*`, `-CNF-*`) | Created only by stage authorizations. |
| M6 (G4, thesis package) | If Stage 6 is not reviewed before M6.10, G4 reports QPAF-v1 only and lists A005 as incomplete future work. |

## 8. Approval

| Role | Name | State | Evidence |
| --- | --- | --- | --- |
| Research Lead | Tấn Phát | `PENDING` | The approval of this amendment must be the Research Lead's own words. Choosing to draft A005 is not an approval. |
| Independent reviewer | Thanh | `PENDING` | Required by the amendment procedure (step 6) before Stage 0 runs. |

After both approvals, a governance event referencing this file and its SHA-256 is
appended (procedure step 9). Until then, no A005 code is merged and no stage runs.
