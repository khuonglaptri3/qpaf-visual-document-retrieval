# M1.7 Draft Evidence Audit — Post-merge reconciliation

**Reviewer:** Thanh — Experiment Governance / Independent QA
**Initial review:** 27/09/2026
**Reconciled:** 28/09/2026 against `765803fee5465006658de35a4272414b27a5bb53`
**Audit scope:** `POST_MERGE_SOURCE_AND_HASH_INSPECTION_NOT_FINAL_QA`
**Package status:** `DRAFT_RECONCILED_FINAL_BLOCKED`
**Execution authorization:** `CLOSED`

## Kết luận

M1.7 Draft đã được reconcile sau khi các nhánh M1.4, M1.5, M1.6 và M1.8 merge.
Năm event và năm trace mới được append; chín row/trace ngày 27/09 vẫn giữ nguyên.
Các claim boundary tiếp tục tách Oracle, software verification, engineering audit
và governance; không có learned scientific result hoặc authorization event.

M1.7 **chưa thể Final/Freeze**. M1.5 đã có hai amendment được Research Lead
approve nhưng thiếu independent sign-off, exact amended package identity và exact
split manifests/hashes. M1.4 revision `m1.4-003` tự ghi `PARTIAL` và zero data
assets. M1.6 có populated output nhưng ba payload hash không khớp manifest, năm
source PDF không có trong workspace và full-corpus scope chưa tái lập được. M1.8
hash-valid nhưng threshold vẫn `PROVISIONAL` chờ M2.3/G1 scope decision. Kết quả
audit hiện tại là `DRAFT_RECONCILED_FINAL_BLOCKED`, không phải PASS của M1.7/G1.

## Phạm vi đã kiểm

1. Đối chiếu status vocabulary, experiment/evidence class và required fields với
   `../02_protocol/run_policy.md`.
2. Đối chiếu dataset/split/metric/seed fields với các policy M1.5 được import.
3. Kiểm current repository evidence cho M1.1, M1.2 và M1.4–M1.10, gồm các
   revision `m1.4-003`, `m1.6-001` và `m1.8-001` vừa merge.
4. Kiểm chuỗi `Experiment → Method → Config → Commit → Data/Hash → Output → Review`
   trong `traceability_matrix.csv`.
5. Ghi mọi missing/unknown/adoption gap vào `issue_log.csv` với owner và closure
   criterion; không suy đoán giá trị lịch sử.
6. Tính lại SHA-256 của M1.6/M1.8 payload, kiểm source locator M1.6 và đối chiếu
   amendment M1.5 với source/config tích hợp.

Đây là source review do Thanh thực hiện trên evidence của các owner khác và trên
Draft registry do Thanh tạo. Nó chưa phải Final independent QA sign-off của một
selected byte-identical package.

## Findings theo task

| Task | Evidence quan sát | Audit finding | Registry treatment |
| --- | --- | --- | --- |
| M1.1 | Report/config/code có; raw historical run provenance thiếu | Bounded Oracle evidence, reproduction unverified | `BLOCKED`, `oracle_upper_bound` |
| M1.2 | Core/config/tests/verification output có | Software verification có, independent rerun thiếu | `BLOCKED`, `integration_test`/`engineering_evidence` |
| M1.4 | `m1.4-003` có 307-file inventory | Metadata vẫn `PARTIAL`, data count 0, provenance review required | `BLOCKED`, `data_audit` |
| M1.5 | A001/A002 `APPROVED`; A001 khớp pairwise source/config | Thiếu exact amended package/split hashes và independent sign-off | `BLOCKED`, `governance` |
| M1.6 | `m1.6-001` có 5 docs/20 pages, report claim `PASS_AUDIT` | 3 payload hash mismatch, 5 source PDF absent, full-corpus scope unverified | `BLOCKED`, `data_audit` |
| M1.7 | 14 registry events, 14 trace rows và 16 issues | Post-merge findings đã ghi; chưa chọn/hash Final package | `BLOCKED`, `governance` |
| M1.8 | `m1.8-001` có 4/4 payload hash hợp lệ | Threshold provisional; M2.3/G1 scope decision pending | `BLOCKED`, `calibration` |
| M1.9 | Checklist/matrices/pre-review có | Tài liệu chưa refresh sau merges; official G1 `NOT_RUN` | `BLOCKED`, `governance` |
| M1.10 | Current progress report có | Draft còn mô tả pre-merge state; Final G1/M1 closure chưa đạt | `BLOCKED`, `governance` |

