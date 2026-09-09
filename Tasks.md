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
**TITLE:** Preregister P1-02R post-hoc W7, prepare its resumable CPU wrapper, and guard one calibration

Preparation update (2026-09-07): the separate 12-query exploratory runner and closed configuration are prepared for review in `docs/QPAF_EXPLORATORY12_EXECUTION_REVIEW.md`. Fixture tests and read-only preflight pass; no protocol adoption, live oracle run, phase decision, schedule change, or execution permission is recorded by this preparation. The original full-W7 source and guards remain unchanged.

Execution amendment (2026-09-07): after review of the exact 12-query pilot and explanation of no retry, the user replied, "So do it for me, I need to reach the goal to see the result as soon as possible". This adopts only the separately versioned exploratory-12 protocol and authorizes Codex to invoke it once on local CPU, one worker/thread, with a 21,600-second cap and no retry. Approval text, timestamp, reviewed config hash, source pins, and limits are recorded in `configs/vidoseek_w7_exploratory12_v1.json` and `runs/exploratory12_preparation_20260907/execution_approval.json`. This is an exploratory result-bearing side study, not a formal Phase 1 decision or schedule extension; full W7/W66, training, Modal/GPU, and frozen P1-02 remain unchanged. Invocation and result verification follow this approval.
**DEPENDENCIES:** P1-02R
**STATUS:** FULL-PAGE SYNTHETIC CALIBRATION PASS — verified 2026-09-06; the one human invocation is consumed; full W7 remains unauthorized
Recovery execution amendment (2026-09-07): after the exact one-run recovery request, the user replied "OK now continue". This authorizes Codex to reuse the four verified results and compute only the eight missing queries once, one CPU worker/thread, an additional 21,600-second cap, no automatic retry, followed by verification/reporting. Approval hashes are recorded in `runs/exploratory12_recovery_preparation_20260907/execution_approval.json`. The invocation launched at 10:02 UTC and is consumed. It completed at 11:42:29 UTC; all twelve results passed independent review and the chart passed visual inspection. See `docs/QPAF_EXPLORATORY12_RESULTS.md` and `docs/QPAF_EXPLORATORY12_RECOVERY_RUN_STATUS.md`. No formal phase decision exists.

Recovery closeout (2026-09-07): the separate case review reconstructed all 144 saved metrics and the relevant-page ranks 4/3/1 for audit query 797. Eleven other queries are at the Global nDCG@10 ceiling; the gain is exploratory and concentrated in one query. `docs/QPAF_QUERY797_CASE_STUDY.md` records the mechanism and `docs/QPAF_NEXT_EVALUATION_PROPOSAL.md` is a review-only draft. No new execution or phase dependency was opened. The preparation and interruption entries below are historical states superseded by this closeout.

Fixed-profile audit closeout (2026-09-08): the user approved one Codex local CPU invocation over all 1,142 frozen ViDoSeek discovery queries and 5,385 pages/query, seven fixed W7 profiles, one worker/thread, a 1,800-second cap and zero retries. The invocation completed in 561.485 seconds. Independent review passed 1,171 artifact hashes, 1,142 checkpoint envelopes and 32,012 recomputed metric values over all 6,149,670 raw pairs. Global/QARF mean nDCG@10 is 0.875138/0.908268; the mean theoretical QPAF-over-QARF headroom bound is 0.091732, so the result is `HEADROOM_POSSIBLE_REVIEW_COMPUTE`. This is not measured QPAF gain or a formal Phase 1 decision. All page-level search, W66, training, Modal/GPU, P1-03 and frozen P1-02 changes remain closed. See `docs/QPAF_FIXED_PROFILE_AUDIT_RESULTS.md`.

Exploratory-24 preparation (2026-09-08): after the user said “Continue” at the fixed-profile closeout, the predeclared representative fallback was made concrete without live search. The 24-query selection removes the original 12 audit indices, samples 24 sorted positions from the 1,130-query remainder with `random.Random(20260820)`, and has canonical query-list SHA-256 `95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b`. A separate guarded runner, closed config and 19 focused tests are prepared; the full suite passes 232. Read-only preflight passes on 129,240 selected pairs without loading relevance or consuming an attempt, and the closed run command refuses before writes. `docs/QPAF_EXPLORATORY24_EXECUTION_REVIEW.md` records the proposed one-worker/thread, 43,200-second, one-invocation, zero-retry contract. No page-level oracle, new metric, formal gate, training, Modal/GPU or P1-02/P1-03 change is authorized by this preparation.

