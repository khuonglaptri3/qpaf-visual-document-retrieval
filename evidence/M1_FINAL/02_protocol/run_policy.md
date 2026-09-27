# Run and Change-Control Policy — Frozen v1

> **Trạng thái:** `FROZEN_M1_5_V1_RECONCILED_WITH_M1_7_DRAFT`  
> **Current authorization:** `ALL_RESULT_BEARING_EXECUTION_CLOSED`

## 1. State model và registry mapping

Preparation, authorization, execution, verification và acceptance là các quyết định
tách biệt. M1.7 registry dùng exact `registry_status` vocabulary bên dưới; trạng thái
gốc/chi tiết được giữ nguyên trong `source_status`.

| Workflow evidence state | `registry_status` | Ý nghĩa |
|---|---|---|
| Planned hoặc Prepared | `PLANNED` | Có trong roadmap/protocol hoặc package đã chuẩn bị; chưa được phép chạy |
| Authorized | `AUTHORIZED` | Một exact invocation đã được duyệt nhưng chưa bắt đầu |
| Executed/attempt started | `STARTED` | Execution đã bắt đầu hoặc create-once attempt đã consumed |
| Verified và accepted complete | `PASS` | Class-specific criteria và artifact-level verification đều pass |
| Completed nhưng vi phạm criterion | `FAIL` | Run/review hoàn tất với failed criterion |
| Dependency/input/approval ngăn completion | `BLOCKED` | Không được diễn giải thành negative scientific result |
| Preregistered stop kết thúc path | `KILLED` | Stop condition đã chấm dứt path |
| Chủ động không chạy | `NOT_RUN` | Có reason và claim limitation |
| Bị version mới thay thế | `SUPERSEDED` | Record cũ vẫn giữ nguyên |

`Prepared`, `Executed`, `Verified` và `Accepted` không được tự ý thêm thành
`registry_status`; chúng nằm trong `source_status`, event sequence, evidence links và
review/claim fields. Không trạng thái nào tự động suy ra trạng thái kế tiếp.

## 2. Classification bắt buộc

Mỗi experiment dùng đúng một `experiment_class` từ M1.7:

- `governance`, `unit_test`, `integration_test`, `smoke_test`;
- `engineering_probe`, `calibration`, `data_audit`, `score_extraction`;
- `oracle_upper_bound`, `learned_training`, `learned_evaluation`;
- `ablation`, `external_evaluation`, `system_test`.

Mỗi event cũng dùng đúng một `evidence_class`:

- `governance_record`, `non_scientific`, `engineering_evidence`;
- `scientific_upper_bound`, `scientific_result`, `system_evidence`.

Exact definitions, ID codes và claim boundaries nằm trong
[test_classification.md](../04_experiment_registry/test_classification.md). Engineering,
preflight và synthetic evidence không được trình bày như scientific result. Oracle
evidence phải dùng `oracle_upper_bound` / `scientific_upper_bound` và
`result_claim_scope=oracle_upper_bound`.

## 3. Required authorization record

Trước một result-bearing invocation, `REGISTERED`/`AUTHORIZED` events phải bind:

- `experiment_id`, `registry_event_id`, task/owner, classification và purpose;
- exact Git commit và allowed tracked/dirty state;
- dataset/revision/data/cache/split/qrels hashes;
- resolved config hash và semantic parent config;
- method, seed, candidate contract, metric version và evaluation unit;
- actor và exact command;
- runtime image/software, hardware/GPU, batch/resource limits;
- wall-time và cost cap;
- approved invocation count và retry count;
- create-once output namespace;
- stop conditions và required failure/success markers;
- approver, approval text và timestamp.

ID phải tuân theo
[experiment_naming_rules.md](../04_experiment_registry/experiment_naming_rules.md).
CSV fields và event lineage phải tuân theo
[experiment_registry.csv](../04_experiment_registry/experiment_registry.csv) và
[append_only_policy.md](../04_experiment_registry/append_only_policy.md). Reviewed row
không để cell trống: dùng đúng `NA`, `PENDING`, `UNKNOWN` hoặc `NOT_RECORDED`; hai giá
trị cuối phải có issue record.

Roadmap, frozen protocol hoặc successful preflight không phải execution authorization.

## 4. Default execution rules

- Result-bearing runs dùng một reviewed tracked commit; record mọi permitted untracked
  state.
- Output namespace create-once; accepted/failed outputs không overwrite.
- Default automatic retries = `0`. Fresh attempt cần reviewed reason, namespace và
  authorization mới.
- `_ATTEMPTED.json` được tạo trước label access/result work; `_SUCCESS.json` chỉ sau
  semantic/count/hash validation.
- Failure/interruption vẫn phải có immutable marker, manifest/telemetry hiện có và
  consumed-attempt record; registry append `FAILED`, `BLOCKED` hoặc `KILLED` event phù hợp.
- QARF seed `20260820` chạy trước; QPAF chỉ sau accepted independent QARF review và
  separate authorization.
- Remaining seeds chỉ chạy sau one-seed development gate decision.
- Confirmation chỉ mở sau method/baseline/checkpoint-selection freeze.
- External labels chỉ mở sau checkpoint/config freeze và separate approval.

## 5. Stop conditions

Stop/fail closed khi có bất kỳ điều nào:

- source/config/data/hash drift;
- split overlap, candidate-key mismatch, missing query hoặc qrels leakage;
- coverage `<0.95` hoặc có query không positive candidate;
- NaN/Inf, invalid metric, broken checkpoint reload;
- resource, timeout, memory, telemetry hoặc cost cap violation;
- output namespace đã tồn tại ngoài declared resume contract;
- actor/invocation/retry/approval mismatch.

Không sửa threshold, split, candidate depth hoặc seed sau khi thấy outcome để cứu run.

## 6. Experiment record and artifacts

Mỗi accepted result phải trace được:

`Experiment ID → Method → Resolved config → Git commit → Data/split/cache hashes →
Run manifest → Predictions/checkpoint/telemetry → Metrics/bootstrap → Independent review`.

Registry tối thiểu ghi event type, start/end, actor, hardware, cost evidence,
attempt/retry count, failure reason, artifact paths + SHA-256, verifier, verification
command, outcome và claim boundary. Status change tạo event mới; không sửa row cũ.

## 7. Git and preservation rules

- Chỉ dùng explicit changed-path allowlist; không dùng `git add -A`.
- Không xóa/migrate historical runs trong task protocol.
- Preserve unrelated tracked/untracked/ignored files và large score payloads.
- Historical source snapshots/tests giữ byte-stable; current-state checks được thêm
  versioned thay vì rewrite provenance.
- Before freeze/run, inspect full allowlisted diff và record clean tracked commit.

## 8. Change control after freeze

Mọi thay đổi sau freeze phải được append vào
[protocol_amendments.md](protocol_amendments.md) với:

- old/new value và affected files;
- reason và evidence;
- leakage/fairness/statistical/claim impact;
- affected runs và rerun requirement;
- requester, reviewer/approver, date và status.

Không amendment nào có hiệu lực trước approval. Evidence sinh trước amendment giữ
nguyên protocol version cũ và không được silently pool với evidence version mới.
Mỗi approved amendment/gate decision được append vào registry dưới
`experiment_class=governance` và `evidence_class=governance_record`.
