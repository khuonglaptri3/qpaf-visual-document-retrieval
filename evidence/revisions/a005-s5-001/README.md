# A005 Stage 5 — ViMDoc confirmation (one-time)

**Record:** [`confirmation.json`](confirmation.json) (create-once), created at `9143fab` by
`scripts/confirm_a005_stage5.py --create` after `--check-hash` returned MATCH for the sealed
qrels (SHA-256 `ce9ad0fb44c2fd1c38794b7a0a67c75be6412a13a960bb7b203b81f484003f2b`, equal to
`a005-s1-001/markers/prepare.json`). The run was done once; it must not be repeated. Method,
seeds and checkpoints are the Stage 4 ones, unchanged. ViDoSeek test was not accessed.

The split holds 8,904 queries (document units). Five of them have no positive document in
their candidate union; they are kept and score nDCG@10 = 0 for every method.

| Method | Confirmation nDCG@10 |
| --- | ---: |
| `train_fitted_static` | 0.958940 |
| `colqwen25` | 0.948576 |
| `uniform_combsum` | 0.944090 |
| `rrf_k60` | 0.937071 |
| `bm25` | 0.873752 |
| `bge_m3` | 0.869504 |
| QARF-SA-v2 (mean of 3 seeds) | 0.960990 (0.961051, 0.961068, 0.960850) |
| QPAF-SA-v2 (mean of 3 seeds) | 0.960760 (0.960615, 0.960325, 0.961340) |

The statistics are in [`../a005-s6-001/`](../a005-s6-001/).

## Replay

```powershell
.venv/Scripts/python.exe scripts/confirm_a005_stage5.py --cache C:/Users/HP/qpaf-cache/a005-s1-001 --check-hash
```
(`--create` refuses to run because the record exists.)
