# M5.4 — matched QARF seed 20260822 (R4, first half)

**Owner:** Tấn Phát. **Status:** authorization `DRAFT_PENDING_APPROVAL`; nothing has been run.
The matched QPAF seed-3 run needs its own authorization (`m5.4-002`). The supervisor refuses it until
this QARF run carries an accepted independent review. Thanh reviews it together with the seed-2 QARF
run (M5.3).

- [`authorization.json`](authorization.json): drafted from the approved seed-1 M3.2 authorization, like
  M5.3. The sealed inputs, metric, runtime, hardware, limits and command are copied exactly. Only the
  config path, the output root and the seed (`20260822`) differ.
- Seed config [`configs/m5.4/shared_base_seed_20260822.toml`](../../../configs/m5.4/shared_base_seed_20260822.toml):
  the frozen M4.3 bytes with only the seed digits changed. Its parsed form equals the M5.2 receipt matrix
  entry for seed `20260822`, for both QARF and QPAF.
- `src/qpaf/m54/supervisor.py` and `scripts/run_m54_authorized.py` are the M5.3 files with only the seed,
  task, run-ID prefix, output root and messages changed. `tests/test_m54_supervisor.py` checks that exact
  substitution, so the M5.3 end-to-end tests cover the same logic. They also reuse the M5.3 fresh-process
  reload worker unchanged.
- Branch `feature/m5-4-seed3-runs` starts from `feature/m5-3-seed2-runs` (`5ca57fb`). The M5.4 PR therefore
  depends on the M5.3 PR.

## Checks

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m54_supervisor tests.test_m53_supervisor -v
```
