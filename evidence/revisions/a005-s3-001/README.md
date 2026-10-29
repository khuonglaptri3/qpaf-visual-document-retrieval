# A005 Stage 3 — ViMDoc validation baselines

**Result:** record [`baselines.json`](baselines.json) (create-once), SHA-256
`01c6076819ad15feb7ef574ab23c1445e861a55d6819d47c4d8f9f9830368eac`, created at `2d27986`
under [`authorization.json`](authorization.json) (course-project light mode). The read-only
`--verify` recomputation returned PASS. No training was run and no confirmation label was read.

## Validation nDCG@10 (document units)

| Baseline | nDCG@10 |
| --- | ---: |
| `train_fitted_static` (weights `[0.1, 0.2, 0.7]`, fitted on train) | **0.956878** |
| `colqwen25` | 0.950613 |
| `uniform_combsum` | 0.937525 |
| `rrf_k60` | 0.923119 |
| `bm25` | 0.876931 |
| `bge_m3` | 0.867827 |

The co-strongest set is `[train_fitted_static]`. It is the Stage 4 anchor w̄.

## Replay

```powershell
.venv/Scripts/python.exe scripts/baselines_a005_stage3.py --cache C:/Users/HP/qpaf-cache/a005-s1-001 --verify
```
