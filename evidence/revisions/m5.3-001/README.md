# M5.3 — matched QARF seed 20260821 (R3, first half)

**Owner:** Tấn Phát. **Status:** supervised run `SUCCESS`. First-pass checks: 35 PASS / 0 FAIL.
Independent review: `PENDING`. The matched QPAF seed-2 run is a separate authorization (`m5.3-002`),
which the supervisor refuses until this QARF run carries an accepted independent review.

- [`authorization.json`](authorization.json): pin
  `93f1d2da7ab18da14b3579b7ebc186b60b3fea1b3f6f6e914bab719cea8f7490`, approved
  2026-10-25T13:59:54Z. The approval text is the Research Lead's verbatim reply in the working session,
  recorded by Claude Code at their request.
- [`governance_events.jsonl`](governance_events.jsonl): `QPAF-REG-20261025-0004` (AUTHORIZED),
  `0005` (STARTED) and `0006` (VERIFICATION_RECORDED; the run stays `STARTED` until the review).
- [`post_run_check.py`](post_run_check.py) and [`post_run_verification.json`](post_run_verification.json):
  the executor's first-pass check, including the seed-1 parity checks.
- Run: `results/m5.3/RUN-QPAF-M5_3-MTH-001-20261025T135954Z-A01/`, committed byte-exact, including the
  16 MB `validation_predictions.json`.
- The authorization was drafted from the approved seed-1 M3.2 authorization.
  The sealed inputs, metric, runtime, hardware, limits and command are copied exactly. Only the config
  path, the output root and the seed (`20260821`) differ.
- Seed config [`configs/m5.3/shared_base_seed_20260821.toml`](../../../configs/m5.3/shared_base_seed_20260821.toml)
  (SHA-256 `d34cb2ee…936c`): the frozen M4.3 `shared_base.toml` bytes with only the seed digits changed.
  Its parsed form equals the M5.2 receipt matrix entry for seed `20260821` (`cache_identity.json`
  `960aed61…3291`).

## What the supervisor adds to the M3.2 mechanics

`src/qpaf/m53/supervisor.py` reuses the M3.2 single-attempt helpers and the M3.4 section names
unchanged. Before the seal check it refuses unless:

- the M5.1 preregistration and confirmation, the M5.2 receipt and the M4.3 freeze match their pins;
- the ten frozen method sources still hash as in the M4.3 freeze;
- the config is the M5.2 receipt config for this seed and method;
- the authorization equals the seed-1 run of the same method in everything except the config and the output root.

For QPAF, it also needs an `ACCEPTANCE_RECORDED`/`PASS` review of the seed-2 QARF run. The QPAF
authorization may differ from that run's only in the method.

After the run, it requires the following before it writes `_SUCCESS.json`:

- the seed-1 `data_manifest.json`, byte for byte (`890f2709…8ddd`);
- the seed-1 provenance inputs, with only the config hash replaced;
- a fresh-process reload of `best.pt` and `last.pt` in a separate interpreter
  (`scripts/reload_m53_checkpoint.py`). Every value must be finite, and the validation scores, weights
  and metrics must match within `1e-7`. The reload report is stored inside `_SUCCESS.json`.

The reload worker reproduced both seed-1 runs exactly before this draft: QARF `e44ac1a4…0914` and
QPAF `e4b00ab4…5c8e`, with score, weight and metric differences all `0.0`.

## Result (validation, 171 queries, development)

Seed `20260821`, 20 epochs, selected epoch 1 (seed 1 also selected epoch 1).

| Metric | Value |
| --- | --- |
| nDCG@10 | `0.7410159807755565` |
| Recall@1 | `0.5673` |
| Recall@3 | `0.7778` |
| MRR@10 | `0.6838` |

Checkpoints: `best.pt` `3924f3ef…0626` and `last.pt` `725bf238…8678`. The fresh-process reload
difference was `0.0` for scores, weights and metrics. Wall time was 238.5 s (load 17.9 s, train
163.9 s) and peak RSS 749 MB. The test split was not opened.

The selected value is the maximum over 20 epochs on the same validation split, so it is optimistic.
No seed comparison or seed-averaged claim is made here; that is M5.7.

## Handover

- **Thanh — independent seed-2 QARF review (as M3.3 did for seed 1).** Replay
  `python evidence/revisions/m5.3-001/post_run_check.py`. Its output must match
  `post_run_verification.json`. The review must also make its own judgement on the run. Record
  `ACCEPTANCE_RECORDED`/`PASS` for this `run_id` and this authorization pin, with the review file and its
  SHA-256 (`verification_ref`/`verification_sha256`), in this `governance_events.jsonl`.
- **Tấn Phát — after that event exists:** draft `evidence/revisions/m5.3-002/authorization.json` for
  QPAF. It differs from this file only in method, run_id and experiment_id. Its `comparator` pins this
  run and the acceptance event. Approve it, then run it with the same supervisor.

## Checks

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m53_supervisor -v
python evidence/revisions/m5.3-001/post_run_check.py
```

The test suite includes read-only checks against the real pins, so a drifted pin fails the tests.
No test trains a model or opens the sealed test qrels.