Exploratory-24 closeout (2026-09-08): after review of the exact contract, the user replied “ok I approved”. The one Codex local CPU invocation completed all 24 queries and 129,240 query-page pairs in 8,700.394 seconds with one worker/thread, under the 43,200-second cap and with no retry. Independent verification passed 82 manifest artifacts, 50 checkpoint envelopes, 25 source snapshots, 960 raw ranking metrics and 415 aggregate comparisons. Mean nDCG@10 is Global 0.817634, QARF 0.853845 and QPAF 0.903856; QPAF-minus-QARF is 0.050011 with CI95 [0.008344, 0.101921], win/tie/loss 5/19/0 and top-5% gain share 0.666315. This clears exploratory W7 continuation signals but is not a formal Phase 1 decision. Full W7/W66, training, Modal/GPU, P1-03 and frozen P1-02 remain closed; every later execution still requires a separate explicit approval. See `docs/QPAF_EXPLORATORY24_RESULTS.md`.

Exploratory-24 W66 preparation (2026-09-08): after the user asked to continue, a separately versioned W66 sensitivity runner, closed config, synthetic tests and execution review were prepared for the exact same 24 query IDs and score bytes. The W66 grid has 66 unique simplex profiles with canonical SHA-256 `c04139858954fd0a7f7baa5dad548f3675a41b8682e9798039508e4077da5973`; the query-list SHA-256 remains `95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b`. The config approves zero seconds and zero invocations pending a separate resource review. No W66 attempt, metric, formal P1-03 decision, training, Modal/GPU action or frozen P1-02 change is authorized by this preparation. See `docs/QPAF_W66_EXPLORATORY24_EXECUTION_REVIEW.md`.

W66 resource-calibration preparation (2026-09-09): the resource review makes the full exploratory-24 W66 invocation a `NO-GO` pending measured controls; conditional scenarios span about 21.76--43.51 hours, with a 99.84-hour stress illustration, and are not approved timeouts. A separate closed synthetic calibration harness is prepared for audit index 1129: it materializes the frozen 24-query subset without decoding `relevance`, adds one deterministic synthetic label to the selected 5,385-page query, exercises one W66 search plus immutable replay, and measures the existing bootstrap functions. It adds single-thread Arrow/numeric verification, a parent/worker watchdog, one-second process-tree resource telemetry, bounded memory/disk/output guards and Windows sleep inhibition. The proposed cap is 21,600 seconds, but approved seconds and invocations remain zero. No calibration attempt, actual-label W66 result, formal P1-03 decision, training, Modal/GPU work or P1-02 change exists. See `docs/QPAF_W66_RESOURCE_BUDGET_REVIEW.md` and `docs/QPAF_W66_RESOURCE_CALIBRATION_EXECUTION_REVIEW.md`.

W66 resource-calibration interruption (2026-09-09): the user approved exactly one Codex synthetic calibration invocation under the six-hour/no-retry contract. The admitted attempt started from commit `90719a8cbbdf5cc8fe7c31020b3b60810c297b09` and is consumed. Independent monitoring found a 1,296.325-second telemetry gap aligned with Windows sleep reason `Button or Lid`, so the run was stopped fail-closed. All 29 source snapshots, thread limits, run-plan/Global checkpoints and hash chains validate, but no query checkpoint, calibration result or complete manifest exists. Partial timing is not a result and no retry is authorized. See `docs/QPAF_W66_RESOURCE_CALIBRATION_INTERRUPTION_REVIEW.md`. The next preparation is an exactly equivalent faster W66 candidate search plus a separate recovery protocol; any new execution requires explicit approval.

