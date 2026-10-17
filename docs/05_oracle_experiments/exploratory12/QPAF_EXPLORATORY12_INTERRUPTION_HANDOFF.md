# Exploratory-12 interruption handoff

Updated 2026-09-07. **The original attempt is interrupted and incomplete. Four saved query results passed integrity review; eight are missing. No recovery was launched.**

## Verified current state

- Repository: `C:\Users\HP\OneDrive\tlcn`; Git HEAD `99823b96c9afd52e11e7ddb001f5b74bf0a1e314`.
- Original run: `runs/vidoseek_w7_exploratory12_v1/`. Keep every byte, checkpoint, snapshot, log, and attempt marker.
- Actual approval: `runs/exploratory12_preparation_20260907/execution_approval.json`. One Codex CPU invocation, one worker/thread, 21,600-second cap, zero automatic retries. `_ATTEMPTED.json` records one consumed and zero remaining.
- The earlier session ended with a usage-limit error at 05:42:17 UTC. Checkpoints continued through 06:22:36 UTC; the limit alone does not establish why the experiment stopped. At 09:34 UTC, original processes were gone, the worker PID belonged to an unrelated process, and there was no complete or handled-failure manifest.
- Global pass: 12/12 checkpoints. QARF/QPAF: 4/12 checkpoints (positions 0–3, audit indices `147, 396, 510, 682`). Missing positions 4–11 have audit indices `792, 797, 848, 880, 881, 940, 1023, 1081`.
- Integrity review: [checkpoint_integrity_review.json](../../../artifacts/vidoseek_exploratory12_interruption_review_20260907/checkpoint_integrity_review.json), status `PASS_SAVED_CHECKPOINTS_ONLY`. All saved checkpoint hashes, query inputs, fixed-weight ranking metrics, and Global-selection chain match. This is a partial-evidence audit, not a completed comparison.
- Canonical config SHA-256: `ebff9cd0f3194530d3d4408bd7a657229641e83cf5e8a7ae576ff02a2edc354e`.
- Checkpoint run identity SHA-256: `1b4e382fc32114aff97e1123c6a390a29037ab2a071d42aa419011c2897193a9`.

The audit loaded the selected score rows to verify saved metrics. It did not run coordinate search, calculate a partial mean/bootstrap, alter the original run, or consume a new invocation. Seven audit checks passed. Source/config pins remain unchanged. No commit or push was performed; pre-existing local changes remain present.

## Work still needed to obtain the result

The original runner exposes only `preflight` and `run`, and `run` refuses any existing output directory. It cannot currently resume this pilot. Do not delete the marker, rename away the output, bypass the guard, invoke the full-W7 launcher, or call the worker directly to evade the one-attempt limit.

A separate recovery amendment would need the following concrete scope before live execution is proposed:

1. Prepare a closed recovery entry point/config using a new run ID and output directory, explicitly linked to this consumed attempt and integrity review. Preserve the original directory; validate and copy its checkpoints into the new directory only under the recovery contract.
2. Preserve the exact 12 queries, 5,385 pages/query, input/source hashes, shared Global selection over all 12, W7 profiles, two-sweep search, tie-breaks, seed `20260820`, and 10,000-resample bootstrap. Reuse the four verified complete query checkpoints and compute only the eight absent results. The interrupted fifth query has no durable result to reuse.
3. Keep the original checkpoint science identity when validating inherited checkpoints, and separately bind the new execution approval, source snapshot, lineage, resource cap, attempt marker, and output manifest. Do not change old hashes to force checkpoint acceptance.
4. Test with synthetic fixtures that continuation equals an uninterrupted run, inherited checkpoints are never recomputed or overwritten, invalid/drifted checkpoints fail closed, authorization is required, and timeout/retry guards remain enforced. No live search belongs in these tests.
5. Distinguish inherited work from newly measured timings. Original checkpoint timestamps and three-decimal progress-log timings are available; the original in-memory timing list was not finalized. Do not present time spent reading inherited checkpoints as their original search runtime or fabricate lost timings.
6. Only after the implementation, fixtures, source pins, and command are reviewable, obtain a new explicit execution authorization covering actor, one invocation, CPU limits, additional wall-time budget, checkpoint reuse, and no automatic retry. The old six-hour allowance does not reset itself.
7. After authorized completion, independently verify all 12 query results, artifact inventory/hashes, lineage, reconstructed rankings, bootstrap, and the exploratory-only decision marker. Then write the complete Global/QARF/QPAF comparison and chart.

Preparation update (2026-09-07): a separate recovery launcher, closed config, and fixture tests are now implemented. See [the execution review](QPAF_EXPLORATORY12_RECOVERY_EXECUTION_REVIEW.md) for exact scope, pins, checks, and future command. No recovery has been authorized or launched. Full W7/W66, P1-03, learned training, Modal/GPU, formal phase decisions, and frozen P1-02 remain unchanged.

## Why execution is stopped

`Tasks.md`, P1-02R-O1's 2026-09-07 execution amendment, authorizes invocation **"once ... with a 21,600-second cap and no retry"**. The immutable `_ATTEMPTED.json` has `remaining_authorized_invocations: 0`. The current request to check and continue interrupted progress permits this audit and status recording; it does not explicitly replace that specific no-retry restriction. New execution therefore requires a separate human decision. There is no approval request for routine read-only checks or status-document edits.
