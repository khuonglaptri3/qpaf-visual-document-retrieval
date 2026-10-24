# M4.7 — G2A: freeze the robustness path

Owner: Tấn Phát. Base: `feature/m4-6-revise-once` `1e1cc6c` (PR #38 open; the
branch is synced with develop after #38 merges). Branch: `feature/m4-7-g2a-freeze`.
No human acceptance is asserted here.

## Authority and scope

Workbook Milestones row 54 asks M4.7 (G2A, dependency: all M4 tasks) for
"Frozen method/config, checkpoints and remaining experiment roster". M4.6 is
final `continue_qpaf` (`evidence/revisions/m4.6-001/final_confirmation.json`).
The Research Lead chose ViDoSeek test 172 as the held-out set for the primary
three-seed claim in the working session on 2026-10-24.

Out of scope: any training or evaluation run, opening test or ViMDoc labels,
the exact M5.1 matrix and drop order, M4.8 (R4 report), and workbook edits
unless asked.

## Approaches and decision

1. Create-once G2A freeze record that pins every frozen input and the roster,
   with read-only replays of M4.3 and M4.6: selected. It costs no compute and
   makes later runs refuse on drift.
2. Prose-only roster in a README: rejected. Nothing would bind M5 runs to the
   frozen bytes.
3. Include ViMDoc in the core: rejected. It needs GPU score extraction and
   three new trainings; not feasible before 13/12, and the Research Lead chose
   ViDoSeek.

## Frozen items

Pinned by SHA-256 in `evidence/revisions/m4.7-001/g2a_freeze.json`:

| Item | Value |
| --- | --- |
| Main method | QPAF-v1, M4.3 freeze `4015c74b54f5ac3d2cbce54f8424c0e9329c009595e81ced5eab0039af7761cc` |
| Checkpoint | `best.pt` `e4b00ab49e186fffe8b369e26491873304b61177c11fd2ce0f455158e30e5c8e`, epoch 19 |
| Config | M4.2 `inputs/shared_base.toml` `3e58a867…9b58`; loss A001 `pairwise_logistic` / `query_mean` |
| Matched comparator | QARF-v1, `RUN-QPAF-M3_2-MTH-001-20261022T035229Z-A01` `best.pt` (as pinned by M4.3) |
| Seeds | `20260820` done; `20260821`, `20260822` use the same resolved config, changing only `training.seed` |
| Selection rule | max validation nDCG@10 over 20 epochs, earlier epoch on ties (unchanged) |
| Inputs | M4.2 bundle manifest `4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86` |
| Baselines | 7-row roster, `baseline_contracts.json` `fa919054…7dcf`; co-strongest `{train_fitted_static}` from M4.4/M4.5 |
| Evaluator | `src/qpaf/m24/evaluator.py` `bfd25f33…6742`; oracle `src/qpaf/m44/oracle.py` `b9416d94…b701` |
| Held-out | ViDoSeek test, 172 IDs, `test_ids.txt` `d34210f9…e6f6`, sealed qrels `05eaaa81…d154`; labels closed |
| Claim rules | `frozen_protocol.md` §5 items 1–9, by reference and hash; no new threshold |
| Statistics | paired query bootstrap, 10,000 resamples, seed `20260820`, percentile CI95, W/T/L, top-5% share |
| ViMDoc 8,904 | `NOT_RUN_DEFERRED`: no verified ViMDoc score cache; the claim is bounded to ViDoSeek |

Required limitations carried into the record: the A001 loss orders static
weights against nDCG@10 (train Spearman +0.537, minimum at BM25-only); A004 did
not pass its gate; learned QARF is a weak comparator (validation 0.752147), so
`QPAF − QARF` mainly shows page-level gating tolerating that loss better, and
§5 item 4 (QPAF beats `train_fitted_static`) is the decisive test.

## Remaining experiment roster

Each entry records workbook task, owner, dependency, tier, allowed data,
whether a separate authorization is required, and its output.

| ID | Task | Owner | Tier | Allowed data | Auth |
| --- | --- | --- | --- | --- | --- |
| R1 | M5.1 preregister three-seed matrix, ablation order, drop-first rules within the optional tier | Thanh | core | none | no |
| R2 | M5.2 seed cache-parity receipt; external labels stay sealed | Khương | core | no labels | no |
| R3 | M5.3 matched QARF/QPAF seed `20260821` | Tấn Phát | core | train, validation | yes |
| R4 | M5.4 matched QARF/QPAF seed `20260822` | Tấn Phát | core | train, validation | yes |
| R5 | M5.5 retriever/normalization one-factor checks; latency and memory on the frozen checkpoints | Khương | optional | validation | yes |
| R6 | M5.6 feature and query-vs-page conditioning ablations | Tấn Phát | optional | validation | yes |
| R7 | TEST-172: one sealed evaluation of the 7 baselines, QARF ×3, QPAF ×3 and the W7/W66 oracle context rows | Tấn Phát runs, Thanh verifies | core | test 172, once | yes |
| R8 | M5.7 three-seed aggregation: seed-averaged paired CI, W/T/L, stability, subgroups, errors | Thanh | core | R7 outputs | no |
| R9 | M5.8 sealed external benchmark | Thanh | deferred | as workbook | yes |
| R10 | ViMDoc confirmation 8,904 | — | deferred | none | — |

Rules recorded with the roster:

- Core items cannot be dropped. M5.1 orders drops only within the optional tier.
- R3 and R4 each include a fresh-process reload check (`<= 1e-7`) and a finite
  output check before their checkpoints may enter R7.
- R7 runs once, after R3 and R4 have independent reviews. No seed, checkpoint,
  baseline or method choice is made after it. Oracle rows are label-using upper
  bounds, never selectable.
- Only R7 may read test labels. R5 and R6 use validation only, and their results
  cannot change the frozen method, config or checkpoints.

## Required behavior

`src/qpaf/m47/g2a.py`, driven by `scripts/freeze_m47_g2a.py`:

- Prerequisites, each refusing with the file named: G2 `GO`/`continue_qpaf` and
  its confirmation `CONFIRMED`; the M4.1 manifest present; the M4.2 manifest pin;
  M4.3 owner confirmation `CONFIRMED`; both M4.4 runs `_SUCCESS.json`; M4.5
  acceptance `ACCEPTED`; M4.6 final confirmation `CONFIRMED` with
  `m4_branch_final = continue_qpaf`.
- Replays in child processes: `scripts/freeze_m43_qpaf.py --verify
  evidence/revisions/m4.3-001` and `scripts/decide_m46_direction.py --verify
  evidence/revisions/m4.6-001`; both must print `"status": "PASS"`.
- Roster check: exactly the ten IDs above; only R7 allows test data; core and
  optional tiers as listed.
- `--output-dir` writes `g2a_freeze.json` and `verification.json` (replay
  outputs) create-once from a clean tracked tree and records `git rev-parse HEAD`.
  `--verify` is read-only and requires byte equality apart from a historical
  source commit that is an ancestor of HEAD.

After the Research Lead reviews the record, their verbatim confirmation goes
into `owner_confirmation.json`, with governance events (`QPAF-M4_7-GAT-001`,
`governance` / `governance_record`) continuing from `QPAF-REG-20261024-0005`,
and a README.

## Claim boundary

No new result. Validation numbers stay single-seed and optimistic. The record
authorizes no run; R3–R7 each need their own authorization.

## Verification

`tests/test_m47_g2a.py`: each prerequisite refuses; pin drift names the file;
a roster with test data outside R7, a missing core item or a core item marked
optional refuses; create-once refusal; `--verify` equality and tamper refusal.
Then the M4.3/M4.6/M4.7 replays, the focused M4.x tests and the full suite
under `.venv`, compared with the M4.2 base-failure list.
