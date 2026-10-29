# A005 Stage 4 — matched QARF-SA-v2 / QPAF-SA-v2 runs on ViMDoc

Six create-once runs (2 granularities x 3 seeds), each with its own `authorization.json`
(course-project light mode), `result.json` and a 2.7 KB `checkpoint.pt` (force-added; `*.pt` is
git-ignored by default). Anchor w̄ = `[0.1, 0.2, 0.7]` (Stage 3 `train_fitted_static`). The
reference is `train_fitted_static` at validation nDCG@10 0.956878. Every run reloaded in a fresh
process with a maximum absolute score difference of 0. No confirmation label was read.

| Method | Seed | Best epoch | Validation nDCG@10 | Gain over static | Reload diff |
| --- | --- | ---: | ---: | ---: | ---: |
| QARF-SA-v2 | 20260820 | 16 | 0.960965 | +0.004087 | 0 |
| QARF-SA-v2 | 20260821 | 13 | 0.960446 | +0.003569 | 0 |
| QARF-SA-v2 | 20260822 | 15 | 0.960414 | +0.003536 | 0 |
| QPAF-SA-v2 | 20260820 | 19 | 0.962421 | +0.005543 | 0 |
| QPAF-SA-v2 | 20260821 | 16 | 0.961939 | +0.005062 | 0 |
| QPAF-SA-v2 | 20260822 | 17 | 0.962267 | +0.005389 | 0 |

The early-stop check passed (QPAF-SA seed 20260820 selected epoch 19, gain 0.0055 >= 0.003).
`--stop-rule` returned `PROCEED` (0 of 3 QPAF-SA seeds selected epoch 0). These are validation
numbers only; they say nothing about the confirmation split.

## Replay

```powershell
.venv/Scripts/python.exe scripts/train_a005_stage4.py --stop-rule
```
