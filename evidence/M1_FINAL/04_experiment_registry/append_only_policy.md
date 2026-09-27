# M1.7 Append-Only Registry Policy — Draft v1

**Status:** `DRAFT_NOT_FROZEN`
**Owner:** Thanh
**Applies to:** `experiment_registry.csv`, status events and linked evidence

## Core rule

Mỗi row là một event bất biến. Khi status, evidence, review hoặc claim thay đổi,
append row mới với `registry_event_id` mới và cùng `experiment_id`. Không sửa row
cũ để làm lịch sử trông hoàn chỉnh hơn.

## Event lifecycle

1. `REGISTERED`: ghi purpose/class/dependency; thường là `PLANNED` hoặc `BLOCKED`.
2. `AUTHORIZATION_RECORDED`: chỉ sau exact invocation approval; status
   `AUTHORIZED` và đủ commit/data/config/namespace/resource fields.
3. `ATTEMPT_RECORDED`: append trước/đầu invocation; status `STARTED`.
4. `VERIFICATION_RECORDED`: append outcome sau hash/semantic checks.
5. `ACCEPTANCE_RECORDED`: `PASS` chỉ khi class-specific criteria và review đạt.
6. `SUPERSESSION_RECORDED`: row cũ giữ nguyên; row mới trỏ
   `supersedes_event_id` và giải thích phạm vi bị thay thế.

Draft hiện tại chỉ dùng `REGISTERED`/`STATUS_RECORDED`; không có authorization.

## Correction policy

- Lỗi chính tả không ảnh hưởng semantics trước first commit có thể sửa trong
  Draft. Sau khi row được commit/review/hash, correction phải append event mới.
- Correction ghi old/new value, lý do, người tạo, reviewer và issue liên quan.
- Không đổi experiment class, evidence class, dataset, split, config, seed,
  candidate hoặc claim scope trên row cũ.
- Duplicate event ID là lỗi; duplicate experiment ID là hợp lệ khi biểu diễn
  event sequence.
- Row bị thay thế không bị xóa và không được dùng làm current state nếu đã có
  valid later event trỏ supersession.

## Missing values

Không để cell trống. `UNKNOWN` và `NOT_RECORDED` bắt buộc trỏ issue. `PENDING`
phải có owner/closure criterion. `NA` chỉ dùng khi field thật sự không áp dụng.
Không backfill một giá trị đoán từ summary hoặc filename.

## Split và authorization binding

- `split_id` và `split_sha256` là field bắt buộc của schema. Result-bearing
  record phải bind exact split manifest; nếu split chưa materialize thì giữ
  `PENDING`, còn provenance lịch sử không recover được thì dùng `UNKNOWN` và
  trỏ issue.
- Trước mọi result-bearing invocation, event `AUTHORIZATION_RECORDED` phải bind
  `authorization_manifest_ref` và `authorization_manifest_sha256` tới một
  immutable manifest. Manifest là nguồn canonical cho authorization; các field
  ngắn trong registry chỉ là summary phục vụ đọc nhanh.
- Manifest authorization phải ghi exact Git state; data, cache, split và qrels
  locator/hash; config; method; seed; candidate definition; metric version và
  evaluation unit; command/runtime/hardware; wall-time và cost cap; stop
  conditions/required markers; output namespace; số invocation/retry được duyệt;
  approver, exact approval text và timestamp; cùng policy cho tracked/dirty state.
- Event không dẫn tới result-bearing execution dùng `NA`. Dữ liệu authorization
  lịch sử không recover được dùng `UNKNOWN` và issue; không dựng lại approval từ
  suy đoán.

## Artifact preservation

- Output/run namespace create-once và giữ cả failed/killed attempt.
- Retry có run ID, attempt number và authorization mới; `retry_of` phải chứa
  exact prior `run_id`, không dùng mô tả tự do.
- Hash là hash exact file được review, không hash thư mục hoặc tự đưa manifest
  vào chính digest của nó.
- Payload ngoài Git phải có immutable locator, manifest, byte size và SHA-256.
- Không xóa historical evidence để làm audit mới; tạo revision/snapshot mới.

## Review và freeze

M1.7 Final chọn một commit/snapshot, bind active protocol hash và ghi reviewer.
Sau freeze, schema/naming/classification change cần approved amendment và
governance event. `qa_signoff.md` là Final-G1 artifact riêng, chỉ tạo sau issue
recheck và không được suy ra từ việc Draft tests pass.
