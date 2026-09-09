# Experiment protocol changelog

## 2026-09-09 - W66 synthetic resource calibration interrupted; attempt consumed

- The user approved exactly one Codex invocation of `vidoseek_w66_resource_calibration_v1`. The admitted attempt started at `2026-09-09T08:29:35.312311+00:00` from commit `90719a8cbbdf5cc8fe7c31020b3b60810c297b09`; `_ATTEMPTED.json` records one consumed and zero remaining invocations.
- A 1,296.325-second telemetry gap aligned with Windows Kernel-Power sleep reason `Button or Lid`, violating the approved one-second telemetry contract. The run was stopped fail-closed and was not retried.
- Independent review verified the config, all 29 source snapshots, single-thread runtime pools, and the hash-sealed run-plan, 66-profile Global, and Global-selection checkpoints. No query checkpoint, calibration result, complete manifest, actual-label W66 result or scientific result exists.
- Partial resource evidence stayed within size limits but is not a completed runtime: 2,353 samples, 466,206,720-byte peak process-tree private memory, 4,262,223,872-byte minimum free RAM, 1,670,379-byte maximum output, and 2,290.438 final worker CPU-seconds.
- Next preparation is an exactly equivalent faster W66 candidate search and a separate recovery protocol with an automatic telemetry-cadence abort. Any live recovery requires new explicit approval; P1-02/P1-03, training and Modal/GPU remain unchanged.

## 2026-09-09 - W66 resource calibration prepared; execution closed

- Independently rechecked the completed W7 timing evidence and current W66 pins. The full 24-query W66 invocation remains a resource `NO-GO`: the available data support only conditional scenarios of about 21.76--43.51 hours and a 99.84-hour stress illustration, not a safe timeout.
- Prepared a separate synthetic calibration for audit index 1129. It loads the frozen 24-query subset with an explicit projection that excludes actual relevance, then applies one deterministic synthetic label to the selected 5,385-page query and runs the unchanged W66 query search plus fixed bootstrap probes.
- Added one-thread numeric/Arrow verification, parent-worker liveness checks, sleep inhibition, one-second CPU/memory/disk/output telemetry, 2-GiB private-byte and 100-MiB output limits, immutable checkpoint replay, complete-only finalization and no-retry failure evidence.
- The proposed 21,600-second cap is not execution permission. The closed config has zero approved seconds and zero invocations; no calibration output, W66 retrieval result, phase decision, training, Modal/GPU action or frozen P1-02 change was produced.

## 2026-09-08 - Exploratory-24 W66 sensitivity prepared; execution closed

- Bound a separate W66 proposal and runner to the exact 24-query W7 selection, normalized score bytes, metric/tie-break semantics, bootstrap settings and existing oracle primitives. The query-list SHA-256 is unchanged, and the 66-profile canonical SHA-256 is `c04139858954fd0a7f7baa5dad548f3675a41b8682e9798039508e4077da5973`.
- Added immutable W66 Global and query checkpoints, complete-only finalization, source/environment/Git guards, and synthetic equivalence, resume, tamper, failure and no-retry tests.
- The closed config records pending resource review, zero approved timeout and zero invocations. Preparation and tests produce no live W66 metric, attempt directory, formal P1-03 decision, training, Modal/GPU work or frozen P1-02 status change.
- `docs/QPAF_W66_EXPLORATORY24_EXECUTION_REVIEW.md` records the exact scope, resource uncertainty, proposed command and separate future approval boundary.

## 2026-09-08 - Exploratory-24 W7 completed and independently verified

- The user approved the exact prepared scope with “ok I approved”. One Codex local CPU invocation completed 24 frozen additional queries and 129,240 query-page pairs in 8,700.394 seconds, using one worker/thread under the 43,200-second cap with zero retries.
- Mean nDCG@10 is Global 0.817634, QARF 0.853845 and QPAF 0.903856. QPAF-minus-QARF is 0.050011 with query-bootstrap CI95 [0.008344, 0.101921], win/tie/loss 5/19/0 and top-5% gain share 0.666315. Six page assignments changed across five queries.
- Independent review verified 82 manifest artifacts, 50 checkpoint envelopes, 25 source snapshots, 960 raw ranking metrics and 415 aggregate metric/delta comparisons. The chart passed visual inspection. Evidence is in `runs/vidoseek_w7_exploratory24_v1/`, `artifacts/vidoseek_exploratory24_review/` and `docs/QPAF_EXPLORATORY24_RESULTS.md`.
- The W7 subset clears its exploratory continuation signals but cannot pass the formal Phase 1 gate. Full W7/W66, P1-03, training, Modal/GPU and frozen P1-02 remain closed; any later execution requires a separate approval.

## 2026-09-08 - Exploratory-24 page-level feasibility prepared; execution closed

- Froze the predeclared uniform 24-query sample from the 1,130-query remainder after excluding the original exploratory-12 indices. The exact audit indices and IDs are published with canonical query-list SHA-256 `95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b`; selection used no relevance, scores, fixed-audit per-query metrics or page-level outcomes.
- Added a separate guarded runner and closed config that reuse the unchanged W7/Global/QARF/QPAF query-sharded primitives for all 5,385 pages/query, with one CPU worker/thread, a 43,200-second cap, one invocation, zero retries and complete-only reporting. Existing run/config/source bytes remain unchanged.
- Nineteen focused tests and the 232-test full suite pass. Read-only preflight validates the 129,240-pair selection, input and headroom-trigger evidence without relevance loading or attempt consumption; the live command refuses before writes while approval is closed.
- This preparation produced no page-level oracle result, new retrieval metric, formal phase decision, training, Modal/GPU action or P1-02/P1-03 change. `docs/QPAF_EXPLORATORY24_EXECUTION_REVIEW.md` contains the exact future command and separate approval boundary.

