# M4.6 revise_once Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record the M4.6 `revise_once` decision, propose amendment A004 (ΔnDCG@10-weighted pairwise loss), implement that loss and a matched v2 trainer without touching M4.3-pinned sources, and run the preregistered train-only alignment gate. No training run.

**Architecture:** New package `src/qpaf/m46/` (loss, config, trainer, probe, direction record) that reuses `qpaf.m24`/`qpaf.m12` unchanged. Thin CLIs in `scripts/`. Evidence in `evidence/revisions/m4.6-001/` and a create-once A004 file beside A003.

**Tech Stack:** Python 3.13.7, Torch 2.11.0+cpu (float64, 1 thread, deterministic), NumPy, `unittest`. Always run with `.venv/Scripts/python.exe -X utf8`.

**Spec:** `docs/superpowers/specs/2026-10-24-m46-revise-once-design.md`

## Global Constraints

- Do not edit any file in the M4.3 `source_sha256` list (`src/qpaf/m11/artifacts.py`, `src/qpaf/m12/{config,features,losses,model}.py`, `src/qpaf/m24/{checkpoint,config,dataset,evaluator,trainer}.py`). `scripts/freeze_m43_qpaf.py --verify evidence/revisions/m4.3-001` must still print `"status": "PASS"`.
- Never deserialize test or confirmation qrels. The probe reads only `train` records via `build_records(..., roles=('train',))`.
- No training run, Modal or GPU. QARF-v2/QPAF-v2 runs need a later authorization.
- Loss name `lambda_pairwise_logistic`, reduction `query_mean`, `metric_cutoff = 10`, `σ = 1`. All other config values equal `results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/inputs/shared_base.toml`.
- Gate thresholds: G-A Spearman(loss, train nDCG@10) `<= -0.5`; G-B min-loss grid point train nDCG@10 `>=` grid max `- 0.01`. One loss candidate only.
- Evidence JSON uses `qpaf.m43.freeze.serialize` bytes (sorted keys, indent 2, UTF-8, final newline) and is create-once (`open('xb')`).
- Owner text is quoted verbatim, never composed: `I confirm to proceed on revise_once cause it potentially lead to better results`, `confirmed_at_utc` `2026-10-24T09:02:43Z` (time Claude read the reply).
- No Claude attribution lines in commits. Do not stage `.gitignore`, `AGENTS.md` or `MergeM*.md`.
- Governance events: class `governance` / `governance_record`, experiment `QPAF-M4_6-GAT-001`, IDs continue after `QPAF-REG-20261024-0001` in recording-date order (`-0002`, `-0003`, …), field style of `evidence/revisions/m4.5-001/governance_events.jsonl`.

## Review Focus

- Tied fused scores: positions must follow `qpaf.m24.evaluator.rank` (score desc, page ID asc), or the loss weights disagree with the reported metric.
- Padded batch columns: masked candidates must get no weight and no gradient.
- Queries with fewer than 11 candidates: the discount beyond the list end must not index out of range.
- A v2 config with any non-loss field changed must still be refused by the M2.4 rules.
- Rerunning a create step over an existing `m4.6-001` file must refuse, not overwrite.

---

### Task 1: A004 amendment record (identity before implementation)

**Files:**
- Create: `evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A004.md`

**Interfaces:**
- Produces: the A004 path, pinned by Task 5.

- [ ] **Step 1: Hash the identity files on the current HEAD** (spec commit `8c9c9e5`): `src/qpaf/m12/losses.py`, `src/qpaf/m24/config.py`, `src/qpaf/m24/trainer.py`, `results/m4.2/.../inputs/shared_base.toml`, `evidence/M1_FINAL/02_protocol/amendments_after_import.md` (A001 row), and the spec.
- [ ] **Step 2: Write the file in the A003 layout.** Header status `PROPOSED / RESEARCH_LEAD_APPROVAL_PENDING / INDEPENDENT_REVIEW_PENDING`. Sections: 1 identity table (Step 1 hashes and HEAD); 2 old → new (`pairwise_logistic`/`query_mean` → `lambda_pairwise_logistic`/`query_mean`/`metric_cutoff 10`, formula from the spec); 3 necessity (probe numbers from the spec, why no-change and listwise are rejected); 4 impact (no leakage: weights use train labels only during training; matched: applied identically to QARF and QPAF; statistics unchanged; claim: post hoc, disclosed); 5 affected runs (M3.2/M3.4 stay valid as v1; new namespaces `QPAF-M4_6-MTH-001/002`; v1 frozen record untouched); 6 approvals (Research Lead: blank, pending their own words; reviewer Thanh: pending). Do not write any approval text.
- [ ] **Step 3: Commit**

