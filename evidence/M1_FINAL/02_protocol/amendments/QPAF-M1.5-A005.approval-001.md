# A005 Research Lead approval — 2026-10-28

**Amendment:** `QPAF-M1.5-A005`, as committed in `0f71e63`, SHA-256
`edf84064de0546bc120c121f41d7a6018635a234c8ecfe3b92fe90c06fa3a4a4`

**Approver:** Tấn Phát (Research Lead), who is also the amendment requester
**Decision:** `APPROVED_RESEARCH_LEAD`
**Recorded:** 2026-10-28T14:20:40Z, by Claude at the Research Lead's request

The Research Lead's reply in the working session, verbatim:

> Duyệt A005 theo bản 0f71e63

The reply answered Claude's request to approve, or not, A005 at `0f71e63`. Earlier
in the same session the Research Lead had also written:

> Tôi sẽ là người để duyệt hết tất cả vì là research lead, nên tôi sẽ là người quyết định thay đổi để có QPAF có kết quả cao hơn.

> Không cần Thanh phải review, Thanh cũng sẽ chỉ dùng gpt thôi

Those two statements are recorded as context. They are not a decision about the
reviewer. The approved text keeps the independent-review requirement unchanged
(A005 §8 and amendment procedure step 6). Changing or removing that requirement
would need its own amendment, which `frozen_protocol.md` §5 item 9 would then
constrain.

## What this approval covers

- The A005 design is fixed as written: the static-anchored gate, the listwise loss
  with a learned temperature, selection over epochs 0–20, ViMDoc confirmation, the
  train-only alignment gates, stop rules and claim boundary.
- A005 §1–§7 apply as written.

## What it does not cover

- **Independent review:** still `PENDING`. A005 §8 requires it before Stage 0 runs,
  so no stage may run yet.
- **Stage authorizations:** none are granted. Every stage needs its own authorization.
- **Data and GPU:** no ViMDoc label access and no GPU use are authorized.
- **Governance event:** the event in A005 §8 is appended only after both approvals.

The original amendment file is unchanged and keeps its `PROPOSED` header as a
historical record.