## 2026-09-08 - Fixed-profile discovery audit completed and independently verified

- The user approved one Codex local CPU invocation for all 1,142 frozen ViDoSeek discovery queries, 5,385 pages/query and seven fixed W7 profiles, with one worker/thread, a 1,800-second cap and zero retries. The create-once attempt completed in 561.485 seconds; the authorization is consumed.
- Global selected visual-only and reached mean nDCG@10 0.875138; QARF reached 0.908268. The mean theoretical QPAF-over-QARF gain bound is 0.091732, with 216 queries retaining positive headroom and 926 already at the QARF ceiling. The review advice is `HEADROOM_POSSIBLE_REVIEW_COMPUTE`.
- Independent verification checked 1,171 artifact hashes and all 1,142 checkpoint envelopes, then recomputed 32,012 metric values from all 6,149,670 raw pairs. The report, per-query table, source summary and visually checked chart are recorded under `docs/QPAF_FIXED_PROFILE_AUDIT_RESULTS.md` and `artifacts/vidoseek_fixed_profile_audit_review/`.
- This audit measured fixed-profile Global/QARF and a mathematical QPAF headroom bound only. It did not execute page-level QPAF search, W66, training, Modal/GPU or a formal phase decision; P1-02/P1-03 remain frozen and every later invocation still requires separate approval.

## 2026-09-07 - Fixed-profile discovery audit prepared; execution closed

- Prepared a separate fixed-W7-profile discovery audit runner, hash-pinned closed config and synthetic fixtures after the user approved implementation/testing. It streams one query at a time, preserves existing Global/QARF metric and tie-break semantics, and reports only the theoretical remaining QPAF gain bound; no page-level search is called.
- Added explicit NumPy/library and Arrow thread limits, source/environment guards, a separate create-once attempt, 1,800-second worker deadline, immutable query checkpoints, complete-only summaries and no-retry refusal. Existing frozen source/configs and all old experiment outputs remain unchanged.
- Live preparation performed only read-only byte-hash/metadata/ID preflight and closed-CLI refusal. Final tests, pins and preservation checks are recorded in `artifacts/vidoseek_fixed_profile_audit_preparation/verification_receipt.json`; the proposed command and approval scope are in `docs/QPAF_FIXED_PROFILE_AUDIT_EXECUTION_REVIEW.md`.
- No execution approval, live audit attempt, new metric, QPAF search, W66, training, Modal/GPU, schedule change or formal phase decision was produced. No previous result is invalidated.

## 2026-09-07 - Exploratory-12 recovery closed out and saved-ranking case study verified

- Recovery completed at 11:42:29 UTC: 12 results, four inherited and eight newly computed. The existing independent review passed 16 checks; the completion audit rechecked all 78 artifact hashes and seven report/review pins. The original report and chart remain byte-identical; chart visual QA passed.
- Added `scripts/inspect_exploratory12_saved_rankings.py` and a separate diagnostic artifact directory. Reconstruction passed 144 existing metric checks without oracle search. Query 797's relevant page moves 4/3/1 under Global/QARF/QPAF; two saved BM25-to-dense page assignments explain the improvement. The other eleven queries are at the Global ceiling.
- Updated current status/tracking and added `docs/QPAF_QUERY797_CASE_STUDY.md` plus a review-only next-evaluation proposal. Historical approval records and all original/recovery run bytes remain preserved. No metric, protocol, source pin, threshold or earlier result was changed or invalidated; no new execution, full phase decision, training or Modal/GPU action occurred.

## 2026-09-07 - One checkpoint recovery invocation approved and launched

- The user replied "OK now continue" to the exact recovery approval request. Recorded actual approval and reviewed/approved hashes in `runs/exploratory12_recovery_preparation_20260907/execution_approval.json`; opened only the separate recovery authorization block.
- Launched one Codex CPU recovery at 10:02 UTC: four saved results reused, eight absent queries to compute, one worker/thread, additional 21,600-second cap, no automatic retry. No original source/config/evidence changed. Result status remains incomplete until all twelve outputs and the manifest are independently verified.
- Current logs and no-retry boundary are in `docs/QPAF_EXPLORATORY12_RECOVERY_RUN_STATUS.md`. This approval does not open full W7/W66, formal phase decisions, training, Modal/GPU, or frozen P1-02.

## 2026-09-07 - Separate checkpoint recovery prepared; execution closed

- Added `scripts/recover_vidoseek_exploratory12.py`, its closed config, and fixture tests. The launcher preserves the original run, validates/copies its reviewed checkpoints to a new output directory, retains the parent science identity, and computes only absent queries after new approval. Original oracle source and config pins are unchanged.
- Added a separate create-once recovery marker, one-worker/thread and additional six-hour deadline guards, lineage/output hashes, incomplete-output handling, and explicit reused-versus-new timing labels. No execution permission was opened and no recovery run was launched.
- Updated two original pilot lifecycle tests to reflect the consumed approved snapshot and to make draft-refusal setup explicit. Recovery fixture equivalence and read-only preflight passed; verification evidence and future execution scope are in `docs/QPAF_EXPLORATORY12_RECOVERY_EXECUTION_REVIEW.md`.

