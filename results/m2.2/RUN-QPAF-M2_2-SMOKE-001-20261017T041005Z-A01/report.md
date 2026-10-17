# M2.2 — Three-retriever smoke report

Status: **FAIL**

Run: `RUN-QPAF-M2_2-SMOKE-001-20261017T041005Z-A01`. Validation/training sample only; no test queries.

| Stage | Status | Seconds | Peak RSS MiB | Peak reserved VRAM MiB |
|---|---|---:|---:|---:|
| prepare | PASS | 5.150 | 3381.0 | 0.0 |
| bm25 | PASS | 0.156 | 3379.8 | 0.0 |
| dense | PASS | 15.124 | 7350.5 | 2268.0 |
| visual | FAIL | 24.312 | 9682.0 | 7700.0 |

Model: ColQwen2.5 (`vidore/colqwen2.5-v0.2`), BGE-M3, frozen BM25.
See resolved_config.json for full model/base/tokenizer/processor commits and predeclared tolerances.
See remote/<stage>/checks.json, resources.json, environment.json and model_files.json.

Limits: small ID-selected page sample, provisional OCR thresholds, 256 visual-token cap. No claim about full-corpus recall, OCR calibration or learned retrieval quality.
