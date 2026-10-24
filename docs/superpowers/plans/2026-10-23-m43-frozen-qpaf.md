# M4.3 Frozen QPAF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the G2-accepted seed-20260820 QPAF pilot as the main method, with a replayable record and a fresh-process reload check.

**Architecture:** `src/qpaf/m43/freeze.py` holds pure checks plus a `collect()` that replays G2, the M3.1 seal and both checkpoints by reusing `scripts/decide_g2.py`, `scripts/seal_m31_inputs.py` and `scripts/audit_m36_integrity.py`. `scripts/freeze_m43_qpaf.py` writes or verifies `evidence/revisions/m4.3-001/`. No training and no test labels.

**Tech Stack:** Python 3.13.7, Torch 2.11.0+cpu, NumPy 2.5.4, pandas 3.0.6, PyArrow 26.0.0, psutil, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-23-m43-frozen-qpaf-design.md`

## Global Constraints

- Only G2 `GO` with branch `continue_qpaf` may produce a freeze; other outcomes refuse.
- Reload tolerance `1e-7` for scores and weights; zero ranking disagreements; metric difference `<= 1e-12`.
- Outputs are create-once (`open('x')`), UTF-8, `indent=2`, `sort_keys=True`, `allow_nan=False`, final newline.
- Never deserialize `qrels_test_sealed.json`; never train; never write outside the output directory.
- Creation requires `git status --porcelain --untracked-files=no` to be empty and records `git rev-parse HEAD`.
- No Claude attribution in commits. Stage only explicit paths.

## Review Focus

- Pinned files edited after the freeze: `--verify` must refuse and name the pin.
- A G2 record replaced by a hand-edited `GO`: replay through `decide_g2.py` must disagree and refuse.
- Method source drift (for example `src/qpaf/m12/model.py`) while the checkpoint still loads: refuse on provenance mismatch.
- `--verify` run after later commits: `source_commit` must be an ancestor of `HEAD`, other fields must match exactly.
- Running creation twice: the second run refuses before any replay.

---

### Task 1: Pure freeze checks

**Files:**
- Create: `src/qpaf/m43/__init__.py`, `src/qpaf/m43/freeze.py`
- Test: `tests/test_m43_freeze.py`

**Interfaces:**
- Produces:
  - `class FreezeError(ValueError)`
  - `PINS: dict[str, tuple[str, str]]` (name → repository path, SHA-256), keys `g2_decision`, `g2_owner_confirmation`, `g2_inputs`, `g2_criteria`, `qarf_authorization`, `qpaf_authorization`, `m35_comparison`, `m36_integrity`
  - `METHOD_SOURCES: tuple[str, ...]` = m11 `artifacts.py`; m12 `config.py`, `features.py`, `losses.py`, `model.py`; m24 `checkpoint.py`, `config.py`, `dataset.py`, `evaluator.py`, `trainer.py`
  - `branch_disposition(decision: dict) -> dict`
  - `check_pins(root: Path, pins: dict) -> dict[str, str]`
  - `check_sources(root: Path, provenance: dict, paths: tuple) -> dict[str, str]`
  - `check_replay(worker: dict, *, tolerance: float = 1e-7) -> dict`
  - `compare_freeze(stored: dict, recomputed: dict, *, is_ancestor) -> None`

- [ ] **Step 1: Write failing tests**
  - `test_only_go_continue_qpaf_freezes`: `{'decision':'GO','m4_branch':'continue_qpaf'}` returns `frozen_qpaf='FROZEN'`, `revise_once='NOT_TRIGGERED'`, `negative_qpaf_result='NOT_TRIGGERED'`. `PARTIAL–INVESTIGATE`/`revise_once`, `NO-GO–PIVOT`/`negative_qpaf_result`, `BLOCKED`/`None` and `GO`/`revise_once` each raise `FreezeError`.
  - `test_pin_drift_names_the_file`: a temporary file under a wrong pin raises with its path in the message. A missing file also raises.
  - `test_source_drift_refuses`: a provenance entry with another hash, or a path missing from provenance, raises.
  - `test_replay_thresholds`: the passing worker (`status='PASS_FRESH_PROCESS'`, diffs `0.0`, `ranking_disagreements=0`, `metric_max_abs_difference=0.0`, `query_count=171`) returns the deterministic subset. Score diff `2e-7`, weight diff `2e-7`, one ranking disagreement, metric diff `1e-11`, a wrong status and `query_count=170` each raise.
  - `test_compare_freeze`: identical records pass. A changed nested value raises. A different `source_commit` passes only when `is_ancestor(old)` is true.

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/test_m43_freeze.py -q`. Expected: FAIL (module missing).

