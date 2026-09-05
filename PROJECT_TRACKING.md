# PROJECT_TRACKING.md

Execution tracker for the Query-Page-Adaptive Fusion (QPAF) research project.

This tracker translates the authoritative dependency DAG in `Tasks.md` into stakeholder-facing execution phases. A task may start only when all upstream completion criteria pass. `Blocked` means the task is prevented by a dependency, protocol gate, or missing approval—not that an experiment produced a negative metric.

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
| P1-02R-O1: Execute the authorized full-page synthetic calibration | One create-once attempt and immutable engineering manifest for query index 570 over 5,385 pages | Human runs the exact allowlisted command once; preflight, timeout, hash, and no-retry contracts hold | In Progress | 2026-09-05 |
| Review and authorize or reject post-hoc W7 | Recorded human decision and, if approved, a separately guarded W7 execution amendment | Full-page calibration is reviewed; task boundaries, resources, and exact execution authority are explicitly decided | Blocked | [INSERT: post-hoc W7 review target date] |
| P1-03: Run W66 sensitivity and decide granularity | W66 results plus machine-readable `proceed_qpaf`, `revise`, or `stop` decision | W7/W66 hashes match; gain, bootstrap, and concentration gates are evaluated without changing the frozen protocol | Blocked | 2026-09-05 |

## Phase 3 — Learned Fusion Implementation

**Goal:** Implement the smallest label-free adaptive models only after the oracle gate authorizes the selected granularity.

| Task | Deliverable | Completion Criteria | Status | Target Date |
| ---- | ----------- | ------------------- | ------ | ----------- |
| P2-01: Build deterministic features | `features.py` and tests for the 13-dimensional query-page feature contract | Features are finite, padded rows are zero, page-associated values are permutation-stable, and labels cannot affect output | Blocked | [INSERT: feature implementation target date] |
| P2-02: Implement gates and listwise loss | Linear QARF/QPAF gates, fusion scorer, masked loss, and gradient tests | Zero initialization yields equal weights; gradcheck and masking tests pass; all outputs and gradients are finite | Blocked | [INSERT: model implementation target date] |
| P2-03: Train the learned QARF baseline | Modal training pipeline, immutable checkpoint, predictions, history, and metrics | Smoke run passes; checkpoint reload reproduces scores; train/validation IDs and manifests are valid | Blocked | [INSERT: QARF training target date] |
| P2-04: Train and evaluate learned QPAF | One-seed confirmation checkpoint, predictions, quality metrics, latency, and memory telemetry | Gain is at least 0.01 nDCG@10 over the strongest deployable baseline; latency is at most 10 ms/query; peak CUDA allocation is below 1.50 GiB | Blocked | [INSERT: QPAF Phase 2 target date] |
| P2-05: Run the CARF diagnostic when eligible | Frozen label-free clusters and QARF–CARF–QPAF oracle comparison | Clustering is deterministic and label-free; K=2/3/4 checks pass; the diagnostic is completed or formally killed by its preregistered condition | Blocked | [INSERT: CARF diagnostic target date] |

## Phase 4 — Benchmark, Robustness, and External Validation

**Goal:** Determine whether the selected learned fusion method generalizes across seeds, design choices, and a sealed external dataset.

| Task | Deliverable | Completion Criteria | Status | Target Date |
| ---- | ----------- | ------------------- | ------ | ----------- |
| P3-01: Run the three-seed confirmation benchmark | Per-seed results, aggregate table, and 10,000-resample bootstrap comparisons | Seeds 20260820–20260822 complete for every learned method with identical test data; success, inconclusive, or refuted is reported | Blocked | [INSERT: benchmark target date] |
| P3-02: Run preregistered ablations | Channel, feature, gate, normalization, candidate-depth, and granularity ablation table | Each run changes one declared factor; three seeds complete or the cell is marked not run with a reason | Blocked | [INSERT: ablation target date] |
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
| M4 — Learned fusion gate | QARF and eligible QPAF/CARF runs meet quality, latency, memory, and reproducibility criteria | Blocked | [INSERT: M4 target date] |
| M5 — Final benchmark release | Three-seed benchmark, ablations, sealed validation, and reproducibility package pass | Blocked | [INSERT: M5 target date] |
