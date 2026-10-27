# M5.4 — matched QPAF seed 20260822 (R4, second half)

**Owner:** Tấn Phát. **Status:** supervised run `SUCCESS`. First-pass checks: 41 PASS / 0 FAIL.
Independent review: `PENDING`.

- [`authorization.json`](authorization.json): pin
  `1d7e64d367a1aa25ae1e7ca8140f61e19d193660a3dfadd294fddec2cf17f845`, approved
  2026-10-26T02:51:55Z. The approval text is the Research Lead's verbatim reply in the working session,
  recorded by Claude Code at their request. The same reply approves `m5.3-002`.
- [`governance_events.jsonl`](governance_events.jsonl): `QPAF-REG-20261026-0004` (AUTHORIZED),
  `0007` (STARTED) and `0008` (VERIFICATION_RECORDED; the run stays `STARTED` until the review).
- [`post_run_check.py`](post_run_check.py) and [`post_run_verification.json`](post_run_verification.json):
  the executor's first-pass check against the seed-1 QPAF run (M3.4) and the matched seed-3 QARF run.
- Run: `results/m5.4/RUN-QPAF-M5_4-MTH-002-20261026T025155Z-A01/`, committed byte-exact, including
  checkpoints, `run.log` and `supervisor.log`.
- The authorization was drafted from the approved seed-3 QARF authorization (`m5.4-001`). Only the method
  (`--method QPAF`, page gate), the run and experiment IDs, the comparator and the seed-1 reference (M3.4)
  differ. The supervisor's `check_comparator` refuses anything else.

## Result (validation, 171 queries, development)

Seed `20260822`, 20 epochs, selected epoch 20 (seed-1 QPAF selected epoch 19).

| Metric | Value |
| --- | --- |
| nDCG@10 | `0.8678608672449859` |
| Recall@1 | `0.7368` |
| Recall@3 | `0.9064` |
| MRR@10 | `0.8287` |

Checkpoints: `best.pt` `6017e3f1…0bea` and `last.pt` `03edb2d2…c364`. The fresh-process reload
difference was `0.0` for scores, weights and metrics. Wall time was 79.5 s and peak RSS 753 MB.
The test split was not opened.

The selected value is the maximum over 20 epochs on the same validation split, so it is optimistic.
No QPAF-versus-QARF, seed-averaged or baseline claim is made here; that is M5.7.

## Handover

- **Thanh — independent seed-3 QPAF review**, together with the seed-2 QPAF review (`m5.3-002`). Use a
  branch made from `feature/m5-4-seed3-runs`. Replay `python evidence/revisions/m5.4-002/post_run_check.py`;
  its output must match `post_run_verification.json`. Record `ACCEPTANCE_RECORDED`/`PASS` for this `run_id`
  and authorization pin, with the review file and its SHA-256, in this `governance_events.jsonl`.
- The seed-2 QPAF run was committed on `feature/m5-3-seed2-runs` after this branch split from it. Review
  it there, or here once `feature/m5-3-seed2-runs` has been merged into this branch.

## Checks

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m54_supervisor tests.test_m53_supervisor -v
python evidence/revisions/m5.4-002/post_run_check.py
```
