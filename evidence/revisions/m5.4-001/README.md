# M5.4 — matched QARF seed 20260822 (R4, first half)

**Owner:** Tấn Phát. **Status:** supervised run `SUCCESS`. First-pass checks: 35 PASS / 0 FAIL.
Independent review: `PENDING`. The matched QPAF seed-3 run needs its own authorization (`m5.4-002`).
The supervisor refuses it until this QARF run carries an accepted independent review. Thanh reviews it
together with the seed-2 QARF run (M5.3).

- [`authorization.json`](authorization.json): pin
  `b3bd04004bf8503aca6d703f20d3405738e50aa41028bc3ce699cd2a540173f9`, approved 2026-10-25T15:48:18Z.
  The approval text is the Research Lead's verbatim reply in the working session, recorded by Claude
  Code at their request.
- [`governance_events.jsonl`](governance_events.jsonl): `QPAF-REG-20261025-0007` (AUTHORIZED),
  `0008` (STARTED) and `0009` (VERIFICATION_RECORDED; the run stays `STARTED` until the review).
- [`post_run_check.py`](post_run_check.py) and [`post_run_verification.json`](post_run_verification.json):
  the M5.3 first-pass check ported to seed 3.
- Run: `results/m5.4/RUN-QPAF-M5_4-MTH-001-20261025T154818Z-A01/`, committed byte-exact, including
  `supervisor.log`, `run.log` and both checkpoints.
- The authorization was drafted from the approved seed-1 M3.2 authorization, like
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

## Result (validation, 171 queries, development)

Seed `20260822`, 20 epochs, selected epoch 1 (seeds 1 and 2 also selected epoch 1).

| Metric | Value |
| --- | --- |
| nDCG@10 | `0.751118077352592` |
| Recall@1 | `0.5848` |
| Recall@3 | `0.7836` |
| MRR@10 | `0.6956` |

Checkpoints: `best.pt` `33d8c3f2…e31a` and `last.pt` `fc87cf90…38e8`. The fresh-process reload
difference was `0.0`. Wall time was 104.2 s (train 72.9 s) and peak RSS 752 MB. The test split was not
opened.

Observation, without interpretation: from epoch 2 onward, validation nDCG@10 is identical for seeds 1, 2
and 3 at every epoch. Their losses, weights and checkpoints all differ: the largest weight difference
from seed 2 is 0.036, and 114 of 171 queries have the same top-10. Only epoch 1, the selected epoch,
differs between seeds. `post_run_verification.json` lists the equal epochs. The selected value is the
maximum over 20 epochs on the same validation split, so it is optimistic. Seed aggregation is M5.7.

## Handover

Thanh reviews this run and the seed-2 QARF run (M5.3) in one pass. Use a branch made from
`feature/m5-4-seed3-runs`, which also contains M5.3. Record a separate `ACCEPTANCE_RECORDED`/`PASS`
event for each run in its own `governance_events.jsonl`, using that run's `run_id` and authorization
pin, and the review file with its SHA-256. The steps are the same as in the M5.3 README handover.

## Checks

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m54_supervisor tests.test_m53_supervisor -v
```
