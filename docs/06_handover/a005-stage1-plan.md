# A005 Stage 1 — Kế hoạch chuẩn bị input ViMDoc (chưa authorize)

**Ngày:** 2026-10-28. **Tiền đề:** Stage 0 `PASS`
([README](../../evidence/revisions/a005-s0-001/README.md)): Spearman −0,994, và bộ trọng số
có loss thấp nhất cho nDCG 0,8627 so với mức tối đa 0,8642.

Stage 1 là bước đầu tiên của A005 **tốn tiền GPU và CPU trên Modal**. Theo A005 §5, nó cần
một resource review và authorization riêng, có **cost cap do Research Lead đặt**. Tài liệu
này chưa cấp quyền chạy gì.

## Việc phải làm

Hợp đồng đã freeze nằm ở `configs/vimdoc_m3_local_v1.json` và
`docs/04_data_protocol/VIMDOC_M3_LOCAL_PACKAGE.md`.

| # | Việc | Loại | Đã có sẵn |
| --- | --- | --- | --- |
| 1-1 | Audit content-hash cho page identity (76.347 asset → 70.080 page). Collision khác nội dung thì `BLOCK` | CPU, chỉ đọc | Script `run_vimdoc_archive_content_audit.py`, chưa chạy trên archive thật |
| 1-2 | OCR Tesseract theo HEAVEN cho 70.080 trang, làm text cho BM25/BGE-M3 | CPU | Pipeline M2.6 (ViDoSeek); spec `vimdoc_ocr_page_identity_v1.json` |
| 1-3 | Score toàn corpus: BM25, BGE-M3, ColQwen2.5; top-200 mỗi kênh; union ≤ 600 trang/query; đủ 3 score cho mọi trang | GPU + CPU | Hợp đồng đã có; **adapter chưa viết** (runner DSE cũ không dùng được) |
| 1-4 | Normalize min-max theo query; ghi cache không chứa nhãn kèm receipt hash | CPU | Helper tham chiếu trong `prepare_vimdoc_m3.py` |
| 1-5 | Coverage chỉ trên train+validation (2.000 ID): macro recall ≥ 0,95, không query nào thiếu positive | CPU, nhãn dev | Chưa có |
| 1-6 | Evaluator theo document (max page score), kiểm chứng độc lập trên dữ liệu tổng hợp | code | Chưa có hash |
| 1-7 | Phân tích overlap document giữa dev và confirmation (yêu cầu của M4.1) | nhãn dev | Chưa có |

Nhãn confirmation 8.904 **không được đọc** trong Stage 1.

## Ước lượng tài nguyên

Phần dưới cần calibrate trước khi chạy full, theo đúng cách đã làm với W66.

- **OCR.** M2.6 chạy 5.385 trang trong 4.846 giây trên 4 CPU, tức khoảng 0,9 giây/trang.
  ViMDoc 70.080 trang ước khoảng **17,5 giờ** trên một worker 4 CPU, hoặc khoảng 2,2 giờ
  nếu chia cho 8 worker. M2.6 cũng cần một lượt recovery cho transport, nên phải dự phòng.
- **ColQwen2.5 và BGE-M3.** Phải embed 70.080 ảnh và text trang, cộng 10.904 query. Chưa
  có số đo ViMDoc. Cần một calibration nhỏ (vài trăm trang) để ra GPU-giờ trước khi xin
  full run.
- **BM25.** Chạy CPU, rẻ, phụ thuộc vào OCR xong trước.
- **Archive.** 17,5 GB. Theo receipt tháng 8, archive đã nằm trên Modal volume
  `/vol/datasets/vimdoc/…`, nhưng trạng thái hiện tại chưa được kiểm lại.

## Lịch

Thời gian tính theo ngày làm việc, chưa gồm thời gian chờ duyệt.

| Bước | Thời gian |
| --- | --- |
| Viết adapter (1-3) và evaluator theo document (1-6), có test | 1–2 ngày |
| Audit (1-1) và calibration nhỏ OCR + GPU | 0,5 ngày |
| Full OCR + score + verify | 1–2 ngày |
| Stage 2–4 (probe ViMDoc, baseline, 6 run train CPU) | khoảng 1–2 ngày |
| Stage 5–6 (mở confirmation một lần, tổng hợp) | 0,5 ngày |

Tổng cộng khoảng **5–8 ngày làm việc**. Nếu bắt đầu ngay, lịch vẫn trước G4 (04/12). A005
§7 đã quy định: nếu Stage 6 chưa xong trước M6.10, G4 chỉ báo cáo QPAF-v1.

## Research Lead cần quyết định

1. **Cost cap** cho Modal ở Stage 1, tính bằng USD. Gồm số invocation tối đa, GPU type và
   timeout.
2. **Duyệt bước calibration nhỏ trước** (audit + vài trăm trang OCR/GPU). Bước này rẻ và cho
   ra con số thật để đặt cost cap cho full run.

Lưu ý: kể cả khi mọi stage đều chạy xong, A005 **không bảo đảm** QPAF-SA vượt baseline trên
ViMDoc. Theo A006, kết quả tối đa là `LIMITED-CLAIM`.