## 2026-09-07 - Exploratory-12 interruption audited; no retry

- Resumed the unfinished follow-up after the earlier Codex session ended with `usage_limit_exceeded`. The experiment continued beyond that session, but its Python processes are now gone; the exact termination cause is unknown. Four query checkpoints exist and no complete or handled-failure manifest exists.
- Verified all 12 Global checkpoints, four saved query results, 18 checkpoint envelopes, source/config pins, input hashes, shared Global selection, and reconstructed saved-ranking metrics. Audit status: `PASS_SAVED_CHECKPOINTS_ONLY`, recorded separately under `artifacts/vidoseek_exploratory12_interruption_review_20260907/`. No oracle search or partial aggregate result was produced; original run bytes are unchanged.
- Corrected the current tracker status from Running to Interrupted / incomplete and saved `docs/QPAF_EXPLORATORY12_INTERRUPTION_HANDOFF.md`. Eight query searches and final statistics/report remain. The consumed no-retry authorization was not reopened; recovery implementation and separate execution review remain necessary. No scientific protocol, source pin, or phase gate changed.

## 2026-09-07 - One Codex exploratory-12 CPU invocation approved

- The user accepted the prepared exploratory protocol and one-run resource/retry scope: "So do it for me, I need to reach the goal to see the result as soon as possible". Recorded actual approval text, timestamp, review hashes, and scope in the separate pilot config and `runs/exploratory12_preparation_20260907/execution_approval.json`.
- Opened only this pilot's protocol-adoption and execution fields for actor `codex`. The reviewed source, 12 fixed IDs, all 5,385 pages/query, W7 primitives, bootstrap, one-worker/thread resources, six-hour limit, and no-retry policy are unchanged. Full W7/W66, formal phase decisions, training, Modal/GPU, and frozen P1-02 remain outside this authorization.

## 2026-09-07 - Separate exploratory-12 implementation prepared; execution closed

- Added a separate runner and hash-pinned closed configuration for the existing fixed 12-query proposal, using the frozen W7 search/checkpoint primitives without editing them. The proposed change selects Global only across those 12 queries; it is explicitly ineligible for formal Phase 1 gates.
- Added synthetic equivalence and lifecycle/guard tests, reverified the score-bundle preflight and calibration evidence, and prepared the exact invocation/output contract in `docs/QPAF_EXPLORATORY12_EXECUTION_REVIEW.md`.
- No protocol adoption or live execution was authorized or performed. No real-label oracle result, full W7, W66, GPU/extraction, or learned result was produced. Prior score outputs, original proposal bytes, scientific thresholds, phase schedule, and P1-02 status are unchanged. Existing user changes remain uncommitted and preserved.

## 2026-09-06 - Full-page synthetic CPU calibration PASS reviewed; attempt consumed

- Verified the human-run outputs from approved commit `b252080d4ea32ea7b5b11450b54a7cb58f214990` and protocol SHA-256 `8d37e6c4dbe46146e9f2d5d3da439a2c72f4e06f3d9c8ce33511484fceccbe34`. Copied immutable marker and manifest bytes into `artifacts/vidoseek_p1_02r_oracle_w7_v1_full_page_calibration/`; originals remain intact.
- Attempt marker: 924 bytes, SHA-256 `9e555783f6d4f3d4de7015cbf0614b8301c4ddad643a4cec90a080e26c20b6d7`. Manifest: 1,671 bytes, SHA-256 `622d2d946bfddd9ff7571626e6ac31b3b45a7b41789413bec9864f6b43078629`.
- PASS: query index 570, 5,385 pages, synthetic relevance, 100 resamples, one CPU worker/thread, 752.7996488000001 seconds worker time, below the 2,700-second limit. Attempt-to-completion timestamps span 755.77775 seconds. Review evidence: `artifacts/vidoseek_p1_02r_full_page_calibration_review.json`.
- The calibration invocation is consumed (zero remaining); the create-once marker is now present in both checkouts. The executed YAML is retained unchanged as the historical approval snapshot; its pre-run counter is not a new authorization. No rerun is allowed.
- Resource review: assuming the same cost for every real query gives 9.950199061685188 CPU days for 1,142 queries. This is an illustrative projection from one synthetic query, not a measured full-W7 duration. A 12-query discovery alternative is drafted in `docs/vidoseek_w7_exploratory12_proposal.json`; it is not approved, implemented, or runnable.
- No W7, W66, Modal/GPU, or learned run was started. P1-02 remains BLOCKED, and no phase gate or scientific threshold was changed.

## 2026-09-05 - One human P1-02R-O1 full-page calibration authorized, not executed

- Authorization text: `Approve local preparation and commit of the guard/provenance amendment for exactly one human-run P1-02R-O1 full-page synthetic calibration from parent commit 9821d100a4d64d73e8772f48f68f30388f851c06, using query index 570, 5,385 pages, 100 resamples, one CPU worker/thread, a 2,700-second hard stop, and no retry. Use an explicit commit allowlist. Do not execute the calibration, W7, Modal/GPU, P1-03/P1-03R, or learned QPAF, and keep P1-02 BLOCKED`
- Bound the approval commit to parent `9821d100a4d64d73e8772f48f68f30388f851c06`, the non-merge direct-child rule, and an exact seven-path allowlist. The live guard also requires a clean tracked checkout and one-thread CPU environment.
- Opened only the full-page calibration, its engineering-manifest write, and temporary checkpoint permissions for one unconsumed human invocation. The immutable attempt marker is created before preflight and forbids retry after either success or failure.
- Did not execute calibration or create its marker/manifest. Full W7, general oracle/output, performance-probe, Modal/GPU, P1-03/P1-03R, and learned-QPAF permissions remain closed; P1-02 remains `BLOCKED` and the task graph and September 5 schedule are unchanged.

