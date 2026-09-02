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
  Capture the exact local and Modal execution contracts from Context A07–A09. Create the Modal App infrastructure only—no method or training code—with a pinned image, human-approved `gpu="L4"` default, explicit timeout, persistent Volume mounts, and named Secrets. Reserve `A100-40GB` for the generic ViDoRe full extractor; a later dataset-specific calibration and human protocol amendment may approve another GPU without altering models or batch size. Pin Python, Modal, and all remote dependencies; record PyTorch, CUDA, driver, actual GPU name/VRAM, platform, model IDs and immutable revisions for BM25 implementation, BGE-M3, and ColQwen2.5. Record ViDoSeek, ViMDoc, and ViDoRe V3 identifiers, revisions, licenses, split hashes, file counts, and qrels checksums. Dataset verification is read-only; MMDocIR is outside the active scope.
**I/O CONTRACT:**
  Inputs: environment metadata [mapping] UTF-8 CPU — actual runtime; dataset files [N bytes] uint8 CPU — read-only; model revisions [3 strings] UTF-8 CPU — immutable IDs
  Outputs: environment manifest [mapping] JSON CPU — local and Modal sections with no null required fields; Modal probe [mapping] JSON CPU — App/run ID, image hash, actual GPU/VRAM, CUDA, driver, PyTorch, Volume; dataset manifest [3 records] JSON CPU — hashes and counts; dependency lock [text] UTF-8 CPU — fully pinned
  Side effects: authenticates to the approved Modal workspace, builds or pulls a Modal image, invokes a non-training environment probe, and writes configs/manifests/lock/tests; does not train or mutate datasets
**IMPLEMENTATION NOTES:**
  Local and Modal environments are separate manifest sections. The Modal default GPU request is exactly `L4`, approved by the human on 2026-08-25; the actual device must report at least 23.5 decimal GB and the manifest must record both decimal GB and binary GiB. Dataset acquisition runs in a separate CPU-only Modal Function and writes only to the persistent Volume; it must never download payloads locally. Mount caches and artifacts through the Volume and call `volume.commit()` after successful remote writes. Select the ViMDoc development sample by sorting unique query IDs on `SHA256(UTF8("20260820:<query_id>"))`, breaking digest ties by query ID, and taking the first 2,000. The sampler may read only the query ID; `doc_ids`, qrels, relevance counts, document length, and retrieval scores are forbidden. For ViMDoc confirmation, remove the final underscore segment from both page stems and raw ground-truth IDs, require every transformed qrels document to resolve to at least one page, hash the canonical binary document qrels, and freeze max-over-page document scoring with ascending page-ID tie handling. Do not drop the 362 unmatched raw page IDs or repeat document labels onto pages. The generic ViDoRe full extractor uses `A100-40GB`; ViDoSeek may use a separately approved dataset-specific GPU after measured calibration without weakening the 23.5 decimal-GB guard or silently changing batch size. Do not copy credentials into the image or repository. Do not describe the 2 GiB MX130 as training/extraction-capable. Dataset paths live in config or environment variables, never source code.
**VERIFICATION:**
  Command: `python -m pytest tests/test_environment_contract.py tests/test_modal_contract.py tests/test_dataset_contract.py -v; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; modal run --write-result artifacts/modal_environment_probe.json modal_app.py::environment_probe`
  Assertions:
    - All dependency versions and all three retriever model revisions are non-empty and immutable.
    - Modal probe reports requested GPU `L4`, CUDA available, actual GPU VRAM at least 23.5 decimal GB, both GB/GiB fields, and a non-empty App/run ID and image-definition hash; dataset manifest contains exactly the three approved datasets, every recorded SHA-256 has length 64, and every ViMDoc document qrel resolves to at least one archive page.
  Expected runtime: under 10 minutes excluding human-provided credentials or downloads
**STOP/KILL CONDITION:**
  HALT and report to the human if Modal authentication is unavailable, the pinned image cannot build, the Volume/Secrets do not resolve, no approved 24+ GiB Modal GPU exists, a model revision is mutable or unavailable, a dataset license forbids the planned use, any required dataset revision cannot be identified, or a qrels ID fails to resolve at the declared evaluation granularity. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P0-03
**TITLE:** Reproduce the baseline and validate the completed score bundle
**DEPENDENCIES:** P0-02
**FILES:** `artifacts/baseline_test_output.txt`, `data/raw_scores.parquet`, `data/cache/retrieval_scores.parquet`, `data/cache/candidate_audit.parquet`, `data/cache/coverage_report.json`, `artifacts/extraction_manifest.json`, `artifacts/_EXTRACTION_SUCCESS.json`, `artifacts/preflight.json`, `artifacts/baseline_metrics.json`, `artifacts/run_manifest.json`, `artifacts/artifact_manifest.json`, `artifacts/_SUCCESS.json`
**DESCRIPTION:**
  Run the original baseline test suite before adding new tests. Submit QPAF score extraction to Modal if a completed bundle does not already exist, import the resulting bundle from the persistent Volume, verify its extraction marker and hashes, then run the local non-training QPAF bundle finalizer. This task validates software behavior and data integrity; it must not claim a learned or oracle improvement.