- [ ] **Step 3: Implement** the interfaces above. Use the pins below. `check_replay` returns only `query_count`, `candidate_count`, `score_max_abs_difference`, `weight_max_abs_difference`, `ranking_disagreements`, `metric_max_abs_difference`, `tolerance`. `compare_freeze` compares `json.dumps(sort_keys=True)` of both records with `source_commit` removed.

| Pin | Path | SHA-256 |
|---|---|---|
| g2_decision | `evidence/revisions/m3.7-001/decision.json` | `888c51d5c1f5309d80ec9f1218d935d4659512a5867b42b031f275196edad621` |
| g2_owner_confirmation | `evidence/revisions/m3.7-001/owner_confirmation.json` | `20e7fdde52b9ea995e83333ffb7d53606353f3714b6f00d2386e4789e4aa298c` |
| g2_inputs | `evidence/revisions/m3.7-001/inputs.json` | `42074ad0a7766923269f736b879401b96d1ad9a24bcc3621c42727bf7cb0dde6` |
| g2_criteria | `evidence/revisions/m3.7-001/criteria.json` | `6dac26ab7b8b54f8c3d7f7cddce598982df789f4691b0a30ea27ad8822d1128a` |
| qarf_authorization | `evidence/revisions/m3.2-001/authorization.json` | `ae51a3a5601d43b0a758d5feb69b74b4ba24b0413965e5fee96ed7015ede9b4b` |
| qpaf_authorization | `evidence/revisions/m3.4-001/authorization.json` | `4be026b852574e7687fdc4b9337f716aa96a64ac39556ae288193bdba99e5365` |
| m35_comparison | `evidence/revisions/m3.5-001/comparison.json` | `ac29ce5b1d691d8ecc8f8b46e665c726494885de3b73f84a82e8adf8979d0c57` |
| m36_integrity | `evidence/revisions/m3.6-001/integrity_review.json` | `497b934ce6222e6e4e70363ef374e88236b7592bb549b0c81bbb89b45291e66f` |

- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `src/qpaf/m43/__init__.py src/qpaf/m43/freeze.py tests/test_m43_freeze.py` with the message `feat(m4.3): add frozen QPAF checks`.

### Task 2: Collect, build and CLI

**Files:**
- Modify: `src/qpaf/m43/freeze.py`
- Create: `scripts/freeze_m43_qpaf.py`
- Test: `tests/test_m43_freeze.py`

**Interfaces:**
- Consumes: Task 1; `scripts.audit_m36_integrity.checked_run(method)` → `(auth, attempt, summary, success, count, steps)`; `check_fresh_process(worker, pid)`; `scripts.audit_m33_qarf.run_read_only(cmd) -> str`.
- Produces:
  - `collect(root: Path) -> tuple[dict, dict]`, returning `(freeze, verification)`
  - `create(root: Path, output_dir: Path) -> dict`
  - `verify(root: Path, output_dir: Path) -> dict`
  - CLI `--output-dir DIR | --verify DIR`, exit `0` on success, `2` on refusal with the message `M4.3 refused: …` on stderr.

- [ ] **Step 1: Write failing tests**
  - `test_create_refuses_existing_output_before_replay`: with `collect` patched to raise, `create(ROOT, existing_dir)` raises `FreezeError('…exists…')`, and `collect` is never called.
  - `test_real_freeze_record` (skipped when `results/m3.1/RUN-QPAF-M3_1-SEAL-001-20261021T142631Z-A01/inputs/score_cache.parquet` is absent): `collect(ROOT)` gives `freeze['branch_disposition']['m4_branch']=='continue_qpaf'`, `freeze['frozen_method']['checkpoint']['sha256']=='e4b00ab49e186fffe8b369e26491873304b61177c11fd2ce0f455158e30e5c8e'`, `selected_epoch==19`, `seed==20260820`, `freeze['matched_comparator']['checkpoint']['sha256']=='e44ac1a4f3887700a70914fdba8a3e7b35330244e746253d1cd828508be30914'`, both replays `score_max_abs_difference <= 1e-7`, and `freeze['test_labels_opened'] is False`.
  - `test_verify_refuses_tampered_record`: write the real record to a temporary directory, change `frozen_method.selected_epoch` and expect `FreezeError` (same skip rule).

- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `collect` pins first. It replays `decide_g2.py --inputs … --expected-inputs-sha256 … --criteria … --expected-criteria-sha256 …` with `run_read_only` and requires `json.loads(stdout) == decision.json`. It then replays `seal_m31_inputs.py --verify <run_path> --expected-manifest-sha256 <pin>` and requires `status=='PASS'` and `parity_identical`.
  - For `QPAF` and `QARF`, call `checked_run`, run `[sys.executable, scripts/audit_m36_integrity.py, '--replay-method', m]`, then `check_fresh_process` and `check_replay`. Also `check_sources` against that run's `provenance.json`.
  - Build `freeze` with these keys: `schema_version`, `task_id`, `owner`, `experiment_id='QPAF-M4_3-GAT-001'`, `experiment_class='governance'`, `evidence_class='governance_record'`, `status='FROZEN_TECHNICAL_PASS_PENDING_OWNER_CONFIRMATION'`, `g2`, `branch_disposition`, `frozen_method` (run_id, attempt, authorization_sha256, config file/resolved/provenance hashes, `frozen_values` from the authorization, checkpoint path/sha256/`selected_epoch`, `selection_rule`, `feature_names`, `parameter_count`, `seed`, `validation` metrics with `optimistic_same_split_selection=True`), `matched_comparator`, `sealed_inputs`, `source_sha256`, `reviews`, `replay` (Task 1 subsets), `seed_plan`, `downstream`, `claim_boundary`, `test_labels_opened=False`, `training_executed=False`, `authorizes_execution=False`, `source_commit`.
  - `verification` holds `checked_utc`, the full worker reports, the seal and G2 replay outputs, `runtime_versions()` and `freeze_sha256`.
  - `create` refuses an existing directory, then a dirty tracked tree, then writes `method_freeze.json` and `verification.json`.
  - `verify` re-collects and calls `compare_freeze` with `git merge-base --is-ancestor`.
- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest tests/test_m43_freeze.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `src/qpaf/m43/freeze.py scripts/freeze_m43_qpaf.py tests/test_m43_freeze.py` with the message `feat(m4.3): replay and record the frozen QPAF`.

### Task 3: Record the freeze revision

**Files:**
- Create: `evidence/revisions/m4.3-001/{method_freeze.json,verification.json,README.md,governance_events.jsonl}`

- [ ] **Step 1:** Stash only the user's `.gitignore` edit (`git stash push -- .gitignore`) so the tracked tree is clean. Run `.venv/Scripts/python.exe scripts/freeze_m43_qpaf.py --output-dir evidence/revisions/m4.3-001`, then `git stash pop`. Expected: `M4.3 frozen QPAF … continue_qpaf`.
- [ ] **Step 2:** Run `--verify evidence/revisions/m4.3-001`. Expected: PASS.
- [ ] **Step 3:** Write the README (scope, pins, replay numbers read from the files, claim boundary, replay command). Append event `QPAF-REG-<UTC date>-<next>` of type `METHOD_FREEZE_RECORDED`, status `PLANNED`, with `freeze_sha256`.
- [ ] **Step 4:** Run the focused suites (`tests/test_m43_freeze.py tests/test_m42_* tests/test_m41_confirmation_seal.py`) and the full suite in the background. Compare the failures with `results/m4.2/verification/active-primary-failed-nodeids.json`.
- [ ] **Step 5:** Commit the four evidence files with the message `docs(m4.3): record the frozen QPAF revision`.

### Task 4: Owner confirmation

- [ ] **Step 1:** Show the Research Lead the freeze numbers and ask them to confirm or not. Record their verbatim reply in `owner_confirmation.json` (`recorded_by` = Claude at their request, `freeze_sha256`). Append event `OWNER_CONFIRMATION_RECORDED`. Commit with the message `docs(m4.3): record the Research Lead's freeze confirmation`.
- [ ] **Step 2:** Write the untracked `MergeM4.3.md` (Vietnamese; sections Kết luận, Nội dung PR, Kết quả, Cảnh báo, Kiểm chứng, Bàn giao).
