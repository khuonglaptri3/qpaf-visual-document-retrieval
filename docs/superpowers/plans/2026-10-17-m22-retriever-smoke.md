# M2.2 — Kế hoạch triển khai và kiểm chứng

**Ngày:** 2026-10-17

**Trạng thái:** COMPLETE — run thật PASS, artifacts đã xác minh và bàn giao.

**Đặc tả:** [M2.2 retriever smoke design](../specs/2026-10-17-m22-retriever-smoke-design.md).

Checklist chỉ đánh dấu xong khi có kết quả kiểm chứng. Kế hoạch này không tự khởi
chạy cloud, thay đổi code hoặc cấp thêm quyền chạy các milestone khác.

## Bước 1 — Chốt cấu hình và kiểm tra môi trường

- [x] Ghi nhận lựa chọn ColQwen2.5 của người dùng.
- [x] Kiểm tra Modal SDK/profile và xác thực API; kết quả trong nhật ký.
- [x] Xác minh repository/revision và cách load ColQwen2.5, base/adapter, tokenizer/processor.
- [x] Khóa BGE-M3, tokenizer và BM25 preprocessing/tham số.
- [x] Chọn môi trường thực thi; kiểm tra container/GPU và các import cần thiết.
- [x] Khóa kích thước mẫu, resource caps, dtype, batch, preprocessing và dung sai parity.
- [x] Tạo `configs/m2.2/retriever_smoke.toml`, xuất được resolved config.

Đầu ra: cấu hình có đầy đủ giá trị hiệu lực và kết quả probe môi trường thật.

## Bước 2 — Xác minh M2.1 và chuẩn bị mẫu

- [x] Xác minh manifest, nguồn dữ liệu và split hashes của M2.1.
- [x] Chọn mẫu xác định từ train/validation; kiểm tra không có test query.
- [x] Lưu query/page IDs, thuật toán chọn mẫu, seed và hashes; không dùng qrels để chọn trang.
- [x] Chuẩn bị text/ảnh cùng trang theo cùng thứ tự, ghi hash và lỗi extraction.
- [x] Kiểm thử sai hash, ID trùng/thiếu và trường hợp vượt giới hạn mẫu.

Đầu ra: sample manifest và input bundle có thể xác minh.

## Bước 3 — BM25

- [x] Tái sử dụng scorer hiện có, lưu score cache đúng schema.
- [x] So sánh tham chiếu độc lập với thống kê corpus mẫu cố định.
- [x] Kiểm tra finite/shape/IDs và cache reload.
- [x] Ghi thời gian, RAM và kích thước cache.

## Bước 4 — BGE-M3

- [x] Load model/tokenizer đúng revision, giữ trọng số cố định.
- [x] Lưu embeddings và scores theo sample manifest.
- [x] Kiểm tra batch/reference, điểm tính lại từ embeddings và cache reload.
- [x] Đo load/encoding/scoring, RAM/VRAM và kích thước artifacts.

## Bước 5 — ColQwen2.5

- [x] Load đúng model/base/adapter và processor/tokenizer đã khóa.
- [x] Tái sử dụng phần retrieval phù hợp, giữ tương thích với M1.1.
- [x] Lưu embeddings/scores; kiểm tra batch/reference, MaxSim và cache reload.
- [x] Đo load/encoding/scoring, RAM/VRAM và kích thước artifacts.

## Bước 6 — Kiểm tra tổng thể và lỗi

- [x] Chạy run thật đủ ba kênh với cùng mẫu và IDs/thứ tự.
- [x] Tổng hợp parity và đối chiếu resource caps.
- [x] Kiểm thử validation trước khi chạy và cách lưu lỗi/OOM/timeout bằng lỗi mô phỏng;
  không cố tình gây OOM thật để kiểm tra logging.
- [x] Chạy kiểm thử liên quan và regression cần thiết cho phần tái sử dụng đã thay đổi.
- [x] Liên kết kết quả kiểm thử và run ID trong nhật ký.

## Bước 7 — Báo cáo và bàn giao

- [x] Cập nhật báo cáo từ bằng chứng thật; các kênh thiếu bằng chứng ghi NOT_RUN.
- [x] Ghi commit/source hashes, môi trường, config và output hashes.
- [x] Kết luận PASS/FAIL, hạn chế mẫu và cấu hình đề xuất cho các bước sau.
- [x] Tạo revision bất biến `evidence/revisions/m2.2-001/` khi có gói bàn giao.
- [x] Tạo điểm tra cứu tại `evidence/M2_FINAL/02_retriever_calibration/README.md`.

[Nhật ký](../progress/2026-10-17-m22-retriever-smoke.md) ·
[Báo cáo](../reports/2026-10-17-m22-retriever-smoke.md)

## B?ng ch?ng ho?n th?nh

Run `RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01` PASS, 4 validation queries ? 16 pages, visual float32.

[B?o c?o](../reports/2026-10-17-m22-retriever-smoke.md) v? [revision m2.2-001](../../../evidence/revisions/m2.2-001/README.md).
