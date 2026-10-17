# Exploratory-12 recovery run

**COMPLETE AND VERIFIED.** Launched 2026-09-07 at 10:02:00 UTC (17:02 Vietnam time); completed at 11:42:29 UTC (18:42:29 Vietnam time). All twelve queries are present: four inherited and eight newly computed. Recovery elapsed time was 6,023.918 seconds. The saved independent review passed all 16 checks; the follow-up audit rechecked 78 artifact hashes and seven report/review pins, independently reconstructed 144 metrics, and visually inspected the chart.

- [Completed comparison](QPAF_EXPLORATORY12_RESULTS.md): Global/QARF/QPAF mean nDCG@10 = 0.952556 / 0.958333 / 1.000000.
- [Query 797 case study](QPAF_QUERY797_CASE_STUDY.md): all gain comes from one query; eleven queries already have Global nDCG@10 = 1.0.
- [Closeout verification receipt](../../../artifacts/vidoseek_exploratory12_closeout_review/closeout_review.json).
- [Next evaluation proposal](../../02_project_plan/QPAF_NEXT_EVALUATION_PROPOSAL.md): draft only; no new execution authorization or formal phase decision.

The following launch and automatic-finalization notes are retained as history. Their references to waiting, running, and pending visual review describe the pre-completion state and are superseded by this closeout. Original attempt, recovery outputs, approval snapshots, and generated report/plot bytes remain preserved. Both invocations are consumed; zero retries were performed.

The user replied "OK now continue" to the explicit recovery approval request. This authorizes Codex to make one recovery invocation, reuse the four verified query results, compute the eight absent results, use one CPU worker/thread with an additional six-hour cap, and perform no automatic retry. Codex will verify all twelve results and produce the comparison report after successful completion.

- [Approval record](../../../runs/exploratory12_recovery_preparation_20260907/execution_approval.json).
- [Launch receipt](../../../runs/exploratory12_recovery_preparation_20260907/launch_receipt.json); original parent PID `16168`. Always check process identity/start time, not PID alone.
- [Progress log](../../../runs/exploratory12_recovery_preparation_20260907/live_stdout.log).
- [Diagnostic log](../../../runs/exploratory12_recovery_preparation_20260907/live_stderr.log).
- [New attempt marker](../../../runs/vidoseek_exploratory12_recovery_v1/_ATTEMPTED.json).
- [Executed recovery config](../../../runs/vidoseek_exploratory12_recovery_v1/resolved_config.json).

The approved configuration byte SHA-256 is `51881b04780976bc4232df8c12a8d167894a06316835c469f6d4276b9e3e6419`; runner hash remains `6adb19f82ebb1037bcabc5bfd1174e95fe6c4728320febe0097cda5b88f49c09`. Source, original score inputs, original attempt, and scientific protocol remain unchanged.

Output: `runs/vidoseek_exploratory12_recovery_v1/`. Its four initial query checkpoints are inherited evidence, not newly completed recovery work. New results count only when query checkpoints 4–11 are durably saved. The runner enforces the additional 21,600-second cap and one-attempt guard. Do not launch another recovery, alter pinned source/config, delete outputs, or reset markers while waiting.

No complete result exists until the new `run_manifest.json` has `status=COMPLETE` and independent output/hash/metric checks pass. `_INCOMPLETE.json` records a handled failure/timeout; a hard termination may leave neither final marker. On either failure, preserve evidence and stop without retry.

Automatic finalization is also running separately (launched 10:10 UTC; initial PID `8208`), so a chat usage limit need not interrupt result verification/report generation. Its [launch receipt](../../../runs/exploratory12_recovery_preparation_20260907/finalizer_launch_receipt.json) pins the supervisor script. It waits for this existing recovery only; it cannot launch or retry the oracle. Every 30 seconds it records [checkpoint progress](../../../runs/exploratory12_recovery_preparation_20260907/monitor_progress.jsonl).

After a complete manifest, the helper runs the hash-pinned `review_result.py` and `write_report.py` in `runs/exploratory12_recovery_preparation_20260907/`. The verifier independently reconstructs all 12 rankings/metrics and the full bootstrap summary, checks all artifact hashes and parent lineage, and writes a separate review. The report generator then creates `docs/05_oracle_experiments/exploratory12/QPAF_EXPLORATORY12_RESULTS.md` and the comparison plot. Finalization logs and `finalization_status.json` are saved in the preparation directory. A generated report still requires Codex's visual inspection and final interpretation; a helper failure stops for inspection without rerunning the oracle.

The original run remains immutable under `runs/vidoseek_w7_exploratory12_v1/`. Full W7/W66, formal Phase 1 decisions, P1-03, training, Modal/GPU, and frozen P1-02 remain outside this approval. The final comparison is exploratory oracle headroom only.