```bash
git add evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A004.md
git commit -m "docs(m4.6): propose amendment A004 before implementation"
```

### Task 2: ΔnDCG@10-weighted pairwise loss

**Files:**
- Create: `src/qpaf/m46/__init__.py`, `src/qpaf/m46/losses.py`
- Test: `tests/test_m46_losses.py`

**Interfaces:**
- Consumes: `qpaf.m12.losses.PairwiseLoss`, `qpaf.m12.features.validate_mask`, `qpaf.m24.evaluator.rank`.
- Produces: `discounts(page_ids: list[str], scores: list[float], cutoff: int = 10) -> list[float]` (per candidate, input order) and `lambda_pairwise_logistic_loss(scores: Tensor[B,N], labels: Tensor[B,N], mask: BoolTensor[B,N], page_ids: list[list[str]], cutoff: int = 10) -> PairwiseLoss`.

Note: the spec divides by IDCG; IDCG is constant per query and cancels in `Σ w·softplus / Σ w`, so `relevant_total` is not an input. Say so in the module docstring.

- [ ] **Step 1: Write the failing tests**

```python
D = [1/math.log2(p+2) for p in range(4)]  # positions 0..3

def test_hand_computed_loss(self):
    s = torch.tensor([[0.9, 0.8, 0.1, 0.0]], dtype=torch.float64)
    y = torch.tensor([[0., 1., 1., 0.]], dtype=torch.float64)
    m = torch.ones_like(s, dtype=torch.bool)
    w = {(1, 0): abs(D[1]-D[0]), (1, 3): abs(D[1]-D[3]), (2, 0): abs(D[2]-D[0]), (2, 3): abs(D[2]-D[3])}
    expected = sum(v*math.log1p(math.exp(s[0, j]-s[0, i])) for (i, j), v in w.items())/sum(w.values())
    out = lambda_pairwise_logistic_loss(s, y, m, [['a', 'b', 'c', 'd']])
    self.assertAlmostEqual(out.loss.item(), expected, places=12)
    self.assertEqual((out.valid_queries, out.skipped_queries, out.pairs), (1, 0, 4))

def test_ties_follow_rank(self):  # equal scores: page ID ascending decides positions
    self.assertEqual(discounts(['b', 'a', 'c'], [0.5, 0.5, 0.1]), [D[1], D[0], D[2]])

def test_positions_past_cutoff_have_zero_discount(self):
    self.assertEqual(discounts([f'p{i:02d}' for i in range(12)], [1-i/12 for i in range(12)])[10:], [0.0, 0.0])

def test_pair_outside_top10_does_not_change_loss(self):
    # 12 candidates; positive and negative at positions 10 and 11.
    # Moving both scores while keeping their order leaves the loss unchanged.

def test_padding_gets_no_weight_or_gradient(self):
    # Batch of a 3-candidate and a 5-candidate query; padded score column gets grad == 0
    # and the loss equals the mean of the two single-query losses.

def test_short_query_has_finite_loss(self):  # 2 candidates, one of each class

def test_gradcheck(self):  # torch.autograd.gradcheck on distinct float64 scores, weights detached

def test_refusals(self):
    # ValueError for: shape mismatch, non-binary labels, non-finite active score,
    # page_ids not aligned with [B,N], cutoff < 1, and no query with both classes.
```

- [ ] **Step 2: Run, expect import failure**

Run: `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m46_losses -v`
Expected: FAIL, `ModuleNotFoundError: qpaf.m46`

- [ ] **Step 3: Implement in `src/qpaf/m46/losses.py`.** Validate inputs exactly as `qpaf.m12.losses.pairwise_logistic_loss` does, plus page-ID alignment and `cutoff`. Per query, weights come from `discounts` on the detached active scores: `w_ij = |d_i − d_j|` for positive `i`, negative `j`. Query loss is `(w * softplus(s_neg[None,:] − s_pos[:,None])).sum() / w.sum()`; raise if `w.sum() == 0` with both classes present. `pairs` counts all positive×negative pairs, as in v1.
- [ ] **Step 4: Run, expect PASS**

Run: `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m46_losses -v`

- [ ] **Step 5: Commit**

```bash
git add src/qpaf/m46/__init__.py src/qpaf/m46/losses.py tests/test_m46_losses.py
git commit -m "feat(m4.6): add the ΔnDCG@10-weighted pairwise logistic loss"
```