## 2026-09-04 - P1-02R-O1 local review hardening committed; execution closed

- Review-hardening authorization text: `Go ahead with a local-only P1-02R-O1 review-hardening patch and commit it using an explicit allowlist. Fix the recorded-state CLI preflight, add Git provenance enforcement for future calibration/full-W7 guards, and add synthetic end-to-end calibration tests. Do not run calibration, W7, Modal/GPU, P1-03/P1-03R, or learned QPAF, and do not relabel P1-02.`
- Fixed the read-only CLI preflight to accept the already-recorded performance-probe marker and manifest only in recorded/sharded-prepared protocol states; exact evidence hashes, schemas, cross-links, and non-result boundaries are still validated.
- Reused one Git checkout guard for the consumed performance probe and both future calibration/full-W7 paths. A future execution approval must name an exact parent commit and exact changed-path allowlist, and the live checkout must be its clean tracked, non-merge direct child.
- Added temporary-fixture calibration coverage for success, create-before-preflight consumption, failed preflight, timeout queue cleanup, immutable manifest creation, synthetic relevance, and retry refusal. No live calibration or W7 path was invoked.
- Kept the protocol status and every execution/readiness flag unchanged: calibration, W7, Modal/GPU, P1-03/P1-03R, and learned QPAF remain unauthorized; P1-02 remains `BLOCKED`.

## 2026-09-02 - P1-02R-O1 query-sharded resumable W7 wrapper prepared; execution closed

- Recorded the user's preparation-only approval verbatim and advanced only the P1-02R-O1 protocol state to `query_sharded_resumable_wrapper_prepared_review_required`.
- Added a two-pass local CPU wrapper without changing `src/oracle_study/qpaf.py`: pass 1 checkpoints all seven W7 Global-profile metrics per query and freezes the shared dataset-level profile only after canonical all-query reduction; pass 2 runs the unchanged query-local QARF/QPAF primitives and checkpoints one result per query.
- Checkpoints use atomic create-once JSON envelopes with a canonical content SHA-256, run-identity SHA-256, per-query input SHA-256, fixed candidate-audit order, and exact phase inventories. Resume reuses only exact validated checkpoints, computes an absent expected checkpoint once, and fails closed without overwrite on invalid existing state, unexpected files, or an incomplete post-pass inventory.
- Added deterministic exact-equivalence tests against frozen `run_qpaf_oracle(..., grids=("w7",))` for rows, summary/bootstrap, and subgroups, plus byte-preserving complete/partial resume and tamper/identity/inventory rejection tests.
- Proposed, but did not authorize or run, one synthetic full-page calibration at candidate-audit index 570 over all 5,385 pages: one CPU worker/thread, 100 bootstrap resamples, a 2,700-second hard stop, and no retry. The quoted CMD command remains closed in the protocol.
- Kept every live execution/output guard false. No live checkpoint, calibration attempt/manifest, W7 result, Modal/GPU work, P1-03/P1-03R work, learned QPAF, or frozen P1-02 relabel was performed.

## 2026-09-02 - P1-02R-O1 bounded CPU probe PASS recorded and authorization closed

- Recording authorization text: `Approve preparing and committing the P1-02R-O1 bounded CPU performance-probe PASS recording using the existing immutable attempt marker and run manifest. Close the consumed probe authorization, update only provenance, task state, protocol, and tests, and return a review-only full-W7 runtime/resource recommendation. Do not execute or authorize W7, Modal/GPU, P1-03/P1-03R, learned QPAF, or relabel P1-02`
- Execution provenance: the one corrective human invocation ran from commit `aebeef11d5964b9c45ea56242f41ad4202aec95c` against protocol SHA-256 `2965484635457fd8a54fa6bb7821a530df7904b348eb2871b90752d70863db13`. The replacement authorization is consumed (`1/1`), has zero invocations remaining, and cannot be retried automatically.
- Immutable engineering evidence: `_ATTEMPTED.json` is 908 bytes with SHA-256 `f394faa42c3ac324e4378bde332a01794848780248b86cda12ccf8bc7fc61ace`; `run_manifest.json` is 2,894 bytes with SHA-256 `2b030610ad7f8fb261799aa1d972ae47ee86724ea536eb4f317e6c2d71704549`. Their schema, protocol/source/attempt cross-links, one-thread CPU environment, and non-result boundaries validate.
- Measured bounded cases: three systematic queries with deterministic synthetic relevance completed at 128/256/512 pages in `0.6704216001089662`/`3.7113504000008106`/`13.628036600071937` seconds. No actual relevance, oracle result, scientific result, full W7, Modal, or GPU was used.
- Review-only resource estimate: linear query scaling plus the measured page-growth range implies 4.97–20.02 single-worker days for 1,142 queries x 5,385 pages; the three-point power fit gives 10.68 days, and a quadratic-log model gives 9.15 days. These derived values exclude full 10,000-resample bootstrap, I/O/materialization, process/checkpoint, contention, and thermal overheads. They are not full-corpus measurements.
- Recommendation and boundary: `NO-GO` for the current monolithic single-worker full W7. A query-sharded/resumable CPU wrapper with exact-semantic equivalence tests is the recommended next preparation for a separate review; it is not authorized here. All probe/oracle/output, Modal/GPU, P1-03/P1-03R, and learned-QPAF guards are closed; P1-02 remains `BLOCKED`, P1-02R remains `PASS`, and no dependency is rewritten.

