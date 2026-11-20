# Runnable Jev team kit ? spec

Date: 2026-11-20. Authorization: user explicitly requires implementation on the three published research branches so teammates clone, run, and continue research. This executes the already-discussed F9/data/baseline/Kev direction; no new approval is needed for reversible implementation/testing/branch updates.

## Outcome and architecture

Provide a real runnable Python toolkit on all three research branches, not just briefs. Preserve F9 and frozen evidence. Shared code handles explicit input/score/split contracts, data preparation, metrics/comparisons, frozen BGE/Qwen/Kev inference and train-only Kev adaptation. Owners get runnable configs and Vietnamese quickstarts. CPU/offline demo must run with Python >=3.11 and stdlib only. Heavy model imports are lazy; model environments are separate from CPU CLI and from each other. No user data or weights are committed.

Approaches: selected reuse F9 source with a shared toolkit plus isolated GPU workers; standalone SciFact cannot validate the project; rewriting retrieval would waste frozen cache. The user's latest direction authorizes executing the selected approach and supplying code on all owner branches, replacing the previous documents-only status.

## Contracts

Pairs are F9-compatible JSON: `dataset` string, `top_k` positive int, `queries` string-ID to nonempty text, `pages` string-ID to OCR text, `pairs` unique ordered [query_id,page_id] rows. Empty OCR is permitted and reported. Optional `units` maps page_id to label-unit ID; optional `base_scores` is a finite vector aligned exactly with pairs. Pair order is NOT retrieval rank: F9 stores page order. Baseline/blend requires explicit base_scores and must never assume pair order is a baseline ranking.

Score caches are `pairs_sha256`, `manifest`, `scores`; scores must exactly cover pairs, finite and non-boolean, with no silently truncated zip or default zero. SHA-256 is over actual input bytes, preserving old F9 cache compatibility. Manifest names model/revision/input cap/precision/code/environment and synthetic status when relevant. Atomic writes prevent partial final caches. Failed inference exits with actionable diagnostics; no zero-score fallback. Chunk resume must fingerprint model/revision/input config and pool; no stale reuse.

Qrels are {query_id: {unit_id: nonnegative numeric relevance}}; full judgments include gold outside pool. Evaluation includes every selected query, rejects absent qrels or score coverage, uses max page score per document when units map to documents, and computes nDCG@10/MRR@10/Recall@10/20 and per-query outputs. Binary labels match historical metrics; graded gain is explicit (2^rel-1). Paired delta/CI/W-T-L compares identical cohorts; bootstrap seed 20260820, 10000 samples by default, optional group resampling. Blend lambda is explicit, not automatically fit on evaluation labels. The new standalone evaluator is explicitly shortlist-only: on document-level ViMDoc it may differ from full F9 because tail pages can fill additional unique documents. Exact historical replay uses legacy screen/stack with full underlying candidates, not a copied historical mean.

Split manifest is {splits:{query_id:train|validation|test}, groups:{query_id:group_id}}. Every selected query is assigned, group IDs cannot span partitions. Training exports only train and page-level judged relevance; unjudged-as-negative requires explicit opt-in. ViMDoc document labels are not page labels. Training format matches pinned Kev upstream noul requests and saves provenance. User decides a final independent evaluation set; known development labels are not advertised as clean final test.

## Required runnable paths

1. `python scripts/run_jev.py doctor` and `demo --out DIR`: stdlib-only offline self-check and clearly synthetic workflow, never fake Jev metrics.
2. Validate/import F9 pairs, prepare candidates from explicit query/page/raw-score inputs or existing F9 data bundle without reading sealed labels, and produce reusable pair/score manifests. Provide private-data missing diagnostics rather than downloading it silently.
3. `score` supports baseline existing base_scores, toy lexical demo, and real BGE/Qwen/Kev backends. Model IDs/revisions default to verified pins; arbitrary local fine-tuned Kev checkpoints supported. Existing F9 result cache can be evaluated directly without GPU.
4. `evaluate`/`compare`: reusable standalone CPU metrics, strict cohort, optional explicit blend; readable JSON/CSV results with per-query evidence.
5. `export-train` and `train`: page-level train-only records, group leakage rejection, inspectable dry-run exact command, official pinned Kev trainer for warm-start and base-control with same data/budget. Actual training is invoked only by explicit user CLI, not demo/doctor/import.
6. Modal/local GPU launch paths and separate reproducible requirements, with model source/pins documented. No import/help/demo command submits paid jobs.
7. Branch-specific quickstarts and configs, one-command demo per owner, practical full-data/GPU commands. Model/data prerequisites remain explicit.

## Constraints and verification

Do not modify existing src/qpaf/lab or f9, sealed qrels, frozen receipts, original result JSON, or user checkout/index. New implementation lives in src/qpaf/jev, new scripts/configs/requirements/tests and task docs. Task bundle root is exactly README.md + evidence/ + superpowers/; superpowers contains only spec.md and plan.md. Logs/reviews/provenance under evidence. LF text files. New meaningful behavior gets TDD. Run focused tests and the full existing suite once, report any environment failures by name, do not imply GPU/model runs occurred if only synthetic/mocked/contract tests ran. No paid GPU job, large weight download, private-data publication, force push or merge to shared main/develop is authorized by this code task. Ordinary fast-forward pushes to the three explicitly requested research branches are authorized.
