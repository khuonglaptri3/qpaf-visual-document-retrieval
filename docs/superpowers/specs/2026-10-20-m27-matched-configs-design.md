# M2.7 — Matched QARF/QPAF configs

## Intent and authority

Implement the user's M2.7 assignment from `POAI_Milestone_Group01.xlsx`,
Milestones row 32 (owner Tấn Phát): *shared-base configs; semantic diff
limited to gate granularity*. Work on `feature/m2-7-matched-configs`, based on
develop `53bcd6b`. Design decisions below were approved by the user in
conversation on 2026-10-20.

Downstream consumers: M2.10 (independent audit of config parity and reload),
M2.11/D1, M3.2 and M3.4 (matched one-seed pilots), M5.3 and M5.4 (seeds 2/3).

## Binding rules

- `evidence/M1_FINAL/02_protocol/frozen_protocol.md` §4: QARF and QPAF share
  candidate rows/order, split IDs, qrels, 13 features, normalization, loss,
  optimizer, learning rate, weight decay, batch size, gradient clip, maximum
  epochs, checkpoint selection, precision, seed, data order, runtime/budget/
  retry policy and evaluation. The only intended difference is
  `gate_granularity`: QARF pools over the query and broadcasts one weight
  vector; QPAF has one weight vector per query-page pair. QARF runs and is
  independently reviewed before matched QPAF is authorized.
- Amendment `QPAF-M1.5-A001` (APPROVED): loss is `pairwise_logistic` /
  `query_mean`, replacing the original masked listwise loss.
- `seed_policy.md`: training seeds `20260820/21/22`, same set for both
  methods; one-seed development gate `20260820`.
- `run_policy.md`: authorization binds resolved config hash, seed, runtime,
  wall-time cap, invocation and retry counts.

## Decisions

1. **Hyperparameters:** adopt the M2.4 values unchanged. They were fixed
   without real-data outcomes; the protocol forbids unrestricted search.
2. **Structure:** one shared base config plus a matched manifest (option A).
   Both methods run from byte-identical `shared_base.toml`, so the
   `config_sha256` bound into both checkpoints is identical. No change to the
   M2.4 runner or checkpoint contract.
3. **Wall-time cap:** 60 minutes per method per seed, recorded as a ceiling.
   A throwaway probe on 2026-10-20 (M2.4 trainer, synthetic rows shaped
   799 train + 171 validation queries x 600 candidates, CPU float64, 1 thread,
   deterministic) measured about 2.4 s per epoch for both methods, i.e. about
   1-2 minutes per full 20-epoch run.
4. **Experiment ID:** `QPAF-M2_7-MTH-001` (registered class `MTH`).

## Artifacts

### `configs/m2.7/shared_base.toml`

M2.4 schema, validated by `qpaf.m24.config.validate`. Values identical to
`configs/m2.4/pipeline.toml` (SHA-256 `257c28db…651d535a`) except
`experiment_id = "QPAF-M2_7-MTH-001"` and the header comment:
data `qpaf_score_rows_v1`, `max_candidates = 600`, `positive_threshold = 1`;
features `qpaf13_v1`, `query_length_cap = 64`; gate linear, `hidden_dim = 16`,
`temperature = 1.0`; loss pairwise_logistic/query_mean; training seed
`20260820`, 20 epochs, batch 16, adam, lr 0.01, weight decay 0.0, max grad
norm 5.0; evaluation selects on `ndcg_at_10`, reload tolerance `1e-7`.

### `configs/m2.7/matched.json`

Exact top-level keys:

| Key | Value |
|---|---|
| `schema_version` | `1` |
| `task_id` | `"M2.7"` |
| `experiment_id` | `"QPAF-M2_7-MTH-001"` |
| `base_config` | `{"path": "configs/m2.7/shared_base.toml", "sha256": <hex>}` |
| `methods` | `{"QARF": {"gate_granularity": "query"}, "QPAF": {"gate_granularity": "page"}}` |
| `allowed_semantic_diff` | `["gate_granularity"]` |
| `seeds` | `{"development_gate": 20260820, "robustness": [20260820, 20260821, 20260822], "override_path": "training.seed"}` |
| `run_order` | `["QARF", "independent_review", "QPAF"]` |
| `shared_inputs` | see below |
| `runtime` | `{"device": "cpu", "dtype": "float64", "threads": 1, "deterministic_algorithms": true, "requirements": "requirements-learned-local.txt"}` |
| `budget` | `{"wall_time_minutes_per_run": 60, "invocations_per_method_per_seed": 1, "retries_without_new_authorization": 0, "shared_by_methods": true}` |
| `loss_authority` | `"QPAF-M1.5-A001"` |
| `status` | `"FROZEN_CONFIG_PENDING_M2.8_INPUTS"` |

`shared_inputs`:

| Key | Value |
|---|---|
| `split_manifest` | `{"path": "evidence/revisions/m2.1-002/data_split_manifest.json", "sha256": "ea5a19f93dce07cce375d6fb6afed630606e00916c5daa10938562aee9cddfad"}` |
| `m25_freeze` | `{"path": "configs/m2.5/freeze.json", "sha256": "317b4333968ae4250e0e9bc71846d37f47e5f958872c8cf27949a0c0d8c3579c"}` |
| `score_cache` | `"PENDING_M2.8"` |
| `qrels` | `"PENDING_M2.8"` |
| `candidate_set` | `"PENDING_M2.8"` |