## Trace samples

### M1.1 Oracle

`QPAF-M1_1-ORC-001` trace được tới code mới, config và report tham chiếu. Không
trace được original run ID/command/commit, exact query/split/cache hashes hoặc
per-query reproduction; report cũng không định danh evaluation unit của
`nDCG@10`. Vì vậy không cấp `PASS`; xem `M17-ISS-006`.

### M1.2 method core

`QPAF-M1_2-MTH-001` trace được tới commit `7a758e3...`, code, config và handoff
verification. Scope chỉ là synthetic method-core correctness. Independent rerun
vẫn thiếu; xem `M17-ISS-007`. Không có learned QPAF-vs-QARF result.

### M1.4–M1.8 gate chain

- M1.4: byte-trace được `m1.4-003`, nhưng metadata tự giới hạn là `PARTIAL`.
- M1.5: A001 semantic reconciliation được source inspection hỗ trợ; A002 và
  package identity chưa đủ để independent sign-off.
- M1.6: engine tests pass, nhưng evidence package không byte-identical với hash
  manifest và source locator không resolve.
- M1.8: package hash hợp lệ; numerical calibration chưa thực hiện.

Do đó M1.7 chỉ có thể ghi reconciliation Draft; xem `M17-ISS-011`–`M17-ISS-016`
cùng các finding lịch sử còn mở.

## Registry/protocol consistency

- Registry status chỉ dùng vocabulary đã frozen trong historical run policy.
- Oracle/software/engineering/governance claims được tách riêng.
- Non-applicable field dùng `NA`; historical missing dùng `UNKNOWN` hoặc
  `NOT_RECORDED` và issue; known future dependency dùng `PENDING`.
- Exact split dùng `split_id`/`split_sha256`; future result-bearing authorization
  phải bind một immutable authorization manifest/hash chứa toàn bộ run contract.
- Không có `AUTHORIZED`/`STARTED`; protocol vẫn ghi
  `execution_authorized=false`.
- Amendment ledger được tham chiếu nhưng chưa được coi là Final binding cho đến
  khi exact package/split hashes và independent review được ghi nhận.
- Mọi current-state update dùng event/trace mới trỏ `supersedes_event_id`; các
  row ngày 27/09 không bị sửa hoặc xóa.

## Open issues và bước tiếp theo

`issue_log.csv` hiện có 16 finding. Sáu finding `M17-ISS-011`–`M17-ISS-016`
ghi riêng trạng thái sau merge. Thứ tự đóng hợp lệ:

Các finding lịch sử `M17-ISS-001` và `M17-ISS-003` đã có evidence mới thay đổi
tình trạng ban đầu, nhưng chưa được coi là closed: phần còn thiếu được tách rõ
thành `M17-ISS-011`, `M17-ISS-013` và `M17-ISS-014` để không rewrite lịch sử.

1. Phát phát hành immutable amended-protocol identity và exact A002 split hashes;
   Thanh recheck trước khi ghi independent decision.
2. Khương phát hành M1.4 revision đủ data/provenance và M1.6 revision mới có
   source locator cùng payload hashes hợp lệ.
3. Phát + Khương chốt bằng governance record việc M1.8 provisional có đủ cho G1
   hay phải calibration trước gate.
4. Thanh append closure/review events, refresh traceability và re-audit.
5. Phát refresh G1/R1 trên một selected immutable commit và tổ chức First Review.
6. Chỉ sau fix/recheck và Technical Sign-off mới tạo Final QA sign-off.

## Draft decision

**`M1.7_DRAFT_RECONCILED__M1.7_FINAL_BLOCKED`**

Quyết định này xác nhận chất lượng cấu trúc Draft, không đóng M1.7, không mở
execution và không thay thế G1.