W66 resource-calibration recovery preparation (2026-09-09): added `candidate_oracle_exact_fast`, which reuses only candidate-invariant ranking state while preserving the frozen candidate/profile order, `1e-12` strict-improvement rule, two-sweep cap and output fields. Exact comparisons pass for W7/W66 random, tie-heavy, zero-relevance and bounded larger fixtures, plus complete query rows and immutable replay. A 512-page one-thread benchmark was exactly equal and measured 53.405 seconds frozen versus 1.471 seconds optimized (36.296x); its 162.764-second quadratic full-page illustration is conditional, not a measured runtime. The separate recovery protocol proposes one 3,600-second/no-retry invocation with fresh checkpoints, the existing CPU/memory/disk/output guards and a new five-second automatic wall/monotonic telemetry-gap abort. Live state remains closed with zero approved seconds/invocations and no recovery output. New explicit approval is required before execution.

W66 resource-calibration recovery result (2026-09-09): the user approved exactly one Codex invocation under the prepared 3,600-second/no-retry contract. It completed from commit `c94fb8e` in 70.611 seconds, with 62.575 seconds in the optimized full-page query search, 442,408,960-byte peak private memory, 487,694-byte maximum output and telemetry gaps below 1.08 seconds. Independent review verified 49 manifest hashes, 33 source snapshots, all four checkpoint envelopes, 129,240 non-label rows, one-thread pools and replay without candidate search. The synthetic query had zero updates and one sweep; 1,501.791-second one-sweep and 3,003.582-second doubled-search 24-query figures are conditional arithmetic only. The recovery attempt is consumed. Next prepare and test a separately versioned full exploratory-24 W66 runner that uses the exact-output optimized oracle, then conduct a separate timeout/execution review. No full W66 run, scientific result or later-phase execution is authorized.

Fixed-profile audit preparation (2026-09-07): the user replied "Ok keep continue please" to the explicit next step of implementation and tests. Prepared `scripts/audit_vidoseek_fixed_profiles.py`, `configs/vidoseek_fixed_profile_audit_v1.json`, and synthetic tests. Read-only preflight checks the existing 1,142-query, 5,385-page/query bundle without relevance values or retrieval metrics. The separate config keeps protocol adoption and execution false; its proposed one-worker/thread, 1,800-second, one-invocation, zero-retry scope is reviewable in `docs/QPAF_FIXED_PROFILE_AUDIT_EXECUTION_REVIEW.md`. No live attempt, QPAF coordinate search, full W7/W66 result, training, Modal/GPU, schedule amendment or phase-dependency change is authorized by this preparation. Verification evidence is under `artifacts/vidoseek_fixed_profile_audit_preparation/`.

Recovery preparation (2026-09-07): the separate launcher/config and fixture tests are implemented; focused tests passed 24 and the full suite passed 182. Read-only preflight passed. Both recovery approval flags remain false, no recovery output directory exists, and the original run/source/config bytes are unchanged. See `docs/QPAF_EXPLORATORY12_RECOVERY_EXECUTION_REVIEW.md` for the exact proposed new invocation and additional six-hour CPU budget. Only separate live execution approval remains before running; no formal gate or research conclusion changed.

Interruption review (2026-09-07, 09:34 UTC): the approved exploratory-12 attempt is no longer running. All 12 Global checkpoints and four complete QARF/QPAF query checkpoints passed hash/input/ranking-metric verification in `artifacts/vidoseek_exploratory12_interruption_review_20260907/checkpoint_integrity_review.json`. Eight query results and finalization remain missing; no complete manifest exists. The earlier Codex usage-limit termination preceded later checkpoints, so the experiment termination cause remains unknown. No live search or retry occurred during this review. Preserve the consumed attempt; `docs/QPAF_EXPLORATORY12_INTERRUPTION_HANDOFF.md` specifies the separate recovery preparation/approval boundary. Full W7/W66, training, and formal phase gates remain closed.

