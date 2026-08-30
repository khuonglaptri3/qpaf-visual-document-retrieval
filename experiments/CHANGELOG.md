# Experiment protocol changelog

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
