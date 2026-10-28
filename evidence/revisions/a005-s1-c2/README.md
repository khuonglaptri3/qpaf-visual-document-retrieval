# A005 Stage 1 calibration C2 — OCR and GPU timing on 128 ViMDoc pages

**Status:** complete, one invocation, no retry. Modal app `ap-J0ohdLRP2i6FTCvPbWzaWz`,
OCR call `fc-01M61HVMMEFF89ZME3WSBY2NWS`, source `47cb212` under
[`authorization.json`](authorization.json). Independent review is `WAIVED_BY_A006`.

The sample is 128 v2 pages (93 `.png`, 35 `.jpg`, 111 documents). They are the pages with
the smallest SHA-256 of `a005-c2:20260820:` + page ID, so no label was used to pick them.
The query side used eight synthetic strings. No qrels, no query table and no score cache
were produced.

| File | SHA-256 |
| --- | --- |
| [`ocr_timing.json`](ocr_timing.json) | `ee8717882787af2e61ad2f1219655c8d5e73391ecd68d6be1b7f7a8576245390` |
| [`gpu_timing.json`](gpu_timing.json) | `ca69eae8f72ddd54ea35064a707d1656f5335846c746601b89ea88603adae7ec` |
| [`ocr.jsonl`](ocr.jsonl) | `2d5de2fbb30fbdbf99bde3f625ddc1ce01fd0b88836b51061ea9a381add046c1` (matches the report) |

## Measurements

| Component | Value |
| --- | --- |
| Tesseract | 5.3.0, `--oem 3 --psm 3`, eng |
| OCR, 1 process | 1.164 s/page |
| OCR, 4 processes on 4 cores | **0.314 s/page**; texts identical to the sequential run (0 mismatches); 2 empty pages |
| ColQwen2.5 passage encoding, L4, batch 2 | **0.575 s/page** (mean 682 image tokens); ViDoSeek was 1.03 s/page |
| MaxSim, CPU (the ViDoSeek code path) | 10,159 pairs/s |
| MaxSim, GPU (same `processor.score`, `device='cuda'`) | **122,207 pairs/s**; max difference from CPU 0.0; 0 ranking disagreements |
| BGE-M3 passage encoding, L4, batch 8 | 0.019 s/page |
| Model load | ColQwen 51 s, BGE-M3 29 s |
| Peak CUDA allocated | 7.7 GiB |

The slow ViDoSeek scoring came from running MaxSim on the CPU. Moving it to the GPU gives
identical scores at about 12 times the speed.

## Full Stage 1 projection

The projection covers 76,347 pages and 10,904 queries, with 10% overhead. Prices are from
https://modal.com/pricing on 2026-10-28.

| Component | Hours | USD |
| --- | ---: | ---: |
| ColQwen2.5 encoding (L4 container: GPU + 4 CPU + 32 GiB) | 12.2 | |
| MaxSim on GPU, 832 million pairs | 1.9 | |
| BGE-M3 encoding | 0.4 | |
| **GPU container subtotal** | 15.9 | **19.8** |
| OCR on 4 cores | 6.7 | 1.9 |
| BM25, normalisation, cache writing (CPU) | < 1 | < 0.5 |
| **Total** | | **about 22** |

Keeping MaxSim on the CPU would add about 21 hours, roughly 26 USD.

## Spend so far

| Run | Upper bound |
| --- | --- |
| C1 | 0.47 USD (reserved; it ran 140 s) |
| C2 | about 0.15 USD (about 5 min of CPU and 5 min of L4) |

Both are well under the 10 USD calibration cap. Actual billing is visible only in the Modal
dashboard of the workspace that ran these apps (`tranthanhzt123321`).