**CALIBRATION EVIDENCE (2026-09-06):** `artifacts/vidoseek_p1_02r_full_page_calibration_review.json` verifies the immutable marker and manifest imported into `artifacts/vidoseek_p1_02r_oracle_w7_v1_full_page_calibration/`. Worker time was 752.7996488000001 seconds for query index 570 and 5,385 pages. No actual relevance, scientific W7 result, Modal/GPU, or learned result was produced by that calibration. The executed YAML remains the hash-pinned historical approval snapshot; its pre-run counter is superseded operationally by the create-once attempt marker (one consumed, zero remaining) in both checkouts. Do not rerun. See `docs/QPAF_CALIBRATION_REVIEW_AND_NEXT_STEP.md` for the historical resource review and proposal; the later pilot approval and interruption are recorded above.
**FILES:** `.gitattributes`, `.gitignore`, `artifacts/vidoseek_p1_02r_oracle_w7_v1_probe/_ATTEMPTED.json`, `artifacts/vidoseek_p1_02r_oracle_w7_v1_probe/run_manifest.json`, `configs/vidoseek_p1_02r_oracle_w7_v1.yaml`, `src/oracle_study/vidoseek_p1_02r_oracle.py`, `src/oracle_study/vidoseek_p1_02r_sharded.py`, `tests/test_vidoseek_p1_02r_oracle_protocol.py`, `tests/test_vidoseek_p1_02r_oracle_safeguards.py`, `tests/test_vidoseek_p1_02r_oracle_sharded.py`, `Tasks.md`, `Context.md`, `experiments/CHANGELOG.md`
**DESCRIPTION:**
  Freeze a separately versioned, post-hoc W7 oracle-upper-bound protocol over the verified P1-02R all-corpus score bundle. The safeguards are a protocol-bound, read-only input preflight; immutable evidence writers; separately guarded CPU-only calibration/oracle entry points; and a two-pass query-sharded wrapper that checkpoints every query and resumes only after exact identity/content-hash validation. One bounded probe was executed by the human and is recorded as an engineering non-result. The local review-hardening patch makes its recorded-state CLI preflight usable, enforces exact live Git provenance in both future execution guards, and covers the calibration lifecycle on temporary seven-page synthetic fixtures. Exactly one human-run full-page synthetic calibration is now authorized behind commit-bound guards, but it was not executed by this amendment; live W7 remains unauthorized and the frozen P1-02/P1-03 task graph is unchanged.
**I/O CONTRACT:**
  Inputs for a future separately approved run: the hash-pinned P1-02R `retrieval_scores.parquet` with 6,149,670 rows, 1,142 queries, 5,385 pages per query, coverage 1.0, and normalized BM25/dense/visual channels; qrels/relevance may enter only oracle selection and evaluation after candidates and scores are frozen.
  Outputs recorded now: immutable attempt marker `artifacts/vidoseek_p1_02r_oracle_w7_v1_probe/_ATTEMPTED.json` (908 bytes, SHA-256 `f394faa42c3ac324e4378bde332a01794848780248b86cda12ccf8bc7fc61ace`) and engineering run manifest `artifacts/vidoseek_p1_02r_oracle_w7_v1_probe/run_manifest.json` (2,894 bytes, SHA-256 `2b030610ad7f8fb261799aa1d972ae47ee86724ea536eb4f317e6c2d71704549`). Planned but not produced: W7 oracle outputs under `artifacts/vidoseek_p1_02r_oracle_w7_v1/`.
  Side effects now: local guard/provenance/protocol/task-state/test preparation only. Fixture tests write only under pytest temporary directories. This amendment creates no live checkpoint directory, calibration attempt/manifest, probe retry, oracle output, Modal/GPU allocation, P1-03/P1-03R execution, learned-QPAF work, or frozen P1-02 relabel. After this exact approval commit, only the separately recorded one-invocation human calibration command may create its immutable attempt marker and engineering manifest.