## 2026-09-02 - Corrective one-replacement P1-02R-O1 CPU probe authorized, not executed

- Prior invocation: the human invoked the command authorized by `fd2f411214b4b47750ffe6488bb0b5b654b55f66`, but CPython stopped during preinitialization with `preconfig_init_utf8_mode: invalid PYTHONUTF8 environment variable value`. The unquoted CMD form stored `PYTHONUTF8` as `1 ` with a trailing space, so the project module never loaded.
- Produced state: no `_ATTEMPTED.json`, input preflight, performance probe, run manifest, or oracle result was produced. The prior one-invocation authorization is nevertheless consumed under its fixed no-retry rule; this amendment does not reopen or retry it.
- Corrective authorization text: `Approve preparing and committing a corrective P1-02R-O1 execution-guard/provenance amendment for exactly one replacement human-run CPU performance-probe invocation. Record the prior invocation as failed before Python/project startup because the approved CMD used unquoted set assignments and set PYTHONUTF8 to 1 ; no attempt marker preflight, probe, manifest, or oracle result was produced. Replace the command with quoted CMD assignments, preserve all fixed limits and no-retry rules, and do not execute the probe yourself, W7 oracle, Modal/GPU, or P1-03, and do not relabel P1-02.`
- Replacement provenance: exactly one separately approved human invocation is available from one clean, non-merge direct child of `fd2f411214b4b47750ffe6488bb0b5b654b55f66` whose changed paths exactly equal the seven guard/provenance files. It is not an automatic retry under the consumed approval.
- Corrected future CMD command: `set "OMP_NUM_THREADS=1" && set "MKL_NUM_THREADS=1" && set "OPENBLAS_NUM_THREADS=1" && set "NUMEXPR_NUM_THREADS=1" && set "PYTHONUTF8=1" && set "PYTHONIOENCODING=utf-8" && set "PYTHONPATH=src" && C:\Python313\python.exe -m oracle_study.vidoseek_p1_02r_oracle performance-probe --protocol configs\vidoseek_p1_02r_oracle_w7_v1.yaml`.
- Unchanged limits and stop rule: CPU-only, one worker/thread, query indices `[0,570,1141]`, page ladders `[128,256,512]`, one repetition, 100 bootstrap resamples, at most 1,536 rows per case, synthetic relevance only, 120 seconds per case, 300 seconds total, and no automatic retry after the replacement starts.
- Scientific boundary: Codex did not execute the replacement, W7 oracle, Modal/GPU, P1-03, or learned QPAF and produced no result. P1-02 remains `BLOCKED`, P1-02R remains `PASS`, P1-03 remains blocked, and no task dependency is rewritten.

## 2026-09-02 - One human-run P1-02R-O1 CPU probe authorized, not executed

- Status: `bounded_cpu_performance_probe_execution_approved`; exactly one human invocation is authorized from the reviewed safeguard baseline `024f2f0a0998f0c781ac738d259603c6bbf29ba9`. Codex did not execute the command, and no attempt marker, probe manifest, W7 oracle result, Modal/GPU work, or P1-03 work was produced.
- Authorization text: `Approve preparing and committing the execution-guard/provenance amendment for exactly one human-run P1-02R-O1 bounded CPU performance probe from commit 024f2f0a0998f0c781ac738d259603c6bbf29ba9. Keep the fixed limits and no-retry rule. Do not execute the probe yourself, W7 oracle, Modal/GPU, or P1-03, and do not relabel P1-02.`
- Checkout provenance: execution requires one clean, non-merge direct child of `024f2f0a0998f0c781ac738d259603c6bbf29ba9`; its changed paths must exactly equal the seven guard/provenance files recorded in the protocol. Any later commit or tracked modification closes the guard.
- One-attempt enforcement: the command atomically creates `artifacts/vidoseek_p1_02r_oracle_w7_v1_probe/_ATTEMPTED.json` before input preflight. Creation consumes the authorization; any failure stops without a PASS manifest, and an existing marker prevents retry.
- Fixed limits are unchanged: CPU-only, one worker/thread, query indices `[0,570,1141]`, page ladders `[128,256,512]`, one repetition, 100 bootstrap resamples, at most 1,536 rows per case, synthetic relevance only, 120 seconds per case, and 300 seconds total.
- Scientific boundary: only the probe-specific execution/engineering-output guards are open. Full W7 oracle/output, Modal/GPU, P1-03, learned-QPAF, and general output guards remain false; P1-02 remains `BLOCKED`, P1-02R remains `PASS`, and no task dependency is rewritten.

## 2026-09-01 - P1-02R-O1 pre-execution safeguards prepared for review

