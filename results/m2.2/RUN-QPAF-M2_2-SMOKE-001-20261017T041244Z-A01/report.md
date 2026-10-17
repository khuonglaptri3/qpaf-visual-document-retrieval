# M2.2 — Three-retriever smoke report

Status: **PASS**

Run: `RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01`. Validation/training sample only; no test queries.

| Stage | Status | Seconds | Peak RSS MiB | Peak reserved VRAM MiB |
|---|---|---:|---:|---:|
| prepare | PASS | 5.878 | 3380.2 | 0.0 |
| bm25 | PASS | 0.182 | 3378.7 | 0.0 |
| dense | PASS | 15.636 | 7392.9 | 2268.0 |
| visual | PASS | 31.188 | 11833.1 | 14978.0 |

Model: ColQwen2.5 (`vidore/colqwen2.5-v0.2`), BGE-M3, frozen BM25.
See resolved_config.json for full model/base/tokenizer/processor commits and predeclared tolerances.
See remote/<stage>/checks.json, resources.json, environment.json and model_files.json.

Limits: small ID-selected page sample, provisional OCR thresholds, 256 visual-token cap. No claim about full-corpus recall, OCR calibration or learned retrieval quality.
