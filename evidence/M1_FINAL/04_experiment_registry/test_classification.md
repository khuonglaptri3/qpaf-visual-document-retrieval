# M1.7 Test and Evidence Classification — Draft v1

**Status:** `DRAFT_NOT_FROZEN`
**Owner:** Thanh
**Source vocabulary:** `../02_protocol/run_policy.md`

## Experiment classes

| `experiment_class` | Ý nghĩa | Claim tối đa |
| --- | --- | --- |
| `governance` | Protocol, registry, gate, amendment, report | Governance state only |
| `unit_test` | Kiểm một hàm/module với fixture kiểm soát | Software correctness |
| `integration_test` | Kiểm nhiều module/interface cùng nhau | Integrated software behavior |
| `smoke_test` | Kiểm bounded path có thể khởi chạy/kết thúc | Operational feasibility |
| `engineering_probe` | Probe tài nguyên, compatibility hoặc feasibility | Engineering observation |
| `calibration` | Chọn/kiểm threshold trước result-bearing run | Calibration evidence only |
| `data_audit` | Identity, hash, collision, split, qrel, coverage | Data-integrity statement |
| `score_extraction` | Tạo score/cache bằng retriever frozen | Engineering artifact; chưa phải method result |
| `oracle_upper_bound` | Dùng label để đo headroom/upper bound | Oracle upper bound only |
| `learned_training` | Fit learned gate trên train data | Training evidence, không tự là final result |
| `learned_evaluation` | Evaluate frozen checkpoint/config | Scientific result trong đúng split/protocol |
| `ablation` | One-factor removal/change đã preregister | Bounded causal comparison |
| `external_evaluation` | Evaluate trên sealed external benchmark | External generalization evidence |
| `system_test` | End-to-end application/reload/performance | System evidence |

## Evidence classes

| `evidence_class` | Dùng cho | Không được suy diễn thành |
| --- | --- | --- |
| `governance_record` | Protocol, registry, gate, report | Scientific result hoặc execution authorization |
| `non_scientific` | Fixture/demo/unit evidence | Corpus result |
| `engineering_evidence` | Audit, cache, smoke, calibration | Learned-method improvement |
| `scientific_upper_bound` | Oracle upper bound | Deployable learned performance |
| `scientific_result` | Valid frozen learned/ablation/external evaluation | Claim ngoài protocol/split đã review |
| `system_evidence` | E2E/reload/latency/memory/application behavior | Retrieval-quality claim nếu không có evaluation |

## Mapping bắt buộc

- `oracle_upper_bound` → `scientific_upper_bound` và
  `result_claim_scope=oracle_upper_bound`.
- `unit_test`, `integration_test`, `smoke_test`, `engineering_probe` →
  `non_scientific` hoặc `engineering_evidence`.
- `data_audit`, `score_extraction`, `calibration` → `engineering_evidence`.
- `governance` → `governance_record`.
- `learned_evaluation`, `ablation`, `external_evaluation` chỉ dùng
  `scientific_result` khi protocol, data, config, commit, output, metric và
  independent review đều hợp lệ.
- `system_test` → `system_evidence` trừ khi có một evaluation record riêng.

## Registry status

Chỉ dùng: `PLANNED`, `AUTHORIZED`, `STARTED`, `PASS`, `FAIL`, `BLOCKED`,
`KILLED`, `NOT_RUN`, `SUPERSEDED`.

`PARTIAL`, `PREPARED`, `VERIFIED`, `ACCEPTED` hoặc mô tả nguồn được giữ ở
`source_status`/`review_status`; chúng không phải `registry_status`. Dependency
thiếu dùng `BLOCKED`, không dùng `FAIL`. Result âm hợp lệ dùng outcome/metric và
claim wording; không tự đổi thành technical failure.

## Ranh giới hiện tại

- M1.1 là Oracle feasibility/reproduction-unverified: không phải learned result.
- M1.2 là method-core software verification trên synthetic fixture: không phải
  QPAF vượt QARF trên corpus thật.
- M1.4/M1.6/M1.8 là engineering/data evidence.
- M1.5/M1.7/M1.9/M1.10 là governance records.
- Draft này không chứa `AUTHORIZED`, `STARTED` hoặc learned scientific result.
