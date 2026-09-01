# Experiment protocol changelog

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
