# M5.9 / G3 — Robustness decision

**Gate owner:** Tấn Phát (Research Lead / Gate Owner).
**Decision:** `LIMITED-CLAIM`. Owner confirmation: `PENDING_RESEARCH_LEAD`.
**Machine-readable rule:** [`criteria.json`](criteria.json), applied by
[`scripts/decide_g3.py`](../../../scripts/decide_g3.py) to the evidence pinned in
[`inputs.json`](inputs.json). The output is [`decision.json`](decision.json).

## Why this record exists

The workbook asks M5.9 whether the result is stable across seeds and checks, with a
`GO / LIMITED-CLAIM / NO-GO / BLOCKED` record. `frozen_protocol.md` §5 lists nine
conditions for a positive core claim, and `statistical_policy.md` §6 gives a
decision table. Neither maps the conditions to these four tokens. They also do not
say what happens when QPAF beats matched QARF but not the strongest deployable
baseline.

**This rule is post hoc.** It was written on 2026-10-28, after the accepted M5.7
result was known. It adds no threshold. The Research Lead chose the token mapping
for a failed item 4 (`LIMITED-CLAIM`, not `NO-GO`) from two options offered in the
working session.

## Rule

Precedence, first match wins:

1. **BLOCKED.** A core-roster acceptance is missing or names other report bytes
   (M5.1, M5.2, M5.3 QARF/QPAF, M5.4 QARF/QPAF, R7, M5.7). Or: the seeds differ from
   the three preregistered seeds, the query or W/T/L counts differ from 172, the R7
   replay differs, or a required value is missing or non-finite.
2. **NO-GO.** Seed-averaged QPAF − matched QARF nDCG@10 is `< 0.01`, or the CI95
   lower bound is `<= 0`.
3. **LIMITED-CLAIM.** Any of these:
   - a co-strongest baseline is not beaten (mean delta `<= 0`);
   - top-5% positive-gain share is `>= 0.90`;
   - latency or memory failed, or was not established (needs an accepted M5.5
     measurement on at least 1,000 measured queries);
   - reload differs by more than `1e-7`;
   - an output is non-finite.
4. **GO.** All nine items pass.

## Result

| Item | Evidence | Check |
| --- | --- | --- |
| 1. Three preregistered seeds | 20260820/21/22, all reviewed and accepted | PASS |
| 2. Mean QPAF − QARF ≥ 0.01 | +0.076175 | PASS |
| 3. CI95 lower > 0 | [+0.042928, +0.109909] | PASS |
| 4. Beats every co-strongest baseline | `train_fitted_static`: −0.006748, CI [−0.019028, +0.005269], W/T/L 7/152/13 | **FAIL** |
| 5. Top-5% gain share < 0.90 | 0.3104 | PASS |
| 6. Median fusion latency ≤ 10 ms | 2.426 ms, but only 171 measured queries (rule: ≥ 1,000) | **NOT ESTABLISHED** |
| 7. Peak CUDA < 1.50 GiB | 0.0324 GiB | PASS |
| 8. Finite outputs, reload ≤ 1e-7 | all six runs finite; max 4.44e-16 | PASS |
| 9. Independent review | M5.1–M5.4, R7 and M5.7 accepted | PASS |

Seed stability is high. The per-seed QPAF − QARF deltas range from 0.0745 to
0.0778 (std 0.0017). The negative baseline delta has the same sign on all three seeds.

## Claim boundary

**May be stated:** on ViDoSeek TEST-172, the frozen QPAF-v1 exceeds the matched
QARF-v1 in seed-averaged nDCG@10 on all three preregistered seeds. The result is
stable across seeds.

**May not be stated:**

- that QPAF improves on the strongest deployable baseline. It does not exceed
  `train_fitted_static`, and this negative result must be reported. The G2A freeze
  had already noted that learned QARF is a weak comparator.
- that QPAF meets the operational latency gate.
- any external or ViMDoc generalization. M5.8 is `NOT_RUN_DEFERRED`, and M5.10/G3A
  bounds the claim separately.

## Re-run

```bash
python scripts/decide_g3.py --inputs evidence/revisions/m5.9-001/inputs.json --expected-inputs-sha256 4c294fab62ef3c69e4369646194d95c48df083b16c2ae5a9243c884054df9222 --criteria evidence/revisions/m5.9-001/criteria.json --expected-criteria-sha256 121eb15edd9a032c7e4c5505be80d70a97ea279ef71f730a6d2a1df91a235017
```

The script only reads committed review records. It does not read test qrels, train,
evaluate, or authorize any run. With `--output`, it refuses to overwrite an existing
file.