**IMPLEMENTATION NOTES:**
  Authorization text: `Approve creating and committing a separately versioned P1-02R post-hoc oracle/task-graph amendment using the verified local score bundle. Prepare the protocol and tests only. Do not execute oracle analysis, Modal/GPU work, or P1-03, and do not relabel frozen P1-02. Return the complete amendment diff and stop/go gates for review.`
  Safeguard-preparation authorization text: `Approve local preparation and commit of the P1-02R-O1 pre-execution safeguards: add a protocol-bound input preflight, an immutable run-manifest writer, and a bounded CPU performance-probe entry point with tests. Do not execute the performance probe or W7 oracle, do not write oracle results, do not run Modal/GPU or P1-03, and do not relabel P1-02. Return the complete diff, proposed probe limits, runtime stop condition, and exact future command for review.`
  One-probe execution-guard authorization text: `Approve preparing and committing the execution-guard/provenance amendment for exactly one human-run P1-02R-O1 bounded CPU performance probe from commit 024f2f0a0998f0c781ac738d259603c6bbf29ba9. Keep the fixed limits and no-retry rule. Do not execute the probe yourself, W7 oracle, Modal/GPU, or P1-03, and do not relabel P1-02.`
  That human invocation failed during CPython preinitialization before project import because the approved unquoted CMD assignment stored `PYTHONUTF8` as `1 ` rather than `1`. The original one-invocation authorization is consumed and cannot be retried. No `_ATTEMPTED.json`, input preflight, performance probe, manifest, or oracle result was produced.
  Corrective replacement authorization text: `Approve preparing and committing a corrective P1-02R-O1 execution-guard/provenance amendment for exactly one replacement human-run CPU performance-probe invocation. Record the prior invocation as failed before Python/project startup because the approved CMD used unquoted set assignments and set PYTHONUTF8 to 1 ; no attempt marker preflight, probe, manifest, or oracle result was produced. Replace the command with quoted CMD assignments, preserve all fixed limits and no-retry rules, and do not execute the probe yourself, W7 oracle, Modal/GPU, or P1-03, and do not relabel P1-02.`
  PASS-recording authorization text: `Approve preparing and committing the P1-02R-O1 bounded CPU performance-probe PASS recording using the existing immutable attempt marker and run manifest. Close the consumed probe authorization, update only provenance, task state, protocol, and tests, and return a review-only full-W7 runtime/resource recommendation. Do not execute or authorize W7, Modal/GPU, P1-03/P1-03R, learned QPAF, or relabel P1-02`
  Sharded-wrapper preparation authorization text: `Approve local preparation and commit of a query-sharded, resumable CPU wrapper for P1-02R-O1 with exact-semantic equivalence tests against the frozen monolithic W7 implementation. Preparation only: do not run the full-page calibration or W7 oracle, do not write live oracle results, do not run Modal/GPU, P1-03/P1-03R, or learned QPAF, and do not relabel P1-02. Keep all current input hashes, W7 profiles, metrics, tie-breaks, seed, bootstrap semantics,and execution guards unchanged. Return the complete allowlisted diff, tests, checkpoint/resume contract, proposedone-query calibration command, and stop/go gates for review.`
  Review-hardening authorization text: `Go ahead with a local-only P1-02R-O1 review-hardening patch and commit it using an explicit allowlist. Fix the recorded-state CLI preflight, add Git provenance enforcement for future calibration/full-W7 guards, and add synthetic end-to-end calibration tests. Do not run calibration, W7, Modal/GPU, P1-03/P1-03R, or learned QPAF, and do not relabel P1-02.`
  Full-page calibration authorization text: `Approve local preparation and commit of the guard/provenance amendment for exactly one human-run P1-02R-O1 full-page synthetic calibration from parent commit 9821d100a4d64d73e8772f48f68f30388f851c06, using query index 570, 5,385 pages, 100 resamples, one CPU worker/thread, a 2,700-second hard stop, and no retry. Use an explicit commit allowlist. Do not execute the calibration, W7, Modal/GPU, P1-03/P1-03R, or learned QPAF, and keep P1-02 BLOCKED`
  The protocol and wrapper preserve the existing implementation semantics: Global searches all seven W7 profiles once for the dataset, QARF searches all seven per query, and QPAF starts from QARF then performs fixed-order coordinate ascent for at most two sweeps. Candidate visits follow descending QARF score with ascending page-ID ties; only nDCG@10 improvements greater than `1e-12` are accepted. The three fusion channels are BM25, dense, and visual; `stage1_score` remains present for provenance but is not a fusion feature.
  The preflight verifies protocol/source hashes; all four pinned input byte counts and byte hashes; both Parquet schemas, row-group and row counts; manifest cross-links; and the integrity-review PASS/boundaries. It reads Parquet metadata but no relevance values and writes no report. The CLI accepts the existing probe marker/manifest only for a recorded, sharded-prepared, or calibration-approved state and only after their exact immutable evidence contracts validate; other callers remain fail-closed by default.
  The recorded performance probe used fixed candidate-audit query indices `[0,570,1141]` and page ladders `[128,256,512]`, one repetition, 100 bootstrap resamples, at most 1,536 rows per case, one sequential worker with one CPU thread, and deterministic synthetic relevance. The three cases completed in `0.6704216001089662`, `3.7113504000008106`, and `13.628036600071937` seconds. It loaded no actual relevance and produced no scientific result.
  The corrective execution checkout was commit `aebeef11d5964b9c45ea56242f41ad4202aec95c`, a clean non-merge direct child of `fd2f411214b4b47750ffe6488bb0b5b654b55f66`. Its create-once marker consumed the sole replacement authorization. All probe execution/output guards are now false, and any retry requires a new task-graph/provenance amendment rather than reuse of this approval.
  Full-corpus W7 runtime remains unmeasured. Scaling the recorded timings linearly across 1,142 queries and empirically across 5,385 pages gives a derived single-worker range of 4.97–20.02 days; the three-point power fit is 10.68 days and an explicit quadratic-log model is 9.15 days. These estimates exclude 10,000-resample full-bootstrap overhead, full input/output materialization, process/checkpoint overhead, host contention, and thermal throttling. The current monolithic single-worker full W7 is therefore `NO-GO`; this is review input, not execution authorization.
  The prepared wrapper leaves `src/oracle_study/qpaf.py` byte-for-byte unchanged. Pass 1 streams the 143 Parquet row groups in frozen candidate-audit query order, stores one hash-sealed seven-profile metric checkpoint per query, and reduces all 1,142 queries before freezing the shared Global profile. Pass 2 rereads the same bounded row groups, runs the unchanged QARF/QPAF primitives one query at a time, and stores one hash-sealed result checkpoint per query. Finalization requires the exact 1,142-file inventories in both phases, restores canonical query order, and runs the seed-20260820/10,000-resample bootstrap exactly once. Existing checkpoints are reused only when the run-plan identity, self-hash, query identity, and input-query hash all match. An absent expected checkpoint is computed once in its canonical pass; an invalid existing checkpoint, unexpected file, or incomplete post-pass inventory fails closed and is never overwritten.
  Exact-semantic fixture tests compare the sharded wrapper with the untouched monolithic `run_qpaf_oracle(..., grids=("w7",))`: result rows, shared Global/QARF/QPAF profiles, candidate assignments/changed pages, summary, bootstrap interval, and subgroup frame match exactly. Resume tests prove a second run reuses every byte without overwrite and that one absent expected checkpoint in either phase is the only file recomputed; tamper, run-identity drift, and unexpected-checkpoint tests fail closed.
  The approved engineering calibration is fixed at candidate-audit query index 570, all 5,385 pages, the same synthetic first-and-middle-page binary relevance rule, 100 bootstrap resamples, one CPU worker/thread, a 2,700-second hard stop, and no retry. Its quoted-CMD command is enabled only for one human invocation from the exact approval commit. This amendment did not create its attempt marker or manifest.
  This calibration approval and any future full-W7 approval must record `approved_parent_commit`, `execution_commit_rule: single_non_merge_direct_child_with_exact_changed_paths`, and an exact `approval_commit_changed_paths` list. Before any work or live write, the shared guard verifies that `HEAD` is the single non-merge child of that parent, that its committed changed paths match exactly, and that tracked status is clean.
