# M2.3 — Hiệu chuẩn đã hoàn tất và cấu hình vận hành đã chốt

**COMPLETE_BOUNDED_CALIBRATION / FROZEN_OPERATING_CONFIGURATION**.
Revision mới này thay trạng thái chờ review của m2.3-001. Không ghi đè run,
review gốc hoặc revision cũ. Quyết định do Codex AI thực hiện theo yêu cầu
hoàn thành của người dùng; không giả chữ ký nghiệm thu độc lập của nhóm.

- [Báo cáo nghiên cứu và quyết định](report_snapshot.md).
- [Manifest bàn giao cho M2.4/M2.6/M2.8](handover.json).
- [Config cố định](ocr_policy_frozen.toml), [quyết định có giới hạn](decision.json).
- [121 page records sau policy](resolved_pages.json), [review cuối](human_reviews.final.json).
- [8 ứng viên](candidate_aggregates.csv), [native review amendments](native_review_changes.json).
- [Confidence được tính lại](confidence_rederived.json), [11 lượt sửa parser](confidence_changes.json).
- [Nguồn và hash](provenance.json), [hash manifest revision](hashes.json).
- [HTML xem raw và text theo policy](../../../results/m2.3/closure/2026-10-17-closed/index.html#reference).
- [Hợp đồng dùng tiếp](../../../docs/superpowers/reports/2026-10-17-m23-downstream-handoff.md).

Giữ native dùng được, bổ sung words OCR ngoài vùng native: Tesseract 5.3.0,
eng/300 DPI/OEM 3/PSM 3; confidence bổ sung60, overlap native0.5; OCR timeout 15s,
CPU4/RAM4096MiB/2 workers. Runtime/language bytes được pin như lượt đo gốc.

121 native đã chốt: 95 PASS/25 HAS_ERRORS/1 NO_TEXT;18 references giữ nguyên.
Có100 quyết định gốc và21 amendment native của Codex AI. Kết quả sau policy:
45 native /70 native+OCR /6 OCR;0 lỗi kỹ thuật, 23 trang có cảnh báo chất lượng.

Phạm vi chốt là cấu hình vận hành từ mẫu nhỏ. Không chứng nhận accuracy toàn
corpus, không gọi holdout đã xem là kiểm định độc lập và không coi empty OCR
là ảnh chắc chắn không chữ. Full OCR/cache/learned training chưa chạy ở đây.

Raw PDFs/ảnh/TSV giữ ở run
`results/m2.3/RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01/` và Volume đã ghi
trong m2.3-001. `source_snapshot.zip` lưu source/config/lock/test của lần chốt;
raw run có source snapshot riêng. `hashes.json` được tạo sau khi gói đầy đủ.
