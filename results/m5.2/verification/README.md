# M5.2 - Technical verification evidence

Main receipt: [m5.2-001](../../../evidence/revisions/m5.2-001/README.md).

**Current status: COMPLETED / ACCEPTED.** On 2026-10-27, Khương confirmed that
M5.2 had been reviewed and requested completion. The exact confirmation is in
[`owner_confirmation.json`](owner_confirmation.json), linked by SHA-256 from
acceptance event `QPAF-REG-20261027-0001`. The reviewer was not named in that
confirmation; no direct reviewer signature or new replay is attributed.

- `test_summary.json`: 13 M5.2 tests and 4 M5.1 tests passed on the exact
  implementation source bytes. This does not claim a local full-pytest run.
- `ci_implementation.json`: all five implementation CI jobs passed on
  Windows/Linux with the repository's Python 3.11/3.14 workflow.
- `read_only_replay.json`: all six input streams passed replay. The 45
  monitored files and file sets were unchanged. The Python audit hook
  recorded no qrels/checkpoint opens or workspace mutations during replay.
  Its elapsed time measures the data audit, not model or fusion latency.
- `governance_events.jsonl`: append-only successor events preserve the
  historical registry. The latest acceptance event records registry status
  PASS and task status COMPLETED, following the owner's report of completed
  review. Earlier STARTED/pending events retain their historical meaning.

Event `QPAF-REG-20261025-0003` corrects the owner/actor display metadata in
event `QPAF-REG-20261025-0002`, which was damaged by PowerShell's US-ASCII
stdin encoding. The original line is retained. Receipt/input hashes,
technical results and the acceptance state at that time were unchanged.

The frozen receipt, its README, verification record, and original test/replay
records retain their creation-time PENDING_USER_REVIEW fields. Current task
acceptance is recorded separately above; none of those sealed bytes changed.
Tan Phat must bind the receipt and input hashes into the separate
authorization/provenance records for M5.3/M5.4. Payload restoration and
replay instructions: [M5.2 handoff](../../../docs/06_handover/m5.2-cache-parity-handoff.md).
