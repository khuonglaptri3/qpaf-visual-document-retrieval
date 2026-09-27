# M1.7 Draft Evidence Audit

**Reviewer:** Thanh — Experiment Governance / Independent QA
**Reviewed:** 27/09/2026
**Audit scope:** `DRAFT_SOURCE_INSPECTION_NOT_FINAL_QA`
**Package status:** `DRAFT_NOT_FROZEN`
**Execution authorization:** `CLOSED`

## Kết luận

M1.7 Draft đã có schema, controlled vocabulary, naming, append-only policy,
current-state registry, traceability matrix và issue log. Các claim boundary
được giữ đúng: M1.1 là Oracle upper bound; M1.2 là synthetic software evidence;
không có learned scientific result hoặc authorization event.

M1.7 **chưa thể Final/Freeze**. Active NEW protocol chưa được adopt; M1.4 thiếu
actual assets; M1.6 chưa chạy; M1.8 chưa calibration; exact split/cache hashes và
selected immutable G1 package chưa tồn tại. Kết quả audit tổng thể là
`DRAFT_COMPLETE_FINAL_BLOCKED`, không phải PASS của M1.7/G1.

## Phạm vi đã kiểm

1. Đối chiếu status vocabulary, experiment/evidence class và required fields với
   `../02_protocol/run_policy.md`.
2. Đối chiếu dataset/split/metric/seed fields với các policy M1.5 được import.
3. Kiểm current repository evidence cho M1.1, M1.2 và M1.4–M1.10.
4. Kiểm chuỗi `Experiment → Method → Config → Commit → Data/Hash → Output → Review`
   trong `traceability_matrix.csv`.
5. Ghi mọi missing/unknown/adoption gap vào `issue_log.csv` với owner và closure
   criterion; không suy đoán giá trị lịch sử.

Đây là source review do Thanh thực hiện trên evidence của các owner khác và trên
Draft registry do Thanh tạo. Nó chưa phải Final independent QA sign-off của một
selected byte-identical package.

## Findings theo task

| Task | Evidence quan sát | Audit finding | Registry treatment |
| --- | --- | --- | --- |
| M1.1 | Report/config/code có; raw historical run provenance thiếu | Bounded Oracle evidence, reproduction unverified | `BLOCKED`, `oracle_upper_bound` |
| M1.2 | Core/config/tests/verification output có | Software verification có, independent rerun thiếu | `BLOCKED`, `integration_test`/`engineering_evidence` |
| M1.4 | Audit files/hash/gap log có | `PARTIAL`; actual research assets thiếu | `BLOCKED`, `data_audit` |
| M1.5 | Historical protocol bytes/hash valid | Active adoption và loss-contract resolution thiếu | `BLOCKED`, `governance` |
| M1.6 | Schema/report tồn tại | Header-only; real corpus audit `NOT_RUN` | `BLOCKED`, `data_audit` |
| M1.7 | Bảy Draft deliverables hiện có | Chưa bind adopted protocol/snapshot; chưa Final | `PLANNED`, `governance` |
| M1.8 | OCR/namespace Draft có | Chưa sample/calibration/numerical threshold | `BLOCKED`, `calibration` |
| M1.9 | Checklist/matrices/pre-review có | Preparation only; official G1 `NOT_RUN` | `BLOCKED`, `governance` |
| M1.10 | Current progress report có | Draft; Final G1/M1 closure chưa đạt | `BLOCKED`, `governance` |

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

M1.4/M1.5/M1.6/M1.8 có đường dẫn current-state nhưng lần lượt partial,
historical-not-adopted, not-run và uncalibrated. Do đó M1.7 chỉ có thể ghi Draft
truthfully; xem `M17-ISS-001`–`M17-ISS-005` và `M17-ISS-009`.

## Registry/protocol consistency

- Registry status chỉ dùng vocabulary đã frozen trong historical run policy.
- Oracle/software/engineering/governance claims được tách riêng.
- Non-applicable field dùng `NA`; historical missing dùng `UNKNOWN` hoặc
  `NOT_RECORDED` và issue; known future dependency dùng `PENDING`.
- Exact split dùng `split_id`/`split_sha256`; future result-bearing authorization
  phải bind một immutable authorization manifest/hash chứa toàn bộ run contract.
- Không có `AUTHORIZED`/`STARTED`; imported protocol vẫn ghi
  `execution_authorized=false`.
- Active protocol reference giữ `PENDING`; Draft không giả mạo old M1.7 hashes
  hoặc coi historical import là NEW adoption.

## Open issues và bước tiếp theo

`issue_log.csv` là source of truth cho 10 finding mở/blocking. Thứ tự đóng hợp lệ:

1. Phát + Thanh giải quyết/adopt active M1.5 successor hoặc amendment.
2. Khương cung cấp selected M1.4 revision, exact data/split/cache evidence, real
   M1.6 audit và calibrated M1.8 package.
3. Thanh append Final registry binding, refresh hashes/traceability và re-audit.
4. Cả nhóm chọn/hash package rồi tiến hành G1 First Review.
5. Chỉ sau fix/recheck và Technical Sign-off mới tạo Final QA sign-off.

## Draft decision

**`M1.7_DRAFT_COMPLETE__M1.7_FINAL_BLOCKED`**

Quyết định này xác nhận chất lượng cấu trúc Draft, không đóng M1.7, không mở
execution và không thay thế G1.
