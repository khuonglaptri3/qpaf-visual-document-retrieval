# PROJECT_TRACKING.md

Execution tracker for the Query-Page-Adaptive Fusion (QPAF) research project.

This tracker translates the authoritative dependency DAG in `Tasks.md` into stakeholder-facing execution phases. A task may start only when all upstream completion criteria pass. `Blocked` means the task is prevented by a dependency, protocol gate, or missing approval—not that an experiment produced a negative metric.

Team execution order, ownership, claim thresholds, and proposed milestone dates are maintained in [`docs/02_project_plan/QPAF_TEAM_RESEARCH_EXECUTION_PLAN.md`](docs/02_project_plan/QPAF_TEAM_RESEARCH_EXECUTION_PLAN.md). That operational plan does not override the dependencies or authorization boundaries in `Tasks.md`.

## Phase 1 — Foundation, Data, and Score Contracts

**Goal:** Establish reproducible code, environment, dataset, score, and metric contracts before interpreting retrieval results.

| Task | Deliverable | Completion Criteria | Status | Target Date |
| ---- | ----------- | ------------------- | ------ | ----------- |
| P0-01: Freeze the baseline | Immutable source snapshot and `baseline_snapshot_manifest.json` | Tracked source hashes match the manifest and the baseline commit is recorded | Completed | [INSERT: baseline freeze target date] |
| P0-02: Freeze environment and datasets | Pinned dependency lock; Modal environment probe; dataset and model manifests | Three approved datasets and retriever revisions are hash-pinned; the Modal L4 environment contract passes | Completed | [INSERT: environment freeze target date] |
| P0-03: Validate the three-channel score bundle | ViDoRe raw/normalized Parquet files, coverage report, manifests, and success markers | Ten-artifact bundle verifies; 309 queries have coverage 0.9576 and zero uncovered queries; results are labeled candidate-pool metrics | Completed | [INSERT: baseline bundle target date] |
| P1-01: Harden normalization and metrics | Reference fixtures and tests for three-channel normalization, stable ranking, nDCG@10, Recall, and MRR | Hand-computed fixtures pass at the specified tolerance; constant channels and page-ID ties are deterministic | Completed | [INSERT: metric-contract target date] |
| P1-02R: Verify all-corpus recovery scores | Integrity-reviewed ViDoSeek bundle with 6,149,670 rows per score table | Hash, schema, row/key, rank, normalization, provenance, and coverage checks pass; no oracle or learned result is claimed | Completed | [INSERT: P1-02R target date] |

## Phase 2 — Oracle Feasibility and Granularity Decision

**Goal:** Measure whether page-level fusion has material, stable headroom before authorizing learned-model work.

