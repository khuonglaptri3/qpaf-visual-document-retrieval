# QPAF-M1.5-A006 — Waive independent review for A005

> **Protocol:** `QPAF-M1.5-v1` (scoped successor `m1.5-002`)
> **Date:** 2026-10-28
> **Requester and approver:** Tấn Phát (Research Lead)
> **Affected contracts:** amendment procedure step 6 and the independent-review requirement in A005 §5 and §8, for A005 only
> **Status:** `APPROVED_RESEARCH_LEAD / NO_INDEPENDENT_REVIEW_BY_DESIGN`
> **Registry classification:** `governance` / `governance_record`

This is the create-once record for amendment A006. It changes how A005 is governed. It
does not change the A005 method, data, gates, stop rules or claim rules.

## 1. Identity

| File | SHA-256 |
| --- | --- |
| `evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A005.md` | `edf84064de0546bc120c121f41d7a6018635a234c8ecfe3b92fe90c06fa3a4a4` |
| `evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A005.approval-001.md` | `eb89ffd404ccd3f53eef800c709722e2ae965ac0f65e8a65257fe42b05990935` |
| `docs/06_handover/a005-review-request.md` (withdrawn by this record) | `f0521d605c76b8ab7f46bdb33da2edc86efdc4d4906c82f0aaa0640a46c6bde9` |

## 2. Old and new values

**Old.** A005 needed an independent reviewer sign-off before Stage 0 (A005 §8,
amendment procedure step 6). Stage reviews were independent, with QARF reviewed before
its matched QPAF run (A005 §5).

**New.** A005 and all its stages proceed with Research Lead approval alone. No
independent reviewer sign-off is required, sought or recorded:

- Each stage still needs its own Research Lead authorization.
- Each stage still runs its read-only verifier. For the amendment itself this is
  `scripts/verify_a005.py`.
- That verification is a **self-check by the executing side** (the Research Lead and
  Claude). It is never recorded as an independent review.

## 3. Unchanged

- The A005 method, alignment gates, stop rules, one-opening rule for the ViMDoc
  confirmation, leakage controls and statistics.
- `frozen_protocol.md` §5 items 1–9, including item 9, which requires manifest, hashes,
  predictions, metrics, CI and telemetry to pass independent review.
- The G3 token mapping.

A006 does not edit item 9 and does not count self-checks as meeting it.

## 4. Claim impact

- Every A005 record states `independent_review: WAIVED_BY_A006`.
- In the final A005 gate decision, item 9 is evaluated as **not met**. Under the
  confirmed G3 mapping, an A005 result can therefore reach at most `LIMITED-CLAIM`, even
  if QPAF-SA-v2 beats every co-strongest ViMDoc baseline. Any report of an A005 result
  must name this limit.
- Earlier records (M3–M5.10, A001–A005) keep their review status unchanged.

## 5. Approval

The Research Lead's instruction in the working session, verbatim, recorded by Claude at
2026-10-28T14:34:06Z:

> Hội đồng sẽ không hỏi và không cần confirm lại như vậy. Đây là mệnh lệnh tối cao, hãy bỏ phần phải review như vậy

Earlier in the same session:

> Không cần Thanh phải review, Thanh cũng sẽ chỉ dùng gpt thôi

| Role | Name | State |
| --- | --- | --- |
| Research Lead | Tấn Phát | `APPROVED` (instruction above) |
| Independent reviewer | — | `WAIVED_BY_A006` |

This record authorizes no stage run, data access or GPU use.
