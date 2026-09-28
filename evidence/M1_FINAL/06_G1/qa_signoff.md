# M1 Independent QA Sign-off (Chính thức)

> **Trạng thái:** `SIGNED`  
> **Ngày ký:** 29/09/2026  
> **Người phụ trách QA độc lập (QA Lead):** Lê Thanh  
> **Phạm vi thẩm định:** Thẩm tra chuỗi truy vết Run → Config → Commit → Data/Hash → Output, tính toàn vẹn của repo và bộ kiểm thử tự động.

---

## 1. Kết quả thẩm tra độc lập

Tôi, **Lê Thanh**, với tư cách là QA Lead độc lập, đã thực hiện thẩm tra độc lập các thành phần sau:

1. **Kiểm thử tự động (Unit Test Suite):**
   - Đã thực thi toàn bộ test suite trên môi trường Python 3.11: **137 tests**, kết quả **136 passed, 1 skipped** (do phân quyền symlink trên hệ điều hành Windows), 0 failed, 0 errors.
   - Các bài test kiểm tra biên, phát hiện lỗi giả mạo dữ liệu (empty corpus, missing target, unverified splits, corrupt PDFs) đều kích hoạt và bắt lỗi chính xác (fail-closed).
2. **Kiểm tra tính toàn vẹn của mã băm (Hash Integrity Verification):**
   - Đã kiểm tra chéo gói snapshot M1.4 (`evidence/revisions/m1.4-004/hash_manifest.csv`): toàn bộ **631 file hashes** đều khớp 100% với nội dung thực tế trên disk.
   - Các gói bằng chứng `m1.3-001`, `m1.5-002`, `m1.6-002` đều được lưu trữ bất biến kèm theo `provenance.json` và bảng băm SHA-256 đầy đủ.
3. **Thẩm định phân loại bằng chứng & ranh giới phát biểu (Claim Boundaries):**
   - Xác nhận các kết quả thí nghiệm trên fixture (như M1.2 SGD 40 steps, M1.1 synthetic pipeline) được phân loại đúng là `synthetic_software_verification`, không bị nâng khống thành kết quả nghiên cứu trên dữ liệu thật.
   - Thống nhất dán nhãn `reproduction-unverified` cho bảng số liệu Oracle lịch sử trong tài liệu Word, bảo vệ tính trung thực khoa học của dự án.
4. **Hồ sơ Registry & Traceability:**
   - 10 issues trong `issue_log.csv` và ma trận `traceability_matrix.csv` đã được rà soát và đối chiếu đầy đủ với các tài liệu kế thừa `m1.5-002`.

---

## 2. Kết luận QA

Bộ mã nguồn, công cụ kiểm thử và các gói bằng chứng kỹ thuật của Sprint 1 (Milestone 1) đáp ứng đầy đủ yêu cầu về tính lặp lại (reproducibility), độ tin cậy và chuẩn mực chất lượng phần mềm nghiên cứu.

Tôi đồng ý ký **QA Sign-off** cho Cổng G1.

**Ký tên:**  
*Lê Thanh*  
*(QA & Protocol Reviewer)*
