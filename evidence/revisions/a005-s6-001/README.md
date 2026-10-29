# A005 Stage 6 — paired statistics and verdict

**Record:** [`aggregate.json`](aggregate.json) (create-once), built from the Stage 5
confirmation record only (no qrels, no model). Paired by query over 8,904 confirmation queries,
bootstrap 10,000 resamples, seed 20260820. The baseline has no seeds, so its per-query values
are used under all three seed keys.

| Comparison (QPAF-SA-v2 minus ...) | Mean delta | CI95 | W / T / L |
| --- | ---: | --- | --- |
| `train_fitted_static` (co-strongest) | +0.001820 | [+0.000541, +0.003173] | 224 / 8482 / 198 |
| QARF-SA-v2 (matched learned comparator) | -0.000230 | [-0.001358, +0.000928] | 208 / 8478 / 218 |

**Verdict: `QPAF_SA_BEATS_BASELINE`.** Rule: every co-strongest comparison needs a positive mean
and a positive CI lower bound; the only co-strongest baseline is `train_fitted_static`.
The margin is small (+0.0018 nDCG@10), and QPAF-SA is not distinguishable from QARF-SA
(CI contains 0). QARF-SA is itself +0.002049 above the static baseline.
`independent_review` is `WAIVED_BY_A006`.

## Replay

```powershell
.venv/Scripts/python.exe scripts/aggregate_a005_stage6.py
```
(refuses to overwrite once the record exists)
