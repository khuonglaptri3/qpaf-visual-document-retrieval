# M2.3 — Kế hoạch thực hiện

- [x] Giữ cách lưu specs/plans/progress/reports và run riêng của M2.2.
- [x] Xác minh CPU runtime thật, pin Tesseract và SHA-256 traineddata.
- [x] Implement config, deterministic sampling, paired OCR và failure/resource evidence.
- [x] Implement HTML dữ liệu thật và importer/summarizer human review.
- [x] Chạy tests phù hợp và xác minh source/config snapshot.
- [x] Chuẩn bị 30 PDF / 120 trang + ca regression, khóa sample IDs/hashes.
- [x] Chạy OCR 150/300 DPI trên CPU trong caps, tải kết quả về local.
- [x] Xác minh toàn bộ payload/hash/ID và kiểm tra HTML dữ liệu thật trên browser.
- [x] Xuất báo cáo DATA_READY_REVIEW_PENDING, runbook, vị trí review và số đo.
- [x] Ghi nhận thay đổi phạm vi: giữ đúng 18 bản chữ người dùng đã làm, thay yêu cầu 41 ban đầu.
- [x] Tự xuất JSON mới từ Edge; nhận đúng 18 bản đã nhập và xác minh identity/hash/native state.
- [x] Lưu manifest 18 page IDs và 54 dòng metrics sơ bộ riêng; giữ lịch sử 41 trang.
- [x] Đọc bản chữ và xem ảnh của 18 trang, báo lỗi tham chiếu và giới hạn số đo.
- [x] Hoàn tất121 kết luận native và18 references; lưu rõ21 amendment AI, giữ100 quyết định gốc.
- [x] Tổng hợp dev/holdout/regression, bổ sung BWE có amendment hồi cứu, so sánh8 ứng viên và chốt operating point.
- [x] Lưu quyết định có giới hạn, policy executable/FROZEN, 23 tests/verification và revision m2.3-002.

**16/16 hoàn tất trong phạm vi hiệu chuẩn có giới hạn.** Hai mục cuối dựa trên
review ảnh và quyết định có nguồn theo yêu cầu người dùng giao Codex hoàn
thành, không chỉ dựa vào test hoặc confidence. Không tạo chữ ký nhóm độc lập.
Xem [nghiên cứu và quyết định](../reports/2026-10-17-m23-research-and-final-decision.md)
và [hợp đồng bàn giao](../reports/2026-10-17-m23-downstream-handoff.md).