**VERIFICATION:**
  Command: `$env:PYTHONPATH='src'; C:\Python313\python.exe -m pytest tests/test_vidoseek_p1_02r_oracle_protocol.py tests/test_vidoseek_p1_02r_oracle_safeguards.py tests/test_vidoseek_p1_02r_oracle_sharded.py tests/test_qpaf.py tests/test_preregistration.py -v`
  Assertions:
    - Only `full_page_calibration_allowed`, `full_page_calibration_output_write_allowed`, and `checkpoint_writes_allowed` are true for the one human calibration. Performance-probe, full-W7, general oracle/output, Modal/GPU, P1-03, and learned-QPAF flags remain false; the consumed replacement probe has zero remaining invocations.
    - The failed original invocation remains recorded separately, and the replacement PASS marker/manifest byte counts, SHA-256 hashes, protocol/source cross-links, timings, and non-result boundaries validate exactly.
    - Fixture tests exercise exact byte/hash/schema/evidence preflight acceptance and tamper rejection without running W7 on the live bundle.
    - The attempt marker and manifest each create once and refuse overwrite; an existing attempt marker blocks retry, result fields remain forbidden, and a synthetic sleeping worker proves timeout termination.
    - The seven W7 profiles, score-channel order, two-sweep constrained QPAF semantics, source-file hashes, metric, tie-break, seed, resample count, decision thresholds, and review-only runtime derivation match the implementation and preregistration.
    - The two-pass sharded wrapper is exactly equivalent to the untouched monolithic W7 implementation on deterministic fixtures, preserves the one shared dataset-level Global profile, bootstraps only after canonical merge, and rejects checkpoint tampering, identity drift, or unexpected inventory without overwrite.
    - The full-page calibration command uses quoted CMD syntax and is authorized for exactly one human invocation; its approved parent, non-merge-child rule, seven-path commit allowlist, fixed limits, unconsumed count, and no-retry rule validate exactly. Full W7, general oracle/output, Modal/GPU, P1-03, and learned-QPAF execution remain unauthorized.
    - Synthetic seven-page end-to-end calibration tests prove marker creation precedes preflight, success writes only an immutable engineering manifest, failed preflight and timeout write no manifest, timeout closes its queue, synthetic relevance excludes live labels, and every consumed attempt refuses retry.
    - The recorded-state CLI preflight passes read-only, while both future calibration/full-W7 approval guards require an exact Git parent, non-merge child, changed-path allowlist, and clean tracked checkout.
    - P1-02 remains BLOCKED, P1-02R remains PASS, and P1-03 keeps dependency `P1-02` and status BLOCKED.
  Expected runtime: under 1 minute on local CPU; this runs tests only, not oracle analysis.
