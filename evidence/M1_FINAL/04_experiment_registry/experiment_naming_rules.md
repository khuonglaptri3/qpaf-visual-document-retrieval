# M1.7 Experiment Naming Rules — Draft v1

**Status:** `DRAFT_NOT_FROZEN`
**Owner:** Thanh
**Execution:** Closed

## 1. Experiment ID

Canonical form:

```text
QPAF-<TASK>-<CLASS>-<SEQ>
```

- `<TASK>` dùng milestone với dấu chấm đổi thành `_`, ví dụ `M1_7`.
- `<CLASS>` là mã ba chữ hoa đã đăng ký: `ORC`, `MTH`, `AUD`, `PRO`, `COL`,
  `REG`, `OCR`, `GAT`, `RPT`; mã mới phải được thêm bằng governance event.
- `<SEQ>` là số ba chữ số tăng đơn điệu trong cùng task/class.
- ID không đổi khi status thay đổi. Retry, verification và acceptance append
  event mới cho cùng experiment ID.

Ví dụ: `QPAF-M1_1-ORC-001`, `QPAF-M1_7-REG-001`.

## 2. Registry event ID

```text
QPAF-REG-<YYYYMMDD>-<NNNN>
```

Ngày là ngày UTC record được append; sequence bốn chữ số không tái sử dụng.
`registry_event_id` nhận diện row bất biến, khác với `experiment_id` nhận diện
luồng công việc. Status transition luôn có event ID mới.

## 3. Run ID và output namespace

Result-bearing invocation, nếu sau này được authorization, dùng:

```text
RUN-<experiment_id>-<YYYYMMDDTHHMMSSZ>-A<NN>
artifacts/<experiment_id>/<run_id>/
```

- `A01` là first authorized attempt; retry dùng `A02` trở lên và phải có
  `retry_of` bằng exact prior `run_id`, cùng authorization mới trong registry.
- Namespace là create-once: nếu đã tồn tại thì invocation dừng, không overwrite.
- Preparation/governance record không có run dùng controlled value `NA`.
- Historical run không recover được ID dùng `UNKNOWN` và một issue; không tự đặt
  ID mới như thể đó là ID gốc.

## 4. Split và authorization manifest

- `split_id` nhận diện exact split manifest; `split_sha256` hash exact bytes của
  manifest đó. Không dùng tên split chung chung thay cho hai field này.
- Result-bearing authorization phải trỏ `authorization_manifest_ref` và hash
  exact file tại `authorization_manifest_sha256`.
- Authorization manifest bind đầy đủ provenance, metric/evaluation contract,
  resource limits, stop conditions và approval record theo
  `append_only_policy.md`; registry không lặp lại contract dài bằng text tự do.
- `authorization_ref` là human-readable approval locator. Nó không thay thế
  immutable manifest/hash.

## 5. Placeholder có kiểm soát

| Token | Dùng khi | Yêu cầu |
| --- | --- | --- |
| `NA` | Field không áp dụng cho class/event | Không được dùng để che dữ liệu đáng lẽ phải có |
| `PENDING` | Artifact/decision đã biết là bước tiếp theo nhưng chưa materialize | Phải có owner hoặc issue |
| `UNKNOWN` | Giá trị lịch sử có tồn tại nhưng chưa recover/verify | Bắt buộc có issue |
| `NOT_RECORDED` | Nguồn lịch sử không ghi field bắt buộc | Bắt buộc có issue |

Không dùng chuỗi rỗng, `TBD`, `maybe`, `done` hoặc status tự chế trong CSV.

## 6. Naming và claim boundary

- Oracle luôn dùng class `oracle_upper_bound`; không dùng `learned_evaluation`.
- Synthetic/unit/integration evidence không dùng `scientific_result`.
- Protocol/amendment/gate/report dùng `governance`/`governance_record`.
- Dataset/collision/split integrity dùng `data_audit`/`engineering_evidence`.
- `PASS` chỉ có nghĩa trong class đã khai báo; không suy ra M1/G1 PASS.

## 7. Freeze rule

Draft này có hiệu lực thiết kế, chưa phải frozen contract. M1.7 Final phải ghi
exact adopted protocol path/hash, selected package commit/hash và reviewer. Sau
freeze, mọi thay đổi naming tạo governance event/amendment; không rewrite file
hoặc row lịch sử để giữ nguyên ID/hash cũ.
