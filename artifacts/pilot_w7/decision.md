# P1-02 W7 Pilot Decision

## Status

`BLOCKED` under the frozen candidate protocol.

Accepted by the user on 2026-08-30 with the exact decision:

> Accept P1-02 BLOCKED under the frozen candidate protocol

## Stop evidence

- Failed full-run source commit: `0cf48ce`.
- Source extraction protocol: `072599c016f836637655485fc628a20c33f7284622fe808466fb7e6626714486`.
- Dataset: `Qiuchen-Wang/ViDoSeek@e91a92ba5f38690696c7e66be5c5474b54c6e791`.
- Corpus: 1,142 queries and 5,385 pages.
- Initial depths `(stage1=200, bm25=100, dense=100)` covered 1,139/1,142 queries: `0.9973730297723292`; three queries had zero relevant candidates.
- Frozen expanded depths `(stage1=300, bm25=200, dense=200)` covered 1,141/1,142 queries: `0.999124343257443`; one query remained uncovered.
- Remaining uncovered query: `027dee01b7aced677eb5093c754ebad82a89015d_1`.
- CPU audit function call: `fc-01M17BMSRGAZB51F6PYEYA1ECK`.
- CPU audit source commit: `8f61c30b5745874fda514979ed8bfebafe1ca7a9`.
- CPU audit SHA-256: `80bd3fa2f9368a395a51528b484f511ad0d4a4e6a33588c52f78c4ba16001d1e`.
- Candidate generation did not use qrels; qrels were used only for post-candidate coverage auditing.

## Consequences

- The zero-uncovered-query gate did not pass.
- ColQwen candidate scoring did not run for the full corpus.
- No full retrieval-score bundle, extraction manifest, or `_EXTRACTION_SUCCESS.json` exists.
- The W7 Global–QARF–QPAF oracle pilot was not run.
- No QPAF gain, bootstrap confidence interval, subgroup result, or deployable result exists.
- P1-03, the Phase 1 gate, and Phase 2 remain blocked by dependency order.

No query was dropped, no relevant page was injected, no candidate depth was changed, and no threshold was weakened. Resuming this research direction would require a separately versioned, explicitly approved post-hoc candidate-pool protocol; it would not retroactively make the frozen P1-02 protocol pass.
