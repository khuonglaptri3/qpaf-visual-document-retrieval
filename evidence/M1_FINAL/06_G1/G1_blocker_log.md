# G1 Official Blocker Log — Sprint 1 (Milestone 1)

> **Gate:** Milestone 1.9 (G1) — Starting Evidence & Protocol Review
> **Date:** 28/09/2026 (Updated: 29/09/2026)
> **Lead / Gate Owner:** Tấn Phát
> **Technical Reviewer:** Trần Đình Khương
> **QA Reviewer:** Lê Thanh

---

## 1. Blocker Log Summary

| Blocker ID | Severity | Finding & Context | Owner | Closure Evidence / Resolution | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **G1-BLK-01** | CRITICAL | **F01/F02/F03: Thiếu dữ liệu corpus thật và rủi ro false PASS trong M1.3/M1.6.** CLI trước đó chấp nhận corpus rỗng và không mở PDF đếm trang thực tế. | Khương | Tải và xác thực 292 PDF ViDoSeek (758 MB, SHA-256 khớp HF LFS). Cập nhật code fail-closed, mở từng PDF đếm 5.385 trang thật. Chạy lại audit xuất `m1.3-001` và `m1.6-002`. | **CLOSED** |
| **G1-BLK-02** | HIGH | **F04: Overlap 205 documents giữa các split trong ViDoSeek.** ViDoSeek chia query-disjoint nhưng có tài liệu dùng chung giữa train/val/test. | Khương + Phát | Đã đo đạc độc lập trong `overlap_report.json`: query overlap = 0, cross-split duplicate leakage = 0. Ghi nhận cơ chế shared retrieval corpus; chấp nhận ranh giới cho giai đoạn M2. | **CLOSED** (Policy reviewed) |
| **G1-BLK-03** | HIGH | **F08: Snapshot M1.4 cũ bị dính file tạm `.tmp` và thiếu 100% data assets.** | Khương | Loại trừ triệt để `.tmp` trong `audit.py`. Tạo snapshot mới `m1.4-004` (631 files, 295 data assets thật). Đã chạy lệnh verify khớp 631/631 hashes. | **CLOSED** |
| **G1-BLK-04** | MEDIUM | **F07: Lệch protocol M1.5 giữa repo cũ và hiện tại sau các amendment A001/A002.** | Phát + Thanh | Phát hành successor package `m1.5-002` với `scoped_contract.md`, phân tách rõ ViDoSeek primary page-level và ViMDoc confirmation document-level. | **CLOSED** |
| **G1-BLK-05** | MEDIUM | **F05/F06: OCR policy M1.8 chưa tích hợp runtime; boundary guard chưa nối launcher.** | Khương + Phát | Đã nối fallback/namespace trong `src/qpaf/m11/dataset.py`, `src/qpaf/m18/` và thêm boundary guard tại `run_m11_modal.py`, `pipeline.py`. Toàn bộ 137 unit tests đều pass. | **CLOSED** |
| **G1-BLK-06** | LOW | **F01/M1.1: Oracle W7/W66 lịch sử không thể tái lập hoàn toàn từ đầu vào cũ.** | Thanh + Phát | Thừa nhận giới hạn trong `results/m1.1/README.md`; dán nhãn `reproduction-unverified`. Tách biệt solver exact simplex mới là nghiên cứu độc lập. | **CLOSED** (Classified) |

---

## 2. Review Conclusion on Blockers

Tất cả 6 blocker kỹ thuật cốt lõi (G1-BLK-01 đến G1-BLK-06) đã được khắc phục hoàn toàn bằng code, kiểm thử thực tế và các gói bằng chứng bất biến (`m1.3-001`, `m1.4-004`, `m1.5-002`, `m1.6-002`). Không còn blocker kỹ thuật nào cản trở việc nghiệm thu Milestone 1 và bước vào công đoạn chuẩn bị dữ liệu M2.
