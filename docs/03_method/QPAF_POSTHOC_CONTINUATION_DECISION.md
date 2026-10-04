# QPAF post-hoc continuation decision

**Decision:** `PROCEED_LOCAL_METHOD_CORE_ONLY`

The user directed Codex on 2026-09-10 to continue toward the recommended test of whether QPAF really improves retrieval. This records a narrow continuation amendment: implement and test P2-01 and P2-02 locally, then prepare the matched learned QARF-versus-QPAF confirmation protocol for separate review.

## Evidence supporting continuation

On the same frozen exploratory-24 ViDoSeek subset, oracle QPAF improved mean nDCG@10 over oracle QARF by `0.05001054981241935` with W7 and `0.03206569322602797` with W66. Both query-bootstrap lower bounds are positive and both top-5%-gain shares are below `0.90`. Independent reviews verified the underlying rankings, metrics, checkpoints, hashes, and scope flags.

This is enough to justify implementing the label-free learned method. It is not proof that learned QPAF improves, because the oracle used relevance labels to select weights and both grids used the same 24-query subset.

## Scope opened by this decision

- P2-01: deterministic 13-feature builder with no relevance or qrels input.
- P2-02: zero-initialized linear QARF/QPAF gates, convex fusion, masked listwise loss, and mathematical tests.
- Local CPU implementation and tests only.

## Scope that remains closed

- Formal P1-03 and the formal Phase 1 `PASS` claim.
- Any optimizer step or trained checkpoint.
- P2-03/P2-04 execution, Modal/GPU use, paid compute, or new oracle invocation.
- Any claim that learned, deployable, or externally generalizable QPAF has improved retrieval.

The machine-readable authority and thresholds are in [`artifacts/qpaf_posthoc_continuation_decision_v1.json`](../../artifacts/qpaf_posthoc_continuation_decision_v1.json).

## Required confirmation gate

The next result-bearing protocol must compare learned QPAF against matched learned QARF and the strongest deployable fixed baseline using identical candidate rows, split, features, loss, optimizer, early stopping, seeds, hardware class, and compute budget. A positive claim requires all three preregistered seeds, mean QPAF-minus-QARF nDCG@10 of at least `0.01`, query-bootstrap CI95 lower bound above `0`, median added fusion latency at most `10.0 ms/query`, peak learned-fusion CUDA allocation below `1.50 GiB`, reproducible checkpoint reload, and independent artifact review.