### Task 3: v2 config and matched trainer

**Files:**
- Create: `src/qpaf/m46/config.py`, `src/qpaf/m46/trainer.py`, `configs/m4.6/shared_base_v2.toml`
- Test: `tests/test_m46_trainer.py`

**Interfaces:**
- Consumes: Task 2 `lambda_pairwise_logistic_loss`; `qpaf.m24.config.validate`, `qpaf.m24.config.METHODS`, `qpaf.m24.trainer.learnable`, `qpaf.m24.trainer.is_better`, `qpaf.m24.checkpoint.save_checkpoint/load_checkpoint`, `qpaf.m24.evaluator.predict/evaluate`, `qpaf.m24.dataset.iter_batches`, `qpaf.m12.model.FusionGate`.
- Produces: `LOSS: dict`, `validate(config) -> None`, `load_config(path) -> dict`, `build_model(config, method) -> FusionGate`, `train(config, method, train_records, validation_records, checkpoint_dir, *, resume=None, stop_after_epoch=None, log=print) -> dict` (same return keys as `qpaf.m24.trainer.train`).

- [ ] **Step 1: Write the failing tests**

```python
def test_v2_toml_differs_from_m42_base_only_in_loss(self):
    # tomllib-load both files; equal after removing 'loss'; v2 loss == LOSS
def test_validate_refuses_v1_loss_and_bad_other_fields(self):
    # loss pairwise_logistic -> ValueError; training.epochs 0 -> ValueError; extra loss key -> ValueError
def test_initial_parameters_match_m24(self):
    # m46.build_model(v2, m) state_dict == m24.build_model(v1, m) state_dict for 'QARF' and 'QPAF'
def test_synthetic_training_is_deterministic_and_uses_v2_loss(self):
    # qpaf.m24.synthetic.make_fixture -> build_records; train QPAF 3 epochs twice in temp dirs:
    # identical history and best.pt sha256; patch m46.trainer.lambda_pairwise_logistic_loss
    # with a wrapping mock and assert it was called
def test_resume_matches_uninterrupted_run(self):
    # stop_after_epoch=2 then resume from last.pt to 3 epochs == straight 3-epoch history
```

- [ ] **Step 2: Run, expect import failure**

Run: `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m46_trainer -v`

- [ ] **Step 3: Implement.**
  - `configs/m4.6/shared_base_v2.toml`: copy the M4.2 `shared_base.toml` bytes, then replace only the `[loss]` table with `name = "lambda_pairwise_logistic"`, `reduction = "query_mean"`, `metric_cutoff = 10`.
  - `config.validate` requires `config['loss'] == LOSS`, then calls `qpaf.m24.config.validate` on a deep copy whose loss is `{'name': 'pairwise_logistic', 'reduction': 'query_mean'}`.
  - `build_model` mirrors `qpaf.m24.trainer.build_model` (fork_rng, `manual_seed(training.seed)`, `.double()`) but calls the m46 `validate`.
  - `train` is the M2.4 epoch loop with the m46 loss. Pass `batch.page_ids` restricted to the `valid` rows. Keep the exception class `TrainingError`.
- [ ] **Step 4: Run, expect PASS.** Then confirm M4.3 is untouched:

Run: `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m46_trainer tests.test_m24_pipeline -v`

- [ ] **Step 5: Commit**

```bash
git add configs/m4.6/shared_base_v2.toml src/qpaf/m46/config.py src/qpaf/m46/trainer.py tests/test_m46_trainer.py
git commit -m "feat(m4.6): add the v2 config and matched trainer"
```

### Task 4: Train-only alignment probe and gate run

**Files:**
- Create: `src/qpaf/m46/probe.py`, `scripts/probe_m46_loss_alignment.py`, `evidence/revisions/m4.6-001/loss_alignment_probe.json`
- Test: `tests/test_m46_probe.py`

**Interfaces:**
- Consumes: Tasks 2–3; `qpaf.m42.active_primary.verify_files`; the M4.4 config `configs/m4.4/evaluation.json` for the bundle path and manifest pin.
- Produces: `grid_points() -> list[list[float]]` (66 points, step 0.1, order `(i, j)` lexicographic, weights `[i/10, j/10, (10-i-j)/10]`), `spearman(a, b) -> float` (average ranks for ties), `gate(grid_rows) -> dict` (`{'spearman': float, 'min_loss_weights': list, 'min_loss_ndcg': float, 'max_ndcg': float, 'G_A': 'PASS'|'FAIL', 'G_B': 'PASS'|'FAIL', 'status': 'PASS'|'REVISION_GATE_FAILED'}`), `run(root) -> dict`.

