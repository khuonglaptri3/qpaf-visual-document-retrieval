# M4.6 — Main-method direction (`revise_once`)

**Owner:** Tấn Phát (Research Lead).
**Final direction:** `continue_qpaf`, confirmed verbatim on 2026-10-24T14:59:12Z
in [`final_confirmation.json`](final_confirmation.json) ("I approved to be
continue with continue_qpaf"), event `QPAF-REG-20261024-0005`. The M4.3-frozen
QPAF-v1 goes to M4.7 unchanged, with the loss-alignment limitation stated.

**How it got there:** the Research Lead first chose `revise_once`
([`owner_confirmation.json`](owner_confirmation.json)). The preregistered
train-only gate for amendment A004 failed, so A004 is not adopted and no v2
model was trained; [`decision.json`](decision.json) keeps its create-time
status `REVISION_GATE_FAILED_RETURN_TO_RESEARCH_LEAD`, which returned the choice
to the Research Lead. No test or confirmation label was opened.

Records: [`decision.json`](decision.json) (create-once, pins every input),
[`loss_alignment_probe.json`](loss_alignment_probe.json),
[`governance_events.jsonl`](governance_events.jsonl) (`QPAF-REG-20261024-0002`
to `-0005`), amendment
[`QPAF-M1.5-A004.md`](../../M1_FINAL/02_protocol/amendments/QPAF-M1.5-A004.md)
and the design
[`2026-10-24-m46-revise-once-design.md`](../../../docs/superpowers/specs/2026-10-24-m46-revise-once-design.md).

## Why `revise_once` was considered

| Evidence (validation, seed `20260820`) | Value |
| --- | ---: |
| `train_fitted_static` nDCG@10 (strongest deployable) | 0.871414 |
| Frozen QPAF-v1 nDCG@10 | 0.866280 |
| Learned QARF-v1 nDCG@10 | 0.752147 |
| QPAF − `train_fitted_static`, CI95 | −0.005134, [−0.013457, +0.002783] |

A train-only probe (799 queries, 66-point static grid) showed that the A001
`pairwise_logistic` loss orders fusion weights against nDCG@10. A004 proposed
one fix: `|ΔnDCG@10|` pair weights (`lambda_pairwise_logistic`).

## Gate result (`loss_alignment_probe.json`)

| Train grid (66 points) | A001 (v1) | A004 (v2) | Gate |
| --- | ---: | ---: | --- |
| Spearman(loss, nDCG@10) | +0.537 | **+0.361** | G-A needs `<= −0.5`: **FAIL** |
| Minimum-loss weights | `[1.0, 0.0, 0.0]` | `[0.6, 0.0, 0.4]` | |
| nDCG@10 at the minimum vs grid max 0.8642 | 0.7290 | **0.7908** | G-B needs `>= 0.8542`: **FAIL** |

A004 moves the minimum toward the visual channel but still ranks the nDCG-best
point `[0.0, 0.1, 0.9]` 45th of 66 by loss. The v1 numbers reproduce the earlier
exploratory probe exactly. The loss and both thresholds were fixed in the design
before the run and were not changed afterwards. Under the stop rule no second
loss is tried.

## Timing and limits

- `revise_once` was chosen after the M4.4 table, the M4.5 audit and the probe
  were seen; it is post hoc, and so are the two gate thresholds, which were set
  before the gate ran.
- The probe uses train labels only; QARF/QPAF checkpoints were scored but not
  retrained. It shows the loss–metric misalignment on static weights; it does
  not measure what a trained v2 gate would reach.
- QPAF-v1, its M4.3 freeze and the M4.4/M4.5 results are unchanged and remain
  the reported method result.

## Next step

M4.7 freezes the robustness path for QPAF-v1 (M4.3 freeze `4015c74b…61cc`,
A001 loss). It must state that the A001 loss orders static weights against
nDCG@10 (Spearman +0.537, minimum at BM25-only) and that A004 did not pass its
gate. `baseline_policy.md` §3.5 (QPAF against `train_fitted_static`) is decided
on confirmation. Thanh's review of A004 and the gate result is still pending.

## Read-only replay

With the M4.2 payload restored (`scripts/run_m44_evaluation.py restore-inputs`):

```powershell
.venv/Scripts/python.exe -X utf8 scripts/probe_m46_loss_alignment.py --verify evidence/revisions/m4.6-001/loss_alignment_probe.json
.venv/Scripts/python.exe -X utf8 scripts/decide_m46_direction.py --verify evidence/revisions/m4.6-001
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m46_losses tests.test_m46_trainer tests.test_m46_probe tests.test_m46_direction
```
