# QPAF Implementation Task DAG

Execute tasks in dependency order. A task may not begin until every dependency is `PASS`. A failed verification blocks every downstream task; never proceed on a red test. Phase gates are hard: never enter Phase $N+1$ while Phase $N$ is unmet. Every task ends as `PASS`, `BLOCKED`, or `KILLED`. `BLOCKED` means a dependency or external input is unavailable and has been reported. `KILLED` means the task's explicit stop condition fired and the research path must not be worked around.

All paths are relative to the repository root that contains this file. Use PowerShell commands exactly as shown for local non-training checks on Windows. Modal Functions run in the pinned Linux image and set `PYTHONPATH=src` inside that image while preserving all arguments and thresholds.

## Dependency Graph

```text
PHASE 0 — ENVIRONMENT AND BASELINE

P0-01 Freeze baseline snapshot
  |
  v
P0-02 Freeze environment and datasets
  |
  v
P0-03 Reproduce baseline and validate score bundle
  |
  +================ PHASE 0 GATE =================+
  |  29 original tests pass; manifest valid;       |
  |  relevant-page coverage >= 0.95; _SUCCESS.json |
  +================================================+
  |
  v
PHASE 1 — CHEAPEST DISPROOF

P1-01 Harden three-channel cache and metric contracts
  |
  v
P1-02 Run W7 Global/QARF/QPAF oracle pilot
  |
  v
P1-03 Run W66 sensitivity and decide granularity
  |
  +=============== PHASE 1 GATE ==================+
  |  By 2026-09-05: QPAF-vs-QARF mean delta >=.03 |
  |  in discovery, CI low >0 in W7 and W66, and   |
  |  top-5%-gain share <.90; otherwise stop/revise |
  +================================================+
  |
  v
PHASE 2 — FULL METHOD

P2-01 Implement 13-feature builder
  |
  v
P2-02 Implement linear gates and listwise loss
  | \
  |  +--> P2-03 Implement QARF training baseline --+
  |                                             |
  +----> P2-04 Implement QPAF training ----------+
                                                |
                         P1-03 --> P2-05 CARF diagnostic
                                                |
  +================ PHASE 2 GATE ================+
  |  Full confirmation run completes; peak VRAM  |
  |  <1.50 GiB; QPAF validation delta >=.01 over |
  |  strongest deployable baseline; no NaN/Inf   |
  +===============================================+
  |
  v
PHASE 3 — BENCHMARK, ABLATION, REPRODUCIBILITY

P3-01 Run three-seed benchmark
  |
  +--> P3-02 Run ablations --------+
  |                                |
  +--> P3-03 Run sealed external validation
                                   |
                                   v
                         P3-04 Package reproducibility artifacts
                                   |
  +================ PHASE 3 GATE ================+
  |  Every planned table cell populated or marked |
  |  not run with reason; variance and CI reported;|
  |  manifest/hash verification passes            |
  +===============================================+
```

## Phase 0 — Environment and Baseline Verification

No new fusion-method code may be written in this phase. Failure to reproduce the frozen baseline or validate the score bundle halts the project because downstream comparisons would be uninterpretable.

### TASK-ID: P0-01
**TITLE:** Freeze the inspected oracle-study baseline in a versioned repository
**DEPENDENCIES:** NONE
**FILES:** `pyproject.toml`, `src/oracle_study/**`, `tests/test_budget.py`, `tests/test_cache.py`, `tests/test_cli_e2e.py`, `tests/test_decision.py`, `tests/test_feasibility.py`, `tests/test_metrics.py`, `tests/test_notebook.py`, `tests/test_preflight.py`, `tests/test_preregistration.py`, `tests/test_qpaf.py`, `tests/test_sampling.py`, `configs/preregistered.yaml`, `artifacts/baseline_snapshot_manifest.json`
**DESCRIPTION:**
  Import the inspected `visual-rag-oracle-study` 0.1.0 snapshot without modification. Initialize Git if necessary, record SHA-256 for every imported source/config/test file, record the source location and import time in `artifacts/baseline_snapshot_manifest.json`, and create an immutable baseline commit. Do not implement Eq. 1–12 or change existing behavior.
**I/O CONTRACT:**
  Inputs: baseline source files [byte sequences] uint8 CPU — exactly the inspected snapshot; source path [string] UTF-8 CPU — existing checkout location
  Outputs: manifest entries [N] JSON CPU — relative path, byte length, SHA-256; git commit [40 hex chars] UTF-8 CPU — clean working tree
  Side effects: creates Git metadata, imports baseline files, writes `artifacts/baseline_snapshot_manifest.json`, creates one baseline commit
**IMPLEMENTATION NOTES:**
  Exclude `.venv`, `__pycache__`, notebooks generated from builders, and result artifacts from the commit unless the existing `.gitignore` explicitly tracks them. Do not normalize or reformat imported source. A byte change from the inspected snapshot is a provenance failure.