- [ ] **Step 1: Write the failing tests**

```python
def test_grid_has_66_simplex_points(self):  # len 66, each sums to 1 within 1e-12, first [0,0,1], last [1,0,0]
def test_spearman_with_ties(self):  # assertAlmostEqual(spearman([1,2,2,3],[1,3,2,4]), 0.9486832980505139, places=12)
def test_gate_thresholds(self):
    # rows with spearman -0.5 exactly and min-loss nDCG == max-0.01 -> both PASS (inclusive);
    # -0.49 -> G_A FAIL; max-0.0101 -> G_B FAIL; either FAIL -> status REVISION_GATE_FAILED
def test_probe_reads_train_only(self):
    # patch build_records; assert roles == ('train',) and that qrels passed hold only train IDs
```

- [ ] **Step 2: Run, expect import failure**

Run: `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m46_probe -v`

- [ ] **Step 3: Implement `probe.py` and the CLI.** `run` verifies the M4.2 bundle (`verify_files`), builds train records only, computes features once, and for every grid point and both losses records `loss` (query-mean over learnable queries) and `ndcg_at_10` (`qpaf.m24.evaluator.evaluate`). It also scores, under both losses, the train rows of QARF `best.pt`/`last.pt` and QPAF `best.pt` (paths as in `src/qpaf/m44/common.py` and `evidence/revisions/m4.3-001/method_freeze.json`). Output keys: `schema_version`, `task_id`, `split: 'train'`, `query_count`, `grid` (per point: weights, `v1_loss`, `v2_loss`, `ndcg_at_10`), `checkpoints`, `gate_v1` (informational), `gate_v2` (decides), `thresholds`, `inputs_sha256`, `test_labels_opened: false`, `source_commit`. The CLI `--output PATH` writes create-once and refuses a dirty tracked tree; `--verify PATH` recomputes and requires byte equality.
- [ ] **Step 4: Run tests, expect PASS**
- [ ] **Step 5: Commit the code, then run the gate once from the clean tree**

```bash
git add src/qpaf/m46/probe.py scripts/probe_m46_loss_alignment.py tests/test_m46_probe.py
git commit -m "feat(m4.6): add the train-only loss alignment probe"
.venv/Scripts/python.exe -X utf8 scripts/probe_m46_loss_alignment.py --output evidence/revisions/m4.6-001/loss_alignment_probe.json
```

Expected v1 values (must reproduce the scratch probe): min-loss point `[1.0, 0.0, 0.0]`, loss `0.41520` (5 d.p.), Spearman `0.537` (3 d.p.). If they differ, stop and report. Record whatever `gate_v2.status` the run gives. **Do not change the loss or the thresholds after seeing it.**

- [ ] **Step 6: Commit the evidence**

```bash
git add evidence/revisions/m4.6-001/loss_alignment_probe.json
git commit -m "docs(m4.6): record the train-only loss alignment gate"
```

### Task 5: Direction record, owner confirmation, events, README

**Files:**
- Create: `src/qpaf/m46/direction.py`, `scripts/decide_m46_direction.py`, `evidence/revisions/m4.6-001/{decision.json,owner_confirmation.json,governance_events.jsonl,README.md}`
- Test: `tests/test_m46_direction.py`

**Interfaces:**
- Consumes: `qpaf.m43.freeze.{sha, check_pins, serialize, write_json, read, git}`; Task 4 output.
- Produces: `PINS: dict[str, tuple[str, str|None]]`, `prerequisites(root) -> dict`, `collect(root) -> dict`, `create(root, output_dir) -> dict`, `verify(root, output_dir) -> dict`; exception `DirectionError(ValueError)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_prerequisites_require_confirmed_go_freeze_and_acceptance(self):
    # temp root with fixture JSON: G2 decision GO/continue_qpaf + confirmation CONFIRMED,
    # M4.3 owner_confirmation CONFIRMED, M4.5 owner_confirmation ACCEPTED -> passes;
    # each of: G2 'NO-GO–PIVOT', G2 confirmation missing, M4.3 not CONFIRMED,
    # M4.5 'PENDING' -> DirectionError naming the file
def test_record_branch_and_status_follow_the_gate(self):
    # gate_v2 PASS -> m4_branch 'revise_once', status 'REVISE_ONCE_GATE_PASSED_AWAITING_A004_APPROVAL';
    # REVISION_GATE_FAILED -> status 'REVISION_GATE_FAILED_RETURN_TO_RESEARCH_LEAD'; authorizes_execution False
def test_pin_drift_refuses(self):
def test_create_once_and_verify_equality(self):
    # create into temp dir; second create raises; verify returns {'status': 'PASS'}; editing one byte -> raises
```

