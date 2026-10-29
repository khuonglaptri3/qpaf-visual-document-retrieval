# A005 Stage 1 — ViMDoc inputs (RUN-QPAF-A005-INP-001)

**Status: `INPUTS_FAILED_COVERAGE` on validation.** All score inputs verify, but 2 of the
400 validation queries have no relevant document in their candidate union. The frozen
contract (`configs/vimdoc_m3_local_v1.json`: `maximum_queries_without_positive_candidate`
0, `drop_uncovered_queries` false) and A005 §5 ("inputs fail verification") stop A005 here
unless the Research Lead amends the rule. Independent review is `WAIVED_BY_A006`.

## What ran

| Step | Where | Result |
| --- | --- | --- |
| prepare | Modal `tranthanhzt123321` | queries `9c118523…`, dev qrels `aab40d99…`, sealed confirmation qrels `ce9ad0fb…` (not read) |
| OCR, 16 shards | Modal `tranthanhzt123321` | 76,347 pages, 2,169 empty |
| query embed, 16 GPU shards | Modal `tranthanhzt123321` | ColQwen2.5 and BGE-M3 scores for every page |
| BM25 | Modal `tranthanhzt123321` | `bm25.npy` `a28f354e…`, parity 0.0 |
| BM25 re-run | Modal `buiphat251399`, cap 2 USD | full matrix SHA-256 **equals** `a28f354e…`; parity 0.0; 2,616 s |
| assemble | local CPU | `candidate_scores.parquet` `296e0821…`, 5,169,549 rows |

Markers of every Modal step are in [`markers/`](markers/). The run history, the spend and
the reason for the BM25 re-run are in [`authorization.json`](authorization.json): the
6.6 GB `bm25.npy` could not be downloaded intact (zero-filled or dropped blocks), and the
original workspace had hit its spend limit. The re-run reproduced the original matrix byte
for byte and returned only the BM25 top-200 and the BM25 scores on each union
(`qpaf.a005.bm25_rerun`, [`bm25_rerun_report.json`](bm25_rerun_report.json)). Seven shard
matrices with the same download fault were re-fetched until they matched their markers.

## Candidate pool and coverage ([`assemble_report.json`](assemble_report.json))

| | Value |
| --- | --- |
| Union size per query | min 223, max 599, mean 474.1 |
| Train (1,600) | macro document recall **1.000**, 0 queries without a positive — pass |
| Validation (400) | macro document recall **0.995**, **2** queries without a positive — **fail** |

The two uncovered validation queries are `8768` (relevant `0102`) and `9437` (relevant
`0283`). Both documents are in the 1,247-document corpus, so this is a retrieval miss in
all three channels, not an identity or qrels error. No rank or score of these queries was
inspected, so the coverage result has not informed any method choice.

## Files outside the repository

`candidate_scores.parquet` (sha `296e0821…`) is kept in the session scratch directory
and is the input of Stages 2–4. The score matrices remain on the `qpaf-artifacts` volume
of `tranthanhzt123321`; the re-run inputs and exchange remain on `qpaf-a005-bm25` in
`buiphat251399`.