**STOP/GO GATES FOR REVIEW:**
  `PASS-RECORDED-CLOSED`: accept the two immutable engineering evidence files and the derived runtime/resource review; this closes the consumed probe authorization without changing any scientific task state.
  `STOP-PROBE-RETRY`: the existing attempt marker and zero remaining invocations forbid every repeat probe command. No probe command is authorized by this record.
  `NO-GO-CURRENT-FULL-W7`: do not execute the current monolithic single-worker implementation because its derived runtime is approximately 5–20 days before excluded overheads.
  `WRAPPER-PREPARED-REVIEW`: accept only if source hashes, exact-equivalence tests, checkpoint/resume tests, focused/full test suites, formatting/lint, and the complete allowlisted diff pass. This is preparation evidence, not runtime or scientific evidence.
  `CALIBRATION-AUTHORIZED-HUMAN-ONLY`: the exact approval commit opens one full-page/single-query synthetic calibration at fixed query index 570 with one worker/thread, a 45-minute hard stop, and no retry. Codex did not execute it; the create-once attempt marker consumes the authorization before preflight.
  `STOP-CALIBRATION`: stop without retry if the calibration attempt marker already exists, any frozen source/input/semantic hash differs, the wrapper checkpoint contract fails, or the calibration exceeds 2,700 seconds. A failed attempt remains consumed and requires review, not an automatic replacement.
  `STOP-FULL-W7`: even a successful calibration does not authorize full W7. A separate reviewed resource plan and separate human execution approval are required; P1-03/P1-03R remain blocked.
  `STOP-LEARNED-QPAF` if a future approved W7 run has mean per-query QPAF-vs-QARF delta nDCG@10 `<0.01`; report and do not retry. `W66-REVIEW-ELIGIBLE` only if the mean is `>=0.03`, the query-bootstrap 95% lower bound is `>0`, and top-5%-gain share is `<0.90`; this permits only a human decision on a separate W66 protocol. All other outcomes are `REVISE-OR-STOP-AFTER-REVIEW`. W7 alone never authorizes P1-03 or Phase 2.
**STOP/KILL CONDITION:**
  HALT on any probe retry; any calibration invocation except the one exact human-run command from the clean allowlisted approval commit; any calibration retry after its create-once attempt marker; live W7/oracle-result write; Modal/GPU action; P1-03/P1-03R or learned-QPAF work; frozen P1-02 relabel; checkpoint identity/content/inventory mismatch; or use of the derived runtime estimate as if it were a full-corpus measurement. Every later execution step requires a separate explicit human-approved amendment.

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