**VERIFICATION:**
  Command: `python -c "import hashlib,json,pathlib,subprocess; m=json.load(open('artifacts/baseline_snapshot_manifest.json',encoding='utf-8')); assert len(m['files'])>=25; assert all(hashlib.sha256(pathlib.Path(x['path']).read_bytes()).hexdigest()==x['sha256'] for x in m['files']); h=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(); assert len(h)==40; assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip(); print('BASELINE_FROZEN',h,len(m['files']))"`
  Assertions:
    - Manifest contains at least 25 tracked source/config/test files and every SHA-256 matches.
    - Git HEAD is exactly 40 hexadecimal characters and the worktree is clean.
  Expected runtime: under 2 minutes
**STOP/KILL CONDITION:**
  HALT and report to the human if the baseline source cannot be located, any imported file differs from its recorded hash, or the destination already has unrelated uncommitted changes. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P0-02
**TITLE:** Freeze the execution environment and dataset identities
**DEPENDENCIES:** P0-01
**FILES:** `modal_app.py`, `configs/modal.yaml`, `configs/environment.yaml`, `configs/datasets.yaml`, `requirements-lock.txt`, `artifacts/environment_manifest.json`, `artifacts/modal_environment_probe.json`, `artifacts/dataset_manifest.json`, `scripts/capture_environment.py`, `scripts/verify_datasets.py`, `tests/test_environment_contract.py`, `tests/test_modal_contract.py`, `tests/test_dataset_contract.py`
**DESCRIPTION:**
  Capture the exact local and Modal execution contracts from Context A07–A09. Create the Modal App infrastructure only—no method or training code—with a pinned image, human-approved `gpu="L4"` default, explicit timeout, persistent Volume mounts, and named Secrets. Reserve `A100-40GB` only as the full score-extraction fallback. Pin Python, Modal, and all remote dependencies; record PyTorch, CUDA, driver, actual GPU name/VRAM, platform, model IDs and immutable revisions for BM25 implementation, BGE-M3, and ColQwen2.5. Record ViDoSeek, ViMDoc, ViDoRe V3, and MMDocIR identifiers, revisions, licenses, split hashes, file counts, and qrels checksums. Dataset verification is read-only.
**I/O CONTRACT:**
  Inputs: environment metadata [mapping] UTF-8 CPU — actual runtime; dataset files [N bytes] uint8 CPU — read-only; model revisions [3 strings] UTF-8 CPU — immutable IDs
  Outputs: environment manifest [mapping] JSON CPU — local and Modal sections with no null required fields; Modal probe [mapping] JSON CPU — App/run ID, image hash, actual GPU/VRAM, CUDA, driver, PyTorch, Volume; dataset manifest [4 records] JSON CPU — hashes and counts; dependency lock [text] UTF-8 CPU — fully pinned
  Side effects: authenticates to the approved Modal workspace, builds or pulls a Modal image, invokes a non-training environment probe, and writes configs/manifests/lock/tests; does not train or mutate datasets
**IMPLEMENTATION NOTES:**
  Local and Modal environments are separate manifest sections. The Modal default GPU request is exactly `L4`, approved by the human on 2026-08-25; the actual device must report at least 23.5 decimal GB and the manifest must record both decimal GB and binary GiB. Mount caches and artifacts through a persistent Modal Volume and call `volume.commit()` after successful remote writes. The unchanged extractor's 23.5 GiB guard may reject L4; in that case use `A100-40GB` for full score extraction rather than weakening the guard or silently changing batch size. Do not copy credentials into the image or repository. Do not describe the 2 GiB MX130 as training/extraction-capable. Dataset paths live in config or environment variables, never source code.
**VERIFICATION:**
  Command: `python -m pytest tests/test_environment_contract.py tests/test_modal_contract.py tests/test_dataset_contract.py -v; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; modal run --write-result artifacts/modal_environment_probe.json modal_app.py::environment_probe`
  Assertions:
    - All dependency versions and all three retriever model revisions are non-empty and immutable.
    - Modal probe reports requested GPU `L4`, CUDA available, actual GPU VRAM at least 23.5 decimal GB, both GB/GiB fields, and a non-empty App/run ID and image-definition hash; dataset manifest contains exactly four named datasets and every recorded SHA-256 has length 64.
  Expected runtime: under 10 minutes excluding human-provided credentials or downloads
**STOP/KILL CONDITION:**
  HALT and report to the human if Modal authentication is unavailable, the pinned image cannot build, the Volume/Secrets do not resolve, no approved 24+ GiB Modal GPU exists, a model revision is mutable or unavailable, a dataset license forbids the planned use, or any required dataset revision cannot be identified. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P0-03
**TITLE:** Reproduce the baseline and validate the completed score bundle
**DEPENDENCIES:** P0-02
**FILES:** `artifacts/baseline_test_output.txt`, `data/raw_scores.parquet`, `data/official_query_metrics.parquet`, `data/cache/retrieval_scores.parquet`, `data/cache/query_metrics.parquet`, `data/cache/coverage_report.json`, `artifacts/artifact_manifest.json`, `artifacts/_SUCCESS.json`, `artifacts/preflight.json`, `artifacts/baseline_metrics.json`, `artifacts/run_manifest.json`
**DESCRIPTION:**
  Run the original baseline test suite before adding new tests. Submit three-channel score extraction to Modal if a completed bundle does not already exist, import the resulting bundle from the persistent Volume, verify its success marker and hashes, then run the existing local non-training preflight and metric implementations. This task validates software behavior and data integrity; it must not claim a learned or oracle improvement.