**I/O CONTRACT:**
  Inputs: imported candidate rows [N,10] Parquet CPU — unique `(dataset,query_id,page_id)`, finite BM25/BGE/DSE/ColQwen scores, explicit candidate provenance; imported normalized scores [N,10] Parquet CPU — identical keys with deterministic branch ranks; extraction manifest and marker [mapping] JSON CPU — matching protocol and SHA-256 values
  Outputs: preserved baseline test log [text] CPU — 29 passes; coverage report [mapping] JSON CPU — overall and per-query; candidate-pool validation metrics [5 methods,4 metrics] float64 CPU — BM25/dense/visual/RRF/fixed, explicitly not full-corpus benchmark metrics; run manifest [mapping] JSON CPU — commit and data hashes; success bundle [10 artifacts] bytes CPU — matching manifest
  Side effects: may invoke `modal_app.py::extract_scores` on Modal; writes copied immutable data and artifact reports; does not train locally or change baseline source
**IMPLEMENTATION NOTES:**
  Run score extraction only on Modal. Finalize locally with `PYTHONPATH=src`. Reject duplicate keys, non-finite scores, missing channel provenance, mismatched hashes, invalid branch-rank permutations, `_EXTRACTION_SUCCESS.json` absence, or `_SUCCESS.json` absence. Candidate generation and normalization must not read qrels. The approved QPAF extractor intentionally does not produce HEAVEN `full_score`, Stage-2 costs, or `official_query_metrics.parquet`; do not fabricate them or route this candidate-only artifact into Budget-Aware HEAVEN reporting.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest -q; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python scripts/finalize_p0_03.py --root .`
  Assertions:
    - Original suite reports exactly 29 passed, 0 failed, 0 errors.
    - `_EXTRACTION_SUCCESS.json` matches the imported extraction manifest and all four remote payload hashes verify.
    - `_SUCCESS.json` and all ten local manifest artifacts verify; relevant-page coverage is at least 0.95 overall and no included query has zero relevant candidates.
  Expected runtime: tests under 10 seconds; preflight under 10 minutes for 1.2 million rows
**STOP/KILL CONDITION:**
  HALT and report to the human if `_SUCCESS.json` is absent, any artifact hash mismatches, the original suite is not exactly 29/29, or relevant-page coverage is below 0.95. This is not a retry condition. Do not attempt a workaround. Report and stop.

**PHASE 0 GATE:** P0-01–P0-03 are `PASS`; baseline is a clean immutable commit; original tests are 29/29; remote environment is declared; datasets and model revisions are frozen; the approved QPAF score bundle and ten local artifacts match their hashes; relevant-page coverage is at least 0.95. This gate does not imply that HEAVEN `full_score` or official full-corpus Budget-Aware metrics exist. Otherwise the project is `BLOCKED` and Phase 1 must not start.

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
**STATUS:** BLOCKED — accepted by the user under the frozen candidate protocol on 2026-08-30
**FILES:** `configs/datasets.yaml`, `configs/environment.yaml`, `configs/modal.yaml`, `modal_app.py`, `scripts/vidoseek_dataset.py`, `scripts/extract_vidore_baseline.py`, `scripts/audit_vidoseek_coverage.py`, `tests/test_vidoseek_extractor.py`, `tests/test_vidoseek_coverage_audit.py`, `tests/test_modal_contract.py`, `configs/pilot_w7.yaml`, `artifacts/vidoseek_score_extraction_calibration.json`, `artifacts/vidoseek_score_extraction_calibration_manifest.json`, `artifacts/vidoseek_score_extraction_full.json`, `artifacts/vidoseek_expanded_coverage_audit.json`, `artifacts/pilot_w7/qpaf_oracle_results.jsonl`, `artifacts/pilot_w7/qpaf_summary.json`, `artifacts/pilot_w7/qpaf_query_summary.parquet`, `artifacts/pilot_w7/qpaf_subgroups.csv`, `artifacts/pilot_w7/qpaf_oracle_gain.png`, `artifacts/pilot_w7/run_manifest.json`, `artifacts/pilot_w7/decision.md`
**DESCRIPTION:**
  Execute exhaustive W7 Global, query-level QARF, and candidate-level QPAF oracle analysis using the existing `run_qpaf_oracle`. This directly tests the cheapest-disproof hypothesis: whether page-level choice adds at least 0.03 discovery mean nDCG@10 over QARF with a positive query-bootstrap interval.
**I/O CONTRACT:**
  Inputs: validated score cache [N rows,3 channels] float64 CPU — coverage at least 0.95; relevance [N] float64 CPU — oracle use only; W7 [7,3] float64 CPU — simplex rows
  Outputs: per-query oracle rows [Q] JSONL CPU — Global/QARF/QPAF metrics and assignments; summary [mapping] JSON CPU — gain, CI, coverage, concentration; subgroup table [G,metrics] float64 CPU
  Side effects: writes a new immutable run directory; does not modify score cache or preregistered thresholds
**IMPLEMENTATION NOTES:**
  Seed bootstrap with 20260820 and use 10,000 resamples. Label every output `oracle_upper_bound`. QPAF $\ge$ QARF $\ge$ Global alone is not evidence because it follows from nested choice sets.
  The ViDoSeek adapter and bounded calibration entry point are prepared locally. The user approved native `pdftotext -layout` on 2026-08-29; this decision is frozen under `datasets[].discovery_extraction.protocol_approval`. After the measured calibration passed, the user approved L4 for full ViDoSeek extraction on 2026-08-29; this dataset-specific decision is frozen under `datasets[].discovery_extraction.full_extraction_gpu_approval`, while the generic ViDoRe extractor remains on A100. The full Function uses a ViDoSeek-only 86,400-second timeout, the Modal maximum, because the four-hour bound is not established for all 1,142 queries and every PDF page; stage caches and visual scores are committed incrementally. The human-run full command is: `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; modal run --write-result artifacts/vidoseek_score_extraction_full.json modal_app.py::extract_vidoseek_scores`. The preparation task does not execute this command.
  Measured L4 calibration evidence: function call `fc-01M16E91CTEN3YCAW0G1SSP5XX`, source commit `662dc335600fc21ac31fb8658ee0b991c3818774`, protocol `be7c5a4e761881fe92fb4cbf661d51586271385a3dea74d3a4d8feafac8e2a5e`, 10 queries, 128 pages, 353.251 seconds, 127/128 non-empty native-text pages, coverage 1.0, zero uncovered queries, and 7.720 GiB peak allocation on an NVIDIA L4 with 22.034 GiB. The returned manifest hash and all four downloaded artifact byte hashes match. This is calibration evidence only, not a P1-02 oracle result.
  The first full L4 attempt on 2026-08-30 stopped at the unchanged coverage gate under source commit `0cf48ce`: 1,142 queries, 5,385 pages, initial/final coverage 0.9973730297723292, three queries with zero relevant candidates, and `expanded_once=false`. No visual scoring, extraction manifest, or success marker was produced. The committed candidate audit was downloaded locally with SHA-256 `ade973204fc1bec1f17947343a6e77fc54dd163052a9b0f8041d08c97ba325c9`. Before any protocol amendment or GPU rerun, run the CPU-only persisted-score audit to determine whether the frozen expanded depths rescue all three queries.
  Measured CPU-only audit evidence: function call `fc-01M17BMSRGAZB51F6PYEYA1ECK`, source commit `8f61c30b5745874fda514979ed8bfebafe1ca7a9`, source protocol `072599c016f836637655485fc628a20c33f7284622fe808466fb7e6626714486`, and local audit SHA-256 `80bd3fa2f9368a395a51528b484f511ad0d4a4e6a33588c52f78c4ba16001d1e`. Frozen expansion from depths `(200,100,100)` to `(300,200,200)` raises coverage from 0.9973730297723292 to 0.999124343257443 and rescues two of three queries, but `027dee01b7aced677eb5093c754ebad82a89015d_1` remains uncovered. Decision: `expanded_depths_still_fail_existing_gate`; P1-02 is BLOCKED and another GPU extraction is forbidden until a separate candidate-pool protocol amendment is explicitly approved. Do not drop the query, inject its relevant page, weaken the zero-query gate, or select new depths from its observed relevance rank.
  On 2026-08-30 the user explicitly accepted: `Accept P1-02 BLOCKED under the frozen candidate protocol`. This closes P1-02 without a score bundle or W7 oracle run. P1-03 and all later tasks that depend on a P1-02 PASS remain blocked; no QPAF gain, confidence interval, subgroup result, or Phase 1 granularity decision may be reported.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m oracle_study.cli qpaf --scores data/vidoseek/cache/retrieval_scores.parquet --grids w7 --bootstrap 10000 --output-dir artifacts/pilot_w7; python -m pytest tests/test_qpaf.py tests/test_preregistration.py -v`
  Assertions:
    - W7 contains exactly 7 unique non-negative profiles and every row sums to one within $10^{-12}$.
    - Summary contains every query, 10,000 bootstrap resamples, finite metrics in $[0,1]$, and `delta_qpaf_vs_qarf` for every query.
  Expected runtime: under 30 minutes on CPU after caching