- [ ] **Step 2: Run, expect import failure**

Run: `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m46_direction -v`

- [ ] **Step 3: Implement.** `PINS` covers: `evidence/revisions/m3.7-001/{decision,owner_confirmation}.json`, `evidence/revisions/m4.3-001/{method_freeze,owner_confirmation}.json`, `results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01/manifest.json` (`aa2ab518…e4a7`), `results/m4.4/RUN-QPAF-M4_4-ORC-001-20261023T172102Z-A01/manifest.json` (`6d796a27…b5a2`), `evidence/revisions/m4.5-001/{verification,owner_confirmation}.json`, the probe output, A004 and the spec. Pins with `None` are hashed at creation and checked by `--verify`; the M4.4 manifests use their full known values from `evidence/revisions/m4.4-001/README.md`. `collect` copies, read from those files: `selection.validation_ndcg_at_10` (`train_fitted_static`, `qpaf`, `learned_qarf`), `uncertainty.qpaf_minus_baseline_ndcg_at_10.train_fitted_static` (`mean_delta`, `ci95`, `wtl`), and `gate_v2`. It adds the timing disclosure, the stop rule as four strings copied from the spec, `owner_confirmation_ref`, `test_labels_opened: false`, `training_executed: false`, `authorizes_execution: false`, `source_commit`. `create` requires a clean tracked tree.
- [ ] **Step 4: Run tests, expect PASS**
- [ ] **Step 5: Write `owner_confirmation.json`** with the M4.3 key set: `decision: 'CONFIRMED'`, `m4_branch: 'revise_once'`, the verbatim text and time from Global Constraints, `recorded_by: 'Claude Code at the Research Lead's request'`, a `context` line saying the reply followed the loss-probe findings and Claude's recommendation, a `scope` saying it approves the direction only, not A004, the gate thresholds or any run, and `authorizes_execution: false`. Commit code and confirmation, then create the record:

```bash
git add src/qpaf/m46/direction.py scripts/decide_m46_direction.py tests/test_m46_direction.py evidence/revisions/m4.6-001/owner_confirmation.json
git commit -m "feat(m4.6): add the direction record and owner confirmation"
.venv/Scripts/python.exe -X utf8 scripts/decide_m46_direction.py --output-dir evidence/revisions/m4.6-001
```

- [ ] **Step 6: Append events and write the README.** Events `DECISION_RECORDED`, `AMENDMENT_PROPOSED` (A004, pending approvals), `REVISION_GATE_RECORDED` (gate status), each with the SHA-256 of its record. The README follows `evidence/revisions/m4.5-001/README.md`: verdict line, evidence table, gate result, timing disclosure, stop rule, claim boundary, replay commands. Then commit:

```bash
git add evidence/revisions/m4.6-001/decision.json evidence/revisions/m4.6-001/governance_events.jsonl evidence/revisions/m4.6-001/README.md
git commit -m "docs(m4.6): record the revise_once direction"
```

### Task 6: Whole-branch verification and handover

**Files:**
- Create (untracked): `MergeM4.6.md`

- [ ] **Step 1: Read-only replays**, each expecting `PASS`:

```bash
.venv/Scripts/python.exe -X utf8 scripts/freeze_m43_qpaf.py --verify evidence/revisions/m4.3-001
.venv/Scripts/python.exe -X utf8 scripts/probe_m46_loss_alignment.py --verify evidence/revisions/m4.6-001/loss_alignment_probe.json
.venv/Scripts/python.exe -X utf8 scripts/decide_m46_direction.py --verify evidence/revisions/m4.6-001
```

- [ ] **Step 2: Focused and full tests.** Run `tests.test_m46_*`, `tests.test_m43_freeze`, `tests.test_m44_evaluation`, `tests.test_m45_baseline_audit`, then the full suite with `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` in the background. New failures are those not in `results/m4.2/verification/active-primary-failed-nodeids.json`; expect none.
- [ ] **Step 3: Write `MergeM4.6.md`** in Vietnamese with the sections Kết luận, Nội dung PR, Kết quả, Cảnh báo, Kiểm chứng, Bàn giao. Quote numbers and hashes from the evidence files. Bàn giao: Research Lead approves A004 in their own words; Thanh reviews A004; then the authorization request for `QPAF-M4_6-MTH-001/002`. Do not commit the file.
