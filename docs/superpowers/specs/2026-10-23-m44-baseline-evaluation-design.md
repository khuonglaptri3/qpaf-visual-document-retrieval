# M4.4 — Full deployable baseline evaluation (validation)

Owner: Tấn Phát. Branch: `feature/m4-4-baseline-evaluation`, stacked on
`feature/m4-3-qpaf-freeze` because the QPAF row binds the M4.3 freeze record.
M4.3 must be merged first. No human acceptance is asserted here.

## Authority and scope

Workbook Milestones row 51: "Predictions and fair baseline table with oracle
rows separated". `baseline_policy.md` §1–§4 fixes the seven deployable rows,
validation selection of the strongest baseline (ties within `1e-12` are
co-strongest) and oracle rows as context only. The M4.2 handoff hands over the
shared bundle `RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01` (manifest
`4752eef3…`) with static weights `[0.0, 0.1, 0.9]`, RRF k=60 and the QARF
checkpoint `e44ac1a4…`.

Decisions confirmed by the Research Lead on 2026-10-23:

- Evaluate on the **171 validation queries only**. The 172 test queries stay
  sealed: only the hash of `qrels_test_sealed.json` is checked, never parsed.
- Compute **new oracle context rows** on the same validation pool with the
  frozen W7/W66 profiles of `src/oracle_study/profiles.py`, declared before
  the run and with no search beyond those profiles.

## Inputs

Restore the seven missing M4.2 payload files (Parquet and `best.pt`) from their
byte-identical local sources (`results/m2.8/...EXPANSION-001.../bundle/`,
`results/m3.2/.../checkpoints/best.pt`): copy only on full SHA-256 match, never
overwrite. Then `scripts/run_m42_active_primary.py --verify` must PASS. Only
validation qrels are deserialized for metrics.

## Runs

One authorization manifest (`evidence/revisions/m4.4-001/authorization.json`)
covers two experiments. Each runs once with no retry, in a create-once
namespace, on local CPU with `float64`, 1 thread and deterministic torch:

1. `QPAF-M4_4-MTH-001` (`learned_evaluation`, `engineering_evidence` until the
   M4.5 review), at `results/m4.4/<run_id>/`:
   - six label-free rows through `qpaf.m25.baselines.predictions` with the M4.2
     contracts;
   - learned QARF reloaded from the bundle checkpoint, with predictions required
     to match M3.2 `validation_predictions.json` within `1e-7`;
   - proposed QPAF from the M4.3 frozen `best.pt`, matched against M3.4 the
     same way;
   - every row scored by `qpaf.m24.evaluator.evaluate`;
   - selection with `qpaf.m25.baselines.select_co_strongest` over the seven
     deployable rows only;
   - single-seed exploratory paired statistics, QPAF minus each deployable row,
     using `scripts.audit_m35_paired.paired_statistics` (10,000 resamples, seed
     20260820).
2. `QPAF-M4_4-ORC-001` (`oracle_upper_bound` / `scientific_upper_bound`), at
   `results/m4.4/<run_id>/`: for W7 and W66, global (one profile for all
   queries), per-query (oracle QARF) and per-page (oracle QPAF) oracles,
   reusing `oracle_study.qpaf` on the same min-max scores. Scores are
   re-evaluated with the m24 evaluator so every row uses one IDCG rule. These
   rows are never eligible for selection.

## Outputs

MTH: `predictions.csv.gz` (wide; deterministic gzip with `mtime=0`),
`per_query_metrics.csv`, `baseline_table.json`/`.md`, `selection.json`
(candidates, contract hashes, metrics, tied set, selected IDs, verifier
`PENDING_M4.5`), `paired_exploratory.json`, `access.json`, `manifest.json`,
`_ATTEMPTED.json`, then `_SUCCESS.json` or `_FAILED.json`.
ORC: `oracle_predictions.csv.gz`, `oracle_per_query.csv`, `oracle_table.json`
and the same markers.

The final table has three separate blocks: deployable baselines (7), proposed
method (frozen QPAF) and oracle context (6). It states that QARF/QPAF
checkpoints were selected on this validation split, so they are optimistic, and
that the evidence is single-seed.

## Governance

The authorization binds commit, input hashes, config, method, seed, metric,
command, runtime, limits (wall time from a synthetic timing probe of the
oracle), stop conditions and the Research Lead's verbatim approval. Nothing runs
before that approval is committed and its hash is recorded in an
`AUTHORIZATION_RECORDED` event. Then come `STARTED` and `VERIFICATION_RECORDED`
events plus a `post_run_check.py` / `post_run_verification.json` pair.

## Verification

`tests/test_m44_evaluation.py`: hand-checked fixtures for the table blocks,
co-strongest ties, oracle exclusion from selection, refusal to parse test qrels,
prediction-parity failure, create-once and authorization mismatch. Then the
focused and full test suites, with base failures compared as in M4.2.
