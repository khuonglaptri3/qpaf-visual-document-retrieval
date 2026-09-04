# Experiment protocol changelog

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