**I/O CONTRACT:**
  Inputs: raw score rows [N, required columns] Parquet CPU — unique `(dataset,query_id,page_id)` and finite three-channel scores; official query metrics [Q,metric columns] Parquet CPU — full-corpus evaluation export; success bundle [10 artifacts] bytes CPU — matching manifest
  Outputs: baseline test log [text] UTF-8 CPU — 29 passes; coverage report [mapping] JSON CPU — overall and per-query; baseline metrics [methods,4] float64 CPU — BM25/dense/visual/RRF/fixed; run manifest [mapping] JSON CPU — commit and data hashes
  Side effects: may invoke `modal_app.py::extract_scores` on Modal; writes copied immutable data and artifact reports; does not train locally or change baseline source
**IMPLEMENTATION NOTES:**
  Run score extraction only on Modal. Run local preflight with `PYTHONPATH=src`. Reject duplicate keys, non-finite scores, missing channel provenance, mismatched hashes, or `_SUCCESS.json` absence. Candidate generation and normalization must not read qrels.
**VERIFICATION:**
  Command: `modal run modal_app.py::extract_scores; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; $env:PYTHONPATH='src'; python -m pytest -q; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python -m oracle_study.cli build-cache --raw data/raw_scores.parquet --query-metrics data/official_query_metrics.parquet --output-dir data/cache; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python -m oracle_study.cli preflight --scores data/cache/retrieval_scores.parquet --metrics data/cache/query_metrics.parquet --output artifacts/preflight.json`
  Assertions:
    - Original suite reports exactly 29 passed, 0 failed, 0 errors.
    - `_SUCCESS.json` and all ten manifest artifacts verify; relevant-page coverage is at least 0.95 overall and no included query has zero relevant candidates.
  Expected runtime: tests under 10 seconds; preflight under 10 minutes for 1.2 million rows
**STOP/KILL CONDITION:**
  HALT and report to the human if `_SUCCESS.json` is absent, any artifact hash mismatches, the original suite is not exactly 29/29, or relevant-page coverage is below 0.95. This is not a retry condition. Do not attempt a workaround. Report and stop.

**PHASE 0 GATE:** P0-01–P0-03 are `PASS`; baseline is a clean immutable commit; original tests are 29/29; remote environment is declared; datasets and model revisions are frozen; score bundle and ten artifacts match their hashes; relevant-page coverage is at least 0.95. Otherwise the project is `BLOCKED` and Phase 1 must not start.

## Phase 1 — Minimal Viable Experiment

This phase is the cheapest disproof. It uses cached scores and exhaustive preregistered profiles; it does not train a gating model. The decision checkpoint is **2026-09-05**.

### TASK-ID: P1-01
**TITLE:** Harden three-channel cache, normalization, and metric contracts
**DEPENDENCIES:** P0-03
**FILES:** `src/oracle_study/cache.py`, `src/oracle_study/metrics.py`, `tests/test_three_channel_contract.py`, `tests/test_metric_reference.py`, `artifacts/metric_reference.json`
**DESCRIPTION:**
  Verify Eq. 1–2 for three channels, stable page-ID tie-breaking, constant-range normalization, missing-score policy, and the exact nDCG@10/Recall@1/Recall@3/MRR@10 definitions. Add hand-computed fixtures; do not change metric semantics merely to match an external library.
**I/O CONTRACT:**
  Inputs: score matrix [C,3] float64 CPU — finite; page IDs [C] string CPU — unique within query; relevance [C] float64 CPU — non-negative
  Outputs: normalized scores [C,3] float64 CPU — $[0,1]$; metric vector [4] float64 CPU — each $[0,1]$; stable order [C] int64 CPU — permutation
  Side effects: writes tests and `artifacts/metric_reference.json`; may make only contract-preserving fixes in existing modules