| Task | Deliverable | Completion Criteria | Status | Target Date |
| ---- | ----------- | ------------------- | ------ | ----------- |
| P1-02: Run the frozen ViDoSeek W7 pilot | Global, QARF, and QPAF oracle summaries under the original top-K protocol | Coverage is at least 0.95 with no uncovered query, then W7 outputs and bootstrap statistics complete | Blocked | 2026-09-05 |
| P1-02R-O1: Record bounded CPU performance probe | Immutable synthetic-only probe marker, manifest, timings, and runtime review | Three frozen probe cases pass within their limits and remain explicitly classified as non-scientific evidence | Completed | 2026-09-05 |
| P1-02R-O1: Execute the authorized full-page synthetic calibration | Verified immutable attempt/manifest and `artifacts/vidoseek_p1_02r_full_page_calibration_review.json`; worker time 752.7996488000001 seconds | Reviewed 2026-09-06: source/protocol hashes, query index 570, 5,385 pages, one worker/thread, timeout and non-result boundaries pass; one attempt consumed, zero remaining | Completed | 2026-09-05 |
| Review and authorize or reject full post-hoc W7 | Calibration review complete; full 1,142-query resource/execution decision remains pending | Full W7 remains unauthorized; the separately approved exploratory-12 side study below cannot satisfy the full-discovery gate | Blocked | [INSERT: post-hoc W7 review target date] |
| Exploratory-12 side study: first real-label oracle comparison | Completed recovery: four inherited and eight new results; `docs/05_oracle_experiments/exploratory12/QPAF_EXPLORATORY12_RESULTS.md`; case analysis in `docs/QPAF_QUERY797_CASE_STUDY.md` | All twelve results and independent review complete; chart visually checked; 144 metrics independently reconstructed. This subset cannot pass/fail formal Phase 1 | Completed; exploratory only | 2026-09-07 |
| Fixed-profile discovery headroom audit | Complete manifest, independent review and `docs/05_oracle_experiments/fixed_profile/QPAF_FIXED_PROFILE_AUDIT_RESULTS.md` | All 1,142 queries and 6,149,670 pairs complete; 1,171 artifact hashes, 1,142 checkpoints and 32,012 metrics independently verify; headroom bound 0.091732 | Completed; post-hoc decision aid | 2026-09-08 |
| Exploratory-24 page-level feasibility | Complete run, independent review and `docs/05_oracle_experiments/exploratory24/QPAF_EXPLORATORY24_RESULTS.md` | All 24 queries and 129,240 pairs complete; 82 artifacts, 50 checkpoint envelopes, 25 source snapshots, 960 raw ranking metrics and 415 aggregate comparisons verify; QPAF-minus-QARF is 0.050011 with CI95 [0.008344, 0.101921] | Completed; exploratory only | 2026-09-08 |
| Exploratory-24 W66 sensitivity | Complete optimized run, independent review, and `docs/05_oracle_experiments/w66/QPAF_W66_EXPLORATORY24_RESULTS.md` | All 24 queries, 66 profiles, and 129,240 pairs complete; 97 artifacts, 50 checkpoint envelopes, 32 source snapshots, 1,503 telemetry samples, 6,624 raw metric values, and 127 aggregate comparisons verify; QPAF-minus-QARF is 0.032066 with CI95 [0.002888, 0.071165] | Completed; exploratory only | 2026-09-09 |
| P1-03: Run W66 sensitivity and decide granularity | W66 results plus machine-readable `proceed_qpaf`, `revise`, or `stop` decision | W7/W66 hashes match; gain, bootstrap, and concentration gates are evaluated without changing the frozen protocol | Blocked | 2026-09-05 |

## Phase 3 — Learned Fusion Implementation

Next review: the bounded exploratory-24 W7 and W66 studies both clear their exploratory continuation signals. W66 completed in 1,551.236275 seconds and reached QPAF 0.885911 with QPAF-minus-QARF 0.032066, but it did not outperform W7 QPAF 0.903856; the complete gap is attributable to one tied-profile initialization-order case. The 2026-09-10 research-focus amendment keeps QPAF as the proposed method, QARF as its mandatory matched baseline, and moves CARF to P3-02 as a granularity ablation. Formal P1-03 and learned execution tasks remain blocked; P2-01/P2-02 are complete only as local non-training method-core validation, while any optimizer step, training, Modal/GPU use, or new oracle invocation requires separate authorization.

**Goal:** Implement the smallest label-free adaptive models only after the oracle gate authorizes the selected granularity.

| Task | Deliverable | Completion Criteria | Status | Target Date |
| ---- | ----------- | ------------------- | ------ | ----------- |
| P2-01: Build deterministic features | `oracle_study.learned.features` and tests for the 13-dimensional query-page feature contract | Features are finite, padded rows are zero, page-associated values are permutation-stable, and labels cannot affect output | Completed locally under the 2026-09-10 non-training continuation amendment; no learned result | 2026-09-10 |
| P2-02: Implement gates and listwise loss | Linear QARF/QPAF gates, fusion scorer, masked loss, and gradient tests | Zero initialization yields equal weights; gradcheck and masking tests pass; all outputs and gradients are finite | Completed locally; zero optimizer steps and no trained checkpoint | 2026-09-10 |
| P2-03: Train the learned QARF baseline | Modal training pipeline, immutable checkpoint, predictions, history, and metrics | Smoke run passes; checkpoint reload reproduces scores; train/validation IDs and manifests are valid | Blocked | [INSERT: QARF training target date] |
| P2-04: Train and evaluate learned QPAF | One-seed confirmation checkpoint, predictions, quality metrics, latency, and memory telemetry | Gain is at least 0.01 nDCG@10 over the strongest deployable baseline; latency is at most 10 ms/query; peak CUDA allocation is below 1.50 GiB | Blocked | [INSERT: QPAF Phase 2 target date] |