- Status: `preexecution_safeguards_prepared_review_required`; the protocol-bound input preflight, immutable engineering run-manifest writer, and bounded CPU performance-probe entry point are prepared and tested locally. The performance probe and W7 oracle were not executed, and no manifest or oracle result was written.
- Authorization text: `Approve local preparation and commit of the P1-02R-O1 pre-execution safeguards: add a protocol-bound input preflight, an immutable run-manifest writer, and a bounded CPU performance-probe entry point with tests. Do not execute the performance probe or W7 oracle, do not write oracle results, do not run Modal/GPU or P1-03, and do not relabel P1-02. Return the complete diff, proposed probe limits, runtime stop condition, and exact future command for review.`
- Preflight contract: read-only validation of pinned source/input bytes and hashes, Parquet metadata, manifest cross-links, integrity-review PASS, and frozen task boundaries; no relevance values, oracle computation, or persisted report.
- Proposed probe limits: CPU-only W7 timing; fixed candidate-audit query indices `[0,570,1141]`; systematic page ladders `[128,256,512]`; one repetition; 100 bootstrap resamples; no actual relevance; at most 1,536 rows per case; one sequential worker with one CPU thread; one create-once engineering manifest containing timings/provenance only.
- Runtime stop: terminate the active child at 120 seconds or when the 300-second ladder budget is exhausted; write no manifest on failure and never retry automatically. A protocol/source/input/approval/checkout mismatch or pre-existing output is an earlier hard stop.
- Exact future CMD command for review only: `set OMP_NUM_THREADS=1 && set MKL_NUM_THREADS=1 && set OPENBLAS_NUM_THREADS=1 && set NUMEXPR_NUM_THREADS=1 && set PYTHONUTF8=1 && set PYTHONIOENCODING=utf-8 && set PYTHONPATH=src && C:\Python313\python.exe -m oracle_study.vidoseek_p1_02r_oracle performance-probe --protocol configs\vidoseek_p1_02r_oracle_w7_v1.yaml`. It is currently fail-closed and requires a separate explicit one-invocation human approval/provenance patch.
- Scientific boundary: all performance-probe, oracle/output-write, Modal/GPU, P1-03, and learned-QPAF guards remain false. Full W7 remains unready and unmeasured; P1-02 remains `BLOCKED`, P1-02R remains `PASS`, and no P1-03 or Phase 2 dependency changes.

## 2026-09-01 - P1-02R post-hoc W7 oracle amendment prepared for review

- Status: `protocol_prepared_review_required`; only the separately versioned protocol, task-graph record, and static contract tests are prepared. No oracle command or output was produced.
- Authorization text: `Approve creating and committing a separately versioned P1-02R post-hoc oracle/task-graph amendment using the verified local score bundle. Prepare the protocol and tests only. Do not execute oracle analysis, Modal/GPU work, or P1-03, and do not relabel frozen P1-02. Return the complete amendment diff and stop/go gates for review.`
- Frozen input: `artifacts/vidoseek_p1_02r_import/retrieval_scores.parquet`, 248,445,561 bytes and 6,149,670 rows, byte SHA-256 `32b39da19e9507a0a5060157630cb40bf5c6bcf6464d88e4bb6136888473173b`, logical-content SHA-256 `41c55a82fd4cd3607347aba68461a11dd4a0781f1e6825a107e44bb4544315e7`, coverage 1.0, and zero uncovered queries. `full_score` remains unavailable and unnecessary for this QPAF-only oracle contract.
- Frozen design: W7 over BM25/dense/visual scores; exhaustive Global and per-query QARF profile search; QARF-initialized, fixed-order, at-most-two-sweep candidate-level coordinate ascent; mean per-query nDCG@10; page-ID tie-break; seed 20260820; 10,000 query-bootstrap resamples.
- Readiness boundary: all-corpus runtime is unmeasured, and protocol-bound preflight/run-manifest support is not implemented. All local-oracle, output-write, Modal, GPU, P1-03, and learned-QPAF execution flags remain false pending review and a separate approval.
- Outcome gates for a future separately approved W7 run: stop learned QPAF below mean delta 0.01; permit only W66 protocol review at mean delta at least 0.03 with CI95 lower bound above 0 and top-5%-gain share below 0.90; otherwise revise or stop after human review. No W7 outcome automatically unblocks P1-03 or Phase 2.
- Scientific boundary: P1-02 remains `BLOCKED`; P1-02R remains a verified post-hoc score-bundle `PASS`; P1-02R-O1 is a preregistered post-hoc oracle upper-bound protocol, not a result, HEAVEN claim, learned model, deployment result, or task-graph relabel.

## 2026-08-31 - P1-02R full extraction integrity verified and execution closed

- Status: `full_extraction_integrity_verified`; the one authorized human-run invocation completed, was consumed, and has zero remaining authorized invocations. The current checkout closes Modal, full-extraction, and GPU execution guards; any retry or second invocation requires new approval.
- Execution provenance: Function call `fc-01M19RE4SXMJ54M15049QSMXKA`, source commit `c7d84aaee0e9caab691a11bba377f4a87c6e059c`, executed protocol status `approved_l4_chunked_full_extraction_execution_only`, and executed protocol-config SHA-256 `cfbfcb24ae477a93b3d6a65b40022d688b8172babb2e8080f82363f73fdd8be2`.
- Imported evidence: receipt SHA-256 `467e8c32e468f065306539d0a22d161431c9af411a0e1475fc9fb297c8a88c87`, extraction-manifest SHA-256 `7600d3483d526710d2613a37f030daec71596b20ed73d9cebb3b1a1ad507b7b8`, and success-marker SHA-256 `ce95947b5a160847208dacf90bd6cc71a804007a2fc8ddd1356b1bee5101dd2b`.
- Measured run: 1,142 queries x 5,385 pages = 6,149,670 pairs per score table in 143 query chunks and 11 page chunks, fixed query/page/visual limits 8/512/128, 7,818.803704091 seconds total on NVIDIA L4 with 22.034 GiB reported VRAM, and `full_score_produced=false` by protocol.
- Integrity result: all four payload byte hashes and both score-table logical-content hashes match the manifest; streamed local checks passed for exact schemas and counts, unique aligned keys, finite and bounded values, exact min-max normalization, branch-rank permutations with page-ID tie-breaking, candidate provenance, coverage 1.0, zero missing relevant pairs, and zero uncovered queries.
- Versioned evidence: commit the receipt, manifest, success marker, coverage report, 1,142-row candidate audit, and integrity review. The 82,665,894-byte raw-score and 248,445,561-byte retrieval-score Parquet payloads remain local and hash-addressed rather than stored in Git.
- Scientific boundary: this is a verified post-hoc recovery score bundle, not a frozen P1-02 PASS, oracle analysis, learned result, HEAVEN result, deployable QPAF result, or P1-03 authorization. Frozen P1-02 and P1-03 remain blocked pending an explicit task-graph decision.

