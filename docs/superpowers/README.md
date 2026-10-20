# Tài liệu thiết kế và thực hiện theo Superpowers

Các thư mục ở đây tổ chức tài liệu theo quy ước Superpowers đang dùng trong repo.
Việc có tài liệu trong thư mục này không đồng nghĩa một skill/plugin đã được chạy,
hay một milestone đã được nghiệm thu.

## M2.7 — Matched config cho QARF/QPAF

Nhiệm vụ của Tấn Phát: khóa config dùng chung cho QARF/QPAF và chứng minh khác
biệt ngữ nghĩa duy nhất là `gate_granularity`. Trạng thái:
`FROZEN_CONFIG_PENDING_M2.8_INPUTS`; independent review chờ M2.10.

- [Thiết kế](specs/2026-10-20-m27-matched-configs-design.md)
- [Kế hoạch](plans/2026-10-20-m27-matched-configs.md)
- [Đặc tả phương pháp và lệnh chạy](../03_method/m2.7-matched-configs.md)
- [Bằng chứng bất biến](../../evidence/revisions/m2.7-001/README.md)

## M2.6 — Full OCR và hash theo trang

Nhiệm vụ của Khương: xử lý toàn bộ 292 PDF / 5.385 trang ViDoSeek theo policy
M2.3 đã khóa, giữ lỗi tường minh và kiểm chứng hash trước khi bàn giao cho M2.8.

- [Thiết kế](specs/2026-10-19-m26-full-ocr-design.md)
- [Kế hoạch](plans/2026-10-19-m26-full-ocr.md)
- [Báo cáo thực thi và kết quả](reports/2026-10-19-m26-full-ocr.md)
- [Vị trí file, cấu trúc bundle và lệnh tái lập](../../results/m2.6/README.md)
- [Biên nhận kiểm thử phần mềm](../../results/m2.6/verification/2026-10-19-software-checks.json)
- [Biên nhận kiểm tra mới khi tiếp tục thu thập](../../results/m2.6/verification/2026-10-19-resumed-checks.json)
- [Bằng chứng bất biến và handover](../../evidence/revisions/m2.6-001/README.md)

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

## M2.3 — Hiệu chuẩn OCR và review thủ công

**Trạng thái mới nhất:** COMPLETE_BOUNDED_CALIBRATION — checklist 16/16,
121 native đã chốt, 18 references giữ nguyên. Config đã FROZEN: native hợp lệ
+ OCR 300 DPI ở vùng chưa có native, confidence bổ sung60. Có review bổ sung
của Codex AI theo yêu cầu người dùng. Xem
[nghiên cứu và quyết định](reports/2026-10-17-m23-research-and-final-decision.md),
[bàn giao cho M2.4/M2.6/M2.8](reports/2026-10-17-m23-downstream-handoff.md) và
[revision m2.3-002](../../evidence/revisions/m2.3-002/README.md).
Ngưỡng chốt là cấu hình vận hành từ mẫu nhỏ, không chứng nhận accuracy corpus.

| Thứ tự | Tài liệu | Nội dung |
|---|---|---|
| 1 | [Đặc tả M2.3](specs/2026-10-17-m23-ocr-calibration-design.md) | Cấu hình, chọn mẫu, giới hạn và ranh giới review |
| 2 | [Kế hoạch M2.3](plans/2026-10-17-m23-ocr-calibration.md) | Checklist thực hiện và phần còn chờ người dùng |
| 3 | [Nhật ký M2.3](progress/2026-10-17-m23-ocr-calibration.md) | Lệnh, runtime, run IDs, lỗi và kết quả thực tế |
| 4 | [Runbook và vị trí dữ liệu](../../results/m2.3/README.md) | Chạy/verify, mở HTML, xuất JSON và tổng hợp |
| 5 | [Báo cáo dữ liệu và tài nguyên](reports/2026-10-17-m23-ocr-calibration.md) | Kết quả thật, run history, kiểm chứng và phần chờ review |

Bằng chứng kỹ thuật: [revision m2.3-001](../../evidence/revisions/m2.3-001/README.md),
[điểm tra cứu M2_FINAL](../../evidence/M2_FINAL/03_ocr_calibration/README.md).

- [Thiết kế và cách review bước 2/bước 4](specs/2026-10-17-m23-manual-review-design.md).
- [Nhật ký thiết kế](progress/2026-10-17-m23-manual-review.md).
- [Mở giao diện offline](../../results/m2.3/review-demo-2026-10-17/index.html)
  từ 16 trang mẫu M2.2 có sẵn. HTML được sinh local, không đưa ảnh nguồn vào Git.
- [Giao diện dữ liệu M2.3 thật](../../results/m2.3/review/index.html), tạo sau khi tải run về;
  tách namespace với bản demo.


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
