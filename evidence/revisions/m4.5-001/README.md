# M4.5 — Independent baseline fairness and uncertainty audit

**Owner:** Thanh. **Technical reviewer:** Codex at Thanh's request.
**Technical verdict:** `PASS`. **Thanh's acceptance:** `ACCEPTED`, recorded
verbatim in [`owner_confirmation.json`](owner_confirmation.json) and event
`QPAF-REG-20261024-0001` in
[`governance_events.jsonl`](governance_events.jsonl). The technical
[`verification.json`](verification.json) is the immutable pre-acceptance
snapshot; its `PENDING_THANH_CONFIRMATION` field records that sequence.
This is a read-only review of the ViDoSeek validation runs (171 queries, learned
seed `20260820`), not a new scientific run or the three-seed confirmation test.

## Inputs and checks

[`verification.json`](verification.json) pins the M4.2, M4.4 MTH and M4.4 ORC
manifests. The auditor rehashes every listed artifact, source/config pin,
authorization and attempt marker. Seven Git-ignored M4.2 payload files were
restored only after their SHA-256 values matched the M4.2 manifest. The M4.2
recipient handoff identifies the downloadable archive for a fresh checkout.

The independent script [`audit_m45_baselines.py`](../../../scripts/audit_m45_baselines.py):

- Recomputes the complete 66-point static grid from raw scores and **799 train
  query labels only**. It obtains weights `[0.0, 0.1, 0.9]` and train nDCG@10
  `0.8642244283102869`; all 66 values match the saved train grid.
- Verifies the seven deployable baseline contracts share one input hash and all
  methods use the same **82,255 candidate pages** over 171 validation queries.
  It replays channel normalization, uniform fusion, `RRF k=60` and the frozen
  train-fitted weights from raw scores. Maximum score discrepancy is
  `2.22e-16`; learned QARF/QPAF scores match the accepted pilot predictions
  exactly.
- Recomputes every per-query and aggregate page metric from saved predictions
  and development qrels, then applies the frozen `1e-12` co-strongest tie rule.
  Only `train_fitted_static` is co-strongest. The oracle rows are re-scored
  separately and cannot enter selection.
- Recomputes QPAF-minus-each-baseline paired query deltas, 10,000 bootstrap
  resamples (seed `20260820`), CI95, W/T/L and gain concentration. The
  primary deltas are saved in [`per_query_deltas.csv`](per_query_deltas.csv).

| Validation nDCG@10 | Value |
| --- | ---: |
| Strongest deployable: `train_fitted_static` | 0.871414 |
| Frozen QPAF | 0.866280 |
| QPAF minus strongest | **−0.005134** |
| Paired CI95 | [−0.013457, +0.002783] |
| Win / tie / loss | 3 / 161 / 7 |

QPAF does **not** exceed the strongest deployable baseline on this validation
split. The CI includes zero. This finding informs M4.6; M4.5 does not choose
`continue_qpaf`, `revise_once` or `negative_qpaf_result`.

## Interpretation limits

- The QARF and QPAF checkpoints were selected on this same validation split;
  the reported validation values are optimistic. Only one learned seed is
  available here. No test or ViMDoc confirmation labels were opened.
- The M4.3 owner confirmation was recorded after M4.4's validation run. The
  frozen method record and separate M4.4 authorization existed for the run;
  this sequence is retained in the review, not silently backdated.
- On this reviewer's Python 3.11, M4.4's original verifier fails an exact
  `selection.json` float equality because Python 3.13's `sum` gives a
  different last bit (at most `6.66e-16`). The independent audit compares
  numerical results within protocol tolerance `1e-12`; it leaves the sealed
  M4.4 code and artifacts unchanged.

## Read-only replay

Restore the seven Git-ignored M4.2 payload files using the pinned M4.2
handoff and verify their hashes. Then, from the repository root:

```powershell
python scripts/audit_m45_baselines.py --output-dir evidence/revisions/m4.5-001 --verify
python -m unittest tests.test_m45_baseline_audit -q
```

The verifier requires exact M4.5 evidence bytes and never writes to a run.
