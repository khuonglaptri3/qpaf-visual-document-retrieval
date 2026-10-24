# M4.3 — Execute the frozen G2 branch (Frozen QPAF)

Owner: Tấn Phát. Base: develop `14dd8e6` (PR #34, M4.2 merged).
Branch: `feature/m4-3-qpaf-freeze`. No human acceptance is asserted here.

## Authority and scope

Workbook Milestones row 50 asks M4.3 for "Frozen QPAF, one preregistered
revision, or documented negative-result pivot", depending on G2. The confirmed
G2 record (`evidence/revisions/m3.7-001`) is `GO` with branch `continue_qpaf`,
so the deliverable is **Frozen QPAF**: the matched seed-20260820 QPAF pilot
from M3.4 becomes the main method, unchanged. `revise_once` and
`negative_qpaf_result` are not triggered and are recorded as such.

Out of scope: new training, seeds `20260821`/`20260822` (workbook M5.3/M5.4),
baselines (M4.4), test or confirmation labels, and the M4.6 direction decision.

## Approaches and decision

1. Freeze record plus fresh-process replay of the accepted artifacts: selected.
   It binds what G2 accepted and proves the checkpoints still reproduce the
   reviewed predictions, at no compute or authorization cost.
2. Retrain seed 20260820 to show reproducibility: rejected. It is a new
   result-bearing run that needs authorization and adds nothing that M3.6's
   reload review and this replay do not already show.

## Required behavior

`src/qpaf/m43/freeze.py`, driven by `scripts/freeze_m43_qpaf.py`:

- Pin by SHA-256 the G2 decision, owner confirmation, inputs and criteria; the
  M3.2 and M3.4 authorizations; the M3.5 comparison and the M3.6 integrity
  review. Any drift refuses.
- Replay G2 with `scripts/decide_g2.py` (no `--output`) in a child process and
  require the printed record to equal `decision.json`. Refuse unless the
  decision is `GO` and the branch is `continue_qpaf`.
- Replay the M3.1 seal with `scripts/seal_m31_inputs.py --verify`.
- For QPAF and QARF, reuse `scripts/audit_m36_integrity.py`: `checked_run`
  for markers, receipts and pins, and `--replay-method` in a fresh descendant
  Python process to reload `best.pt`, re-predict the 171 validation queries and
  recompute the reported metrics. Require score and weight differences
  `<= 1e-7`, zero ranking disagreements and metric differences `<= 1e-12`.
- Write `evidence/revisions/m4.3-001/method_freeze.json` (create-once) with:
  method, gate granularity, frozen config values, config file / resolved config
  / provenance hashes, `best.pt` hash and selected epoch 19, the selection rule,
  13 feature names, hashes of the model, feature, loss, trainer and evaluator
  sources, the matched QARF checkpoint, the sealed-input manifest, the branch
  disposition, the seed plan (completed 20260820; 20260821/20260822 pending in
  M5.3/M5.4 with the same resolved config except `training.seed`), the claim
  boundary and the source commit.
- Write `verification.json` (create-once) with the replay outputs.
- `--verify` is read-only: it re-runs every check and requires the recomputed
  freeze record to equal the stored one, field for field.
- Creation requires a clean tracked tree and records `git rev-parse HEAD`.

After the user reviews the result, their verbatim confirmation is recorded in
`owner_confirmation.json`, and `governance_events.jsonl` receives the freeze and
confirmation events (`QPAF-M4_3-GAT-001`, class `governance` /
`governance_record`). The confirmation text is quoted, never composed.

## Claim boundary

Single development seed; the checkpoint was selected on the same validation
split used for the G2 comparison, so its validation numbers are optimistic. No
baseline comparison, no test or confirmation access, no three-seed claim, and
no change to the frozen protocol.

## Verification

`tests/test_m43_freeze.py` covers branch disposition (only `GO` /
`continue_qpaf` freezes), pin drift, create-once refusal, replay threshold
failures and freeze-record equality on synthetic fixtures. Then the focused
M3.x/M4.x tests and the full suite are run. Known base failures are compared
with `results/m4.2/verification/active-primary-base-comparison.json`.