**IMPLEMENTATION NOTES:**
  Use the existing $10^{-15}$ constant-range rule. Test one channel with all equal scores, tied fused scores, one positive, multiple graded positives, and empty arrays. Candidate coverage is computed before normalization.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_three_channel_contract.py tests/test_metric_reference.py tests/test_metrics.py tests/test_cache.py -v`
  Assertions:
    - Hand-computed metric values agree within absolute tolerance $10^{-12}$ and repeated tie rankings are identical in 100 repetitions.
    - Every finite normalized value lies in $[0,1]$ within $10^{-12}$; constant channels become exact zeros.
  Expected runtime: under 5 seconds
**STOP/KILL CONDITION:**
  HALT and report to the human if the existing metric disagrees with the hand-computed formula by more than $10^{-12}$ or fixing it changes a previously reported result. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P1-02
**TITLE:** Run the W7 Global–QARF–QPAF oracle pilot
**DEPENDENCIES:** P1-01
**FILES:** `configs/pilot_w7.yaml`, `artifacts/pilot_w7/qpaf_oracle_results.jsonl`, `artifacts/pilot_w7/qpaf_summary.json`, `artifacts/pilot_w7/qpaf_query_summary.parquet`, `artifacts/pilot_w7/qpaf_subgroups.csv`, `artifacts/pilot_w7/qpaf_oracle_gain.png`, `artifacts/pilot_w7/run_manifest.json`, `artifacts/pilot_w7/decision.md`
**DESCRIPTION:**
  Execute exhaustive W7 Global, query-level QARF, and candidate-level QPAF oracle analysis using the existing `run_qpaf_oracle`. This directly tests the cheapest-disproof hypothesis: whether page-level choice adds at least 0.03 discovery mean nDCG@10 over QARF with a positive query-bootstrap interval.
**I/O CONTRACT:**
  Inputs: validated score cache [N rows,3 channels] float64 CPU — coverage at least 0.95; relevance [N] float64 CPU — oracle use only; W7 [7,3] float64 CPU — simplex rows
  Outputs: per-query oracle rows [Q] JSONL CPU — Global/QARF/QPAF metrics and assignments; summary [mapping] JSON CPU — gain, CI, coverage, concentration; subgroup table [G,metrics] float64 CPU
  Side effects: writes a new immutable run directory; does not modify score cache or preregistered thresholds
**IMPLEMENTATION NOTES:**
  Seed bootstrap with 20260820 and use 10,000 resamples. Label every output `oracle_upper_bound`. QPAF $\ge$ QARF $\ge$ Global alone is not evidence because it follows from nested choice sets.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m oracle_study.cli qpaf --scores data/cache/retrieval_scores.parquet --grids w7 --bootstrap 10000 --output-dir artifacts/pilot_w7; python -m pytest tests/test_qpaf.py tests/test_preregistration.py -v`
  Assertions:
    - W7 contains exactly 7 unique non-negative profiles and every row sums to one within $10^{-12}$.
    - Summary contains every query, 10,000 bootstrap resamples, finite metrics in $[0,1]$, and `delta_qpaf_vs_qarf` for every query.
  Expected runtime: under 30 minutes on CPU after caching
**STOP/KILL CONDITION:**
  HALT and report to the human if any qrels value enters score normalization/candidate construction, any query is missing from output, or mean QPAF-vs-QARF nDCG@10 is below 0.01. The last condition kills learned QPAF and selects the simpler QARF/static path. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P1-03
**TITLE:** Run W66 sensitivity and issue the Phase 1 granularity decision
**DEPENDENCIES:** P1-02
**FILES:** `configs/pilot_w66.yaml`, `scripts/decide_granularity.py`, `tests/test_granularity_decision.py`, `artifacts/pilot_w66/qpaf_oracle_results.jsonl`, `artifacts/pilot_w66/qpaf_summary.json`, `artifacts/pilot_w66/qpaf_query_summary.parquet`, `artifacts/pilot_w66/qpaf_subgroups.csv`, `artifacts/pilot_w66/qpaf_oracle_gain.png`, `artifacts/pilot_w66/run_manifest.json`, `artifacts/phase1_decision.json`, `artifacts/phase1_decision.md`
**DESCRIPTION:**
  Repeat the oracle analysis with all 66 simplex profiles at 0.1 increments, compare W7 and W66, measure gain concentration, and produce a machine-readable decision by 2026-09-05. Proceed to learned QPAF only if page-level headroom is positive, practically material, and not concentrated in a tiny query subset.
**I/O CONTRACT:**
  Inputs: validated score cache [N,3] float64 CPU; W66 [66,3] float64 CPU; W7 summary [mapping] JSON CPU
  Outputs: W66 rows [Q] JSONL CPU; comparison summary [mapping] JSON CPU; phase decision [mapping] JSON CPU — `proceed_qpaf`, `revise`, or `stop`
  Side effects: writes immutable W66 run and phase decision; no threshold changes
