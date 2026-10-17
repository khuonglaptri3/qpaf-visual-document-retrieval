# M2.3 — Bàn giao dữ liệu để review

**ENGINEERING_DATA_VERIFIED / HUMAN_REVIEW_PENDING**. Chưa PASS chất lượng M2.3,
chưa đóng băng threshold, chưa có human references được nhận.

Run: `RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01`.
121 trang, 242 OCR attempts, 0 lỗi kỹ thuật; 121 native reviews /41 references chờ người dùng.

- [Báo cáo chụp tại bàn giao](report_snapshot.md).
- [Mục tiêu review từng trang](review_targets.csv).
- [Danh tính và phạm vi bàn giao](handover.json).
- [Mở HTML hiện hành](../../../results/m2.3/review/index.html).
- [Runbook](../../../results/m2.3/README.md).

Raw PDFs, ảnh, txt/TSV và HTML được sinh ở local/Modal Volume, ngoài Git.
`run_hashes.json` và `remote_hashes.json` ràng buộc payload đó; clone Git riêng
không đủ để khôi phục toàn bộ dữ liệu. Volume `qpaf-m23-ocr-artifacts`,
`runs/<run-id>/output/`. Source snapshot ZIP nằm trong thư mục run.

Giữ revision này bất biến. Sau human review, tạo revision mới để tổng hợp hoặc
freeze quyết định, không sửa gói dữ liệu ban đầu thành một kết luận chất lượng.
