# A003 independent review sign-off — 2026-10-21

**Amendment:** `QPAF-M1.5-A003`, SHA-256 `0afacbde32d2aa4a31a53c39888f11cd20d03af5febfe28aac074de4d23e514c`

**Independent reviewer:** Thanh (`@xThanhSaDec`), separate from amendment requester and implementer Tấn Phát
**Decision:** `ACCEPTED_FOR_D1_READINESS`

Thanh explicitly confirmed in the working session on 2026-10-21 that his name
may be recorded as the accepting reviewer for A003 and the M2.10 replay.
Codex performed the technical inspection and replay at Thanh's request;
this record does not claim that Thanh personally executed the commands.

The acceptance is based on
[`A003.technical-review-001.md`](QPAF-M1.5-A003.technical-review-001.md)
and [`m2.10-003/audit.json`](../../../revisions/m2.10-003/audit.json):

- The expansion reads frozen score arrays and ordered page IDs, not qrels,
  split membership or query-ID content. Its one-document rule was recorded
  before implementation and used unchanged for all splits and methods.
- A003 remains **post hoc** because the uncovered training query was known
  before the amendment. It is not represented as a preregistered hypothesis.
- The source matrices and all six regenerated candidate payloads matched
  their recorded byte hashes. Candidate replay and real-input binding passed.
- All 1,142 queries have a relevant candidate; candidate coverage alone makes
  no claim about ranking quality or learned-model performance.

This is the independent reviewer sign-off required by amendment procedure
step 6. The original amendment and its pending state remain historical records.
The effective accepted policy for the next pilot package is
`qpaf_m28_top_document_expansion_v1`, as bound by `m2.8-002` and `m2.7-003`.
This sign-off does not authorize an M3 execution.
