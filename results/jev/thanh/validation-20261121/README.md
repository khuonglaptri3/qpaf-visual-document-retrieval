# Thanh — matched validation baselines (2026-11-21)

This is a **development validation** comparison on Phát's frozen top-20 pairs. It evaluates the supplied gate scores, fresh BGE and Qwen3-4B scores with one evaluator. It is not a Jev model result or a clean held-out claim.

## Inputs and checks

| Dataset | Queries | Ordered pairs | Label unit | Pairs SHA-256 | Qrels SHA-256 |
| --- | ---: | ---: | --- | --- | --- |
| ViDoSeek validation | 171 | 3,420 | page | `b1cb9f569e3673e69889eb17fb3588b9ae5b0421b3611416d786948f2a6aba3f` | `691b6bc4ada3bc64fe3c408fe32498b04c7f30900eadb39ae09ddbe29aea302c` |
| ViMDoc validation | 400 | 8,000 | document (max page score) | `a748fe3a4e457bad6ed8ded177c8e871c0bd37c74028d22d34506453032cfb42` | `aab40d996476fe297be8d000e17bfd6b326b3c318879321f45583cd8bdc42017` |

The private `phat-validation-scoring-inputs.zip` matched SHA-256 `93f376361cc565f9ebafa03d4ea50c4d5286ed7196c4dee675dec2fd7a4cdedb`; all three input files matched the byte sizes and hashes in [Phát's handoff at `2843c68`](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/2843c6827108e5453a28d48aff9e26c179d82014/docs/reports/tasks/phat-validation-handoff-20261120/README.md). The ViDoSeek qrels are the tracked M2.8 expansion development file. The ViMDoc native development qrels were extracted from Thanh's `qpaf-lab-share.zip` after matching its manifest. Neither private pairs/OCR nor the ViMDoc qrels are committed here.

`run_jev.py doctor` passed on both pairs files and all four returned score caches: exact pairs hash, complete length and finite values. The supplied gate mean recomputed to 0.868306310973 on ViDoSeek and 0.960560425314 on ViMDoc; the latter exactly matches Phát's handoff. All evaluations below use `k=10`, the same cohort/qrels within each dataset, and `provided_candidate_pool` ranking scope.

## Results

Delta, 95% percentile CI and W/T/L are right minus gate for per-query nDCG@10, with 10,000 paired query bootstrap resamples and seed `20260820`. Blend weights were fixed from the earlier F9 development recipe for Qwen (ViDoSeek 0.9, ViMDoc 0.5); BGE 0.5 is a diagnostic setting. These blend rows are exploratory and were not selected by these validation results.

### ViDoSeek (page)

| Method | nDCG@10 | MRR@10 | Recall@10 | Δ nDCG vs gate [CI95] | W/T/L |
| --- | ---: | ---: | ---: | --- | ---: |
| Gate, no rerank | 0.868306 | 0.829163 | 0.988304 | reference | — |
| BGE pure | 0.901665 | 0.873552 | 0.988304 | +0.033359 [+0.002490, +0.064140] | 32/122/17 |
| Qwen4B pure | 0.914400 | 0.889864 | 0.988304 | +0.046093 [+0.013889, +0.079354] | 31/122/18 |
| Gate + BGE, λ=0.5 | 0.913976 | 0.887749 | 0.994152 | +0.045670 [+0.025636, +0.066719] | 29/137/5 |
| Gate + Qwen4B, λ=0.9 | 0.920395 | 0.897953 | 0.988304 | +0.052089 [+0.021732, +0.083441] | 30/128/13 |

Qwen4B pure minus BGE pure is +0.012734 nDCG@10, CI95 [−0.014404, +0.039534], W/T/L 18/138/15. The interval includes zero. All 171 queries have a relevant page within the supplied top-20 pool (mean Recall@20 = 1.0).

### ViMDoc (document)

| Method | nDCG@10 | MRR@10 | Recall@10 | Δ nDCG vs gate [CI95] | W/T/L |
| --- | ---: | ---: | ---: | --- | ---: |
| Gate, no rerank | 0.960560 | 0.951631 | 0.987500 | reference | — |
| BGE pure | 0.940500 | 0.926016 | 0.985000 | −0.020061 [−0.035563, −0.005178] | 16/354/30 |
| Qwen4B pure | 0.954918 | 0.943750 | 0.987500 | −0.005643 [−0.018220, +0.006548] | 16/364/20 |
| Gate + BGE, λ=0.5 | 0.962749 | 0.954250 | 0.987500 | +0.002189 [−0.006084, +0.010269] | 15/375/10 |
| Gate + Qwen4B, λ=0.5 | 0.970237 | 0.964167 | 0.987500 | +0.009677 [+0.002493, +0.017276] | 17/380/3 |

Qwen4B pure minus BGE pure is +0.014418 nDCG@10, CI95 [+0.002789, +0.026908], W/T/L 28/361/11. Five of 400 queries have no relevant document in the supplied pool (Recall@20 = 0.9875 for all methods).

## Scoring provenance and resource measurements

Both models used pinned revisions in `configs/jev/models.json`, input cap 1,024 and batch size 4. BGE used fp16 and Qwen4B bf16 on Modal A100-80GB. The four runs were sequential on the private `jev-thanh` Volume, with no reused chunks. Each `*-scores.json` stores the full model/runtime/code manifest, numeric scores and binding to the pairs digest; `manifest.json` indexes every committed output by SHA-256.

| Dataset/model | Modal app | Input tokens | Chunk scoring seconds | Peak CUDA allocated |
| --- | --- | ---: | ---: | ---: |
| ViDoSeek BGE | [`ap-izlM7Fz66PKzj4zXhPyIm1`](https://modal.com/apps/tlcn-group1/main/ap-izlM7Fz66PKzj4zXhPyIm1) | 856,518 | 16.04 | 1.24 GB |
| ViDoSeek Qwen4B | [`ap-0APhICpzAf7MPbvgE72E9v`](https://modal.com/apps/tlcn-group1/main/ap-0APhICpzAf7MPbvgE72E9v) | 1,183,046 | 113.88 | 8.44 GB |
| ViMDoc BGE | [`ap-cN3pa7zrAD9JycutSGAQLa`](https://modal.com/apps/tlcn-group1/main/ap-cN3pa7zrAD9JycutSGAQLa) | 3,896,912 | 48.31 | 1.24 GB |
| ViMDoc Qwen4B | [`ap-f1jQD7pTcRE5jcSuUf9uTd`](https://modal.com/apps/tlcn-group1/main/ap-f1jQD7pTcRE5jcSuUf9uTd) | 4,510,906 | 353.50 | 8.44 GB |

Chunk scoring seconds exclude image setup, model download and other wall time. No provider billing receipt was available, so this report makes no currency or billed-duration claim. Two setup attempts before the successful ViDoSeek BGE run ended with zero scoring output: a connection reset during image build and a Python 3.11 client/3.13 worker mismatch. The successful jobs used Modal SDK 1.5.5 from a separate Python 3.13 client.

## Interpretation and handoff

- The rankings are **top-20 shortlist evaluations**. They do not replay F9 full-ranking or validate retrieval outside the supplied candidate pool. Raw-channel gate provenance was not independently reconstructed from Phát's private rebuild files; the supplied pairs hash and gate metrics were checked.
- The historical BGE cache covers only 2,877/3,420 ViDoSeek pairs. The older lab-share manifest pins BGE at `5617a9f61b028005a4858fdac845db406aefb181`, while this Jev configuration pins `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`; its runtime also differs. No old and new scores were spliced. All 3,420 pairs were scored again under one policy.
- ViDoSeek rerankers improve the gate on this validation cohort. ViMDoc BGE pure is worse; Qwen4B pure has an interval spanning zero. The ViMDoc Qwen blend has a positive query-bootstrap interval, but its λ came from earlier development work and this is not a fresh held-out confirmation.
- Phát's archived Qwen means (ViDoSeek 0.9122, ViMDoc 0.9552) differ slightly from this new Jev-runtime scoring (0.9144, 0.9549). Historical per-pair Qwen scores and evaluator reports were not in the transferred archive, so exact replay/parity remains open. Do not substitute these numbers for the F9 historical claims.
- Phát's handoff reports that 162/171 ViDoSeek validation queries share a reference document with training queries. The CIs here resample queries, not documents; document-group sensitivity for these new scores is still open. No Jev/Kev checkpoint has been evaluated, and the train export currently lacks judged negatives.
- The committed `*-scores.json`, `*-gate/bge/qwen*.json`, `*-vs-*.json` and CSV files provide the aligned scores, per-query metrics and comparisons for Khương's matched Jev evaluation. Compare a future Jev report only after matching `pairs_sha256`, `qrels_sha256`, label unit and ranking scope.
