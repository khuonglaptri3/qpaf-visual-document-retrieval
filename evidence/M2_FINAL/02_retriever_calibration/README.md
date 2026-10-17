# M2.2 — Three-retriever calibration

**Technical result:** PASS on a real bounded sample.

**Selected revision:** [m2.2-001](../../revisions/m2.2-001/README.md).

**Selected run:** `RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01`.

BM25, BGE-M3 and ColQwen2.5 passed on the same 4 validation queries × 16 pages.
ColQwen2.5 uses float32, batch 2, a 256-visual-token cap and pinned model/base/
processor/tokenizer revisions. The earlier bfloat16 attempt failed token-embedding
parity and remains recorded as FAIL; tolerances were not relaxed.

- [Detailed report](../../../docs/superpowers/reports/2026-10-17-m22-retriever-smoke.md)
- [Implementation plan](../../../docs/superpowers/plans/2026-10-17-m22-retriever-smoke.md)
- [Execution journal](../../../docs/superpowers/progress/2026-10-17-m22-retriever-smoke.md)
- [Selected run report](../../../results/m2.2/RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01/report.md)
- [Full regression receipt](../../../results/m2.2/verification/tests-2026-10-17T041449.342184_0000.json)
- [Reproduction and verification commands](../../../results/m2.2/README.md)

Regression: 164 tests, 163 passed, one platform skip, no failures/errors, in the
pinned Modal Linux/PyTorch environment. The receipt includes source/test hashes.

Payloads persist locally under the selected run and in Modal Volume
`qpaf-m22-smoke-artifacts`, path `runs/<run-id>`. Scores/embeddings and rendered
images stay outside Git; hashes and small reports remain versioned.

This is engineering calibration. One page returned no OCR words and is explicitly
marked `NO_TEXT_DETECTED / M23_REVIEW_PENDING`. This record does not certify OCR
quality, full-corpus retrieval recall, or authorize learned training. Technical
PASS here is not an invented independent QA/Research Lead signature.
