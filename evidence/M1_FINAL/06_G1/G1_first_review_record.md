# Biên bản G1 First Review — Milestone 1 (Sprint 1)

> **Thời gian:** 28/09/2026 (Phiên rà soát và khắc phục) — Kết luận: 29/09/2026
> **Địa điểm / Phương thức:** Hội đồng kỹ thuật dự án QPAF
> **Chủ trì:** Tấn Phát (Research Lead / Protocol Owner)
> **Thành viên tham dự:**
> - Trần Đình Khương (Data & Technical Owner)
> - Lê Thanh (QA & Protocol Reviewer)
> - Tấn Phát (Research Lead)

---

## 1. Mục đích cuộc họp

Đánh giá tính sẵn sàng và độ tin cậy của toàn bộ bằng chứng khởi đầu (starting evidence), giao thức thực thi (protocol), cấu trúc phân chia dữ liệu (splits/corpus), kho lưu trữ mã nguồn và chính sách OCR trước khi chuyển sang Sprint 2 (M2 — Chuẩn bị và trích xuất đặc trưng corpus thật).

---

## 2. Báo cáo bằng chứng kỹ thuật từ các thành viên

1. **Khương báo cáo dữ liệu & collision (M1.3, M1.4, M1.6):**
   - Đã tải toàn bộ corpus ViDoSeek chính thức tại revision `e91a92ba5f38690696c7e66be5c5474b54c6e791`: gồm file annotations `vidoseek.json` và 292 file PDF nguyên gốc trong `vidoseek_pdf_document.zip` (758.769.613 bytes, hash SHA-256 khớp LFS).
   - Đã mở và kiểm tra từng trang của toàn bộ 292 file PDF: xác định chính xác **5.385 trang** thực tế.
   - Sinh phân vùng splits xác định theo tỷ lệ 70/15/15: Train (799 queries), Val (171 queries), Test (172 queries). Đã kiểm chứng tính toàn vẹn và cờ `--verify-splits` chỉ đọc thành công.
   - Đã render và hash 5.385 trang (72 DPI RGB): phát hiện 5 cặp trùng lặp nội bộ (intra-split), **0 trường hợp rò rỉ xuyên split (zero cross-split leakage)**, **0 orphan queries** (toàn bộ 1.142 queries đều trỏ đúng tài liệu và số trang hợp lệ).
   - Đã tạo snapshot M1.4 mới (`m1.4-004`) với 631 file, phân loại rõ ràng 295 file data và loại trừ hoàn toàn file tạm.

2. **Thanh báo cáo QA & Kiểm tra tính độc lập (M1.1, M1.7):**
   - Đã đối chiếu kết quả Oracle lịch sử: thống nhất gắn nhãn `reproduction-unverified` cho các bảng số liệu cũ trong tài liệu Word; ghi nhận solver exact simplex mới là bài đo upper-bound độc lập.
   - Đã kiểm tra lại 137 unit tests trên môi trường Python 3.11: 136 tests passed, 1 skip (do phân quyền symlink trên Windows).
   - Đã xác thực 631/631 hashes của repository snapshot `m1.4-004`.

3. **Phát báo cáo Protocol & Runtime Safety (M1.2, M1.5, M1.8):**
   - M1.2 đã có biên nhận kiểm thử phần mềm độc lập trên fixture synthetic, gradient và loss hoạt động chuẩn xác theo finite-difference tests.
   - Đã chốt successor contract `m1.5-002` thống nhất sử dụng ViDoSeek làm primary corpus (page-level) và giữ ViMDoc cho confirmation (document-level).
   - Đã hoàn thiện cơ chế fail-closed, timeout, OCR quality fallback và boundary guard ngăn chặn chạy GPU/Modal trái phép.

---

## 3. Thảo luận & Xử lý Blocker

- **Về việc 205 documents dùng chung giữa các query splits:** Hội đồng thống nhất rằng đây là đặc thù chuẩn của bài toán Information Retrieval trên tập tài liệu chia sẻ (shared corpus retrieval), miễn là tập câu hỏi (queries) được phân chia disjoint tuyệt đối (query overlap = 0) và không có trang nội dung nào bị rò rỉ chéo.
- **Về hiệu chuẩn OCR (M1.8):** Thống nhất lịch trình chuyển giai đoạn hiệu chuẩn số liệu (calibration) sang M2.3 và trích xuất OCR quy mô lớn sang M2.6, M1 hoàn thành trọn vẹn ở mức chốt policy, cơ chế fallback và kiểm thử an toàn phần mềm.

---

## 4. Quyết định First Review

Hội đồng kỹ thuật đồng thuận **ĐÓNG TOÀN BỘ BLOCKER** trong `G1_blocker_log.md` và xác nhận Milestone 1 đạt tiêu chuẩn nghiệm thu có điều kiện để chuyển tiếp sang Milestone 2.
