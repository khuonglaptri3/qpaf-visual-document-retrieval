# Biên bản Đóng Milestone 1 (M1 Closure Record)

> **Mã mốc:** Milestone 1 (M1) — Khảo sát Khả thi, Công cụ & Nền tảng Nghiên cứu
> **Chu kỳ sprint:** Sprint 1
> **Ngày phê duyệt đóng mốc:** 29/09/2026
> **Trạng thái đóng mốc:** `CLOSED / COMPLETED_WITH_G1_PASS`
> **Chủ trì duyệt đóng:** Tấn Phát (Research Lead)

---

## 1. Tóm tắt kết quả đạt được của Milestone 1

| Nhiệm vụ | Người phụ trách | Kết quả cốt lõi bàn giao | Trạng thái nghiệm thu |
| :--- | :--- | :--- | :--- |
| **M1.1** | Thanh | Đã rà soát Oracle W7/W66 lịch sử, dán nhãn `reproduction-unverified`. Dựng hoàn chỉnh pipeline trích xuất đa phương thức và exact binary simplex solver trên fixture. | **ACCEPTED** (Feasibility scope) |
| **M1.2** | Phát | Dựng mô hình lõi 13 features → gate → loss/gradient; finite-difference gradient tests pass; biên nhận phần mềm hợp lệ. | **ACCEPTED** (Software core verified) |
| **M1.3** | Khương | Tải toàn bộ ViDoSeek (292 PDFs, 5.385 trang); xuất splits tất định 799/171/172; bộ công cụ `--verify-splits` chỉ đọc hoạt động hoàn hảo. Xuất `m1.3-001`. | **ACCEPTED** (Real corpus verified) |
| **M1.4** | Khương | Hoàn tất kiểm kê 631 file repository trong `m1.4-004`, gồm 295 data assets thật, loại trừ toàn bộ file tạm; xác thực 631/631 hashes. | **ACCEPTED** (Snapshot verified) |
| **M1.5** | Phát (Thanh review) | Chốt giao thức kế thừa `m1.5-002` với `scoped_contract.md`, phân tách rõ vai trò ViDoSeek primary page-level và ViMDoc confirmation. | **ACCEPTED** (Successor frozen) |
| **M1.6** | Khương | Chạy collision audit trên 5.385 trang thật: 0 cross-split leakage, 0 orphan queries (1.142 queries hợp lệ), 5 cặp duplicate nội bộ. Xuất `m1.6-002`. | **ACCEPTED** (Zero leakage verified) |
| **M1.7** | Thanh | Cập nhật hồ sơ thực nghiệm, 10 open issues, ma trận truy vết và chính sách append-only. | **ACCEPTED** (Draft governance ready) |
| **M1.8** | Khương | Tích hợp OCR quality/confidence fallback, cơ chế timeout và quản lý namespace metadata. Test runtime pass 100%. | **ACCEPTED** (Software integration complete) |
| **M1.9 (G1)** | Toàn nhóm | Đã tổ chức G1 First Review, giải quyết toàn bộ 6 blocker trong `G1_blocker_log.md`. Đạt Technical Sign-off và QA Sign-off. Ra quyết định `CONDITIONAL_PASS`. | **PASSED (G1 Gate)** |
| **M1.10 (R1)** | Phát | Hoàn thành báo cáo tổng kết Sprint 1 `Sprint_1_Progress_Report.md`. | **COMPLETED** |

---

## 2. Kế hoạch chuyển tiếp sang Milestone 2 (Sprint 2)

Milestone 1 chính thức khép lại. Nhóm dự án đủ điều kiện và được cấp quyền chuyển sang Milestone 2 với các nhiệm vụ trọng tâm:
1. **M2.2:** Smoke/calibrate mô hình trích xuất (BM25, BGE-M3, ColQwen2) trên mẫu nhỏ có kiểm soát.
2. **M2.3:** Lấy mẫu đại diện (khoảng 30 PDF / 100–150 trang) để đo đạc và hiệu chuẩn ngưỡng OCR chính thức.
3. **M2.6:** Thực thi trích xuất native/OCR toàn bộ 5.385 trang của corpus ViDoSeek.
4. **M2.8:** Xây dựng cache điểm số (score cache) của 3 retriever và tạo candidate pool.

---

## 3. Xác nhận đóng mốc

Hội đồng dự án gồm **Tấn Phát**, **Trần Đình Khương**, và **Lê Thanh** nhất trí ký biên bản chính thức đóng Milestone 1.
