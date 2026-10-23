# M3.6 OOM-attribution source revision — 2026-10-23

**Decision owner:** Tấn Phát — Research Lead / Protocol Owner.
**Status:** `PENDING_RESEARCH_LEAD_APPROVAL`
**Amends:** [m3.6-005](../m3.6-005/criteria_revision.md), which source
of OOM attribution counts. Nothing else changes.

## What happened

The m3.6-005 probe ran once (`RUN-QPAF-M3_6-SYS-002-20261023T025923Z-A01`,
app `ap-6dVacK0O5OPY9CIhWdjYK7`, source commit `959f512`):

- *below* (2,048 MiB) completed;
- *above* (4,608 MiB) failed. The client received
  `InternalFailure: Server has lost track of input`;
- Modal retried the above input 7 times on its own. The provider export
  ([`provider_stats_probe.json`](../m3.6-005/provider_stats_probe.json)) shows
  1 successful input, 1 failed input, 9 containers, 8 errored containers;
- Modal's app logs
  ([`provider_app_logs_probe.txt`](../m3.6-005/provider_app_logs_probe.txt))
  contain 8 lines `Runner killed (SIGKILL), exit code: 137. Most often this
  happens when the process runs out of memory…`, one per errored container.

m3.6-005 accepts the OOM wording "in its error or in a provider exit reason".
The pinned classifier looked for provider exit reasons only in the stats
export, which has no such field. So it returned `INCONCLUSIVE` and the
[m3.6-005 review](../m3.6-005/technical_review.json) records
`technical_verdict: BLOCKED`. That record stays as it is.

## New rule

A Modal runner-kill line in the provider app logs of the same app counts as a
provider exit reason, under all of these conditions:

1. Only lines that start with `Runner killed (SIGKILL)` count. The probe
   prints nothing of that form, so application output cannot qualify.
2. Every such line must carry the m3.6-005 OOM wording (`exit code 137` or
   `out of memory`).
3. Their number must equal the provider's `container_error_count`. Each
   errored container needs its own attributed kill.
4. Every other m3.6-005 condition still applies unchanged: exactly one
   successful and one failed input, every container beyond the below control
   errored, and any completed above-limit attempt is
   `ENFORCEMENT_NOT_DEMONSTRATED`.

`scripts/m36_memory_probe.py` `classify_with_provider_logs` implements this,
through `--classify … --provider-logs`. Applied to the same run, it returns
`ENFORCEMENT_DEMONSTRATED`, which makes A02 bounded below 4,096 MiB and A03
below 5,120 MiB by Modal's own accounting. The exact peak stays `UNAVAILABLE`.
The new review goes to `evidence/revisions/m3.6-006/technical_review.json`.

## Status, cost and controls

- **Post hoc, twice.** m3.6-005 was written after the A02/A03 results were
  seen. This revision was written after the probe returned `INCONCLUSIVE`
  and after it was known that the new reading turns it into
  `ENFORCEMENT_DEMONSTRATED`. QA should weigh it as such.
- **No new run.** No GPU invocation, rerun or edit of any raw record. The
  probe records, provider export and app logs are used byte-for-byte as
  committed in `7af8312`.
- **Log provenance.** The logs were exported read-only with the observer
  environment (Modal SDK 1.6.2, as in m3.6-004) by
  `python -m modal app logs ap-6dVacK0O5OPY9CIhWdjYK7` under profile
  `buiphat251399`, after the app stopped (03:03:21Z) and before commit
  `7af8312` (03:04:48Z). The exact fetch second was not recorded.
- **Provider retries.** `retries=0` was configured. Modal still retried the
  failed input, as the m3.6-005 authorization's `provider_retry_note`
  anticipated. The client made exactly two calls. All 7 retries were
  OOM-killed; none completed.
- **In-sandbox RSS.** The below control's gVisor `ru_maxrss` read 6.5 GB under
  the 4 GiB limit. That confirms gVisor process RSS is not container usage.
- **Unchanged:** all m3.6-004 verdicts, every threshold, and the requirement
  for Khương's owner acceptance and Thanh's QA acceptance of the m3.6-006
  review.

## Approval

Pending: Tấn Phát's own words go here verbatim, with the time of the reply.
