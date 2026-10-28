# A005 Stage 0 — ViDoSeek train-only alignment gate

**Result:** `PASS`. **Record:** [`alignment_probe.json`](alignment_probe.json)
(create-once), SHA-256 `3513b862f871db4b28d2b81ff8c549d917894a6b1dbac9bcecc5bccc39a4af83`.
It was created at `a15cd73` under [`authorization.json`](authorization.json), which the
Research Lead approved. Independent review is `WAIVED_BY_A006`. The read-only
`--verify` recomputation returned PASS.

## Result

The run used 799 ViDoSeek train queries and the 66-point static grid. The loss is the
A005 listwise loss, profiled over `log τ ∈ [log 1e-3, 0]`.

| | A001 (v1) | A004 | **A005** | Gate |
| --- | ---: | ---: | ---: | --- |
| Spearman(loss, train nDCG@10) | +0.537 | +0.361 | **−0.994** | G-A `<= −0.5`: **PASS** |
| Lowest-loss weights | `[1, 0, 0]` | `[0.6, 0, 0.4]` | `[0, 0.2, 0.8]` | |
| nDCG@10 there (grid max 0.8642) | 0.7290 | 0.7908 | **0.8627** | G-B `>= 0.8542`: **PASS** |
| Rank of nDCG-best `[0, 0.1, 0.9]` by loss | 48 / 66 | 45 / 66 | **2 / 66** | |

The profiled temperature at the minimum is `τ ≈ 0.059`, inside the bounds. All 66 grid
nDCG@10 values replay the M4.6 probe exactly (difference 0.0).

## What this does and does not show

- It shows that the A005 loss orders static fusion weights almost exactly like train
  nDCG@10. This removes the loss–metric misalignment that A001 and A004 had.
- It does not show that a trained QPAF-SA-v2 beats the baseline. No model was trained,
  and no validation, test or ViMDoc label was read.
- By the outcome rule, A005 may now request a separate Stage 1 authorization for the
  ViMDoc inputs. This record does not grant it.

## Replay

```powershell
.venv/Scripts/python.exe scripts/probe_a005_stage0.py --verify
```