**STOP/KILL CONDITION:**
  HALT and report to the human if any qrels value enters score normalization/candidate construction, any query is missing from output, or mean QPAF-vs-QARF nDCG@10 is below 0.01. The last condition kills learned QPAF and selects the simpler QARF/static path. This is not a retry condition. Do not attempt a workaround. Report and stop.

### TASK-ID: P1-02R
**TITLE:** Verify the post-hoc all-corpus recovery score bundle
**DEPENDENCIES:** P1-01; user authorization on 2026-08-30 to prepare a local-only post-hoc draft after the accepted P1-02 block
**STATUS:** PASS — verified post-hoc recovery score artifact; the one execution authorization is consumed and closed; frozen P1-02 and P1-03 remain blocked
**FILES:** `configs/vidoseek_p1_02r.yaml`, `scripts/vidoseek_p1_02r.py`, `scripts/extract_vidoseek_p1_02r.py`, `tests/test_vidoseek_p1_02r.py`, `tests/test_vidoseek_p1_02r_full.py`, `modal_app.py`, `tests/test_modal_contract.py`, `artifacts/vidoseek_p1_02r_coverage_audit.json`, `artifacts/vidoseek_p1_02r_l4_cost_calibration.json`, `artifacts/vidoseek_p1_02r_score_extraction_full.json`, `artifacts/vidoseek_p1_02r_import/extraction_manifest.json`, `artifacts/vidoseek_p1_02r_import/_EXTRACTION_SUCCESS.json`, `artifacts/vidoseek_p1_02r_integrity_review.json`, `experiments/CHANGELOG.md`
**DESCRIPTION:**
  Preserve P1-02 as BLOCKED and define a separately versioned P1-02R candidate pool containing every prepared ViDoSeek corpus page for every query. This removes score-depth truncation without changing the dataset, preprocessing, retriever implementations/revisions, score definitions, qrels boundary, metrics, or zero-uncovered-query gate. This is post-hoc protocol preparation, not an experimental result.
