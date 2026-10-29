# A005 Stage 2 — ViMDoc train-only alignment gate

**Result:** `PASS`. **Record:** [`alignment_probe.json`](alignment_probe.json)
(create-once), SHA-256 `344f19d548725848ebd5540a8f22446582066241e3b7ff847a75af9d1b67e6d8`.
It was created at `f7d2a64` under [`authorization.json`](authorization.json) (course-project
light mode; the Research Lead delegated the decision, text recorded in the file). The
read-only `--verify` recomputation returned PASS.

## Result

The run used 1,600 ViMDoc train queries (1,599 learnable) and the 66-point static grid, in
document units, with the A005 profile loss over `log τ ∈ [log 1e-3, 0]`.

| Quantity | Value | Gate |
| --- | ---: | --- |
| Spearman(loss, train nDCG@10) | **−0.997** | G-A `<= −0.5`: PASS |
| Lowest-loss weights | `[0.1, 0.2, 0.7]` | |
| nDCG@10 at the lowest-loss weights | 0.9612 (grid max 0.9612) | G-B: PASS |

The lowest-loss point is also the nDCG-best point of the grid. No validation, confirmation
or test label was read, and nothing was trained.

## Replay

```powershell
.venv/Scripts/python.exe scripts/probe_a005_stage2.py --cache C:/Users/HP/qpaf-cache/a005-s1-001 --verify
```
