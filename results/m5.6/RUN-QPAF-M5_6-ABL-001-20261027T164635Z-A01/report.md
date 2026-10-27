# M5.6 / R6 — feature-group and conditioning ablations

Validation only (171 queries), seed 20260820, exploratory. Selected epochs maximise validation
nDCG@10, so every absolute value is optimistic; read the paired deltas.

| Run | Omitted | Epoch | nDCG@10 | R@1 | R@3 | MRR@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| R6-00 | none (control) | 19 | 0.866280 | 0.736842 | 0.906433 | 0.828279 |
| R6-01 | rr_bm25, rr_dense, rr_visual | 19 | 0.865805 | 0.730994 | 0.906433 | 0.825907 |
| R6-02 | gap_bm25, gap_dense, gap_visual | 11 | 0.866658 | 0.736842 | 0.918129 | 0.830173 |
| R6-03 | disagreement_bm25_dense, disagreement_bm25_visual, disagreement_dense_visual | 7 | 0.866479 | 0.736842 | 0.918129 | 0.829978 |
| R6-04 | query_length | 19 | 0.867970 | 0.736842 | 0.906433 | 0.828864 |

| Contrast | Mean ΔnDCG@10 | 95% CI | W/T/L |
| --- | ---: | --- | --- |
| R6-01 - R6-00 | -0.000475 | [-0.006412, +0.004994] | 3/166/2 |
| R6-02 - R6-00 | +0.000378 | [-0.004469, +0.004924] | 4/165/2 |
| R6-03 - R6-00 | +0.000199 | [-0.004517, +0.004480] | 5/163/3 |
| R6-04 - R6-00 | +0.001690 | [+0.000000, +0.005071] | 1/170/0 |
| QPAF − QARF, three-seed query mean | +0.118704 | [+0.081876, +0.156545] | 61/97/13 |

R6-00 reproduces the M3.4 pilot: PASS. Fresh-process reload: PASS.
No test label, primary-method change, GPU or Modal call. Independent review pending.
