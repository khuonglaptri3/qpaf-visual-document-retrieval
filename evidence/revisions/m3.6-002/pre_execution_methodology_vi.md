# M3.6 — Cơ sở phép đo GPU trước execution

Revision này tiếp nối, không sửa báo cáo CPU hoặc gói protocol review M3.6-001.
Khương yêu cầu chạy gói đã trình bày và báo kết quả: “Chạy đi  rồi báo cáo kết quả
về đây nhớ deepsearch trước khi làm”. Đây là authorization cho resource benchmark
label-free đã trình bày: 20 warmup, 1.122 query measured, 3 passes, best checkpoints,
FP64, page ranking, Modal A10; không training/model selection/test quality metrics.
172 held-out IDs chỉ được dùng text và cached scores cho phép đo tài nguyên.

## Deepsearch và kiểm chứng

TinyFish deep research `01a16430-2260-7736-a7b0-ce923d0b5f8c` hoàn tất sau 505 giây
trước GPU execution. Báo cáo cung cấp 46 links; các gợi ý được kiểm tra với nguồn
gốc và implementation hiện tại, không được coi tự động là authority.

| Quyết định | Cơ sở gốc và giới hạn |
| --- | --- |
| Đồng bộ trước wall timer và sau GPU work; báo CUDA events riêng | [PyTorch CUDA semantics 2.11](https://docs.pytorch.org/docs/2.11/notes/cuda.html) và [benchmark tutorial](https://docs.pytorch.org/tutorials/recipes/recipes/benchmark.html). Dùng một default stream, không concurrent requests. |
| `.eval()` và `inference_mode()` | [PyTorch inference mode 2.11](https://docs.pytorch.org/docs/2.11/generated/torch.autograd.grad_mode.inference_mode.html). Không gọi optimizer/backward. |
| CPU/GPU parity <=1e-7 là gate dự án | [PyTorch numerical accuracy 2.11](https://docs.pytorch.org/docs/2.11/notes/numerical_accuracy.html) không hứa bitwise equality xuyên nền tảng. Sai số vượt ngưỡng vẫn phải stop theo protocol, không tự nới ngưỡng. |
| Reset allocator peak trước load model trong mỗi process | [reset_peak_memory_stats](https://docs.pytorch.org/docs/2.11/generated/torch.cuda.memory.reset_peak_memory_stats.html). Peak bao gồm model, parity, warmup và measured live tensors; reserved báo riêng. CUDA context/driver nằm ngoài tensor allocator metric. |
| Thread env đặt trước process; Torch threads=1 trước ops | [PyTorch threading environment](https://docs.pytorch.org/docs/2.11/threading_environment_variables.html). Không dùng CPU environment đã pin để cài CUDA. |
| Timeout/retries/container limits được chỉ định tường minh | [Modal timeouts](https://modal.com/docs/guide/timeouts), [retries](https://modal.com/docs/guide/retries), [resource limits](https://modal.com/docs/guide/resources). Function timeout 900s, startup120s; watchdog local900s gồm build và stop app; no auto retry. |
| Pin base OCI digest, package versions, bind resolved image ID và bundle hash trước invocation | [Modal Image](https://modal.com/docs/reference/modal.Image). [Named image](https://modal.com/docs/guide/named-images) là tên mutable, không tự bảo đảm bất biến; ghi resolved image ID. Source và payload allowlist được copy vào image, không mount repository root. |

Primary latency là median trên 1.122 per-query medians, mỗi query có 3 measured
passes. Báo p95 trên các per-query medians và per-pass p50/p95. P95 này không phải
service tail dưới concurrent load. Ba passes/20 warmups là quyết định kỹ thuật và
protocol dự án; không gán cho paper. Validation parity chạy trước 20 warmups và
có thể làm nóng thêm thiết bị; cold-start được báo riêng. Timer primary bao gồm
instrumentation đồng bộ/CUDA events và release tensors, nên là phép đo thận trọng
của đường eager hiện tại. CUDA event interval có thể chứa khoảng trống do Python
và validation đồng bộ trong model; không gọi đó là tổng kernel-only time.

## Paper liên quan và điều không được suy ra

- [Wang, Zheng, Wang 2018](https://arxiv.org/abs/1810.13103) nghiên cứu late fusion
  thích ứng query từ score curves và có neural variant. Đây là tiền lệ trực tiếp
  cho ý tưởng, không xác nhận gate 13 features hoặc hiệu quả ViDoSeek hiện tại.
- [Bruch, Gai, Ingber](https://arxiv.org/abs/2210.11934) phân tích convex combination
  và RRF trong hybrid retrieval. Một trọng số CC không phải learned query/page
  gate; paper này không chứng minh QPAF vượt baseline.
- [QuARI 2025](https://arxiv.org/abs/2505.21647) dùng query-specific feature-space
  transformation cho retrieval. Khác score fusion hiện tại; không gọi là phương
  pháp gần nhất hoặc dùng kết quả của paper làm bằng chứng QPAF.
- [Santhanam et al. 2022](https://arxiv.org/abs/2212.01340) đề nghị đánh giá IR kèm
  latency, hardware và cost. Không cung cấp ngưỡng 10ms/1,50GiB của dự án.
- [Cawley & Talbot 2010](https://www.jmlr.org/papers/v11/cawley10a.html) giải thích
  selection bias khi chọn mô hình và đánh giá trên cùng validation. Benchmark
  resource không tạo quality confirmation hoặc G2 decision.

Loại khỏi synthesis: gợi ý bỏ parity gate khi fail; khẳng định CC là query-adaptive;
giả định 172 test IDs đã dùng để chọn checkpoint; lời khuyên named image tự khóa
version; quy tắc một số lượng warmup/iterations duy nhất cho mọi loại benchmark.
Không có thay đổi architecture/checkpoint/threshold dựa trên kết quả resource.

## Chi phí và stop

[Modal pricing](https://modal.com/pricing) kiểm ngày22/10/2026: A10
0,000306 USD/s; CPU0,0000131 USD/core/s; RAM0,00000222 USD/GiB/s.
Một container2cores/4GiB,900s tương ứng allocated compute0,306972USD.
Budget mục tiêu0,50USD bao gồm build; timeout/watchdog/no retries giới hạn công
việc nhưng không phải hard cap hóa đơn của nhà cung cấp.
[Modal budgets](https://modal.com/docs/guide/budgets) và
[billing](https://modal.com/docs/guide/billing) không cung cấp per-function hard
dollar cap. Không thay đổi budget/account settings của người dùng.
Build commands có timeout240s/90s, không GPU; ghi tổng elapsed, image ID, packages
và actual execution telemetry. Không gọi allocated-rate estimate là hóa đơn.
Nếu init, parity, hash, GPU/runtime, output namespace hoặc resource integrity
không hợp lệ thì giữ failed artifact; không retry bằng namespace mới để cứu run.
