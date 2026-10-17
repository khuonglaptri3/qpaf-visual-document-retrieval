# M2.2 — Three-retriever smoke report

Status: **FAIL**

Run: `RUN-QPAF-M2_2-SMOKE-001-20261017T040322Z-A01`. Validation/training sample only; no test queries.

| Stage | Status | Seconds | Peak RSS MiB | Peak reserved VRAM MiB |
|---|---|---:|---:|---:|
| prepare | FAIL | 5.200 | 3379.4 | 0.0 |
| bm25 | NOT_RUN | 0.000 | 0.0 | 0.0 |
| dense | NOT_RUN | 0.000 | 0.0 | 0.0 |
| visual | NOT_RUN | 0.000 | 0.0 | 0.0 |

Model: ColQwen2.5 (`vidore/colqwen2.5-v0.2`), BGE-M3, frozen BM25.
See resolved_config.json for full model/base/tokenizer/processor commits and predeclared tolerances.
See remote/<stage>/checks.json, resources.json, environment.json and model_files.json.

Limits: small ID-selected page sample, provisional OCR thresholds, 256 visual-token cap. No claim about full-corpus recall, OCR calibration or learned retrieval quality.
