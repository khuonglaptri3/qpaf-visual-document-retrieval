# M3.5 — paired QPAF versus QARF development comparison

**Owner:** Thanh. **Technical verdict:** `PASS` in
[`comparison.json`](comparison.json). The technical snapshot records owner
acceptance as pending at audit time. Thanh subsequently accepted it in
[`owner_confirmation.json`](owner_confirmation.json); the append-only M3.4
[`governance_events.jsonl`](../m3.4-001/governance_events.jsonl) records M3.5
`PASS`. M3.6's separate integrity/resource review and the G2 decision remain
pending.

[`audit_m35_paired.py`](../../../scripts/audit_m35_paired.py) independently
recomputes both runs' per-query validation metrics from committed predictions
and the hash-verified M3.1 development qrels. It checks the two authorizations,
prediction hashes, accepted QARF review, matching config/data manifest/input
provenance, identical query and candidate page order, and replays both first-pass
checks (QARF 30/30, QPAF 39/39). The recomputed per-query and aggregate metrics
match both published runs exactly. Every query's four method scores and deltas,
top-ranked page and first positive rank are in [`per_query.csv`](per_query.csv).

## Development result — seed 20260820, 171 paired queries

| Metric | QPAF minus QARF mean | Paired query-bootstrap CI95 | Win / tie / loss |
| --- | ---: | ---: | ---: |
| nDCG@10 | +0.114132 | [+0.077501, +0.152040] | 57 / 101 / 13 |
| Recall@1 | +0.152047 | [+0.081871, +0.222222] | 33 / 131 / 7 |
| Recall@3 | +0.122807 | [+0.064327, +0.181287] | 25 / 142 / 4 |
| MRR@10 | +0.131391 | [+0.086945, +0.177605] | 57 / 101 / 13 |

For each metric, the script resamples the **171 paired queries** with
replacement 10,000 times using NumPy `default_rng(20260820)` and linear
2.5/97.5 percentiles. Win/tie/loss uses `±1e-12`. The largest nine positive
nDCG gains (top 5%, rounded up) contribute 28.09% of all positive nDCG gain;
the median delta is zero. This is a descriptive interval for this one
development seed, not the frozen three-seed final gate.

QPAF loses nDCG on 13 queries. The worst query,
`008179ae43fe6605078e2dfbc1e02a2bfb1f3f48_0`, drops by `0.5`:
its first relevant page falls from rank 1 under QARF to rank 3 under QPAF.
Nine more worst cases, including relevant-page ranks, are in `comparison.json`;
all 171 rows are retained in `per_query.csv` for failure review.

Both models selected their checkpoints using this same validation split
(QARF epoch 1, QPAF epoch 19). The CI does not account for this selection or
training-seed variation. It is not a test-set or baseline result, and it does
not by itself satisfy the three-seed or G2 gates. The shared frozen config and
both summaries retain the historical `QPAF-M2_7-MTH-001` experiment ID; the
authorizations and run IDs identify M3.2/M3.4. M3.4's authorization text is
preserved as the Research Lead's verbatim working-session reply.

## Replay

Restore only `inputs/qrels_development.json` and `inputs/splits/val_ids.txt`
under the M3.1 seal path in both authorizations. The audit verifies their
SHA-256 values and never opens the sealed test qrels. With Python 3.13.7 and
NumPy 2.5.4 (the pinned M3.2/M3.4 runtime), run:

```powershell
python scripts/audit_m35_paired.py
```

The default is read-only. `--output-dir <new-directory>` creates the JSON and
CSV once. The restored M3.1 files remain local and are excluded from Git.
