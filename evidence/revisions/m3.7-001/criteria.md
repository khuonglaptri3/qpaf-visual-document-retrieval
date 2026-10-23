# G2 decision criteria — one-seed development gate

**Gate owner:** Tấn Phát — Research Lead / Protocol & Gate Owner.
**Status:** `CONFIRMED_BY_RESEARCH_LEAD`
**Machine-readable rule:** [`criteria.json`](criteria.json), applied by
[`scripts/decide_g2.py`](../../../scripts/decide_g2.py).

## Why this record exists

The workbook (row 44) asks M3.7 for a `GO / PARTIAL–INVESTIGATE / NO-GO–PIVOT /
BLOCKED` decision on whether learned QPAF outperforms matched learned QARF.
`run_policy.md` §4 says the remaining seeds run only "after the one-seed
development gate decision". The frozen protocol sets numeric thresholds only
for the final three-seed claim (`frozen_protocol.md` §5, `statistical_policy.md`
§6), and no numeric rule was frozen for the one-seed gate.

**This rule is post hoc.** It was written on 2026-10-23, after the M3.5 result
(nDCG@10 delta +0.114132, CI95 [+0.077501, +0.152040]) was known. To limit
that, it introduces **no new threshold**: it applies the frozen thresholds
unchanged to the single development seed `20260820`.

## Rule

| Check | Threshold (frozen) | Evidence |
| --- | --- | --- |
| Mean QPAF − QARF nDCG@10 | `>= 0.01` | M3.5 `comparison.json` |
| Paired query-bootstrap CI95 lower bound | `> 0` | M3.5 `comparison.json` |
| Top-5% positive-gain share | `< 0.90` | M3.5 `comparison.json` |
| Median online fusion latency (QPAF) | `<= 10.0` ms/query | M3.6-004 `technical_review.json` |
| Peak learned-fusion CUDA allocation (QPAF) | `< 1.50` GiB | M3.6-004 `technical_review.json` |
| Fresh-process reload score difference (QPAF) | `<= 1e-7` | M3.6-001 `integrity_review.json` |
| Finite outputs | integrity `PASS` | M3.6-001 `integrity_review.json` |

Precedence (first match wins):

1. **BLOCKED** — M3.3, M3.5, M3.6 technical, M3.6 owner or M3.6 QA acceptance
   missing; pairing or the M3.5 replay invalid; test labels opened; any
   required value missing or non-finite. No scientific interpretation.
2. **NO-GO–PIVOT** — mean `< 0.01` or CI95 lower `<= 0`.
3. **PARTIAL–INVESTIGATE** — quality passes, but concentration `>= 0.90` or an
   operational gate fails.
4. **GO** — everything passes.

The four outcomes map to the M4.3/M4.6 branches `continue_qpaf`,
`revise_once`, `negative_qpaf_result`, and none (BLOCKED).

## What G2 does not claim

G2 uses one seed. Both checkpoints were selected on the same validation split
the comparison uses. No baseline, confirmation or test data is involved. A
`GO` lets the team request authorization for seeds `20260821`/`20260822` and
the M4 tasks. It does not authorize them, and it is not the final three-seed
claim.

## Confirmation

Tấn Phát (Research Lead / Gate Owner), in the working session on
2026-10-23T02:58:43Z, recorded verbatim by Claude at their request:

> I approved as Tấn Phát, confirm for m3.6-005 and approved probe run plan.
> Finally, I confirm the m3.7 criteria (frozen threshold-seed20260820)
