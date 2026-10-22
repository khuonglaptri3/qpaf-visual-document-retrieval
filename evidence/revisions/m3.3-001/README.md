# M3.3 — independent QARF validation

**Owner:** Thanh. **Technical verdict:** `PASS` in
[`validation.json`](validation.json). The audit was executed by Codex at
Thanh's request, separately from the M3.2 runner and its first-pass checker.
The create-once technical report records owner acceptance as pending at audit
time. Thanh subsequently confirmed acceptance in
[`owner_confirmation.json`](owner_confirmation.json); the append-only
[`governance_events.jsonl`](../m3.2-001/governance_events.jsonl) records the
M3.3 `PASS` event. This accepts M3.3 as a prerequisite for M3.4, which still
needs its own authorization.

[`audit_m33_qarf.py`](../../../scripts/audit_m33_qarf.py) is a read-only audit
unless given a new `--output` path. It checks the M3.2 authorization pin,
supervisor markers, all 16 receipt outputs and the committed predictions;
replays the externally pinned M3.1 seal; independently computes validation
metrics from predictions, sealed candidate pages and development qrels; then
loads `best.pt` in a fresh Python process and reproduces every validation
score. It never opens test qrels, trains a model or authorizes M3.4.

The technical result is 171 validation queries and 82,255 candidates.
Recomputed nDCG@10, Recall@1, Recall@3 and MRR@10 match the reported values
with zero difference; fresh reload's largest score difference is
`3.3306690738754696e-16` against the `1e-7` tolerance. The M3.2 first-pass
checker now reports 30 PASS, 0 FAIL and 0 SKIPPED.

The frozen `shared_base.toml` and M3.2 `summary.json` contain experiment ID
`QPAF-M2_7-MTH-001`, while the authorization, run namespace and registry use
`QPAF-M3_2-MTH-001`. The review records this inherited naming discrepancy;
it does not edit the hash-bound M3.2 run. Validation nDCG@10 peaks at epoch 1
and falls afterward, so its selected maximum is not an independent estimate
of generalization. No baseline, QPAF comparison or scientific gain is claimed.

To replay, restore the 12 M3.1 inputs at the paths specified by its manifest
and verify their SHA-256 values. Then use Python 3.13.7, Torch 2.11.0+cpu,
NumPy 2.5.4, pandas 3.0.6 and PyArrow 26.0.0:

```powershell
python scripts/audit_m33_qarf.py
```

The script reruns the M3.1 seal verifier with external manifest pin
`0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893`.
Its output is read-only by default. M3.2's 16 MB predictions and checkpoints
are in Git; the large M3.1 input copies remain local and are not added here.
