# M3.1 — Matched pilot input seal

**Technical verification: PASS. Human acceptance: PENDING_USER_REVIEW.**

Owner: Khương. Authority: completed workbook, Milestones row 39. Source commit:
`2113b043cbcd56b8a18467dd91f52ef95662dac1`. Run: `RUN-QPAF-M3_1-SEAL-001-20261021T142631Z-A01`.

Read the [Vietnamese review report](../../../docs/GUILDLINE_OVERVIEWS_PROPOSAL/M3_1_REVIEW.md).

- [External manifest pin](seal_pin.json), [manifest](manifest.json), [verification](verification.json).
- [Execution](execution.json), [read-only replay](read_only_replay.json), [authorization](authorization.json).
- [Software checks](software_checks.json), [test log](tests.txt), [AI code review](code_review.json).
- [Payload reconstruction](payload_materialization.json), [documentation cleanup](documentation_cleanup.json).
- [Append-only local events](governance_events.jsonl); historical registries stay unchanged.

The complete payload is local at `results/m3.1/RUN-QPAF-M3_1-SEAL-001-20261021T142631Z-A01/inputs/`. This revision retains
portable evidence, not the Parquet payloads or duplicate test labels. Verify the
run directory with the external pin, as shown in the report. The copied manifest's
input paths are relative to that run directory, not this evidence directory.

No learned training, model forward or test-label deserialization occurred in the
M3.1 seal/replay. M3.2/M3.4 execution remains a separate authorization decision.
