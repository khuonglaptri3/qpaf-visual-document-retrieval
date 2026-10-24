# M4.6 — Main-method direction: `revise_once` (loss revision)

Owner: Tấn Phát. Base: develop `d9b5c34` (PR #37, M4.5 merged).
Branch: `feature/m4-6-revise-once`. No independent acceptance is asserted here.

## Decision and authority

Workbook Milestones row 53 asks M4.6 for a `continue_qpaf / revise_once /
negative_qpaf_result` decision. The Research Lead chose `revise_once` in the
working session. Their reply, recorded verbatim (received about
2026-10-24T09:02Z):

> I confirm to proceed on revise_once cause it potentially lead to better results

The reply states an expected benefit. The technical basis below, the train-only
gate and the stop rule are what bound the revision; a better result is not
assumed and does not change any rule.

## Evidence basis

- M4.4/M4.5 (validation, 171 queries, seed `20260820`, accepted by Thanh):
  QPAF − `train_fitted_static` nDCG@10 = −0.005134, CI95 [−0.013457, +0.002783].
  Learned QARF ranks 6 of 7 deployable rows (0.752147).
- Loss-alignment probe (train, 799 queries, read-only; to be committed as
  `scripts/probe_m46_loss_alignment.py` and its output in the evidence folder):
  - On the 66-point static grid, the `pairwise_logistic` minimum is BM25-only
    `[1, 0, 0]` (loss 0.41520), which has the **lowest** train nDCG@10 (0.7290,
    rank 66/66). The nDCG-best point `[0, 0.1, 0.9]` ranks 48/66 by loss.
  - Spearman(loss, train nDCG@10) = +0.537: lower loss goes with lower nDCG.
  - QARF converges to that minimum: epoch-20 weights ≈ `[0.9985, 0.0006, 0.0008]`,
    loss 0.41524. Epoch 1 (the selected checkpoint) is the least converged.
  - QPAF also averages BM25 weight 0.949 and recovers nDCG through page-level
    switching.

So the matched comparison is fair but both methods optimize an objective that
rewards the wrong ranking. That is a defect in the shared training objective,
not in the gate granularity, and it is the only thing this revision changes.

**Timing disclosure.** The revision is chosen after the M4.4 validation table,
the M4.5 audit and the train probe were seen. It is post hoc. Validation and
confirmation outcomes did not choose the loss form; it is fixed below before
any new training or gate run.

## Approaches

1. **ΔnDCG@10-weighted pairwise logistic (LambdaRank-style): selected.** Keeps
   the existing pairwise form and `σ = 1`; adds pair weights from the primary
   metric, so pairs that cannot change the top 10 contribute nothing. The only
   new constant is the cutoff 10, which is the frozen primary metric.
2. Masked listwise softmax cross-entropy (the original v1 loss replaced by A001):
   rejected. Fused scores lie in [0, 1], so at temperature 1 the softmax over up
   to 600 candidates is nearly uniform and the loss again approximates an
   all-candidate mean margin. Making it top-focused needs a temperature, which
   would be a new tuned hyperparameter.
3. Tune learning rate, epochs or temperature on validation: rejected as result
   shopping (`frozen_protocol.md` §2, out of scope).

## Revision: amendment `QPAF-M1.5-A004`

One change, applied identically to QARF and QPAF:

- Loss `pairwise_logistic` → `lambda_pairwise_logistic`, reduction `query_mean`.
- For each learnable query: rank active candidates by the current fused scores
  (detached) with `qpaf.m24.evaluator.rank`. For each positive `i` and negative
  `j`, `w_ij = |ΔnDCG@10|` from swapping their positions, with the IDCG of
  `min(relevant_total, 10)` binary gains. The query loss is
  `Σ w_ij · softplus(s_j − s_i) / Σ w_ij`. If both classes exist, some pair
  touches the top 10, so `Σ w_ij > 0`; if not, raise.
- Everything else stays: 13 features, linear gate, temperature 1.0, Adam,
  learning rate 0.01, weight decay 0, batch size 16, gradient clip 5.0, 20 epochs,
  max-validation-nDCG@10 selection with earlier-epoch ties, float64 CPU,
  deterministic algorithms, seed `20260820` and data order.

A004 is a create-once file `evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A004.md`
in the A003 format: identity hashes before implementation, old/new values,
necessity, leakage/fairness/statistical impact, affected runs, Research Lead
approval and a pending independent-review field. Existing ledgers are not
edited.

## Frozen sources stay byte-identical

The M4.3 freeze pins ten method sources, including `qpaf/m24/config.py`,
`qpaf/m24/trainer.py` and `qpaf/m12/losses.py`. They are not edited, so
`freeze_m43_qpaf.py --verify` keeps passing. New code lives in `src/qpaf/m46/`:

- `losses.py`: `lambda_pairwise_logistic_loss(scores, labels, mask, relevant_total)`,
  returning the existing `PairwiseLoss` fields.
- `config.py`: accepts only `loss = {name = "lambda_pairwise_logistic",
  reduction = "query_mean", metric_cutoff = 10}` and validates every other field
  by calling `qpaf.m24.config.validate` on a copy with the v1 loss.
- `trainer.py`: the M2.4 epoch loop with the loss injected. It reuses
  `build_model`, `learnable`, checkpoints, `predict` and `evaluate` unchanged.
- `configs/m4.6/shared_base_v2.toml`: the M4.2 `shared_base.toml` with only the
  loss section changed.

## Train-only alignment gate (preregistered here)

Run once, before any training, with `scripts/probe_m46_loss_alignment.py` on the
799 train queries and the 66-point static grid. Validation, test and
confirmation labels are not used. Both must hold for the new loss:

- G-A: Spearman(loss, train nDCG@10) `<= −0.5`.
- G-B: the minimum-loss grid point has train nDCG@10 `>=` grid maximum `− 0.01`.

These two thresholds are new and are fixed here, before the run. The output
also records the old loss on the same grid for comparison.

If either check fails, `revise_once` stops: no training, the record says
`REVISION_GATE_FAILED`, and the direction returns to the Research Lead to
choose `continue_qpaf` or `negative_qpaf_result`. No second loss is tried.

## Execution (separate authorization)

After A004 has the Research Lead approval and the gate passes, the team requests
authorization for two matched local CPU runs (`QPAF-M4_6-MTH-001` QARF-v2 and
`-002` QPAF-v2), same budget as M3.2/M3.4 (3,600 s wall time, 1 invocation, no
retries, $0). Thanh's independent review of A004 is required before the runs,
per the amendment procedure step 6.

## Stop rule (preregistered here)

After the runs and their post-run verification:

1. Apply the frozen G2 rule (`evidence/revisions/m3.7-001/criteria.json`,
   unchanged) to QPAF-v2 vs QARF-v2.
2. G2 `NO-GO–PIVOT` or `PARTIAL–INVESTIGATE` → `negative_qpaf_result`. There is
   no second revision.
3. G2 `GO` → QPAF-v2 replaces QPAF-v1 as the main method for M4.7, whatever its
   validation delta against `train_fitted_static`. v1 and v2 are not picked
   between on validation. `baseline_policy.md` §3.5 is still decided on
   confirmation, and learned QARF-v2 replaces v1 as the learned baseline.
4. QPAF-v1, its M4.3 freeze and the M4.4/M4.5 results remain reported and are
   never deleted.

## Records

`evidence/revisions/m4.6-001/`:

- `decision.json` (create-once): branch `revise_once`; SHA-256 pins of the G2
  decision and confirmation, the M4.3 freeze and confirmation, the M4.4 MTH/ORC
  manifests, the M4.5 verification and acceptance, the probe output, A004 and
  this spec; key numbers read from those files; the timing disclosure; the gate
  and stop rules; `authorizes_execution: false`.
- `owner_confirmation.json`: the verbatim reply above, `recorded_by` Claude
  Code at the Research Lead's request.
- `loss_alignment_probe.json`: the v1-loss probe already run, then the gate run.
- `governance_events.jsonl`: `DECISION_RECORDED`, then `AMENDMENT_PROPOSED` and
  `REVISION_GATE_RECORDED`, IDs continuing from `QPAF-REG-20261024-0001`,
  experiment `QPAF-M4_6-GAT-001`, class `governance` / `governance_record`.
- `README.md`.

`scripts/decide_m46_direction.py` writes `decision.json` create-once from a
clean tracked tree and `--verify` recomputes it read-only. It refuses unless G2
is confirmed `GO`, the M4.3 freeze is confirmed, M4.5 is `ACCEPTED` and every
pin matches.

## Claim boundary

Validation only, seed `20260820`, checkpoints selected on validation. No test
or confirmation label is opened. This task makes no performance claim. Seeds
`20260821`/`20260822` and the M4.7 freeze come later.

## Verification

- `tests/test_m46_losses.py`: hand-computed weights and loss on small cases,
  ties follow `rank`, zero weight outside the top 10, finite-difference
  gradient check, and refusal for invalid inputs.
- `tests/test_m46_direction.py`: only confirmed G2 `GO`, confirmed M4.3 and
  accepted M4.5 are allowed; pin drift refuses; create-once and `--verify`
  equality.
- The M4.3 freeze `--verify` still passes, the focused M3.x/M4.x tests pass,
  and the full suite runs under `.venv`. Failures are compared with
  `results/m4.2/verification/active-primary-failed-nodeids.json`.

## Out of scope

Training before authorization, other loss forms, hyperparameter changes,
seeds `20260821`/`20260822`, M4.7, and workbook status edits unless asked.
