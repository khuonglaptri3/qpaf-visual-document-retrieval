# M5.2 - Technical verification evidence

Main receipt: [m5.2-001](../../../evidence/revisions/m5.2-001/README.md).

- `test_summary.json`: 13 M5.2 tests and 4 M5.1 tests passed on the exact
  implementation source bytes. This does not claim a local full-pytest run.
- `ci_implementation.json`: all five implementation CI jobs passed on
  Windows/Linux with the repository's Python 3.11/3.14 workflow.
- `read_only_replay.json`: all six input streams passed replay. The 45
  monitored files and file sets were unchanged. The Python audit hook
  recorded no qrels/checkpoint opens or workspace mutations during replay.
  Its elapsed time measures the data audit, not model or fusion latency.
- `governance_events.jsonl`: append-only successor events preserve the
  historical registry. Registry status remains STARTED with technical
  verification passed and owner/independent review pending.

Event `QPAF-REG-20261025-0003` corrects the owner/actor display metadata in
event `QPAF-REG-20261025-0002`, which was damaged by PowerShell's US-ASCII
stdin encoding. The original line is retained. Receipt/input hashes,
technical results and the pending-acceptance state are unchanged.

Owner acceptance and independent review remain PENDING_USER_REVIEW.
Tan Phat must bind the receipt and input hashes into the separate
authorization/provenance records for M5.3/M5.4. Payload restoration and
replay instructions: [M5.2 handoff](../../../docs/06_handover/m5.2-cache-parity-handoff.md).
