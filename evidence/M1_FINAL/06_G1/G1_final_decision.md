# Quyết định Nghiệm thu Cổng G1 (G1 Final Decision)

> **Cổng đánh giá:** Milestone 1.9 (G1) — Gate 1 Review
> **Ngày ban hành:** 29/09/2026
> **Chủ trì ký duyệt:** Tấn Phát (Research Lead)
> **Trạng thái quyết định:** `CONDITIONAL_PASS / PROCEED_TO_M2_DATA_PREP`

---

## 1. Căn cứ quyết định

1. **Báo cáo rà soát và kiểm thử:** [m1.1-m1.8-readiness-audit-2026-09-28.md](../../../docs/m1.1-m1.8-readiness-audit-2026-09-28.md) và biên bản khắc phục [m1-readiness-remediation-2026-09-28.md](../../../docs/m1-readiness-remediation-2026-09-28.md).
2. **Bằng chứng dữ liệu thật:**
   - [`evidence/revisions/m1.3-001/audit_report.json`](../revisions/m1.3-001/audit_report.json): 292 PDFs, 5.385 trang, 1.142 queries, splits xác định 799/171/172.
   - [`evidence/revisions/m1.6-002/collision_report.md`](../revisions/m1.6-002/collision_report.md): 0 leakage, 0 orphan queries, danh mục 5 duplicate nội bộ và báo cáo overlap 205 shared documents.
   - [`evidence/revisions/m1.4-004/audit_metadata.json`](../revisions/m1.4-004/audit_metadata.json): 631 file, 295 data assets, loại trừ file tạm, 631/631 hash khớp.
3. **Bằng chứng giao thức & phần mềm:**
   - [`evidence/revisions/m1.5-002/scoped_contract.md`](../revisions/m1.5-002/scoped_contract.md): Giao thức kế thừa chốt dataset role và cấu trúc 13 features/ranks.
   - Bộ kiểm thử unit test: 137 tests (136 passed, 1 skip).
4. **Các chữ ký nghiệm thu chuyên môn:**
   - [`technical_signoff.md`](technical_signoff.md): Ký bởi Trần Đình Khương.
   - [`qa_signoff.md`](qa_signoff.md): Ký bởi Lê Thanh.

---

## 2. Quyết định chính thức

Hội đồng dự án chính thức thông qua:

1. **Kết quả G1:** **`PASS (CONDITIONAL)`** — Chấp nhận toàn bộ gói bằng chứng kỹ thuật Milestone 1 (M1.1 – M1.8).
2. **Cho phép triển khai Milestone 2 (M2):** Cho phép tiến hành các tác vụ chuẩn bị dữ liệu, lấy mẫu hiệu chuẩn OCR (M2.3), trích xuất native/OCR (M2.6) và xây dựng cache điểm số (M2.8) theo đúng kế hoạch.
3. **Giới hạn thực thi (Execution Boundary):**
   - **MỞ (AUTHORIZED):** Các tác vụ CPU, trích xuất text/ảnh cục bộ và các đợt chạy hiệu chuẩn có kiểm soát trên Modal với ngân sách quy định.
   - **ĐÓNG (RESTRICTED):** Nghiêm cấm chạy huấn luyện mô hình học máy (learned training) hoặc suy luận quy mô lớn cho đến khi cache điểm số và split freeze của M2 được nghiệm thu tại Cổng G2.

---

## 3. Chữ ký phê duyệt

**Tấn Phát**  
*Research Lead & Gate Owner*  
*(Đã ký điện tử và lưu trữ kèm hash bằng chứng bất biến)*
