# ViDoSeek exploratory-24 W66: verified Global / QARF / QPAF sensitivity

**Completed and independently verified: 24 frozen queries, 66 simplex profiles, 5,385 pages/query, and 129,240 query-page pairs.** The optimized implementation preserved the original two-sweep candidate/profile iteration and update semantics exactly.

This is a relevance-informed oracle upper-bound sensitivity study on the same bounded exploratory subset used for W7. It is not trained or deployable performance, full-discovery evidence, or a formal Phase 1 decision.

## Mean retrieval quality

Single-seed study (`20260820`). Global chooses one fixed W66 profile over the 24 queries; QARF chooses one W66 profile per query; QPAF applies page-specific oracle assignments from the 66-profile menu.

| Method | Exact mean nDCG@10 | Display value |
| --- | ---: | ---: |
| Global | 0.8296782270669829 | 0.829678 |
| QARF | 0.8538451195715936 | 0.853845 |
| QPAF | 0.8859108127976215 | 0.885911 |

The selected Global profile is exactly `[0.0, 0.2, 0.8]` for BM25, dense, and visual weights.

## Paired gains and uncertainty

Query-bootstrap percentile 95% intervals use 10,000 resamples with seed `20260820`. They describe this exploratory sample only.

| Comparison | Exact mean nDCG@10 change | Exact bootstrap 95% interval | Win / tie / loss |
| --- | ---: | --- | --- |
| QARF minus Global | 0.02416689250461061 | [0.0, 0.06371171194374382] | 2 / 22 / 0 |
| QPAF minus QARF | 0.03206569322602797 | [0.002888476746941956, 0.07116543024082586] | 4 / 20 / 0 |
| QPAF minus Global | 0.05623258573063858 | [0.015377926934522603, 0.10714133906910528] | — |

QPAF-minus-QARF positive-gain concentration (`top_5pct_gain_share`) is exactly `0.7397878446931598`. The fractions of queries gaining at least 0.01, 0.03, and 0.05 are each `0.16666666666666666`. QPAF changed five of 129,240 page assignments across four queries.

## W66 compared with W7 on the identical subset

| Quantity | W7 | W66 | W66 minus W7 |
| --- | ---: | ---: | ---: |
| Global mean nDCG@10 | 0.8176338593037377 | 0.8296782270669829 | +0.0120443677632452 |
| QARF mean nDCG@10 | 0.8538451195715936 | 0.8538451195715936 | 0.0 |
| QPAF mean nDCG@10 | 0.9038556693840128 | 0.8859108127976215 | -0.0179448565863913 |
| QPAF-minus-QARF mean gain | 0.05001054981241935 | 0.03206569322602797 | -0.01794485658639138 |

W66 therefore **does not outperform W7 in this run**. It still clears the three exploratory continuation signals: mean QPAF-minus-QARF gain is at least 0.03, the bootstrap lower bound is above zero, and top-5% gain share is below 0.90.

The lower W66 QPAF score is not evidence that adding profiles is intrinsically harmful. At audit index 798 (`04450a0f59f81025574451222aa26322ae7ede42_2`), multiple QARF profiles tie at nDCG@10 `0.0`. Grid order makes W7 initialize QPAF from `[1.0, 0.0, 0.0]`, where one accepted page change reaches `0.43067655807339306`; W66 initializes from `[0.0, 0.0, 1.0]`, where the frozen search accepts no update. The lost query gain divided by 24 is `0.017944856586391377`, which accounts for the complete W7-minus-W66 mean QPAF gap. The conclusion is that this oracle heuristic is sensitive to tied-profile initialization order.

## Every selected query

| Audit index | Global | QARF | QPAF | QPAF minus QARF | Changed pages |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 92 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 141 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 148 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 398 | 0.430677 | 0.430677 | 0.500000 | 0.069323 | 1 |
| 513 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 640 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 676 | 0.430677 | 0.430677 | 0.630930 | 0.200253 | 2 |
| 686 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 798 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 |
| 803 | 0.630930 | 0.630930 | 1.000000 | 0.369070 | 1 |
| 832 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 842 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 855 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 889 | 0.630930 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 890 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 892 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 950 | 0.500000 | 0.500000 | 0.630930 | 0.130930 | 1 |
| 992 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 1034 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 1067 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 1082 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 1084 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 1093 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 1129 | 0.289065 | 0.500000 | 0.500000 | 0.000000 | 0 |

Unrounded values and full query IDs remain in the immutable local `per_query.json`; its SHA-256 is `ff084afca65246bfa84c6cf9c4aaa8a4ea7f8a201df73d4dcd546695383a504d`. The table includes every frozen query without outcome filtering.

## Project interpretation and next step

The evidence supports continuing the project around **QPAF** as the proposed method. **QARF remains the required matched learned baseline**, because the project must measure whether page-level adaptation improves over query-level adaptation. **CARF is a granularity diagnostic/ablation**, not a co-primary method and not a Phase 2 training gate; it belongs in P3-02, where QARF, label-free clustered CARF, and QPAF can be compared under the preregistered K=2/3/4 sensitivity.

The next reviewable engineering step is local preparation of P2-01 and P2-02 (deterministic features, linear gates, listwise loss, and tests). This result does not authorize training, Modal/GPU use, P2-03, or P2-04.

## Execution and verification evidence

- [Tracked closeout receipt](../../../artifacts/vidoseek_w66_exploratory24_optimized_review/closeout_receipt.json), which records the execution scope, exact results, verification counts, hashes, and closed boundaries.
- [Independent integrity review](../../../artifacts/vidoseek_w66_exploratory24_optimized_review/result_integrity_review.json): 97 manifest artifacts, 50 checkpoint envelopes, 32 source snapshots, 1,503 telemetry samples, 1,584 fixed-profile ranking reconstructions, 72 final ranking reconstructions, 6,624 raw metric values, and 127 aggregate/delta comparisons passed.
- Run-manifest SHA-256: `9e691aa27bddfdaa92728da171128ceadf64e1f21863acf2c221b7e5dde5c78f`. The full run directory remains local and Git-ignored.
- Frozen query-list SHA-256: `95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b`; W66-profile SHA-256: `c04139858954fd0a7f7baa5dad548f3675a41b8682e9798039508e4077da5973`.
- One local CPU worker/thread, one invocation, zero retries, Python 3.13.7; completed in exactly `1551.236275000003` seconds under the 7,200-second cap. Maximum monotonic telemetry gap was `1.1164282000027015` seconds under the five-second limit.

`phase1_decision=NOT_APPLICABLE_EXPLORATORY_W66_SUBSET`. Frozen P1-02 and formal P1-03 remain `BLOCKED`. Full-discovery W7/W66, training, and Modal/GPU remain closed.
