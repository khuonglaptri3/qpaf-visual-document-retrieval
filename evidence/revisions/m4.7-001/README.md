# M4.7 — G2A: freeze the robustness path

**Owner:** Tấn Phát (Research Lead). **Status:** frozen, technical replay
`PASS`, **confirmed by the Research Lead** on 2026-10-24T16:01:24Z ("xác nhận",
recorded verbatim in [`owner_confirmation.json`](owner_confirmation.json), event
`QPAF-REG-20261024-0006` in [`governance_events.jsonl`](governance_events.jsonl)).
`g2a_freeze.json` is create-once and keeps its creation-time status
`G2A_FROZEN_TECHNICAL_PASS_PENDING_OWNER_CONFIRMATION`. **Experiment:**
`QPAF-M4_7-GAT-001` (`governance` / `governance_record`). Nothing was trained or
evaluated; no test, ViMDoc or confirmation label was deserialized.

[`g2a_freeze.json`](g2a_freeze.json) (SHA-256 `26d9bab6…3217`, source commit
`8102e15`) is create-once. [`verification.json`](verification.json) pins it and
holds the two child-process replays, both `PASS`:
`scripts/freeze_m43_qpaf.py --verify evidence/revisions/m4.3-001` and
`scripts/decide_m46_direction.py --verify evidence/revisions/m4.6-001`. The
design is
[`2026-10-24-m47-g2a-freeze-design.md`](../../../docs/superpowers/specs/2026-10-24-m47-g2a-freeze-design.md).

## Frozen items

| Item | Value |
| --- | --- |
| Main method | QPAF-v1, M4.3 freeze `4015c74b…61cc`, `best.pt` `e4b00ab4…e5c8e`, epoch 19 |
| Config, loss | M4.2 `shared_base.toml` `3e58a867…9b58`; `pairwise_logistic` / `query_mean` (A001) |
| Matched comparator | QARF-v1 `best.pt` `e44ac1a4…0914` |
| Seeds | `20260820` done; `20260821`, `20260822` change only `training.seed` |
| Baselines | 7 rows, contracts `fa919054…7dcf`; co-strongest `train_fitted_static` |
| Evaluator, oracle | `qpaf/m24/evaluator.py` `bfd25f33…6742`; `qpaf/m44/oracle.py` `b9416d94…b701` |
| Held-out | ViDoSeek test, 172 IDs `d34210f9…e6f6`, sealed qrels `05eaaa81…d154`, labels closed |
| Claim rules | `frozen_protocol.md` §5 items 1–9, by hash; no new threshold |
| ViMDoc 8,904 | `NOT_RUN_DEFERRED`: no verified score cache; claim bounded to ViDoSeek |

Prerequisites checked: G2 `GO` confirmed, M4.1 seal, M4.2 bundle, M4.3
confirmed, both M4.4 runs `SUCCESS`, M4.5 `ACCEPTED`, M4.6 `continue_qpaf`
confirmed.

## Remaining experiment roster

| ID | Task | Owner | Tier | Data | Auth |
| --- | --- | --- | --- | --- | --- |
| R1 | M5.1 preregistration (matrix, ablation order, optional-tier drops) | Thanh | core | none | no |
| R2 | M5.2 seed cache-parity receipt | Khương | core | no labels | no |
| R3 | M5.3 QARF/QPAF seed `20260821` | Tấn Phát | core | train, validation | yes |
| R4 | M5.4 QARF/QPAF seed `20260822` | Tấn Phát | core | train, validation | yes |
| R5 | M5.5 retriever/normalization checks, latency, memory | Khương | optional | validation | yes |
| R6 | M5.6 feature and conditioning ablations | Tấn Phát | optional | validation | yes |
| R7 | TEST-172: baselines, QARF ×3, QPAF ×3, W7/W66 oracle rows | Tấn Phát / Thanh | core | test, once | yes |
| R8 | M5.7 three-seed aggregation | Thanh | core | R7 outputs | no |
| R9 | M5.8 sealed external benchmark | Thanh | deferred | as workbook | yes |
| R10 | ViMDoc confirmation | — | deferred | none | — |

Rules:

- Core items cannot be dropped. M5.1 orders drops only within the optional tier.
- R3 and R4 each include a fresh-process reload check (`<= 1e-7`) and a finite
  output check before their checkpoints may enter R7.
- R7 runs once, after R3 and R4 have independent reviews. No seed, checkpoint,
  baseline or method choice is made after it. Oracle rows are label-using upper
  bounds, never selectable.
- Only R7 may read test labels. R5 and R6 use validation only and cannot change
  the frozen method, config or checkpoints.

## Limitations carried forward

- The A001 loss orders static weights against nDCG@10 (train Spearman +0.537,
  minimum at BM25-only).
- A004 did not pass its train-only gate and is not adopted.
- Learned QARF is a weak comparator (validation 0.752147), so `QPAF − QARF`
  mainly shows page-level gating tolerating that loss better; §5 item 4 (QPAF
  beats `train_fitted_static`) is the decisive test.

## Claim boundary

No new result. Validation numbers stay single-seed and optimistic. This record
authorizes no run; R3–R7 each need their own authorization.

## Read-only replay

With the M4.2 payload restored (`scripts/run_m44_evaluation.py restore-inputs`)
and the M3.1 inputs at their sealed paths (about three minutes):

```powershell
.venv/Scripts/python.exe -X utf8 scripts/freeze_m47_g2a.py --verify evidence/revisions/m4.7-001
```