## 2026-08-30 - P1-02R one human-run L4 chunked full-extraction approval

- Status: `approved_l4_chunked_full_extraction_execution_only`; the run is approved but not executed.
- Approval text: `Approve one human-run P1-02R chunked full-extraction invocation on Modal L4 using frozen limits query=8, page=512, visual batch=128. Update and commit only the execution guards and provenance. Do not execute Modal yourself, run P1-03, or relabel frozen P1-02`.
- Approved preparation: source commit `09aa4bad08fd5362a64537b506e48dca640cfb4e` and prepared protocol SHA-256 `49e63f2b017fa66a43a3af4d6189a2ab218b61fff838270ebfab954f4933b421`.
- Authorized Function: only `extract-vidoseek-p1-02r-scores`, requesting one L4 with query chunks at most 8, page chunks at most 512, passage/query encode batches at most 2/8, and visual score batch 128.
- Human-run command: `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; modal run --write-result artifacts\vidoseek_p1_02r_score_extraction_full.json modal_app.py::extract_vidoseek_p1_02r_scores`.
- Unchanged: dataset/revision, prepared corpus, BM25, BGE-M3, DSE, ColQwen2.5, raw-score definition, qrels boundary, coverage gate, frozen P1-02 `BLOCKED` record, and P1-03 block.
- Execution boundary: the coding agent did not run Modal or allocate GPU. No automatic retry or second invocation is authorized; a failure requires review and new approval.

## 2026-08-30 - P1-02R L4 calibration recorded and chunked full extraction prepared

- Status: `l4_cost_calibration_recorded_chunked_full_extraction_prepared`; no Modal Function or GPU execution is currently authorized.
- Local-preparation authorization text: `Record the P1-02R L4 calibration result and prepare a memory-safe chunked full-extraction implementation locally. Do not execute Modal or GPU.`
- Exact calibration evidence: `artifacts/vidoseek_p1_02r_l4_cost_calibration.json`, SHA-256 `b53d0e885e9e979f7dc85b4588cae70d305a7ad17da9d303abf0b278310b93af`, Function call `fc-01M18YTTTN7Y33Z8W0Z3ZQGY5J`, source commit `6fdbd99ebd349ff1a9ce950faf154d6518a4b8bb`, and executed protocol-config SHA-256 `77cd5f8920cb9f01d3a69ccd409e15391e68e4a759d8dfad9d7b889eb98307af`.
- Measured calibration: NVIDIA L4 with 22.034 GiB VRAM; fixed 8-query x 512-page sample; 4,096 pairs; 588.160496293 seconds total; 8,288,322,048 bytes (7.719 GiB) peak allocation; sample-score-cache SHA-256 `9550af44e6cf89fdb8bfe4a7b9fcfd366caf27aa673ec1f79fdcdb6cd1277807`; `full_extraction_started=false`.
- Non-result projection: 7,860.383886004963 seconds (2.183439968334712 L4-hours), excluding queueing, retry/OOM backoff, BM25/BGE/DSE regeneration, full output materialization, and price changes. This is engineering review input, not a full result or monetary estimate.
- Prepared implementation: a separate `extract-vidoseek-p1-02r-scores` path validates/reuses the frozen parent BM25/BGE-M3/DSE matrices, caps query/page chunks at 8/512, keeps passage/query encode batches at or below 2/8 and visual scoring at 128, persists atomic resumable embedding/visual-score chunks, and streams final Parquet row groups without materializing the 6,149,670-row table in RAM.
- Execution boundary: the completed audit and calibration are closed against rerun; `modal_allowed=false`, `full_extraction_execution_allowed=false`, and `gpu_execution_allowed=false`. No full-extraction command is authorized or recorded. Frozen P1-02 remains `BLOCKED`, and P1-03 remains blocked.

## 2026-08-30 - P1-02R bounded L4 cost-calibration execution approval

- Status: `approved_l4_cost_calibration_execution_only`; full extraction remains unapproved under P1-02R.
- Approval text: `Approve execution of the bounded P1-02R L4 cost calibration on Modal. Do not run full extraction.`
- Authorized Function: only `calibrate-vidoseek-p1-02r-cost`, requesting L4 with the frozen 8-query x 512-page systematic sample, 4,096 all-corpus pairs, and visual score batch 128.
- Unchanged: dataset/revision, prepared corpus, BM25, BGE-M3, DSE, ColQwen2.5, raw-score definition, qrels boundary, coverage gate, original P1-02 `BLOCKED` record, and P1-03 block.
- Human-run command: `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; modal run --write-result artifacts\vidoseek_p1_02r_l4_cost_calibration.json modal_app.py::calibrate_vidoseek_p1_02r_cost`.
- Execution boundary: the coding agent did not run Modal or allocate GPU. This approval does not cover `extract_vidoseek_scores`, any other Modal Function, changed limits/batches, full score extraction, or treating the calibration projection as an experimental result.

