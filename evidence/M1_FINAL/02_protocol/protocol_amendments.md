# Protocol Amendment Ledger

> **Protocol:** `QPAF-M1.5-v1`  
> **Ledger mode:** Append-only after freeze  
> **Current state:** Protocol frozen; chưa có post-freeze amendment  
> **Registry classification:** `governance` / `governance_record`

Mọi thay đổi từ sau initial freeze identity bên dưới là post-freeze amendment. Chỉ
append amendment mới; không sửa/xóa entry cũ hoặc silently thay semantics của v1.

## Initial freeze identity

| Field | Value |
|---|---|
| Frozen protocol version | `QPAF-M1.5-v1` |
| Frozen at | `2026-09-25T20:43:27.4530745+07:00` |
| Source Git HEAD | `20cb3bf6d42c1d44d4516bfb5fdc9b82c8732455` |
| Source branch/worktree | `chore/repository-hygiene`; `DIRTY_RECORDED_NOT_A_FREEZE_COMMIT` |
| Protocol package identity | [protocol_freeze_manifest.json](protocol_freeze_manifest.json) |
| Owner freeze instruction | `RECORDED_IN_CURRENT_WORKING_SESSION_2026-09-25` |
| Independent reviewer sign-off | `PENDING_NOT_CLAIMED` |
| Execution authorization | `CLOSED_NOT_GRANTED_BY_PROTOCOL_FREEZE` |

## Amendment register

| ID | Date | Requester | Affected field/file | Old value | New value | Reason/evidence | Leakage/fairness/statistical impact | Affected runs / rerun | Approver | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — | — | No post-freeze amendments |

## Required amendment procedure

1. Assign monotonic ID `QPAF-M1.5-A###`.
2. Record exact old/new values, files and hashes before implementation/execution.
3. Explain why the change is necessary and why a simpler no-change path is invalid.
4. Assess data leakage, matched-comparison, statistical and claim-boundary impact.
5. List every prior/future run affected and whether rerun is mandatory.
6. Obtain Research Lead approval and independent reviewer sign-off.
7. Create a new protocol/config version and output namespace when semantics change.
8. Preserve old protocol, artifacts and registry records unchanged.
9. Append a M1.7 `governance` / `governance_record` event referencing the amendment
   path, protocol hashes, approver and effective version.

Emergency technical corrections do not bypass this process if they can change rows,
scores, ranking, metrics, seeds, resource behavior or claim interpretation.