**IMPLEMENTATION NOTES:**
  W66 must be generated by integer triples summing to 10. Use identical candidate pool, normalization, metrics, bootstrap seed, and qrels. If QPAF gain is clear, CARF remains a diagnostic required before claiming page-level necessity.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m oracle_study.cli qpaf --scores data/cache/retrieval_scores.parquet --grids w66 --bootstrap 10000 --output-dir artifacts/pilot_w66; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python scripts/decide_granularity.py --w7 artifacts/pilot_w7/qpaf_summary.json --w66 artifacts/pilot_w66/qpaf_summary.json --output artifacts/phase1_decision.json; python -m pytest tests/test_granularity_decision.py -v`
  Assertions:
    - W66 has exactly 66 unique simplex profiles and W7/W66 use identical query IDs and data hashes.
    - `proceed_qpaf` requires mean QPAF-vs-QARF delta at least 0.03, bootstrap lower bound above 0 in both W7 and W66, and top-5%-gain share below 0.90.
  Expected runtime: under 4 hours on CPU after caching
**STOP/KILL CONDITION:**
  HALT and report to the human if the result is `stop`, query/data hashes differ across grids, or the decision file is produced after 2026-09-05 without an approved schedule update. If mean gain is between 0.01 and 0.03 or either CI crosses zero, mark `revise` and do not enter Phase 2. This is not a retry condition. Do not attempt a workaround. Report and stop.

**PHASE 1 GATE:** By 2026-09-05, W7 and W66 have identical data hashes; mean QPAF-vs-QARF discovery $\Delta\mathrm{nDCG@10}\ge0.03$ in both grids; both bootstrap lower bounds are $>0$; top-5%-gain share is $<0.90$; and P1-03 outputs `proceed_qpaf`. `revise` requires human approval for a new preregistration. `stop` kills learned QPAF.

## Phase 2 — Full Method Implementation

### TASK-ID: P2-01
**TITLE:** Implement the deterministic 13-feature builder
**DEPENDENCIES:** P1-03
**FILES:** `src/oracle_study/features.py`, `tests/test_features.py`
**DESCRIPTION:**
  Implement Eq. 3 exactly: three normalized scores, three normalized ranks, three median-relative score margins, three query-level top-1/top-2 gaps, and one rank-disagreement value. Use page ID as the deterministic tie-break and never read labels.
**I/O CONTRACT:**
  Inputs: scores [B,C,3] float32 CPU or CUDA — finite $[0,1]$; page IDs [B,C] string CPU — valid positions unique; valid mask [B,C] bool CPU or CUDA
  Outputs: features [B,C,13] float32 same device as scores — finite, padded rows zero
  Side effects: NONE
**IMPLEMENTATION NOTES:**
  Feature preprocessing is stop-gradient. Sorting may run on CPU, but returned numeric features must preserve batch/candidate order. When one valid candidate exists, define top-2 equal to top-1 so gap is zero; training still rejects fewer than two candidates.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_features.py -v`
  Assertions:
    - Output is exactly `[2,5,13]` for the reference fixture, finite float32, and padded feature rows are exact zeros.
    - Permuting input row order while preserving page IDs changes no page-associated feature by more than $10^{-7}$; adding a `relevance` column cannot affect output bytes.
  Expected runtime: under 3 seconds
**STOP/KILL CONDITION:**
  HALT and report to the human if deterministic ranks cannot be reproduced across 100 runs or any feature requires qrels/oracle assignments. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P2-02
**TITLE:** Implement linear QARF/QPAF gates and masked listwise ranking loss
**DEPENDENCIES:** P2-01
**FILES:** `src/oracle_study/models.py`, `src/oracle_study/losses.py`, `tests/test_models.py`, `tests/test_losses.py`, `tests/test_gradients.py`
**DESCRIPTION:**
  Implement Eq. 4–12 with `LinearQPAFGate`, `LinearQARFGate`, `FusionScorer`, and `ListwiseRankLoss`. Initialize all gate parameters to zero, keep logits/softmax/log-softmax/loss in fp32, and use native PyTorch autograd; no custom backward or CUDA code.
**I/O CONTRACT:**
  Inputs: features [B,C,13] float32 device; scores [B,C,3] float32 device; relevance [B,C] float32 device; valid mask [B,C] bool device
  Outputs: weights [B,C,3] float32 device — simplex; fused scores [B,C] float32 device; loss [] float32 device — finite non-negative
  Side effects: NONE
**IMPLEMENTATION NOTES:**
  Reject a batch containing a query with no positive valid candidate. Use masked `log_softmax`, not manual exponentiation. Clip gradients in the training loop, not inside the modules. Keep debug boundary assertions configurable.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_models.py tests/test_losses.py tests/test_gradients.py -v`
  Assertions:
    - Zero initialization produces weights exactly $1/3$ within $10^{-7}$ and fused scores equal arithmetic mean within $10^{-7}$.
    - `torch.autograd.gradcheck` passes in float64 with `eps=1e-6`, `atol=1e-4`; padded-value perturbations change loss by less than $10^{-7}$; all gradients are finite.
  Expected runtime: under 10 seconds
**STOP/KILL CONDITION:**
  HALT and report to the human if gradcheck fails after two implementation attempts, loss is non-finite on any boundary fixture, or the derived gradient in Eq. 11 disagrees with autograd by more than $10^{-4}$. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P2-03
**TITLE:** Implement the learned QARF training and evaluation baseline
**DEPENDENCIES:** P2-02
**FILES:** `modal_app.py`, `src/oracle_study/dataset.py`, `src/oracle_study/train.py`, `src/oracle_study/evaluate.py`, `configs/qarf_train.yaml`, `tests/test_dataset.py`, `tests/test_evaluation.py`, `tests/test_modal_training_contract.py`
**DESCRIPTION:**
  Build padded query batches, then submit `LinearQARFGate` training to Modal with Eq. 7–12, checkpoint the best validation nDCG@10 model in the persistent Volume, and evaluate deterministic rankings. This is the strongest learned query-adaptive baseline under the same features, loss, optimizer, split, and budget as QPAF. No optimizer step may run locally.
**I/O CONTRACT:**
  Inputs: train/validation score rows [N,3] float64 CPU; relevance [N] float64 CPU; config [mapping] YAML CPU — seed, batch 32, AdamW, gradient clip 1.0
  Outputs: checkpoint [42 parameters plus metadata] bytes CPU; metrics [4] float64 CPU; predictions [N] Parquet CPU; history [epochs,loss+metrics] CSV CPU
  Side effects: invokes `modal_app.py::train_qarf`; creates a unique run directory in the Modal Volume and synchronized `experiments/`; appends one row to `experiments/results.jsonl`
**IMPLEMENTATION NOTES:**
  Local tests may validate collation, forward/backward math, and checkpoint serialization on fixed tensors but may not create optimizer steps or trained checkpoints. Fit nothing on validation/test other than evaluation. Save the resolved config, commit, dirty diff, data hashes, seed, Modal App/run ID, image hash, actual GPU, command, and peak memory. Resume only from a checkpoint with identical config/data hashes.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_dataset.py tests/test_evaluation.py tests/test_modal_training_contract.py -v; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; modal run modal_app.py::train_qarf`
  Assertions:
    - A 20-query, 2-epoch Modal smoke run completes with finite loss, post-clip gradient norm at most 1.0001, and identical metrics on two repeated evaluations; its manifest contains the Modal App/run ID and image hash.
    - The checkpoint reload reproduces every fused score within $10^{-7}$ and results ledger gains exactly one append-only row.
  Expected runtime: local non-training tests under 30 seconds; Modal smoke job under 10 minutes excluding cold image build
