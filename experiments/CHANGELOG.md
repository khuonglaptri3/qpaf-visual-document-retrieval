# Experiment protocol changelog

## 2026-08-30 - P1-02R all-corpus candidate-pool local integration

- Status: `approved_local_integration_only`; CPU-audit execution remains disabled.
- Draft authorization text: `Prepare the P1-02R post-hoc protocol draft. Keep the retrievers unchanged, revise only the candidate-pool rule, add local tests, and do not run Modal.`
- Local-integration authorization text: `Approve P1-02R all-corpus protocol for local integration and CPU-audit preparation only. Do not execute Modal`.
- Frozen parent: P1-02 remains `BLOCKED` under extraction protocol `072599c016f836637655485fc628a20c33f7284622fe808466fb7e6626714486`; this draft does not replace or retroactively pass it.
- Change: replace score-depth shortlist membership with every prepared ViDoSeek corpus page for every query. The pool is deterministic, query-independent, score-independent, and frozen before qrels are used for coverage auditing.
- Derived workload: 1,142 queries x 5,385 pages = 6,149,670 candidate pairs, about 9.06 times the measured expanded-pool mean of 594.1979 candidates per query.
- CPU-audit integration: use the frozen prepared-corpus marker and annotation hash to test qrel-page membership directly, without loading score caches or materializing all candidate pairs. A separate CPU-only, Volume-backed Modal entry point is prepared behind an execution-approval guard.
- Unchanged: dataset/preprocessing, BM25, BGE-M3, DSE, ColQwen2.5, raw-score definitions, normalization, metrics, qrels boundary, and the zero-uncovered-query gate.
- Execution boundary: no Modal command was run. `modal_allowed=false`, `cpu_audit_execution_allowed=false`, and `gpu_execution_allowed=false`; the prior L4 approval is not reused because the candidate-scoring workload changed materially.

## 2026-08-29 - ViDoSeek full extraction GPU

- Status: approved by the user.
- Approval text: `Approve L4 for full ViDoSeek extraction`.
- Change: request `L4` and use a ViDoSeek-only 86,400-second timeout for `modal_app.py::extract_vidoseek_scores`; keep the generic ViDoRe extractor on `A100-40GB` and its existing timeout.
- Evidence: the bounded ViDoSeek calibration completed on NVIDIA L4 with 22.034 GiB available, 7.720 GiB maximum allocation, 100% candidate coverage, and manifest SHA-256 `2213b96ee99f4e2409355db80d650590393a8953f67f90de8259cd84373499c7`.
- Unchanged: model IDs/revisions, batches, candidate depths, 23.5 decimal-GB preflight guard, preprocessing, qrels boundary, and output integrity gates.
- Execution status: local protocol/code preparation only; no Modal command was executed for this change.