Pilot command (M3.2, M3.4), unchanged runner:
`python scripts/run_m24_pipeline.py --config configs/m2.7/shared_base.toml --method QARF|QPAF --scores … --queries … --qrels … --splits … --output …`.
Seeds 2/3 (M5.3, M5.4) apply only `training.seed`, identically to both
methods; materializing a per-seed base file is out of scope here.

## Parity verifier

### `src/qpaf/m27/matched.py`

Pure functions; every failure raises `ParityError(ValueError)` with a
specific message.

- `load_manifest(path)`: strict validation: exact keys at every level, methods
  exactly `QARF`/`QPAF`, `allowed_semantic_diff == ["gate_granularity"]`,
  integer seeds in `[0, 2**32)`, development seed in the robustness list,
  pending inputs exactly `"PENDING_M2.8"`, hashes 64 lowercase hex.
- `resolve(manifest, method, seed, root)`: load the base via
  `qpaf.m24.config.load_config`, set `training.seed = seed` and re-validate,
  add top-level `gate_granularity` from the manifest. The method name is the
  lookup key, not a config field.
- `semantic_diff(left, right)`: flatten nested dicts to dotted paths; return
  `{path: [left_value, right_value]}` for every differing or one-sided path.
- `check_parity(manifest, root)`: run the checks below; return a JSON-ready
  report.

### Checks (fail-closed)

1. **Bytes pinned:** SHA-256 of the base file equals `base_config.sha256`.
2. **M2.4 values unchanged:** `semantic_diff(base, configs/m2.4/pipeline.toml)`
   equals exactly `{"experiment_id": [...]}`.
3. **Matched pair, every robustness seed:**
   `semantic_diff(resolve(QARF, s), resolve(QPAF, s))` equals exactly
   `{"gate_granularity": ["query", "page"]}`.
4. **Manifest matches running code:** the manifest granularities equal
   `qpaf.m24.config.METHODS`.
5. **Identical initialization, every robustness seed:**
   `qpaf.m24.trainer.build_model(cfg, "QARF")` and `(cfg, "QPAF")` have
   bit-identical state dicts and equal parameter counts.
6. **Identical data order:** train one epoch of each method on the M2.4
   synthetic fixture with the base config; the per-step
   `(valid_queries, pairs)` sequences must be equal. They depend only on batch
   composition, so a mismatch means a different batch order.
7. **Shared inputs pinned:** recompute SHA-256 of the split manifest and the
   M2.5 freeze; both must match. Pending inputs must be the exact sentinel.

Checks 5 and 6 need torch; without it the verifier fails with a clear
`ParityError` (it never reports a partial pass).

### `scripts/verify_m27_matched.py`

No arguments: print the report. `--output <path>`: write it create-once
(`FileExistsError` if present), UTF-8, LF, sorted keys, indent 2, like M2.5.
`ParityError`/`FileExistsError` exit with code 2 and an `Error:` line, like the
M2.4 runner.

Report fields: `task_id`, `experiment_id`, `status`,
`base_config_sha256`, `manifest_sha256`, `source_sha256` for
`src/qpaf/m27/matched.py`, `src/qpaf/m24/config.py`,
`src/qpaf/m24/trainer.py`, `scripts/verify_m27_matched.py`; per-seed
semantic diffs; M2.4 drift diff; initialization and data-order results;
shared-input hash checks; `pending_inputs`; `wall_time_cap_minutes`;
`independent_review: "PENDING"`.

## Line endings

`.gitattributes` already normalizes text to LF and byte-pins
`/evidence/revisions/**`. Add `/configs/m2.7/** -text -eol`, following
`/configs/m2.6/full_ocr.toml`, so hashed config bytes are identical on every
checkout. Write config files with LF.

## Tests: `tests/test_m27_matched.py`

`unittest`, matching CI (`python -m unittest discover -s tests`). Torch checks
use `@unittest.skipUnless(HAS_TORCH, …)` like `tests/test_m24_pipeline.py`.

- Happy path: the committed files pass `check_parity`; each seed's diff is
  exactly `gate_granularity`; initialization and data order are identical.
- Fail-closed, on temporary copies only: edited base (hash mismatch); a second
  differing field between methods; base drift from M2.4 values; unknown or
  missing manifest key; granularity mapping disagreeing with `METHODS`;
  invalid seed; development seed not in robustness list; pending input missing
  or replaced by a fake value; split-manifest hash mismatch.
- `semantic_diff` unit cases: equal, changed leaf, one-sided key, nested.
- Script: create-once refusal; exit code 2 on `ParityError`.

## Evidence and docs

- `evidence/revisions/m2.7-001/verification.json`: create-once output of the
  script from the committed configs.
- `evidence/revisions/m2.7-001/README.md`: short Vietnamese summary in the
  m2.5-001 style.
- `docs/03_method/m2.7-matched-configs.md` (Vietnamese): matched rule (§4,
  A001), artifacts, pilot commands, seed rule, wall-time cap and its
  measurement, verification commands, limits.
- One line in `docs/03_method/README.md`; link the M2.4 doc's "không khóa
  matched config (M2.7)" note to the new doc; add an M2.7 entry to
  `docs/superpowers/README.md`.

## Done criteria

- `tests/test_m27_matched.py` passes and the full suite is no worse than
  develop.
- `verification.json` generated from the committed configs; status
  `FROZEN_CONFIG_PENDING_M2.8_INPUTS`; `independent_review: PENDING`.

## Out of scope

Real-data training (M3.2/M3.4), the score cache (M2.8), the M2.10 audit
itself, runner changes, and editing `POAI_Milestone_Group01.xlsx` (the user
maintains it).