**I/O CONTRACT:**
  Inputs: query IDs [Q] UTF-8 CPU and prepared-corpus page IDs [P] UTF-8 CPU — both non-empty and unique; no scores or qrels enter candidate construction
  Outputs: candidate page indices [Q,P] int64 CPU — each query receives indices `0..P-1` in prepared-corpus marker order; protocol [mapping] YAML CPU — the CPU audit, calibration, consumed human invocation, and closed execution state are frozen; audit [mapping] JSON CPU — coverage, missing relevant pairs, zero-covered queries, and provenance; calibration manifest [mapping] JSON — measured component timings, peak allocation, and an explicitly non-result projection; verified full-extraction score bundle [6,149,670 rows, four raw/normalized score columns] Parquet — written in 143 bounded query row groups; integrity review [mapping] JSON — imported byte/content hashes, schemas, row/key checks, normalization/rank checks, coverage, provenance, and scientific boundaries
  Side effects: one completed human-run chunked Modal Function invocation plus local evidence/guard recording; no coding-agent Modal invocation, retry, oracle analysis, P1-03 execution, frozen P1-02 relabel, or QPAF result claim
**IMPLEMENTATION NOTES:**
  The frozen ViDoSeek corpus implies 1,142 x 5,385 = 6,149,670 candidate pairs. This is about 9.06 times the measured frozen-expanded mean candidate count, so the prior L4 approval is not reused. Candidate rows must be frozen before qrels; qrels may enter only the subsequent coverage audit/evaluation. The CPU audit checks qrel-page membership against the prepared page-ID set in O(Q+P+R) memory instead of materializing all query-page tuples; it loads no score cache. The returned audit is a PASS: coverage 1.0, all 1,142 relevant pairs selected, zero missing pairs, zero uncovered queries, and `gpu_used=false`; its SHA-256 is `bbb947ca9b04bf291e94298516d8529888b677eee92e212dd8967fac413beca0`.
  The bounded L4 calibration returned `status=complete` from Function call `fc-01M18YTTTN7Y33Z8W0Z3ZQGY5J` under source commit `6fdbd99ebd349ff1a9ce950faf154d6518a4b8bb`: 8 queries x 512 pages = 4,096 all-corpus pairs, 588.160496293 seconds total, 8,288,322,048 bytes (7.719 GiB) peak allocation, and an engineering projection of 7,860.383886004963 seconds (2.183439968334712 L4-hours) for the full workload. The projection excludes queueing, retries/OOM backoff, BM25/BGE/DSE regeneration, output materialization, and price changes; it is not a result or monetary estimate. The exact returned artifact is `artifacts/vidoseek_p1_02r_l4_cost_calibration.json`, SHA-256 `b53d0e885e9e979f7dc85b4588cae70d305a7ad17da9d303abf0b278310b93af`.
  The user first authorized only local preparation with `Record the P1-02R L4 calibration result and prepare a memory-safe chunked full-extraction implementation locally. Do not execute Modal or GPU.` The prepared path is separate from frozen `run_extraction`: it validates and reuses the parent BM25/BGE-M3/DSE `[1142,5385]` caches, encodes ColQwen queries in chunks of at most 8 and pages in chunks of at most 512, retains the calibrated batch ceilings (query 8, passage 2, score 128), atomically commits resumable embedding and `[1142,<=512]` visual-score chunks, then streams final Parquet row groups in 8-query chunks. Preparation was checkpointed at `09aa4bad08fd5362a64537b506e48dca640cfb4e` with protocol SHA-256 `49e63f2b017fa66a43a3af4d6189a2ab218b61fff838270ebfab954f4933b421`. The user then approved exactly one human-run invocation with `Approve one human-run P1-02R chunked full-extraction invocation on Modal L4 using frozen limits query=8, page=512, visual batch=128. Update and commit only the execution guards and provenance. Do not execute Modal yourself, run P1-03, or relabel frozen P1-02`. The human-run command is `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; modal run --write-result artifacts\vidoseek_p1_02r_score_extraction_full.json modal_app.py::extract_vidoseek_p1_02r_scores`. The completed audit and calibration Functions remain closed. Do not change `INITIAL_DEPTHS`, `EXPANDED_DEPTHS`, `run_extraction`, or the frozen P1-02 records. P1-03 remains blocked unless a later human-approved task-graph amendment explicitly accepts a completed P1-02R run.
  The one authorized invocation completed as Function call `fc-01M19RE4SXMJ54M15049QSMXKA` under source commit `c7d84aaee0e9caab691a11bba377f4a87c6e059c` and executed protocol-config SHA-256 `cfbfcb24ae477a93b3d6a65b40022d688b8172babb2e8080f82363f73fdd8be2`. The imported manifest SHA-256 is `7600d3483d526710d2613a37f030daec71596b20ed73d9cebb3b1a1ad507b7b8`; all four payload byte hashes and both score-table logical-content hashes match. Streamed local checks passed for 6,149,670 unique aligned rows per score table, 1,142 queries, 5,385 pages per query, finite scores, exact min-max normalization, all four branch-rank permutations and page-ID tie-breaking, coverage 1.0, zero missing relevant pairs, and zero uncovered queries. The measured full runtime was 7,818.803704091 seconds on NVIDIA L4 with fixed query/page/visual limits 8/512/128. `full_score` was intentionally not produced. The invocation is consumed, the current execution guard is closed, and the historical command must not be rerun without new approval. This is a verified post-hoc recovery score artifact, not an oracle, learned, HEAVEN, or deployable QPAF result.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_vidoseek_p1_02r.py tests/test_vidoseek_p1_02r_full.py tests/test_modal_contract.py tests/test_vidoseek_coverage_audit.py tests/test_score_extractor.py -v`
  Assertions:
    - The protocol is `post_hoc` and `full_extraction_integrity_verified`; its immutable approval records exactly one human L4 invocation, its result consumes that invocation, and the current Modal/full-extraction/GPU flags are closed while the unchanged BM25/model definitions and fixed calibration/full-chunk limits remain locked.
    - The checked-in audit artifact matches its recorded byte hash, source commit, executed protocol hash, Function call ID, all-corpus shape, PASS decision, and zero-uncovered-query gate.
    - Candidate construction accepts only query/page IDs, returns every page for every query, and cannot accept scores or qrels.
    - The persisted CPU audit accepts only the frozen parent run, requires no score cache, reports coverage 1.0 when every qrel page exists in the prepared corpus, and keeps the unchanged gate red when a qrel page is absent.
    - The checked-in calibration artifact matches its byte hash, source/protocol/image identifiers, exact 8 x 512 sample, measured timings, peak allocation, L4 identity, sample-score-cache hash, non-result projection, and `full_extraction_started=false` boundary.
    - The receipt, imported manifest, success marker, and integrity review cross-match their recorded byte hashes, Function call, executed source/config, artifact set, row/content hashes, coverage, and scientific-scope boundaries without requiring the large Parquet payloads in Git.
    - The completed Modal audit, calibration, and full-extraction paths reject repeat execution in the current checkout; the fixed-argument L4 full Function checks the closed P1-02R protocol guard before importing Torch or loading models.
    - Query/page chunk coverage is contiguous and bounded at 8/512; synthetic streamed Parquet output exactly matches a full-table reference hash while using bounded row groups; cache checks permit restart without retaining the full embedding set or full row table.
    - Frozen P1-02 depth constants remain `(200,100,100)` and `(300,200,200)`.
  Expected runtime: under 1 minute on local CPU
**STOP/KILL CONDITION:**
  HALT on any new Modal/GPU invocation from this checkout, any retriever/config revision change, any required frozen parent score cache that is missing/non-finite/wrong-shaped, any use of qrels or observed relevance rank in candidate construction or score-chunk selection, or any change to the original P1-02 behavior. The historical L4 invocation used fixed query/page/visual limits 8/512/128 and is consumed; any retry or second invocation requires a new explicit approval and provenance patch. P1-02 remains BLOCKED, and P1-03 remains unauthorized.

### TASK-ID: P1-02R-O1
**TITLE:** Preregister P1-02R post-hoc W7 and prepare its pre-execution safeguards
**DEPENDENCIES:** P1-02R
**STATUS:** ONE CORRECTIVE REPLACEMENT HUMAN PROBE AUTHORIZED — prior invocation failed before project startup; replacement not yet executed
**FILES:** `configs/vidoseek_p1_02r_oracle_w7_v1.yaml`, `src/oracle_study/vidoseek_p1_02r_oracle.py`, `tests/test_vidoseek_p1_02r_oracle_protocol.py`, `tests/test_vidoseek_p1_02r_oracle_safeguards.py`, `Tasks.md`, `Context.md`, `experiments/CHANGELOG.md`
**DESCRIPTION:**
  Freeze a separately versioned, post-hoc W7 oracle-upper-bound protocol over the verified P1-02R all-corpus score bundle and prepare only the safeguards needed for a later execution decision. The safeguards are a protocol-bound, read-only input preflight; an atomic create-once run-manifest writer; and a separately guarded CPU-only performance-probe entry point. This task does not execute the probe or oracle and does not change the frozen P1-02/P1-03 task graph.
**I/O CONTRACT:**
  Inputs for a future separately approved run: the hash-pinned P1-02R `retrieval_scores.parquet` with 6,149,670 rows, 1,142 queries, 5,385 pages per query, coverage 1.0, and normalized BM25/dense/visual channels; qrels/relevance may enter only oracle selection and evaluation after candidates and scores are frozen.
  Outputs prepared now: the amended YAML protocol, safeguard module, and focused tests. Planned but not produced: a create-once consumed-attempt marker at `artifacts/vidoseek_p1_02r_oracle_w7_v1_probe/_ATTEMPTED.json`, one engineering-only probe manifest at `artifacts/vidoseek_p1_02r_oracle_w7_v1_probe/run_manifest.json`, and the still-unauthorized W7 oracle outputs under `artifacts/vidoseek_p1_02r_oracle_w7_v1/`.
  Side effects now: local corrective execution-guard/provenance/test/documentation changes and one corrective approval commit only; no attempt marker, probe manifest, oracle output, Modal/GPU allocation, P1-03 execution, learned-QPAF work, or frozen P1-02 relabel.
**IMPLEMENTATION NOTES:**
  Authorization text: `Approve creating and committing a separately versioned P1-02R post-hoc oracle/task-graph amendment using the verified local score bundle. Prepare the protocol and tests only. Do not execute oracle analysis, Modal/GPU work, or P1-03, and do not relabel frozen P1-02. Return the complete amendment diff and stop/go gates for review.`
  Safeguard-preparation authorization text: `Approve local preparation and commit of the P1-02R-O1 pre-execution safeguards: add a protocol-bound input preflight, an immutable run-manifest writer, and a bounded CPU performance-probe entry point with tests. Do not execute the performance probe or W7 oracle, do not write oracle results, do not run Modal/GPU or P1-03, and do not relabel P1-02. Return the complete diff, proposed probe limits, runtime stop condition, and exact future command for review.`
  One-probe execution-guard authorization text: `Approve preparing and committing the execution-guard/provenance amendment for exactly one human-run P1-02R-O1 bounded CPU performance probe from commit 024f2f0a0998f0c781ac738d259603c6bbf29ba9. Keep the fixed limits and no-retry rule. Do not execute the probe yourself, W7 oracle, Modal/GPU, or P1-03, and do not relabel P1-02.`
  That human invocation failed during CPython preinitialization before project import because the approved unquoted CMD assignment stored `PYTHONUTF8` as `1 ` rather than `1`. The original one-invocation authorization is consumed and cannot be retried. No `_ATTEMPTED.json`, input preflight, performance probe, manifest, or oracle result was produced.
  Corrective replacement authorization text: `Approve preparing and committing a corrective P1-02R-O1 execution-guard/provenance amendment for exactly one replacement human-run CPU performance-probe invocation. Record the prior invocation as failed before Python/project startup because the approved CMD used unquoted set assignments and set PYTHONUTF8 to 1 ; no attempt marker preflight, probe, manifest, or oracle result was produced. Replace the command with quoted CMD assignments, preserve all fixed limits and no-retry rules, and do not execute the probe yourself, W7 oracle, Modal/GPU, or P1-03, and do not relabel P1-02.`
  The protocol freezes the existing implementation rather than adding a runner: Global searches all seven W7 profiles once for the dataset, QARF searches all seven per query, and QPAF starts from QARF then performs fixed-order coordinate ascent for at most two sweeps. Candidate visits follow descending QARF score with ascending page-ID ties; only nDCG@10 improvements greater than `1e-12` are accepted. The three fusion channels are BM25, dense, and visual; `stage1_score` remains present for provenance but is not a fusion feature.
  The preflight verifies protocol/source hashes; all four pinned input byte counts and byte hashes; both Parquet schemas, row-group and row counts; manifest cross-links; and the integrity-review PASS/boundaries. It reads Parquet metadata but no relevance values, writes no report, and refuses an existing probe manifest or oracle output directory.
  The proposed performance probe is CPU-only W7 timing over fixed candidate-audit query indices `[0,570,1141]` and systematic page ladders `[128,256,512]`, one repetition, 100 bootstrap resamples, at most 1,536 rows per case, one sequential worker with one CPU thread, and deterministic synthetic relevance. It loads no actual relevance and persists only elapsed timings and provenance in a create-once engineering manifest; all scientific result fields are rejected.
  The corrective execution checkout must be one clean, non-merge direct child of failed approval commit `fd2f411214b4b47750ffe6488bb0b5b654b55f66`, and its changed paths must exactly match the seven-file guard/provenance allowlist. The replacement command uses quoted CMD assignments and atomically creates `_ATTEMPTED.json` before input preflight; that consumes the replacement authorization even if preflight or timing fails, so another attempt requires another new human approval.
  The prior under-30-minute estimate applied to the frozen shortlist, not the 5,385-page all-corpus pool. All-corpus runtime remains unmeasured, the full protocol-bound W7 runner remains absent, and `ready_for_execution_approval=false`.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; C:\Python313\python.exe -m pytest tests/test_vidoseek_p1_02r_oracle_protocol.py tests/test_vidoseek_p1_02r_oracle_safeguards.py tests/test_qpaf.py tests/test_preregistration.py -v`
  Assertions:
    - Only `performance_probe_allowed` and `performance_probe_output_write_allowed` are true; all full-oracle, Modal, GPU, P1-03, learned-QPAF, and general output-write flags remain false.
    - The failed original invocation is recorded as consumed with no generated marker/preflight/probe/manifest/result, and the separately approved replacement requires the exact corrective direct-child commit topology, changed-path allowlist, clean tracked checkout, quoted CMD assignments, fixed one-thread environment, and one-invocation approval provenance.
    - Fixture tests exercise exact byte/hash/schema/evidence preflight acceptance and tamper rejection without running W7 on the live bundle.
    - The attempt marker and manifest each create once and refuse overwrite; an existing attempt marker blocks retry, result fields remain forbidden, and a synthetic sleeping worker proves timeout termination.
    - The seven W7 profiles, score-channel order, two-sweep constrained QPAF semantics, source-file hashes, metric, tie-break, seed, resample count, and decision thresholds match the current implementation and preregistration.
    - P1-02 remains BLOCKED, P1-02R remains PASS, and P1-03 keeps dependency `P1-02` and status BLOCKED.
  Expected runtime: under 1 minute on local CPU; this runs tests only, not oracle analysis.
