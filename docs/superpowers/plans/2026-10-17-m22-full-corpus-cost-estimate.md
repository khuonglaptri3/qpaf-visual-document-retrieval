# Dự trù chi phí tạo cache toàn ViDoSeek sau M2.2

**Ngày:** 2026-10-17. **Trạng thái:** Ước tính để lập ngân sách, chưa chạy full corpus.
Người dùng cho biết giới hạn billing hiện tại là **30 USD**. Chưa xác minh đó là
Workspace usage budget hay net spend limit, và chưa thay đổi thiết lập tài khoản.

## Phạm vi và giả định

- 5385 pages, tối đa 1142 queries, 6149670 query-page pairs.
- Giữ cấu hình M2.2 đã PASS: ColQwen2.5 float32, batch 2, tối đa 256 visual tokens;
  BGE-M3 float32; model/base/processor revisions không đổi.
- Encode tài liệu một lần, giữ embeddings/cache; không encode lại cho từng query,
  seed hoặc lượt huấn luyện gate khi retriever/preprocessing không đổi.
- Full runner thuộc M2.8, cần sharding/checkpoint/resume; không nâng giới hạn hoặc
  dùng nguyên runner smoke M2.2 để chạy toàn corpus.
- Không nhân chi phí trọn smoke run với số trang: smoke có load, reference pass,
  kiểm tra và overhead không lặp lại cho mỗi nhóm trang ở full runner.

## Ngoại suy từ run PASS

Nguồn: `results/m2.2/RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01/remote/*/resources.json`.

Giá công bố tại thời điểm đọc: A10 0.000306 USD/s, CPU 0.0000131 USD/core/s,
RAM 0.00000222 USD/GiB/s. A10 + 4 physical CPUs + 32 GiB = 1.545984 USD/h,
chưa tính network/storage/region modifiers, nhiều container hoặc usage khác.

| Thành phần | Ngoại suy thời gian | Chi phí compute tuyến tính |
|---|---:|---:|
| Dense: page/query encoding và scoring | 2.97 phút | 0.076 USD |
| Visual: page encoding | 40.77 phút | Nằm trong tổng visual |
| Visual: query encoding | 1.21 phút | Nằm trong tổng visual |
| Visual: scoring tất cả cặp | 4.68 phút | Nằm trong tổng visual |
| Visual tổng | 46.67 phút | 1.202 USD |

Scoring ngoại suy từ 64 cặp rất nhỏ; throughput thực có thể khác nhiều theo batch,
độ dài query, kích thước ảnh, padding và I/O. Dense/OCR cũng chưa có mẫu đủ lớn
để coi đây là dự báo đáng tin cậy hay khoảng tin cậy thống kê.

## Ngân sách dự trù

Đặt **3–10 USD** cho một lượt chuẩn bị text và tạo cache ba kênh toàn ViDoSeek
với cấu hình trên, gồm khoảng dự phòng vận hành, OCR/CPU, I/O và sửa lỗi.
Đây là planning allowance, không phải hóa đơn đo thật hay hard cap đã cấu hình.
Không suy ra rằng 30 USD chắc chắn đủ toàn bộ dự án.

Nếu tăng độ phân giải từ 256 lên 768 visual tokens, đổi dtype/batch, thêm corpus,
chạy lại embeddings hoặc triển khai nhiều thí nghiệm, cần benchmark/dự toán mới.
Huấn luyện QARF/QPAF dự kiến học gate trên cache; không mặc định fine-tune retrievers.

Workspace usage budget tính trước credits; net spend limit tính sau credits.
Cần phân biệt hai giá trị khi xác định mục tiêu chỉ dùng phần credit miễn phí.
Chưa khởi chạy compute và chưa chỉnh budget trong lần lập dự toán này.

Nguồn: [Modal pricing](https://modal.com/pricing),
[budgets/spend limits](https://modal.com/docs/guide/budgets),
[báo cáo M2.2](../reports/2026-10-17-m22-retriever-smoke.md).
