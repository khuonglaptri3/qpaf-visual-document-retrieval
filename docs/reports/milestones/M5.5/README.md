# M5.5 — Chẩn đoán validation và đo tài nguyên GPU

Ngày: 27/10/2026. Owner: Khương. PR: [#45](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/pull/45).
Nhánh: `feature/m5-5-diagnostics`.

**Đã hoàn thành kỹ thuật R5-01/02/03/04. Nghiệm thu độc lập của Thanh vẫn PENDING.**
Đây là báo cáo hiện hành; các receipt CPU ghi GPU-deferred là snapshot bất biến
của lượt trước. Không sửa snapshot để biến nó thành kết quả GPU mới.

| Hạng mục | Kết quả hiện hành | Bằng chứng |
| --- | --- | --- |
| R5-01/02/03 | Tám hàng CPU, 171 query / 82.255 candidate; giữ nguyên kết quả | [Run CPU](../../../../results/m5.5/RUN-QPAF-M5_5-ABL-001-20261027T033016Z-A01/report.md) |
| Replay CPU | PASS đúng Python/thư viện gốc; 0 write/network/forbidden import/test-qrels attempt trong verifier | [Receipt mới](evidence/cpu-replay-005/verification.json) |
| R5-04 | Hai method đạt ngưỡng latency/CUDA theo protocol validation đã ghi | [Kiểm chứng timings thô](evidence/gpu-attempt-003/gpu-offline-verification.json) |
| Review kỹ thuật | Review độc lập bằng AI; các finding material có RED→GREEN | [Review cuối](evidence/final-engineering-review.md) |
| Human acceptance | PENDING; không tự gán chữ ký hoặc quyết định của Thanh | [Trạng thái](evidence/completion-status.json) |

## Số đo R5-04 mới

Run được khôi phục và kiểm chứng:
`RUN-QPAF-M5_5-SYS-001-20261027T143954Z-A03`.
Modal A10G, 2 physical CPU cores, RAM request/limit 5 GiB; Python3.13.7,
Torch2.11.0+cu126, FP64 eager, batch1, CPU một thread. Hai method chạy ở hai
process mới, cùng checkpoint seed20260820 đã freeze.

| Method | Median online ms/query | P95 của query medians | Peak CUDA allocated GiB | Peak CUDA reserved GiB |
| --- | ---: | ---: | ---: | ---: |
| QARF | 2.569362 | 2.649429 | 0.032428265 | 0.033203125 |
| QPAF | 2.4263995 | 2.49541425 | 0.032439709 | 0.033203125 |

Cả hai đạt median `<=10ms` và CUDA allocated `<1.50GiB`. Median ở đây là
median của 171 per-query medians qua sáu vòng. Online fusion gồm CPU feature,
H2D, gate/fusion, D2H và deterministic page ranking, sau khi cached scores đã
ở RAM; cold start, queue, file I/O và retriever extraction nằm ngoài số này.
[CSV 2.052 lượt đo](evidence/gpu-attempt-003/gpu-timings.csv) và
[dữ liệu gốc đầy đủ](evidence/gpu-attempt-003/recovered-gpu-result.json) giữ các
giai đoạn riêng, event p50/p95 và từng vòng.

Protocol có **20 warm-up events, sau đó 6 × 171 = 1.026 timed events/method**;
chỉ có **171 ID validation duy nhất**. Warm-up dùng 20 ID đầu và có overlap với
pool đo. Đây là diễn giải đếm lượt đo được ghi rõ dưới quyền tự quyết mà owner
đã giao; không phải thiết kế M3.6 với >=1.000 ID khác nhau. Không mở rộng sang
train/test, không train hoặc chạy lại retriever, không đổi QPAF-v1/baseline.

Parity trên toàn bộ 171 query/82.255 candidate: sai khác score tối đa
`4.44e-16`, weight tối đa `7.77e-16`, **0 khác biệt thứ hạng**; dưới tolerance1e-7.
Process RSS được báo riêng: QARF4.7573GiB, QPAF4.7039GiB theo giao diện trong
container. RSS/cgroup và [provider samples](evidence/gpu-attempt-003/provider-function-stats.json)
không phải bằng chứng peak RAM vật lý liên tục của host; không gộp chúng với CUDA.

## Nguồn gốc, khôi phục và kiểm chứng

Owner đã cho phép Modal/GPU và giao chi tiết trong phạm vi validation.
[Authorization A03](evidence/gpu-attempt-003/gpu-authorization.json),
[bundle manifest](evidence/gpu-attempt-003/gpu-bundle-manifest.json) và
[workload](evidence/gpu-attempt-003/gpu-workload.json) khóa nguồn/input/runtime.
GPU bundle không có qrels; reference được kiểm finite/coverage/hash trước run.

Có **ba GPU invocations**, không có automatic retry. A01 mất phản hồi ở input
plane; A02 bị BlobCreate401 khi xuất kết quả lớn từ restricted Function. A03 đo
thành công; bước đọc log ban đầu gặp provider rate limit. SDK observer1.6.2 đã
đọc lại **chính Call ID A03**, không chạy thêm GPU. Dữ liệu gzip/base64 được ghép
theo stream và khớp đầy đủ số chunk/byte/SHA256; sau đó verifier tính lại counts,
statistics, parity và verdict từ timings thô. [Biên nhận khôi phục](evidence/gpu-attempt-003/gpu-recovery-receipt.json).
Các `_FAILURE` client ban đầu được giữ nguyên; không tạo `_SUCCESS` giả cho chúng.

CPU được replay ở Python3.11.14/NumPy2.4.6/pandas3.1.0/PyArrow26.0.0 trên CPU-only
Modal bằng snapshot/asset đã pin. Release M4.2 là draft: chỉ dùng URL asset đọc
tạm thời; không chuyển GitHub token sang Modal hoặc lưu token/URL đó vào repo.
Không tạo run khoa học CPU mới. [Hash/check layout](evidence/bundle-validation.json)
và [manifest toàn task](evidence/bundle-manifest.json) ràng buộc artifact hiện hành.

Lỗi CI Ubuntu được tái hiện bằng Git maintenance thật; fixture giờ đợi maintenance
ở foreground trước khi xóa repository tạm. Test bắt được lỗi trước sửa và qua
sau sửa. Full suite mới nhất: **651 tests OK, 4 skipped**; [raw log](evidence/final-software-tests-framing.txt).
CI hiện hành có ở [PR checks](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/pull/45/checks)
và được ghi trong [workflow](evidence/workflow.md);
method-core riêng đã qua23 test không skip. Các lần kiểm tra môi trường lỗi cũng
được giữ log, không trình bày như lượt PASS.

## Kiểm lại và bàn giao

```powershell
python docs/reports/milestones/M5.5/evidence/verify_gpu_result.py --evidence-dir docs/reports/milestones/M5.5/evidence/gpu-attempt-003 --check-only
```

Lệnh trên chỉ đọc và tính lại kết quả đã lưu; không cần GPU/Modal. Xem
[bàn giao hiện hành](../../../06_handover/m5.5-cpu-results-and-gpu-handoff.md),
[spec](superpowers/spec.md), [plan](superpowers/plan.md) và
[workflow/provenance](evidence/workflow.md). Báo cáo CPU ban đầu được giữ nguyên
bytes tại [snapshot](evidence/archive-M5_5_Khuong-cpu.txt).

Thanh cần review độc lập protocol đếm lượt, receipts và kết quả rồi ghi nghiệm thu.
PR chưa merge. Ba minor còn để lại được ghi trong [review cuối](evidence/final-engineering-review.md):
verifier có thể tự decode log và kiểm per-pass stats; worker có thể kiểm reference
chặt hơn. Reviewer đã kiểm độc lập cả ba trên dữ liệu thực tế, không có finding material.