**STOP/GO GATES FOR REVIEW:**
  `GO-HUMAN-CORRECTIVE-REPLACEMENT-PROBE-ONCE`: after this corrective approval commit is reviewed, the human may run the exact quoted-assignment CMD command once. It creates the immutable attempt marker first, then performs the protocol-bound preflight and bounded synthetic-label timing ladder.
  `STOP-PROBE`: before compute on any protocol/source/approval/direct-parent/changed-path/checkout/thread/input mismatch; during execution, terminate an active case at 120 seconds or the overall ladder at 300 seconds. The replacement authorization remains consumed after any failure, no PASS manifest is written, and another attempt is forbidden without new approval. An existing attempt marker, manifest, or oracle-output path is also a hard stop.
  `GO-AFTER-PROBE`: a PASS engineering manifest permits only human review of runtime evidence. It never authorizes the full W7 oracle. Full W7 still requires a separate protocol-wrapper/resource-plan review and explicit approval.
  `STOP-LEARNED-QPAF` if a future approved W7 run has mean per-query QPAF-vs-QARF delta nDCG@10 `<0.01`; report and do not retry. `W66-REVIEW-ELIGIBLE` only if the mean is `>=0.03`, the query-bootstrap 95% lower bound is `>0`, and top-5%-gain share is `<0.90`; this permits only a human decision on a separate W66 protocol. All other outcomes are `REVISE-OR-STOP-AFTER-REVIEW`. W7 alone never authorizes P1-03 or Phase 2.
  Exact replacement human-run CMD command, authorized for one invocation only after review of the corrective approval commit: `set "OMP_NUM_THREADS=1" && set "MKL_NUM_THREADS=1" && set "OPENBLAS_NUM_THREADS=1" && set "NUMEXPR_NUM_THREADS=1" && set "PYTHONUTF8=1" && set "PYTHONIOENCODING=utf-8" && set "PYTHONPATH=src" && C:\Python313\python.exe -m oracle_study.vidoseek_p1_02r_oracle performance-probe --protocol configs\vidoseek_p1_02r_oracle_w7_v1.yaml`.
