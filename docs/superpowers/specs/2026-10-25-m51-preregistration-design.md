# M5.1 preregistration design

## Intent

Thanh owns R1: lock the remaining matched seeds, optional one-factor diagnostic order and drop-first rule before M5.3/M5.4 or TEST-172. The record is a governance plan, not an execution authorization or result.

## Choices

- A prose-only plan would be easy to read but hard to check for silent seed or roster drift.
- A structured record alone would be checkable but difficult for the team to use.
- **Chosen:** a create-once JSON record, a short Vietnamese README and a read-only verifier that binds the record to the M4.7 G2A freeze and M1.5 policy. No input labels are read.

## Boundaries

R1–R4, R7 and R8 are core and cannot be dropped. R5/R6 are diagnostic and optional. R9/R10 remain deferred under G2A; this record does not promote them. Seed `20260820` is already complete, and `20260821`/`20260822` are the only remaining matched QARF/QPAF seeds. Matched runs change only `training.seed`, use the same input/order/config/budget, retain all valid seeds, and require fresh-process reload and finite-output checks before TEST-172. R7 is one sealed test evaluation after independent seed reviews. A004 failed its gate and is not used.

R5 and R6 stay on validation, are diagnostic, and cannot alter the frozen primary method or strongest baseline. The drop rule affects only the optional tier: omit R6 first, then R5 if necessary; record every omission and its effect on claims. In particular, omitting operational measurements cannot support an operational-good-enough claim. The exact authorized diagnostic run packages remain future tasks, not authority granted by R1.

## Verification

The verifier rejects hash drift, a changed core roster, wrong seed matrix, altered test boundary, or an optional drop outside R5/R6. It checks the saved JSON and produces no result-bearing run. Thanh accepted the finished record; owner signoff is a separate append-only artifact linked by SHA-256.
