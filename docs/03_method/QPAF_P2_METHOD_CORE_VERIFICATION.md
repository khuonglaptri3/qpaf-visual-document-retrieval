# QPAF P2 local method-core verification

## Outcome

P2-01 and P2-02 pass their local, non-training contracts. This verifies that the proposed learned QPAF computation is deterministic and that its forward/loss gradients match the declared mathematics. It does **not** confirm improved retrieval performance because no optimizer step or learned evaluation was executed.

The implementation lives under `oracle_study.learned` rather than adding new top-level `oracle_study/*.py` files. Completed exploratory protocols froze a non-recursive hash inventory of the top-level package; the nested package preserves those historical artifacts without changing their source pins.

## Implemented contract

- Thirteen label-free features: three normalized scores, three normalized ranks, three median-relative margins, three query-level top-1/top-2 gaps, and rank disagreement.
- Normalized-rank convention: best candidate `1`, worst candidate `0`; ascending page ID breaks equal-score ties.
- Zero-initialized 42-parameter linear QARF and QPAF gates.
- Query-pooled QARF weights and page-specific QPAF weights.
- Convex three-channel fusion.
- HEAVEN-compatible deterministic max aggregation by evaluation-unit group when candidate input is already in ascending page-ID order.
- Masked listwise cross-entropy with relevance-gain targets and stable `log_softmax`.

## Verification

Focused P2 verification passed `14` tests. The tests cover 100-run feature determinism, permutation stability, padding isolation, absence of a relevance argument, equal weights at zero initialization, checkpoint reload, hand-computed loss, deterministic tied-max gradient routing, float64 gradcheck, finite gradients, and exact agreement between Eq. 11 and PyTorch autograd. Ruff passed on every new implementation and test file.

The repository suite passed `386` tests with one stale completed-run preflight assertion deselected. The unfiltered suite has the same `386` passes and one failure: the historical test expects the optimized W66 attempt directory not to exist, while that run has since completed and its immutable attempt evidence correctly exists. That test is hash-pinned by the completed W66 protocol, so this patch does not rewrite it or historical provenance.

Machine-readable hashes and commands are recorded in [`qpaf_p2_method_core_verification.json`](../../artifacts/qpaf_p2_method_core_verification.json).

## Actual blocker to a real QPAF improvement claim

The ViMDoc dataset, document-level HEAVEN mapping, and label-free 2,000-query confirmation sample are materialized and frozen on Modal. However, [`score_input_probe_vimdoc.json`](../../artifacts/score_input_probe_vimdoc.json) records `score_extraction_started=false`, and the repository contains no verified ViMDoc three-channel training score bundle. Therefore QARF/QPAF training cannot yet begin reproducibly.

The next safe task is preparation of a closed ViMDoc score-extraction and matched-training package. It must pin the selected queries, candidate construction, BM25/BGE-M3/ColQwen2.5 revisions, score normalization, document aggregation, split, features, loss, optimizer, early stopping, seeds, GPU, timeout, output manifests, and exact claim thresholds. Modal/GPU extraction and training remain separate result-bearing approvals.
