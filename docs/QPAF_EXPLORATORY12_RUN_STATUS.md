# Exploratory-12 live run

Recovery closeout (2026-09-07): the separately approved recovery completed at 11:42:29 UTC and all twelve results passed independent verification; chart visual QA passed. See [current recovery status](QPAF_EXPLORATORY12_RECOVERY_RUN_STATUS.md) and [completed comparison](QPAF_EXPLORATORY12_RESULTS.md). The original attempt described below remains immutable and incomplete; the following interruption notes are historical.

Current status (2026-09-07, checked at 09:34 UTC / 16:34 Vietnam time): **INTERRUPTED / INCOMPLETE; 4 of 12 query checkpoints verified; no completed comparison.**

The previous Codex session ended at 05:42:17 UTC with `usage_limit_exceeded`. The experiment continued afterward: query checkpoints 2 through 4 were saved later, with the last at 06:22:36 UTC (13:22:36 Vietnam time). At this review, neither original Python process remained and no Python process was running. PID `18784` had been reused by `ETDCtrl.exe`; PID existence alone must not be treated as worker liveness. The exact experiment termination time and cause are unknown. Neither `run_manifest.json` nor `_INCOMPLETE.json` exists.

Read-only follow-up completed:

- [Checkpoint integrity audit](../artifacts/vidoseek_exploratory12_interruption_review_20260907/checkpoint_integrity_review.json): `PASS_SAVED_CHECKPOINTS_ONLY`. Verified the approved config, environment, live/snapshotted source hashes, attempt consumption, all 18 checkpoint envelopes, query identities, input hashes, and the shared Global selection chain.
- Recomputed all seven Global-profile metrics for all 12 queries and reconstructed Global/QARF/QPAF rankings and metrics for the four saved query results from their weights. All matched. No coordinate search, bootstrap, new invocation, or partial aggregate result was produced.
- [Process/session evidence](../artifacts/vidoseek_exploratory12_interruption_review_20260907/process_and_session_evidence.json) records the observed process state, session-limit error, log hashes, and checkpoint timestamps.
- The audit's before/after inventory confirms the original run directory was not modified. The review script is preserved at `runs/exploratory12_preparation_20260907/audit_interruption.py`.

Still unfinished: query positions 5–12 (audit indices `792, 797, 848, 880, 881, 940, 1023, 1081`), final per-query/summary/timing/preflight exports, the complete manifest, full metric/bootstrap verification, and the promised comparison report/chart. No full-sample mean or research conclusion is available.

The one-run authorization is consumed. The `execution_authorized: true` value in the original config is a historical approval snapshot; the immutable attempt marker and existing output directory close execution operationally. No retry or resume is authorized. A separate recovery launcher, closed config, and fixture tests are now prepared; see [the execution review](QPAF_EXPLORATORY12_RECOVERY_EXECUTION_REVIEW.md). The [continuation handoff](QPAF_EXPLORATORY12_INTERRUPTION_HANDOFF.md) preserves the original audit and boundaries.

## Historical launch record

Status at launch: **RUNNING; no completed comparison yet.**

The user approved the prepared 12-query experiment on 2026-09-07 after reviewing its one-worker CPU scope, six-hour limit, and no-retry behavior. Codex launched the single permitted invocation at 2026-09-07 05:14:27 UTC (12:14:27 Vietnam time).

- Parent Python PID: `8360`; worker PID observed after startup: `18784`.
- [Launch receipt](../runs/exploratory12_preparation_20260907/launch_receipt.json).
- [Approval record](../runs/exploratory12_preparation_20260907/execution_approval.json).
- [Progress log](../runs/exploratory12_preparation_20260907/live_stdout.log).
- [Diagnostic log](../runs/exploratory12_preparation_20260907/live_stderr.log).
- [Immutable attempt marker](../runs/vidoseek_w7_exploratory12_v1/_ATTEMPTED.json).
- [Executed configuration snapshot](../runs/vidoseek_w7_exploratory12_v1/resolved_config.json).

Startup passed the protocol-bound checks. The Global pass completed for all 12 selected queries and froze one shared profile before QARF/QPAF search. Only completed query checkpoints count as progress; a live process does not establish a result.

The invocation is consumed. Do not launch again, delete the run directory, or restart from a checkpoint automatically. The original protocol, source, limits, and selected query IDs must remain unchanged while the worker runs. The runner enforces its six-hour limit internally. Absence of `run_manifest.json` with `status=COMPLETE` means no complete experiment result; `_INCOMPLETE.json` records a handled failure or timeout.

After completion, use the prepared read-only metric/hash checks in `runs/exploratory12_preparation_20260907/review_result.py`. They reconstruct saved rankings and metrics without repeating the coordinate search. Review outputs go in the separate `artifacts/vidoseek_exploratory12_review/` directory. Preserve the immutable run directory.

Full W7/W66, formal Phase 1 decisions, learned-model training, and Modal/GPU remain outside this authorization. This run's result is an exploratory oracle upper bound on 12 queries.