**STOP/KILL CONDITION:**
  HALT and report to the human if train/validation query IDs overlap, any manifest field is missing, or baseline metrics change after checkpoint reload by more than $10^{-7}$. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P2-04
**TITLE:** Implement and run learned QPAF on confirmation data
**DEPENDENCIES:** P2-02, P2-03
**FILES:** `modal_app.py`, `configs/qpaf_train.yaml`, `src/oracle_study/train.py`, `src/oracle_study/evaluate.py`, `tests/test_qpaf_remote_contract.py`, `experiments/qpaf_confirmation/**`, `artifacts/phase2_qpaf_summary.json`
**DESCRIPTION:**
  Submit `LinearQPAFGate` training to Modal with page-specific Eq. 4–6 and the identical data, features, objective, optimizer, early-stopping rule, image, GPU class, and budget used by QARF. Run seed 20260820 first for the Phase 2 gate; Phase 3 expands to three seeds. No optimizer step may run locally.
**I/O CONTRACT:**
  Inputs: confirmation train/validation batches with scores [B,C,3], features [B,C,13], relevance [B,C], mask [B,C]; config [mapping] YAML CPU
  Outputs: checkpoint [42 parameters plus metadata] bytes CPU; predictions [N] Parquet CPU; metrics [4] float64 CPU; latency samples [Q] float64 CPU; peak memory [scalar] float64 CPU
  Side effects: invokes `modal_app.py::train_qpaf`, persists the immutable run to the Modal Volume and synchronized `experiments/qpaf_confirmation/<run_id>`, and appends the result ledger
**IMPLEMENTATION NOTES:**
  Set anomaly detection for the first 100 debug steps only. Measure fusion latency after 20 warm-up queries and over at least 1,000 queries; exclude retriever score extraction. On CUDA, enforce the 1.50 GiB hard cap.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_qpaf_remote_contract.py -v; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; modal run modal_app.py::train_qpaf`
  Assertions:
    - Full confirmation run completes with finite loss/gradients, peak CUDA allocation below 1.50 GiB when CUDA is used, and no data-hash change from QARF.
    - Validation mean nDCG@10 exceeds the strongest deployable baseline by at least 0.01 and median added fusion latency is at most 10.0 ms/query.
  Expected runtime: local non-training test under 30 seconds; full cached-score Modal run under 4 hours excluding cold image build
**STOP/KILL CONDITION:**
  HALT and report to the human if peak VRAM reaches 1.50 GiB, any NaN/Inf occurs, data hashes differ from QARF, or validation gain is below 0.01. Do not reduce batch size or alter thresholds. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P2-05
**TITLE:** Implement the preregistered CARF diagnostic without qrels leakage
**DEPENDENCIES:** P1-03, P2-01
**FILES:** `src/oracle_study/carf.py`, `configs/carf_k3.yaml`, `tests/test_carf.py`, `artifacts/carf_oracle_summary.json`, `artifacts/carf_cluster_manifest.json`
**DESCRIPTION:**
  Cluster each query's candidates using only normalized score/rank features, with $K=3$, seed 20260820, and sensitivity $K=2,4$. Freeze cluster assignments before joining qrels, then compute CARF oracle profiles to locate headroom between QARF and QPAF.
**I/O CONTRACT:**
  Inputs: label-free features [C,13] float32 CPU; valid mask [C] bool CPU; profile grid [7 or 66,3] float64 CPU; relevance [C] float64 CPU — joined only after clustering
  Outputs: cluster IDs [C] int64 CPU — values $0..K-1$; cluster manifest [mapping] JSON CPU — feature/data hashes; CARF metrics [4] float64 CPU
  Side effects: writes frozen cluster assignments and CARF oracle summary; does not change learned QPAF
**IMPLEMENTATION NOTES:**
  The clustering function signature must not accept relevance. Assert cluster artifact timestamp/hash precedes the qrels join. Empty clusters are an observable failure; do not silently reduce $K$.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_carf.py -v; python -m oracle_study.carf --config configs/carf_k3.yaml --scores data/raw_scores.parquet --output artifacts/carf_oracle_summary.json`
  Assertions:
    - Cluster IDs are byte-identical across two runs with seed 20260820 and unchanged after relevance-label permutation.
    - CARF nDCG@10 lies between QARF and QPAF oracle within $10^{-12}$ for the reference fixture; $K=2,3,4$ all produce no empty cluster.
  Expected runtime: tests under 10 seconds; full diagnostic under 2 hours on CPU
