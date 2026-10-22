# M3.4 — matched learned QPAF pilot

**Owner:** Tấn Phát. **Status:** supervised run `SUCCESS`, first-pass checks
39 PASS / 0 FAIL / 0 SKIPPED; independent review `PENDING` (M3.5 Thanh, M3.6
Khương). No QPAF-versus-QARF, baseline or scientific claim is made here.

- [`authorization.json`](authorization.json): pin
  `4be026b852574e7687fdc4b9337f716aa96a64ac39556ae288193bdba99e5365`, approved
  2026-10-22T11:21:02Z. The approval text is the Research Lead's verbatim reply
  in the working session, recorded by Claude Code at their request.
- [`governance_events.jsonl`](governance_events.jsonl): `QPAF-REG-20261022-0023`
  (AUTHORIZED), `0024` (STARTED), `0025` (VERIFICATION_RECORDED, still `STARTED`).
- [`post_run_check.py`](post_run_check.py) and
  [`post_run_verification.json`](post_run_verification.json): the M3.2 first-pass
  check plus nine matched checks against the QARF run.
- Run: `results/m3.4/RUN-QPAF-M3_4-MTH-001-20261022T112102Z-A01/` (21 files,
  committed byte-exact, including the 16 MB `validation_predictions.json`).

## What makes the run matched

`src/qpaf/m34/supervisor.py` reuses the M3.2 single-attempt helpers unchanged
and refuses to start unless the QARF run carries event `QPAF-REG-20261022-0022`
(M3.3 `ACCEPTANCE_RECORDED` / `PASS`) and this authorization equals the QARF one
in sealed inputs, config, metric, runtime, hardware, limits and seed, with the
command differing only in `--method QPAF` and the output root. After the run:

| Check against `RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01` | Result |
| --- | --- |
| `resolved_config.json` SHA-256 `8935618a…4be2` | identical |
| `data_manifest.json` SHA-256 `890f2709…8ddd` (rows, order, counts) | identical |
| Provenance inputs (scores, queries, qrels, splits, config) | identical |
| Candidate pages per validation query, in order | identical |
| Fusion weights | vary across pages (QPAF); constant per query (QARF) |

## Result (validation, 171 queries, development)

Seed `20260820`, 20 epochs, selected epoch 19 (epoch 20 ties; ties keep the
earlier epoch). nDCG@10 `0.8662796720664044`, Recall@1 `0.7368`, Recall@3
`0.9064`, MRR@10 `0.8283`. Reload parity `0.0` (tolerance `1e-7`, in-process).
Wall time 75.978 s; peak RSS 754 MB. Test split not opened. The selected value
is the maximum over 20 epochs on the same validation split, so it is
optimistic; the paired comparison with QARF belongs to M3.5.

## Replay

Restore the M3.1 inputs (manifest pin
`0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893`), use
Python 3.13.7, Torch 2.11.0+cpu, NumPy 2.5.4, pandas 3.0.6 and PyArrow 26.0.0,
then run `python evidence/revisions/m3.4-001/post_run_check.py`; its output
must match `post_run_verification.json`.
