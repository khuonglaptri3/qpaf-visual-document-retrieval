# M4.3 — Frozen QPAF (G2 branch `continue_qpaf`)

**Owner:** Tấn Phát. **Status:** frozen, technical replay `PASS`, **confirmed by
the Research Lead** on 2026-10-23T17:44:18Z ("I approved M4.3 freeze", recorded
verbatim in [`owner_confirmation.json`](owner_confirmation.json), event
`QPAF-REG-20261023-0011`). `method_freeze.json` is create-once and keeps its
creation-time status `FROZEN_TECHNICAL_PASS_PENDING_OWNER_CONFIRMATION`.
**Experiment:** `QPAF-M4_3-GAT-001` (`governance` / `governance_record`).
Nothing was trained and no test or confirmation label was read.

The workbook (Milestones row 50) asks M4.3 for "Frozen QPAF, one preregistered
revision, or documented negative-result pivot". G2 (`evidence/revisions/m3.7-001`)
is `GO` / `continue_qpaf`, confirmed by the Research Lead, so the matched
seed-20260820 QPAF pilot of M3.4 becomes the main method unchanged.
`revise_once` and `negative_qpaf_result` were not triggered.

## Frozen method

| Item | Value |
| --- | --- |
| Run | `RUN-QPAF-M3_4-MTH-001-20261022T112102Z-A01` |
| Checkpoint `best.pt` | `e4b00ab49e186fffe8b369e26491873304b61177c11fd2ce0f455158e30e5c8e`, epoch 19 |
| Gate | linear, page granularity, 13 features, 42 parameters |
| Config | `shared_base.toml` `3e58a867…9b58`; resolved `8935618a…4be2` |
| Selection | max validation nDCG@10 over 20 epochs; ties keep the earlier epoch |
| Matched QARF | `RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01`, `best.pt` `e44ac1a4…0914`, epoch 1 |
| Sealed inputs | M3.1 manifest `0832af15…7893` |

[`method_freeze.json`](method_freeze.json) also binds the G2 decision, owner
confirmation, inputs and criteria, the M3.2/M3.4 authorizations, the M3.5
comparison, the M3.6 integrity review and ten method source files. Those
source files must still match the bytes recorded in both runs' provenance.

## Replay (`verification.json`)

- `scripts/decide_g2.py` still derives a record equal to `decision.json`.
- The M3.1 seal replay returns `PASS` with identical parity.
- For QPAF and QARF, `scripts/audit_m36_integrity.py --replay-method` reloads
  `best.pt` in a fresh descendant process and predicts the 171 validation
  queries (82,255 candidates). Score, weight and metric differences are `0.0`
  (tolerance `1e-7`), and no ranking differs. The recomputed validation nDCG@10
  is `0.8662796720664044` for QPAF and `0.7521473770883798` for QARF.

`freeze_sha256` = `4015c74b54f5ac3d2cbce54f8424c0e9329c009595e81ced5eab0039af7761cc`,
source commit `69b5309`.

## Claim boundary

One development seed. The checkpoint was selected on the validation split used
by G2, so its validation numbers are optimistic. There is no baseline
comparison (M4.4), no test or confirmation access, and no three-seed claim.
Seeds `20260821`/`20260822` (M5.3/M5.4) must use the same resolved config and
method sources, changing only `training.seed`.

## Replay command

With the M3.1 inputs restored at their sealed paths, use Python 3.13.7, Torch
2.11.0+cpu, NumPy 2.5.4, pandas 3.0.6 and PyArrow 26.0.0:

```powershell
.venv/Scripts/python.exe scripts/freeze_m43_qpaf.py --verify evidence/revisions/m4.3-001
```

It is read-only, takes about three minutes, and must print `"status": "PASS"`.
