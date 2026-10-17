# M2.3 — Điểm tra cứu dữ liệu OCR calibration

**Trạng thái mới nhất: COMPLETE_BOUNDED_CALIBRATION / FROZEN_OPERATING_CONFIGURATION.**
M2.3 hoàn tất trong phạm vi mẫu hiện có. 121 native và18 references đã chốt;
không còn review pending. Review bổ sung/quyết định do Codex AI theo yêu cầu
người dùng; không giả chữ ký nghiệm thu độc lập hoặc accuracy toàn corpus.

- [Revision chốt m2.3-002](../../revisions/m2.3-002/README.md).
- [Nghiên cứu nguồn gốc và quyết định](../../../docs/superpowers/reports/2026-10-17-m23-research-and-final-decision.md).
- [Hợp đồng cho M2.4/M2.6/M2.8](../../../docs/superpowers/reports/2026-10-17-m23-downstream-handoff.md).
- [Config đã chốt](../../../configs/m2.3/ocr_policy_frozen.toml).
- [HTML cuối, xem cả text theo policy](../../../results/m2.3/closure/2026-10-17-closed/index.html#reference).

Phần dưới là lịch sử nhận review trước khi đóng m2.3-002.

Đã nhận JSON của Khuong: 107 PASS, 6 HAS_ERRORS, 7 PENDING, 1 UNSURE;
còn 8 native cần chốt và 41 references cần xác nhận theo export/protocol cũ.
Người dùng đã đổi phạm vi thành 18 references đã làm. Xem
[tổng hợp human review](../../../docs/superpowers/reports/2026-10-17-m23-human-review-summary.md)
và [summary](../../../results/m2.3/reviews/2026-10-17T110738920Z-khuong/summary.json).

- [Revision dữ liệu bất biến m2.3-001](../../revisions/m2.3-001/README.md).
- [Báo cáo kết quả và tài nguyên](../../../docs/superpowers/reports/2026-10-17-m23-ocr-calibration.md).
- [Mở giao diện review 121 trang](../../../results/m2.3/review/index.html).
- [Lệnh và cách xuất JSON để tổng hợp](../../../results/m2.3/README.md).

Run chọn: `RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01`.
Đã có native text, ảnh và OCR 150/300 DPI cho toàn bộ 121 trang; 242 attempts,
0 lỗi kỹ thuật. Export cũ có native đã chốt 113/121 và full-page references 0/41;
export lúc 12:47 có 18 DRAFT references và 0 CONFIRMED; gói QA mới đã có
18/18 CONFIRMED dưới tên Codex cùng provenance và diff.

Các run cũ và lỗi cap render được giữ trong lịch sử. Không có huấn luyện gate
13 features, OCR toàn corpus M2.6 hoặc cache retriever M2.8 trong gói này.
