# Tài liệu thiết kế và thực hiện theo Superpowers

Các thư mục ở đây tổ chức tài liệu theo quy ước Superpowers đang dùng trong repo.
Việc có tài liệu trong thư mục này không đồng nghĩa một skill/plugin đã được chạy,
hay một milestone đã được nghiệm thu.

## M2.2 — Chạy thử có kiểm soát ba retriever

**Trạng thái:** PASS kỹ thuật — đã chạy mẫu thật đủ ba kênh trên Modal.

Run được chọn: `RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01`.
Mẫu: 4 validation queries × 16 pages; ColQwen2.5 float32, batch 2.
Xem [báo cáo kết quả](reports/2026-10-17-m22-retriever-smoke.md) và
[bằng chứng m2.2-001](../../evidence/revisions/m2.2-001/README.md).

M2.2 xác nhận BM25, BGE-M3 và ColQwen2.5 hoạt động đúng trên cùng mẫu nhỏ,
đồng thời đo tài nguyên để chuẩn bị cho các bước sau.

Đọc các tài liệu theo thứ tự:

| Thứ tự | Tài liệu | Câu hỏi được giải đáp |
|---|---|---|
| 1 | [Đặc tả M2.2](specs/2026-10-17-m22-retriever-smoke-design.md) | Làm gì, dùng model nào, giới hạn và tiêu chí hoàn thành là gì? |
| 2 | [Kế hoạch M2.2](plans/2026-10-17-m22-retriever-smoke.md) | Làm theo bước nào, mỗi bước cần kiểm tra và bàn giao gì? |
| 3 | [Nhật ký M2.2](progress/2026-10-17-m22-retriever-smoke.md) | Đã làm gì, gặp lỗi gì, hiện đang ở đâu? |
| 4 | [Báo cáo M2.2](reports/2026-10-17-m22-retriever-smoke.md) | Run thật cho kết quả gì, các kênh PASS/FAIL ra sao? |

## Nơi lưu các thành phần khác của M2.2

Các thành phần sau đã có implementation, run và revision bàn giao.

| Thành phần | Đường dẫn từ gốc repo |
|---|---|
| Cấu hình | `configs/m2.2/retriever_smoke.toml` |
| Implementation | `src/qpaf/m22/` |
| Runner | `scripts/run_m22_smoke.py` |
| Kiểm thử | `tests/test_m22_*.py` |
| Kết quả từng lần chạy | `results/m2.2/<run-id>/` |
| Bằng chứng bàn giao theo revision | `evidence/revisions/m2.2-001/` |
| Điểm tra cứu revision được chọn | `evidence/M2_FINAL/02_retriever_calibration/README.md` |

## Quy tắc cập nhật

- `specs/`: đặc tả và quyết định thiết kế; thay đổi quan trọng phải có lý do và ngày.
- `plans/`: checklist thực hiện; đánh dấu hoàn thành khi có kiểm chứng liên kết.
- `progress/`: ghi thêm các sự kiện, lệnh, lỗi, quyết định và kết quả kiểm tra;
  giữ lịch sử để biết việc gì đã xảy ra.
- `reports/`: tổng hợp trạng thái hiện tại và kết quả từ các run có bằng chứng;
  khi bàn giao, chụp đúng bản báo cáo vào revision bất biến.
- Mỗi run dùng thư mục riêng; không ghi đè run cũ. Bằng chứng đã bàn giao dùng
  revision mới khi sửa. Scores, embeddings và payload lớn lưu local/Modal ngoài
  Git; manifest phải chỉ rõ vị trí và SHA-256 để xác minh khi truy xuất.
- Giữ nguyên tài liệu M1 hiện có. M2.2 không tạo thêm bản kế hoạch/nhật ký/báo cáo
  trùng nội dung ở gốc `docs/` hoặc chỉ trong `.superpowers/` vốn đang bị Git ignore.
