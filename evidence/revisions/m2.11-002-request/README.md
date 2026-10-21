# M2.11 — D1 resubmission request (decision not recorded)

**Requested by:** Tấn Phát (Research Lead), 2026-10-21. **Decision owner:** Thanh.
[`request.json`](request.json) binds every input by SHA-256. It is **not** a D1
decision. Only a new create-once `evidence/revisions/m2.11-002/decision.json`,
written by the D1 owner after the reviews below, can replace the `BLOCKED`
decision in [m2.11-001](../m2.11-001/README.md).

## What changed since the BLOCKED decision

| m2.11-001 blocker | Resolution | Evidence |
| --- | --- | --- |
| `M2.8_ZERO_UNCOVERED_GATE_FAILED` | Amendment A003 adds label-free top-document pages. Macro recall is 1.0 and no query is uncovered (train 799/799, validation 171/171, test 172/172). | [A003](../../M1_FINAL/02_protocol/amendments/QPAF-M1.5-A003.md), [m2.8-002](../m2.8-002/README.md) |
| `M2.7_REAL_INPUT_BINDING_NOT_FROZEN` | A separate binding pins the unchanged `matched.json` and binds the real cache, candidates, qrels, query texts and splits. Real-row batch order is identical for QARF and QPAF for all three seeds, checked without training. | [m2.7-003](../m2.7-003/README.md) |
| `NAMED_HUMAN_REVIEW_PENDING` | **Still open** (see below). | — |

The [M2.10 replay](../m2.10-002/README.md) rehashed the payloads, replayed
the candidates from the full score matrices, replayed the binding and passed
all test groups.

## Steps for Thanh and the reviewer

1. **A003 independent review** (amendment procedure step 6). Check that the
   rule reads no labels or query-ID content, that it is recorded as post hoc,
   and that one fixed policy was used with development coverage audited before
   test. Record a named sign-off next to the amendment and append the M1.7
   `governance_record` event.
2. **M2.10 confirmation.** With the three M2.8-001 `scores.npy` files and the
   M2.8-002 Parquet files present locally, run
   `python scripts/audit_m210_a003_readiness.py --output evidence/revisions/m2.10-003/audit.json`
   and check that it reproduces m2.10-002.
3. **Named independent D1 review**, then record
   `evidence/revisions/m2.11-002/decision.json` (`PASS`, `PARTIAL`, `BLOCKED`
   or `FAIL`) in the format of m2.11-001, citing the hashes in `request.json`.

Getting the payloads: the three score matrices are in Modal Volume
`qpaf-m28-score-cache` (workspace `tlcn-group1`) under
`runs/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01/<channel>/scores.npy`.
Running `python scripts/run_m28_expansion.py --develop` regenerates the
M2.8-002 Parquet files deterministically in a new namespace. To audit the
exact frozen run instead, its Parquet files can be shared and checked against
`m2.8-002/bundle_hashes.json`.

Until the D1 owner records a non-blocked decision, M3 stays closed. A D1 PASS
still does not authorize a pilot run by itself: every M3 run needs its own
authorization record under the run policy §3.
