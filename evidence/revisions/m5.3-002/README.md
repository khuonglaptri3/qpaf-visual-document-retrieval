# M5.3 — matched QPAF seed 20260821 (R3, second half)

**Owner:** Tấn Phát. **Status:** supervised run `SUCCESS`. First-pass checks: 41 PASS / 0 FAIL.
Independent review: `PENDING`.

- [`authorization.json`](authorization.json): pin
  `132a1287c2cd3aeb688399b3fde39a0582bc3d8b53a2b057242df5c9257eaecd`, approved
  2026-10-26T02:51:55Z. The approval text is the Research Lead's verbatim reply in the working session,
  recorded by Claude Code at their request. The same reply approves `m5.4-002`.
- [`governance_events.jsonl`](governance_events.jsonl): `QPAF-REG-20261026-0003` (AUTHORIZED),
  `0005` (STARTED) and `0006` (VERIFICATION_RECORDED; the run stays `STARTED` until the review).
- [`post_run_check.py`](post_run_check.py) and [`post_run_verification.json`](post_run_verification.json):
  the executor's first-pass check against the seed-1 QPAF run (M3.4) and the matched seed-2 QARF run.
- Run: `results/m5.3/RUN-QPAF-M5_3-MTH-002-20261026T025155Z-A01/`, committed byte-exact, including
  checkpoints, `run.log` and `supervisor.log`.
- The authorization was drafted from the approved seed-2 QARF authorization (`m5.3-001`). Only the method
  (`--method QPAF`, page gate), the run and experiment IDs, the comparator and the seed-1 reference (M3.4)
  differ. The supervisor's `check_comparator` refuses anything else.

## Result (validation, 171 queries, development)

Seed `20260821`, 20 epochs, selected epoch 9 (seed-1 QPAF selected epoch 19).

| Metric | Value |
| --- | --- |
| nDCG@10 | `0.866252499336626` |
| Recall@1 | `0.7368` |
| Recall@3 | `0.9123` |
| MRR@10 | `0.8297` |

Checkpoints: `best.pt` `6a379d5e…0a66` and `last.pt` `e44c74b1…b637`. The fresh-process reload
difference was `0.0` for scores, weights and metrics. Wall time was 80.6 s and peak RSS 758 MB.
The test split was not opened.

The selected value is the maximum over 20 epochs on the same validation split, so it is optimistic.
No QPAF-versus-QARF, seed-averaged or baseline claim is made here; that is M5.7.

## Handover

- **Thanh — independent seed-2 QPAF review**, on a branch made from `feature/m5-3-seed2-runs`. Replay
  `python evidence/revisions/m5.3-002/post_run_check.py`; its output must match `post_run_verification.json`.
  Record `ACCEPTANCE_RECORDED`/`PASS` for this `run_id` and authorization pin, with the review file and its
  SHA-256, in this `governance_events.jsonl`. That review closes M5.3; one PR for the whole task follows.

## Checks

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m53_supervisor -v
python evidence/revisions/m5.3-002/post_run_check.py
```
