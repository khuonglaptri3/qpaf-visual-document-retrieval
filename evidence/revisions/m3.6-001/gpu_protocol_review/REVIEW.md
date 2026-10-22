# M3.6 — Gói review protocol GPU

**Trạng thái: PREPARED FOR PROTOCOL REVIEW, NOT EXECUTION.**

Đây là gói để chốt workload/phương pháp trước khi triển khai và review GPU
executor. Chưa có GPU invocation, immutable image hoặc execution authorization.
Không dùng gói này làm bằng chứng resource PASS.

## Workload cụ thể

Nguồn: các split ID đã seal trong M3.1. Chọn ID bằng ascending
`SHA256("qpaf-m36-label-free-resource-v1:" + query_id)`, tie theo `query_id`.
Không có labels hoặc model output trong selection.

| Vai trò | Warm-up | Measured | Tổng |
| --- | ---: | ---: | ---: |
| Train | 14 | 785 | 799 |
| Validation | 2 | 169 | 171 |
| Test | 4 | 168 | 172 |
| **Tổng unique** | **20** | **1.122** | **1.142** |

Warm-up và measured không giao nhau. IDs ở
[`gpu_workload.json`](gpu_workload.json); hashes của workload và plan nằm trong
[`package_hashes.json`](package_hashes.json). Phần preparation chỉ đọc ID files
và metadata/hash; chưa dùng test text/score để chạy benchmark.

**Cần chốt:** có cho phép đọc text + raw score đã cache của 172 test ID cho
phép đo label-free này hay không. Không deserialize/upload qrels test hoặc
development, không tính quality cho test, không fitting, tuning hoặc chọn
checkpoint. Nếu muốn giữ cả text/score test untouched, workload hiện tại không
được chạy; cần nguồn query khác hoặc amendment phù hợp.

## Đề xuất phép đo

- Giữ nguyên hai best checkpoints, seed, gate/source và float64. Kiểm hash và
  GPU-vs-pinned-CPU validation score parity trong `1e-7` trước timing.
- Một query mỗi lần, 20 warm-up/method, cùng 1.122 measured ID và cùng thứ tự;
  đề xuất 3 passes. Con số 3 là lựa chọn kỹ thuật cần review.
- Báo riêng CPU tensorization/features, H2D, GPU gate/fusion, D2H và page ranking.
  Dùng CUDA events cho device time và synchronized wall timer cho toàn đường
  fusion online. Không gộp loading/cold-start, disk I/O hoặc retriever extraction.
- Đề xuất gate `10 ms` áp dụng cho toàn bộ overhead fusion online sau khi raw
  retrieval scores ở RAM; báo thêm paired QPAF−QARF. Cần owner chốt định nghĩa
  này, không dùng riêng delta để che chi phí chung của cả hai method.
- Báo p50/p95 raw per-pass; median và p95 across per-query medians. Không gọi
  query-distribution p95 này là service-tail latency dưới tải.
- Reset peak CUDA stats, báo allocated/reserved peaks cùng baseline và scope;
  tách CPU RSS. Model/live fusion tensors thuộc scope; retrievers ngoài scope.
- Active pilot là page-level. Giữ page ranking như authorization hiện tại;
  document aggregation của ViMDoc là scope khác cần quyết định riêng.

Nguồn và sự khác nhau giữa literature/protocol/đề xuất kỹ thuật nằm trong
[`literature_and_methodology_vi.md`](../literature_and_methodology_vi.md).
Ngưỡng `20 / >=1000 / <=10ms / <1.50GiB / <=1e-7` đến từ protocol dự án.

## Hardware, runtime, budget đề xuất

Modal A10 × 1, CPU 2 physical cores, RAM 4 GiB, timeout 900 giây; một invocation,
không automatic retry. Python 3.13.7, Torch 2.11.0+cu126, FP64; cùng numerical
library versions như audit CPU. Manifest chi tiết:
[`gpu_review_plan.json`](gpu_review_plan.json).

Giá kiểm ngày 22/10/2026 từ [Modal](https://modal.com/pricing): allocated
GPU/CPU/RAM ở timeout ước tính **0,306972 USD**. Đề xuất budget **0,50 USD**;
image-build/lifecycle chưa được bound nên con số này **chưa là hard cost cap**.
Máy local có RTX 2050 4 GiB/driver 546.18 nhưng chưa chuẩn bị hay thử CUDA
runtime; task này không sửa driver hoặc môi trường CPU đã pin.

## Ba quyết định cần review

1. Workload label-free có 172 held-out query ID, với giới hạn access nêu trên.
2. Scope `10 ms`, page ranking và 3 measurement passes.
3. A10/runtime/budget đề xuất thay cho thay đổi driver/runtime máy local.

Sau khi protocol được chấp nhận mới hoàn thiện GPU executor, image bất biến,
exact command/commit, namespace create-once, stop conditions và cost enforcement.
Chỉ sau review các thành phần đó mới xin execution authorization theo
[`run_policy.md` §3](../../../M1_FINAL/02_protocol/run_policy.md).
