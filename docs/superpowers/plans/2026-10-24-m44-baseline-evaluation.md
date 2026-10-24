# M4.4 Baseline Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate the seven deployable baselines, the frozen QPAF and the W7/W66 oracle context rows on the 171 ViDoSeek validation queries, then select the strongest baseline.

**Architecture:** `src/qpaf/m44/evaluation.py` (MTH run) and `src/qpaf/m44/oracle.py` (ORC run) share input checks in `src/qpaf/m44/common.py`. `scripts/run_m44_evaluation.py` provides `restore-inputs`, `execute` and `verify`. The frozen contract is `configs/m4.4/evaluation.json`. Runs are create-once under `results/m4.4/<run_id>/`. Governance lives in `evidence/revisions/m4.4-001/`.

**Tech Stack:** Python 3.13.7, Torch 2.11.0+cpu, NumPy 2.5.4, pandas 3.0.6, PyArrow 26.0.0, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-23-m44-baseline-evaluation-design.md`

## Global Constraints

- Validation only: the 171 IDs of `inputs/splits/val_ids.txt`. Never open `qrels_test_sealed.json`. Refuse if the development qrels contain a test ID.
- M4.2 bundle manifest pin `4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86`. M4.3 freeze pin `4015c74b54f5ac3d2cbce54f8424c0e9329c009595e81ced5eab0039af7761cc`.
- Roster `qpaf.m25.baselines.ROSTER`. Static weights come from the bundle `train_fit.json` (`[0.0, 0.1, 0.9]`). Co-strongest tolerance `1e-12`.
- Learned parity against the saved M3.2/M3.4 predictions `<= 1e-7` (`scripts.audit_m36_integrity.compare_predictions`).
- Paired statistics: `scripts.audit_m35_paired.paired_statistics`, 10,000 resamples, seed `20260820`, labeled single-seed exploratory.
- Oracle: `oracle_study.profiles.get_profiles('w7'|'w66')`, `oracle_study.qpaf._global_oracle` / `_query_oracle`, `scripts.qpaf_candidate_oracle_optimized.candidate_oracle_exact_fast`, all on `qpaf.m25.baselines._normalized` scores. Every row is re-scored by `qpaf.m24.evaluator.evaluate`.
- Torch runs on CPU in `float64` with 1 thread and deterministic algorithms. Wall-time caps: MTH `1800` s, ORC `3600` s (the synthetic probe measured about 376 s for both grids).
- JSON is written create-once with `sort_keys`, `indent=2` and a final newline. CSV.gz is written with `gzip.GzipFile(mtime=0, filename='')` and `repr(float)` cells.
- No Claude attribution. Stage only explicit paths.

## Review Focus

- A bundle file restored with wrong bytes: `restore-inputs` refuses and never overwrites.
- An authorization whose approval block is still empty or `PENDING`: `execute` refuses before `_ATTEMPTED.json`.
- An oracle row reaching selection: the selection input must be exactly the seven-row roster.
- A float lost in the CSV: reading `predictions.csv.gz` back gives bit-identical scores and metrics.
- A tracked tree that is dirty at execution: refuse (the user's `.gitignore` edit is stashed during execution).

---

### Task 1: Common inputs and contract

**Files:** Create `src/qpaf/m44/__init__.py`, `src/qpaf/m44/common.py`, `configs/m4.4/evaluation.json`, `scripts/run_m44_evaluation.py` (`restore-inputs` only); Test `tests/test_m44_evaluation.py`.

**Interfaces (Produces):**
- `class EvaluationError(ValueError)`; `require(ok, message)`; `sha(path)`; `write_json(path, data)`; `read(path)`
- `restore_inputs(root: Path, bundle: Path) -> list[str]`: copies the missing manifest files from `RESTORE_SOURCES` only on SHA match, using `open('xb')`.
- `validation_qrels(qrels: dict, splits: dict) -> dict`: exact validation IDs; raises on any test ID.
- `load_context(root: Path) -> dict` with keys `config`, `bundle`, `shared`, `splits`, `records` (validation `QueryRecord`s), `freeze`, `coverage`.
- `check_authorization(root, path, expected_sha256, experiment_id, run_id) -> dict`.
- `write_csv_gz(path, header: list[str], rows: Iterable[list]) -> None`; `read_csv_gz(path) -> list[dict]`.

- [ ] **Step 1: Tests**
  - `test_validation_qrels_refuses_test_ids`
  - `test_restore_refuses_wrong_bytes_and_never_overwrites`
  - `test_csv_gz_is_deterministic_and_lossless` (two writes give identical bytes; `float(cell)` round-trips)
  - `test_authorization_refusals`: empty approval text, `PENDING` approval, wrong pin, wrong commit, wrong run ID and an existing output each raise.
  - `test_real_context` (skips when the bundle is not restored): 171 records, coverage `1.0`, freeze checkpoint `e4b00ab4…`.
- [ ] **Step 2:** Run `.venv/Scripts/python.exe -m pytest tests/test_m44_evaluation.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Run `restore-inputs`, then `scripts/run_m42_active_primary.py --output <bundle> --verify --expected-manifest-sha256 4752eef3…`. Expected: `PASS`.
- [ ] **Step 4:** Tests PASS.
- [ ] **Step 5:** Commit with the message `feat(m4.4): add shared validation inputs and contract`.