## Phase 4 — Benchmark, Robustness, and External Validation

**Goal:** Determine whether the selected learned fusion method generalizes across seeds, design choices, and a sealed external dataset.

| Task | Deliverable | Completion Criteria | Status | Target Date |
| ---- | ----------- | ------------------- | ------ | ----------- |
| P3-01: Run the three-seed confirmation benchmark | Per-seed results, aggregate table, and 10,000-resample bootstrap comparisons | Seeds 20260820–20260822 complete for every learned method with identical test data; success, inconclusive, or refuted is reported | Blocked | [INSERT: benchmark target date] |
| P3-02: Run preregistered ablations and CARF diagnostic | Channel, feature, gate, normalization, candidate-depth, W7/W66, and QARF–CARF–QPAF granularity evidence | Each learned run changes one declared factor; three seeds complete or the cell is marked not run with a reason; CARF K=2/3/4 clusters are deterministic, label-free, frozen before qrels, and reported as oracle-only | Blocked | [INSERT: ablation target date] |
| P3-03: Run sealed ViDoRe V3 validation | External predictions, metrics, and protocol audit | No external labels influence training or selection; dataset hashes match the seal; all metrics and confidence intervals are reported | Blocked | [INSERT: external validation target date] |

## Phase 5 — Reproducibility and Research Delivery

**Goal:** Package measured evidence so another technical team can audit and reproduce the final conclusion without relying on undocumented state.

| Task | Deliverable | Completion Criteria | Status | Target Date |
| ---- | ----------- | ------------------- | ------ | ----------- |
| Consolidate final results | Global/QARF/CARF/QPAF results table with baseline, learned, oracle, latency, and memory labels | Every planned cell is measured or marked not run; oracle upper bounds and candidate-only metrics are unambiguous | Blocked | [INSERT: results consolidation target date] |
| Complete provenance and run ledgers | Resolved configs, immutable checkpoints, append-only results, commands, and SHA-256 manifests | Every reported number resolves to a dataset hash, code commit, config, seed, and run identifier | Blocked | [INSERT: provenance audit target date] |
| P3-04: Publish the reproducibility package | `QPAF_REPRODUCIBILITY.zip`, reproduction commands, manifest, and technical report | Package hashes verify; a clean-environment reproduction check has zero failures; final learned result is labeled accurately | Blocked | [INSERT: reproducibility release target date] |

## Milestones

| Milestone | Completion Condition | Status | Target Date |
| --- | --- | --- | --- |
| M1 — Reproducible foundation established | Phase 1 foundation tasks and validated ViDoRe score bundle complete | Completed | [INSERT: M1 target date] |
| M2 — ViDoSeek all-corpus recovery verified | P1-02R integrity and 1.0 coverage gates pass without relabeling P1-02 | Completed | [INSERT: M2 target date] |
| M3 — Fusion granularity decision | Authorized W7/W66 evidence yields a reviewed proceed, revise, or stop decision | Blocked | 2026-09-05 |
| M4 — Learned fusion gate | Matched QARF and QPAF runs meet quality, latency, memory, and reproducibility criteria | Blocked | [INSERT: M4 target date] |
| M5 — Final benchmark release | Three-seed QARF/QPAF benchmark, CARF granularity ablation, other ablations, sealed validation, and reproducibility package pass | Blocked | [INSERT: M5 target date] |