## 2026-08-30 - P1-02R CPU audit PASS and bounded L4 calibration preparation

- Status: `cpu_audit_passed_cost_calibration_prepared`; no Modal or GPU execution is currently authorized.
- Preparation authorization text: `Record the P1-02R CPU-audit PASS and prepare a bounded L4 cost-calibration command locally. Do not execute Modal or GPU`.
- Verified audit evidence: returned artifact `artifacts/vidoseek_p1_02r_coverage_audit.json`, SHA-256 `bbb947ca9b04bf291e94298516d8529888b677eee92e212dd8967fac413beca0`, Function call `fc-01M18KYEZTRZANMQKXZ6KY467H`, source commit `318b09d487eb93ea4690ebe7cb54812d4bffdc72`, and executed protocol-config SHA-256 `1411724e3bc330f1821ab75ff1bb84838334a214c1c65261c53044c7b1100c17`.
- Gate result: coverage 1.0; 1,142/1,142 relevant pairs selected; zero missing relevant pairs; zero queries without a relevant candidate; 5,385 pages per query and 6,149,670 derived candidate pairs; qrels were not used to construct candidates; `gpu_used=false`.
- Calibration preparation: add a fixed 8-query x 512-page systematic sample over frozen order, containing every sampled page for every sampled query (4,096 pairs) at the unchanged visual score batch 128. It measures ColQwen2.5 model load, passage/query encoding, visual scoring, peak allocation, and a componentwise linear full-workload projection. It does not alter or call the frozen `run_extraction` path.
- Execution guard: the prepared Function is `calibrate-vidoseek-p1-02r-cost` on L4, but `modal_allowed=false`, `cost_calibration_execution_allowed=false`, and `gpu_execution_allowed=false`. The prior P1-02 L4 approval is not reused.
- Prepared future command, not executed: `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; modal run --write-result artifacts\vidoseek_p1_02r_l4_cost_calibration.json modal_app.py::calibrate_vidoseek_p1_02r_cost`.
- Boundary: P1-02 remains `BLOCKED`; this PASS is only the separately versioned P1-02R coverage gate. No calibration result, full score extraction, QPAF result, P1-03 authorization, or monetary cost claim is recorded.

## 2026-08-30 - P1-02R all-corpus CPU coverage audit approval

- Status: `approved_cpu_audit_execution_only`; GPU execution remains disabled.
- Draft authorization text: `Prepare the P1-02R post-hoc protocol draft. Keep the retrievers unchanged, revise only the candidate-pool rule, add local tests, and do not run Modal.`
- Local-integration authorization text: `Approve P1-02R all-corpus protocol for local integration and CPU-audit preparation only. Do not execute Modal`.
- CPU-audit authorization text: `Approve execution of the P1-02R CPU-only coverage audit on Modal. Do not run GPU`.
- Frozen parent: P1-02 remains `BLOCKED` under extraction protocol `072599c016f836637655485fc628a20c33f7284622fe808466fb7e6626714486`; this draft does not replace or retroactively pass it.
- Change: replace score-depth shortlist membership with every prepared ViDoSeek corpus page for every query. The pool is deterministic, query-independent, score-independent, and frozen before qrels are used for coverage auditing.
- Derived workload: 1,142 queries x 5,385 pages = 6,149,670 candidate pairs, about 9.06 times the measured expanded-pool mean of 594.1979 candidates per query.
- CPU-audit integration: use the frozen prepared-corpus marker and annotation hash to test qrel-page membership directly, without loading score caches or materializing all candidate pairs. A separate CPU-only, Volume-backed Modal entry point is prepared behind an execution-approval guard.
- Unchanged: dataset/preprocessing, BM25, BGE-M3, DSE, ColQwen2.5, raw-score definitions, normalization, metrics, qrels boundary, and the zero-uncovered-query gate.
- Execution boundary: no Modal command was run by the coding agent. Only `audit-vidoseek-p1-02r-all-corpus` is authorized, with no GPU or Secret; `gpu_execution_allowed=false`, and the prior L4 approval is not reused because the candidate-scoring workload changed materially.

## 2026-08-29 - ViDoSeek full extraction GPU

- Status: approved by the user.
- Approval text: `Approve L4 for full ViDoSeek extraction`.
- Change: request `L4` and use a ViDoSeek-only 86,400-second timeout for `modal_app.py::extract_vidoseek_scores`; keep the generic ViDoRe extractor on `A100-40GB` and its existing timeout.
- Evidence: the bounded ViDoSeek calibration completed on NVIDIA L4 with 22.034 GiB available, 7.720 GiB maximum allocation, 100% candidate coverage, and manifest SHA-256 `2213b96ee99f4e2409355db80d650590393a8953f67f90de8259cd84373499c7`.
- Unchanged: model IDs/revisions, batches, candidate depths, 23.5 decimal-GB preflight guard, preprocessing, qrels boundary, and output integrity gates.
- Execution status: local protocol/code preparation only; no Modal command was executed for this change.