**STOP/KILL CONDITION:**
  HALT before execution on missing corrective approval/provenance, a checkout that is not the clean single direct child of `fd2f411214b4b47750ffe6488bb0b5b654b55f66`, changed-path drift, unquoted CMD assignment, any input byte/content hash, schema, row/query/page, or coverage mismatch, any source/profile/metric/seed/bootstrap/tie-break drift, any actual-relevance load for the probe, or an existing attempt/output path. Kill the active child process at 120 seconds or when the 300-second ladder budget is exhausted; the replacement authorization remains consumed, write no PASS manifest, and do not retry. Any attempted oracle-result persistence, full W7, Modal/GPU, P1-03, learned-QPAF execution, or P1-02 relabel remains a hard stop requiring a separate human decision.

### TASK-ID: P1-03
**TITLE:** Run W66 sensitivity and issue the Phase 1 granularity decision
**DEPENDENCIES:** P1-02
**STATUS:** BLOCKED — dependency P1-02 did not pass
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
  Command: `$env:PYTHONPATH='src'; python -m oracle_study.cli qpaf --scores data/vidoseek/cache/retrieval_scores.parquet --grids w66 --bootstrap 10000 --output-dir artifacts/pilot_w66; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python scripts/decide_granularity.py --w7 artifacts/pilot_w7/qpaf_summary.json --w66 artifacts/pilot_w66/qpaf_summary.json --output artifacts/phase1_decision.json; python -m pytest tests/test_granularity_decision.py -v`
  Assertions:
    - W66 has exactly 66 unique simplex profiles and W7/W66 use identical query IDs and data hashes.
    - `proceed_qpaf` requires mean QPAF-vs-QARF delta at least 0.03, bootstrap lower bound above 0 in both W7 and W66, and top-5%-gain share below 0.90.
  Expected runtime: under 4 hours on CPU after caching