**STOP/KILL CONDITION:**
  HALT and report to the human if clustering reads qrels, any cluster is empty for more than 1% of queries, or CARF/QPAF ordering violates the nested reference fixture. This is not a retry condition. Do not attempt a workaround. Report and stop.

**PHASE 2 GATE:** P2-01–P2-04 are `PASS`; P2-05 is `PASS` or explicitly `KILLED` because the approved CARF condition did not hold; the confirmation run completes without NaN/Inf; peak CUDA allocation is below 1.50 GiB; learned QPAF validation nDCG@10 is at least 0.01 above the strongest deployable baseline; and median fusion latency is at most 10.0 ms/query.

## Phase 3 — Benchmark and Ablation Suite

### TASK-ID: P3-01
**TITLE:** Run the three-seed confirmation benchmark and statistical comparison
**DEPENDENCIES:** P2-04
**FILES:** `modal_app.py`, `configs/benchmark.yaml`, `experiments/benchmark/**`, `artifacts/benchmark_results.parquet`, `artifacts/benchmark_summary.json`, `artifacts/bootstrap_comparisons.json`, `artifacts/results_table.md`
**DESCRIPTION:**
  Run fixed fusion, RRF, learned QARF, eligible learned CARF, and learned QPAF with seeds 20260820–20260822 under identical confirmation protocol. Aggregate query-level predictions, mean/std across seeds, and 10,000-resample query-bootstrap comparisons. Fill the confirmation columns of Context Table 1.
**I/O CONTRACT:**
  Inputs: frozen confirmation data [N rows] Parquet CPU; resolved configs [methods,seeds] YAML CPU; checkpoints [methods,seeds] bytes CPU
  Outputs: result rows [methods,seeds,metrics] float64 CPU; bootstrap comparisons [pairs,CI] float64 CPU; table [Markdown] UTF-8 CPU
  Side effects: creates immutable per-run directories, appends ledger rows, writes aggregate artifacts