### Task 2: MTH run (deployable table, QPAF, selection, paired)

**Files:** Create `src/qpaf/m44/evaluation.py`; extend the CLI and tests.

**Interfaces:** `method_predictions(context) -> dict[str, list[dict]]` (seven roster rows plus `qpaf`); `build_table(metrics: dict, per_query: dict) -> dict` with blocks `deployable`, `proposed_method`, `notes`; `selection(metrics, contracts) -> dict`; `paired(per_query) -> dict`; `execute_mth(root, authorization, expected_sha256, run_id) -> dict`; `verify_mth(root, run_dir, expected_manifest_sha256) -> dict` (re-hash, then recompute metrics, selection and paired from `predictions.csv.gz`).

- [ ] **Step 1: Tests**
  - `test_co_strongest_ties_and_qpaf_excluded`: two rows equal within `1e-12` are both selected; `qpaf` is never selected; a missing roster row raises.
  - `test_learned_parity_failure` raises at `2e-7`.
  - `test_table_blocks` checks the order and the `optimistic_same_split_selection` notes.
  - `test_paired_sign`: delta = qpaf − baseline.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit with the message `feat(m4.4): evaluate deployable baselines and frozen QPAF`.

### Task 3: ORC run

**Files:** Create `src/qpaf/m44/oracle.py`; extend the CLI and tests.

**Interfaces:** `oracle_scores(records, grid) -> dict[str, list[dict]]` (keys `oracle_global_<grid>`, `oracle_qarf_<grid>`, `oracle_qpaf_<grid>`); `execute_orc(...)`; `verify_orc(...)`.

- [ ] **Step 1: Tests**
  - `test_oracle_order_on_fixture`: per-query nDCG satisfies `qpaf >= qarf >= global`.
  - `test_oracle_metric_matches_m24`: equal within `1e-12` when coverage is full.
  - `test_oracle_rows_never_selectable`.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Commit with the message `feat(m4.4): add W7/W66 oracle context rows`.

### Task 4: Authorization, execution, verification

- [ ] Draft `evidence/revisions/m4.4-001/authorization.json` (status `DRAFT`, run_policy §3 fields, two experiments, source commit = HEAD after Task 3). Commit it.
- [ ] Ask the Research Lead to approve. Quote the reply verbatim into the approval block, commit, and append `AUTHORIZATION_RECORDED`.
- [ ] Stash `.gitignore`, run `execute --experiment MTH`, then `ORC`, then pop the stash. Append `STARTED` events.
- [ ] Run `verify` for both runs and save `post_run_verification.json`. Append `VERIFICATION_RECORDED`. Write the README with the three-block table. Commit the results and evidence.
- [ ] Run the full suite, compare against the base failures, and write `MergeM4.4.md`.
