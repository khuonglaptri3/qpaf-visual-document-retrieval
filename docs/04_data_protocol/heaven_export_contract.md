# HEAVEN cloud export contract

This repository deliberately keeps model execution separate from oracle analysis. Run the
official HEAVEN implementation at a frozen commit, then export two tables.

The official control flow was verified against `retrieval/heaven/heaven.py`: it calls
`Stage1Retrieval.compute_scores()`, obtains `stage1_scores` from
`filter_and_combine(...)`, loads Stage-2 matrices, then obtains `final_scores` from the
Stage-2 `filter_and_combine()` method.

## 1. Candidate score table

For each query, first obtain full-corpus ranks independently from DSE Stage 1, BM25, and
BGE-M3. Form the union of Stage-1 Top300, BM25 Top200, and BGE Top200 without qrels. Score
every page in that union with all three QPAF branches: BM25, BGE-M3, and ColQwen2.5.

For the ColQwen2.5 branch, snapshot `stage2.score_key + stage2.score_non_key` immediately
after `_load_or_compute_scores()` and **before** Stage-2 `filter_and_combine()`. The official
method masks these tensors in place, so exporting them afterward would no longer be an
unfiltered candidate score and would invalidate QPAF. `stage1_scores` and `final_scores`
can be exported at the corresponding local variables in `HEAVEN.run()`.

Write one row per `(dataset, query_id, page_id)` with:

```text
dataset,query_id,page_id,source,relevance,bm25_score,dense_score,
stage1_score,visual_score,full_score,stage2_ms,stage2_flops
```

Relevant pages outside the union may be appended only for coverage auditing. Mark them so
they cannot enter the candidate mask through fabricated scores. Prefer retaining their real
branch scores; if those cannot be produced, calculate coverage from qrels and the saved
full-corpus rank lists before invoking `build-cache`.

## 2. Full-corpus query metric table

Evaluate Stage 1 and final HEAVEN rankings against the untouched full corpus and write:

```text
dataset,query_id,source,relevant_count,ndcg_stage1,ndcg_full,
recall_stage1,recall_full,stage1_margin,stage2_ms,stage2_flops,
recall1_stage1,recall1_full,recall3_stage1,recall3_full,
mrr10_stage1,mrr10_full
```

`stage1_margin` is the Stage-1 Top1 score minus Top2 score. `stage2_ms` is incremental
Stage-2 latency: 50 warm-up queries, three timed passes in identical query order, CUDA
events with synchronization, and the per-query median. Record incremental Stage-2 FLOPs
using one fixed profiler configuration.
The six explicit secondary-metric columns are strongly recommended. The two legacy
`recall_stage1/full` fields are Recall@3 and remain in the stable base schema.

## 3. Integrity checks

- Save query/page mapping and qrels checksums in the manifest.
- Run the same 20 queries twice and compare ranking hashes before full encoding.
- Do not use qrels in union construction, normalization, or score generation.
- Keep excluded/missing queries in an explicit error table; never silently drop them.
- Use `official_query_metrics.parquet` with `build-cache --query-metrics` for real results.

The upstream `evaluate()` currently reports MRR and Recall, not nDCG. Calculate nDCG@10
from the saved ranking and qrels with this package; use upstream metrics only for the
paper/code reproduction check. BM25 is not part of the official HEAVEN pipeline and must
be built over the same page OCR separately.