**IMPLEMENTATION NOTES:**
  Never select the best seed. Report all seeds and mean/std. Use the same candidate rows and page-ID tie-break. Oracle rows remain upper bounds and do not enter learned-baseline significance tests.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_benchmark.py -v; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; modal run modal_app.py::benchmark`
  Assertions:
    - Exactly three unique seeds exist for every learned method and every method uses identical test query/data hashes.
    - A success claim requires QPAF mean delta at least 0.01 and bootstrap 95% lower bound above 0; otherwise result is `inconclusive` or `refuted`.
  Expected runtime: agent setup under 2 hours; compute runs may continue up to the declared job limit
**STOP/KILL CONDITION:**
  HALT and report to the human if any run uses a different split/candidate hash, fewer than three seeds complete, or a result row is overwritten rather than appended. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P3-02
**TITLE:** Run channel, feature, gate, normalization, and candidate-depth ablations
**DEPENDENCIES:** P3-01
**FILES:** `modal_app.py`, `configs/ablations.yaml`, `experiments/ablations/**`, `artifacts/ablation_results.parquet`, `artifacts/ablation_table.md`, `tests/test_ablation_config.py`
**DESCRIPTION:**
  Run the dossier-required ablations: remove each channel; scores/ranks only versus all 13 features; linear gate versus one-hidden-layer MLP; QARF/CARF/QPAF with matched budget; W7/W66 oracle; candidate depth sensitivity; and min–max versus one preregistered alternative normalization. Change one factor per run.
**I/O CONTRACT:**
  Inputs: base config [mapping] YAML CPU; ablation matrix [rows,one changed field] YAML CPU; frozen data [N] Parquet CPU
  Outputs: ablation metrics [rows,seeds,4] float64 CPU; config diff [rows,1 changed field] JSON CPU; ablation table [Markdown] UTF-8 CPU
  Side effects: creates immutable run directories and appends ledger rows
**IMPLEMENTATION NOTES:**
  Each ablation inherits the exact base config and changes one field. A candidate-depth or normalization change receives a new cache/data hash and must not be compared as if protocol-identical without labeling it.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_ablation_config.py -v; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; modal run modal_app.py::run_ablations`
  Assertions:
    - Every ablation config differs from its parent in exactly one declared field and has three seeds or is marked not run with a reason.
    - Table contains all seven ablation families and every reported metric is finite in $[0,1]$.
  Expected runtime: configuration/test under 10 minutes; compute bounded by declared job budget
**STOP/KILL CONDITION:**
  HALT and report to the human if any ablation changes more than one experimental factor, uses test metrics for selection, or exceeds the declared total compute budget. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P3-03
**TITLE:** Run sealed ViDoRe V3 external validation
**DEPENDENCIES:** P3-01
**FILES:** `configs/external_vidore_v3.yaml`, `experiments/external_vidore_v3/**`, `artifacts/external_results.parquet`, `artifacts/external_summary.json`, `artifacts/external_protocol_audit.json`
**DESCRIPTION:**
  Evaluate the frozen checkpoints and hyperparameters on sealed ViDoRe V3 without tuning. Audit translated-variant grouping, full-corpus/candidate protocol, qrels isolation, and dataset revision. This tests external generalization; it does not establish Vietnamese retrieval.
**I/O CONTRACT:**
  Inputs: sealed score cache [N,3] float64 CPU; frozen checkpoints [methods,seeds] bytes CPU; sealed qrels [N] float64 CPU — evaluation only
  Outputs: external metrics [methods,seeds,4] float64 CPU; protocol audit [mapping] JSON CPU; predictions [N,method,seed] Parquet CPU
  Side effects: creates immutable external run directories; appends ledger rows once per run
**IMPLEMENTATION NOTES:**
  Config/checkpoint/data hashes must be frozen before the first test metric is computed. Do not retrain, recalibrate normalization with qrels, or choose a checkpoint using external results.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m oracle_study.external_eval --config configs/external_vidore_v3.yaml --output artifacts/external; python -m pytest tests/test_external_protocol.py -v`
  Assertions:
    - Every checkpoint/config timestamp and hash predates the first external metric artifact; train and external query IDs have zero overlap.
    - All three seeds are evaluated and repeated evaluation reproduces every metric within $10^{-12}$.
  Expected runtime: agent setup under 2 hours; cached-score evaluation under 1 hour
**STOP/KILL CONDITION:**
  HALT and report to the human if external qrels were accessed before configs/checkpoints were frozen, any query overlap exists, or dataset revision differs from the manifest. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P3-04
**TITLE:** Package the complete reproducibility and results artifact set
**DEPENDENCIES:** P3-02, P3-03
**FILES:** `README.md`, `requirements-lock.txt`, `experiments/results.jsonl`, `experiments/CHANGELOG.md`, `artifacts/results_table.md`, `artifacts/ablation_table.md`, `artifacts/reproducibility_manifest.json`, `artifacts/reproduce_commands.ps1`, `artifacts/QPAF_REPRODUCIBILITY.zip`, `tests/test_reproducibility_package.py`
**DESCRIPTION:**
  Populate every Context results-table row with measured values or an explicit `not run` reason, preserve seed status and oracle labels, collect resolved configs/manifests/predictions/commands, compute SHA-256 for the package, and document a fresh-checkout reproduction path.
**I/O CONTRACT:**
  Inputs: all completed run directories [N files] bytes CPU; results ledger [append-only rows] JSONL CPU; tables [Markdown] UTF-8 CPU
  Outputs: reproducibility package [ZIP] bytes CPU; manifest [entries] JSON CPU — path, size, SHA-256; command list [text] UTF-8 CPU
  Side effects: writes final documentation/package; does not delete or rewrite run outputs
**IMPLEMENTATION NOTES:**
  Keep oracle and deployable sections separate. Never fill an unmeasured cell with an estimate. Include the dirty diff for any run whose manifest says `git_dirty=true`. Package validation must run from a fresh temporary extraction directory.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_reproducibility_package.py -v; python -m oracle_study.verify_package --zip artifacts/QPAF_REPRODUCIBILITY.zip --manifest artifacts/reproducibility_manifest.json`
  Assertions:
    - Every ZIP member hash matches, all result rows reference an existing config/data/commit hash, and a fresh extraction reproduces the metric-fixture tests with 0 failures.
    - Results table has no unlabeled empty cell; every learned row reports three seeds and variance, while every oracle row is labeled `upper bound`.
  Expected runtime: under 30 minutes excluding full experiment reruns
**STOP/KILL CONDITION:**
  HALT and report to the human if any reported number lacks a source run, any manifest hash fails, a dirty run lacks its diff, or a fresh extraction cannot run the documented verification. This is not a retry condition. Do not attempt a workaround. Report and stop.

**PHASE 3 GATE:** P3-01–P3-04 are `PASS`; every planned table cell is measured or explicitly marked `not run` with a reason; every learned result has three-seed mean/std and query-bootstrap CI; every oracle is labeled as an upper bound; all package hashes verify; and the fresh-extraction test has 0 failures. Only then may the project report a learned QPAF result.
