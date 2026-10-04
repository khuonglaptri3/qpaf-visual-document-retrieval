# M1 Technical Sign-off (Chính thức)

> **Trạng thái:** `SIGNED`  
> **Ngày ký:** 29/09/2026  
> **Người phụ trách kỹ thuật (Owner):** Trần Đình Khương — Data & Technical Lead  
> **Đối tượng nghiệm thu:** Toàn bộ công cụ, dữ liệu corpus thật, phân chia splits và kiểm kê repository M1.3, M1.4, M1.6, M1.8.

---

## 1. Nội dung xác nhận kỹ thuật

Tôi, **Trần Đình Khương**, xác nhận các nội dung kỹ thuật sau đã được kiểm chứng thực tế trên hệ thống và dữ liệu thật:

1. **Corpus ViDoSeek thật (M1.3):**
   - Đã tải, lưu trữ và xác thực hash SHA-256 của `vidoseek.json` và `vidoseek_pdf_document.zip` (758.769.613 bytes).
   - Đã mở và đếm trang thực tế của 292 file PDF, ghi nhận chính xác 5.385 trang.
   - Tập splits Train/Val/Test (799/171/172) tạo ra hoàn toàn tất định, kiểm thử `--verify-splits` chỉ đọc đạt kết quả 100% tin cậy, không rò rỉ.
2. **Kiểm kê Repository (M1.4):**
   - Đã tạo revision `evidence/revisions/m1.4-004/` bao gồm 631 file (trong đó có 295 data assets thật, 28 source files).
   - Đã loại trừ hoàn toàn các file tạm thời `.tmp` và thư mục scratch/build. Lệnh xác thực manifest đã chạy pass 631/631 file hashes.
3. **Collision & Leakage Audit (M1.6):**
   - Đã thực thi audit trên 5.385 trang PDF thật được render ở 72 DPI RGB, ghi nhận kết quả tại `evidence/revisions/m1.6-002/`.
   - Kết quả: **0 cross-split leakage**, **0 orphan queries** (1.142/1.142 query hợp lệ), danh mục 5 nhóm trùng lặp nội bộ và 205 documents dùng chung theo đúng bản chất bài toán retrieval.
4. **Cơ chế Runtime & OCR Fallback (M1.8):**
   - Đã tích hợp các hàm kiểm soát ranh giới thực thi (`assert_execution_authorized`), kiểm tra chất lượng OCR và namespace metadata. Đã vượt qua toàn bộ 137 unit tests.

---

## 2. Kết luận ký duyệt

Tôi xác nhận hoàn thành đầy đủ trách nhiệm kỹ thuật của Milestone 1 theo đúng các tiêu chí của Cổng G1. Đề nghị Hội đồng kỹ thuật thông qua kết quả G1.

**Ký tên:**  
*Trần Đình Khương*  
*(Data & Technical Lead)*