**STOP/KILL CONDITION:**
  HALT and report to the human if the result is `stop`, query/data hashes differ across grids, or the decision file is produced after 2026-09-05 without an approved schedule update. If mean gain is between 0.01 and 0.03 or either CI crosses zero, mark `revise` and do not enter Phase 2. This is not a retry condition. Do not attempt a workaround. Report and stop.

**PHASE 1 GATE:** By 2026-09-05, W7 and W66 have identical data hashes; mean QPAF-vs-QARF discovery $\Delta\mathrm{nDCG@10}\ge0.03$ in both grids; both bootstrap lower bounds are $>0$; top-5%-gain share is $<0.90$; and P1-03 outputs `proceed_qpaf`. `revise` requires human approval for a new preregistration. `stop` kills learned QPAF.

**CURRENT PHASE 1 STATUS:** BLOCKED — P1-02 was accepted as BLOCKED under the frozen candidate protocol on 2026-08-30, so the Phase 1 gate was not evaluated and Phase 2 is not dependency-unblocked.

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
  Inputs: features [B,C,13] float32 device; scores [B,C,3] float32 device; evaluation relevance [B,U] float32 device; page-to-unit groups [B,C] int64 device; valid masks [B,C] and [B,U] bool device
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
  Inputs: train/validation page-score rows [N,3] float64 CPU; evaluation-unit relevance [Q,U] float64 CPU; page-to-unit mapping [N] string CPU; config [mapping] YAML CPU — seed, batch 32, AdamW, gradient clip 1.0
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
  Submit `LinearQPAFGate` training to Modal with page-specific Eq. 4–6 and the identical data, features, objective, optimizer, early-stopping rule, image, GPU class, and budget used by QARF. For ViMDoc, apply Eq. 6a–6b and compute loss/metrics on HEAVEN documents; for page-qrels datasets, use the identity evaluation mapping. Run seed 20260820 first for the Phase 2 gate; Phase 3 expands to three seeds. No optimizer step may run locally.
**I/O CONTRACT:**
  Inputs: confirmation train/validation batches with scores [B,C,3], features [B,C,13], page-to-document groups [B,C], document relevance [B,U], page mask [B,C], document mask [B,U]; config [mapping] YAML CPU
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
