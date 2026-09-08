# Query 797: what the saved QPAF weights corrected

**Verified post-hoc case study, 2026-09-07.** Reconstructed from the completed exploratory-12 recovery; no oracle search was rerun. This is a deliberately selected explanation of the only improving query, not representative performance evidence. Single-seed exploratory study: seed 20260820.

## Identity and outcome

- Query ID: `04450a0f59f81025574451222aa26322ae7ede42_1`; frozen audit index 797, checkpoint position 5 (zero-based).
- Relevant page ID: `04450a0f59f81025574451222aa26322ae7ede42_6`.
- Saved metadata: `source_type=2d_layout|query_type=single_hop`.
- Candidate pool: all 5,385 pages; exactly one positive relevance label.
- Weight order throughout: **BM25, dense, visual**. `stage1_score` is provenance only and is not fused.

| Method | Saved weighting | Relevant-page rank | nDCG@10 |
| --- | --- | ---: | ---: |
| Global | Visual for every page: `[0,0,1]` | 4 | 0.430677 |
| QARF oracle | BM25 for every page: `[1,0,0]` | 3 | 0.500000 |
| QPAF oracle | BM25 on 5,383 pages; dense on two pages | 1 | 1.000000 |

With one relevant page, nDCG@10 is `1/log2(rank+1)` when rank is at most 10. This independently reproduces the reported values. Global is selected over the same 12 exploratory queries; it is not a separately trained static baseline.

## The two saved weight changes

All page IDs in this table share prefix `04450a0f59f81025574451222aa26322ae7ede42`; the suffix identifies the exact page. Scores are the existing per-query normalized values, rounded here to six decimals.

| Page suffix | Relevant | BM25 | Dense | Visual | QARF rank | QPAF rank | QPAF score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `_1` | 0 | 1.000000 | 0.926680 | 1.000000 | 1 | 3 | 0.926680 |
| `_2` | 0 | 0.938260 | 0.930388 | 0.970149 | 2 | 2 | 0.938260 |
| `_6` | 1 | 0.625620 | 0.981792 | 0.980100 | 3 | 1 | 0.981792 |

The saved QPAF solution changes only `_1` and `_6` from BM25 to dense. It lowers the top distractor from 1.000000 to 0.926680 and raises the relevant page from 0.625620 to 0.981792. The unchanged `_2` page retains 0.938260. Thus the final top three are `_6`, `_2`, `_1`.

**Dense alone does not solve this query:** the relevant page is third under dense ranking too. Dense ranks `_5` and `_19` above it; QPAF leaves those pages on their lower BM25 scores. The observed benefit is selective suppression and promotion across pages, not choosing dense for the whole query. The checkpoint records two accepted updates; this reconstruction verifies the final assignment, not an unsaved chronological optimization trace.

## What this establishes, and what remains unknown

The saved weights and frozen scores explain the rank improvement exactly. They demonstrate one case where page-specific assignments outperform all query-level W7 profiles selected by QARF. The oracle used relevance labels to choose assignments; no trained gate has learned to make these choices without labels.

The query text and page images were not inspected in this analysis. The metadata does not establish a semantic cause such as OCR failure, table comprehension, or layout reasoning. Label correctness at the document-content level and whether the planned label-free features can predict these assignments remain untested.

## The other eleven queries and the ceiling

All other selected queries already place their only relevant page first with Global. Their nDCG@10 is 1.0 under all three methods. There is no remaining nDCG@10 headroom on those eleven queries. They remain in every aggregate; excluding them would change the target population after seeing outcomes.

The QPAF-minus-QARF mean is therefore `0.5/12 = 0.041667`; wins/ties/losses are 1/11/0, and the saved 10,000-resample bootstrap interval is [0, 0.125]. All positive gain is concentrated in query 797. This neither establishes broad benefit nor formally rejects QPAF: the subset is explicitly ineligible for the Phase 1 decision.

## Evidence and reproduction

- [Original complete comparison](QPAF_EXPLORATORY12_RESULTS.md), retained byte-for-byte.
- [Case review and input/output hashes](../artifacts/vidoseek_exploratory12_case797_review/case_review.json).
- [All 5,385 page scores, channel ranks, fused ranks and weights](../artifacts/vidoseek_exploratory12_case797_review/query_page_rankings.csv).
- [Relevant-page ranks for all twelve queries](../artifacts/vidoseek_exploratory12_case797_review/all_query_relevant_ranks.csv).
- [Saved checkpoint](../runs/vidoseek_exploratory12_recovery_v1/checkpoints/queries/000005.json).
- [Reconstruction script](../scripts/inspect_exploratory12_saved_rankings.py).

The script verifies all 78 recovery artifact hashes and the full input score-file hash, then checks 144 saved metrics (12 queries x 3 methods x 4 metrics) using stable score-descending/page-ID-ascending ranking and the independent one-positive closed form. It fails if any query has a different relevance-count contract. It imports no oracle runner and writes only a new diagnostic directory.

Run from the repository root with Python 3.13 and the existing pandas/numpy/pyarrow environment. On this machine that interpreter is `C:\Python313\python.exe`. CMD example; choose a new output directory if reproducing again:

```bat
set "OMP_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "NUMEXPR_NUM_THREADS=1"
C:\Python313\python.exe scripts\inspect_exploratory12_saved_rankings.py --run runs/vidoseek_exploratory12_recovery_v1 --output artifacts/vidoseek_exploratory12_case797_reproduction --audit-index 797
```

Expected: `PASS_SAVED_RANKING_RECONSTRUCTION`, `metrics_checked=144`, `global_ceiling_queries=11`, relevant ranks 4/3/1. The current checkout includes uncommitted implementation and local data; a clean checkout of HEAD alone is insufficient. Preserve the linked inputs and script with their hashes when packaging reproduction.

Next: [review-only evaluation proposal](QPAF_NEXT_EVALUATION_PROPOSAL.md).
