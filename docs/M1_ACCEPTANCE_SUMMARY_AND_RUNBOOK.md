# BẢNG NGHIỆM THU CHỐT LẠI M1.1 – M1.10 & TOÀN BỘ CẨM NANG LỆNH TERMINAL (RUNBOOK)

> **Dự án:** QPAF (Query-Performance-Aware Multimodal Fusion for Visual Document Retrieval)  
> **Giai đoạn:** Sprint 1 — Milestone 1 (M1.1 – M1.10)  
> **Ngày phê duyệt:** 29/09/2026  
> **Baseline Commit:** `765803f` (`develop`)  
> **Quyết định Cổng G1:** `CONDITIONAL_PASS / PROCEED_TO_M2_DATA_PREP`  
> **Trạng thái mốc M1:** `CLOSED`

---

## PHẦN I: BẢNG NGHIỆM THU CHỐT LẠI TỪ M1.1 ĐẾN M1.10

| Nhiệm vụ | Người phụ trách | Mục tiêu & Phạm vi | Bằng chứng thực tế & Artifact bất biến | Kết quả nghiệm thu |
| :--- | :--- | :--- | :--- | :---: |
| **M1.1** | Lê Thanh | Khảo sát Oracle W7/W66 lịch sử; dựng pipeline đa phương thức 5 giai đoạn và solver exact simplex binary | - Báo cáo phân loại Oracle: [`results/m1.1/README.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/results/m1.1/README.md)<br>- Solver exact simplex per-page: `src/qpaf/m11/oracle.py`<br>- Pipeline fixture kiểm thử phần mềm 5 stages: [`configs/m1.1/software_fixture.toml`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/configs/m1.1/software_fixture.toml) | **ACCEPTED**<br>*(Feasibility scope; dán nhãn `reproduction-unverified`)* |
| **M1.2** | Tấn Phát | Thiết kế bộ 13 đặc trưng (`qpaf13_v1`), mạng Gating Network gán trọng số và hàm pairwise ranking loss | - Module 13 features & Gating MLP: `src/qpaf/m12/gate.py`<br>- Bộ test gradient sai phân hữu hạn & tối ưu SGD 40 bước: [`tests/test_m12_*.py`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/tests/)<br>- Biên nhận kiểm chứng phần mềm: `scripts/verify_m12.py` | **ACCEPTED**<br>*(Core software verified)* |
| **M1.3** | Trần Đình Khương | Chuẩn bị corpus ViDoSeek thật, mở 292 PDF đếm trang thực tế, sinh splits 70/15/15 và bộ kiểm tra split chỉ đọc | - Payload: `vidoseek.json` & `vidoseek_pdf_document.zip` (758 MB)<br>- Báo cáo audit 292 PDF / 5.385 trang thật: [`evidence/revisions/m1.3-001/audit_report.json`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/revisions/m1.3-001/audit_report.json)<br>- Tập split xác định 799/171/172: [`evidence/revisions/m1.3-001/splits/`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/revisions/m1.3-001/splits/) | **ACCEPTED**<br>*(Real corpus verified)* |
| **M1.4** | Trần Đình Khương | Kiểm kê toàn bộ repository, loại trừ file rác `.tmp`, xác thực mã băm SHA-256 từng file | - Snapshot 631 files (295 data assets, 28 source): [`evidence/revisions/m1.4-004/audit_metadata.json`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/revisions/m1.4-004/audit_metadata.json)<br>- Bảng băm kiểm chứng: [`evidence/revisions/m1.4-004/hash_manifest.csv`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/revisions/m1.4-004/hash_manifest.csv)<br>- Lệnh `--verify` kiểm tra khớp 631/631 file hashes | **ACCEPTED**<br>*(Snapshot verified)* |
| **M1.5** | Tấn Phát *(Thanh review)* | Chốt văn bản giao thức kế thừa (Successor Protocol), thống nhất dataset role và tiêu chuẩn nghiên cứu | - Bản hợp đồng giao thức: [`evidence/revisions/m1.5-002/scoped_contract.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/revisions/m1.5-002/scoped_contract.md)<br>- Bảng băm mã nguồn & gói manifest: [`evidence/revisions/m1.5-002/package_manifest.json`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/revisions/m1.5-002/package_manifest.json)<br>- Nhật ký quản trị append-only: [`evidence/revisions/m1.5-002/governance_events.jsonl`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/revisions/m1.5-002/governance_events.jsonl) | **ACCEPTED**<br>*(Protocol frozen)* |
| **M1.6** | Trần Đình Khương | Collision, Alias & Leakage Audit trên 5.385 trang PDF thật; đối chiếu qrels và đo ranh giới chia sẻ tài liệu | - Báo cáo collision: [`evidence/revisions/m1.6-002/collision_report.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/revisions/m1.6-002/collision_report.md)<br>- Kết quả: **0 cross-split leakage**, **0 orphan queries** (1.142/1.142 queries hợp lệ), 5 cặp duplicate nội bộ, đo đạc 205 documents dùng chung giữa các query splits<br>- Danh mục trang & alias: `page_manifest.csv`, `alias_manifest.csv` | **ACCEPTED**<br>*(Zero leakage verified)* |
| **M1.7** | Lê Thanh | Thiết lập Sổ đăng ký thực nghiệm (Registry), quy tắc đặt tên, ma trận truy vết và theo dõi issue | - Sổ thực nghiệm: [`evidence/M1_FINAL/04_experiment_registry/experiment_registry.csv`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/04_experiment_registry/experiment_registry.csv)<br>- Ma trận truy vết: [`traceability_matrix.csv`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/04_experiment_registry/traceability_matrix.csv)<br>- Bảng theo dõi 10 issues mở: [`issue_log.csv`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/04_experiment_registry/issue_log.csv) | **ACCEPTED**<br>*(Traceability verified)* |
| **M1.8** | Trần Đình Khương | Thiết lập cơ chế định tuyến OCR fallback, kiểm soát chất lượng văn bản, timeout và ranh giới bảo vệ GPU | - Logic định tuyến native $\rightarrow$ OCR fallback: `src/qpaf/m11/dataset.py`<br>- Quản lý namespace metadata & ranh giới an toàn: `src/qpaf/m18/namespace.py`<br>- Boundary guard: `src/qpaf/m13/boundary.py`<br>- Toàn bộ 137 unit tests vượt qua an toàn | **ACCEPTED**<br>*(Runtime guards active)* |
| **M1.9 (G1)** | Toàn nhóm | Tổ chức Hội đồng Nghiệm thu Cổng G1, giải quyết blocker, thẩm tra kỹ thuật và ban hành quyết định Cổng G1 | - Nhật ký giải quyết 6 blocker: [`evidence/M1_FINAL/06_G1/G1_blocker_log.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/06_G1/G1_blocker_log.md)<br>- Biên bản First Review: [`evidence/M1_FINAL/06_G1/G1_first_review_record.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/06_G1/G1_first_review_record.md)<br>- Ký Technical Sign-off: [`evidence/M1_FINAL/06_G1/technical_signoff.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/06_G1/technical_signoff.md)<br>- Ký QA Sign-off: [`evidence/M1_FINAL/06_G1/qa_signoff.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/06_G1/qa_signoff.md)<br>- Quyết định G1: [`evidence/M1_FINAL/06_G1/G1_final_decision.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/06_G1/G1_final_decision.md) | **PASSED**<br>*(Conditional Pass)* |
| **M1.10 (R1)** | Tấn Phát | Báo cáo tiến độ tổng kết Sprint 1 và ban hành Biên bản Đóng Milestone 1 chính thức | - Báo cáo Sprint 1 hoàn chỉnh: [`evidence/M1_FINAL/07_R1/Sprint_1_Progress_Report.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/07_R1/Sprint_1_Progress_Report.md)<br>- Biên bản đóng mốc M1: [`evidence/M1_FINAL/07_R1/M1_closure_record.md`](file:///C:/Users/lanph/OneDrive/Desktop/Artificial_Intelligent_Project/evidence/M1_FINAL/07_R1/M1_closure_record.md) | **COMPLETED**<br>*(Milestone 1 Closed)* |

---

## PHẦN II: TOÀN BỘ CÁC LỆNH TERMINAL CỦA DỰ ÁN (PROJECT RUNBOOK)

Mọi lệnh chạy trên PowerShell tại thư mục gốc:
`C:\Users\lanph\OneDrive\Desktop\Artificial_Intelligent_Project`

### 1. Thiết lập môi trường thực thi chuẩn UTF-8
Bắt buộc kích hoạt cờ UTF-8 để không bị lỗi decode chuỗi ký tự tiếng Việt khi chạy qua subprocess:
```powershell
$env:PYTHONUTF8 = '1'
```

---

### 2. Chạy toàn bộ bộ kiểm thử tự động (Unit Test Suite - 137 tests)
Chạy toàn bộ 137 tests kiểm tra toàn diện mã nguồn từ M1.1 đến M1.8:
```powershell
$env:PYTHONUTF8 = '1'; .venv/Scripts/python.exe -m unittest discover -s tests -v
```
*(Chạy nhanh không in chi tiết từng dòng test:)*
```powershell
$env:PYTHONUTF8 = '1'; .venv/Scripts/python.exe -m unittest discover -s tests
```

---

### 3. Tải và tự động tái lập hoàn chỉnh Corpus ViDoSeek từ Hugging Face
Tải file zip tài liệu PDF gốc (758 MB), file annotations `vidoseek.json`, đối chiếu hash SHA-256 từ Hugging Face LFS, và tự động giải nén 292 file PDF vào `data/raw/vidoseek-e91a92b/pdfs/pdf`:
```powershell
.venv/Scripts/python.exe scripts/download_primary_corpus.py `
  --manifest data/manifests/vidoseek-e91a92b-location.json `
  --extract --force
```

---

### 4. Rà soát Corpus thật & Sinh phân chia Splits xác định (M1.3)
Quét toàn bộ 292 PDF trong file zip, mở từng file PDF để đếm 5.385 trang thật, kiểm tra tính hợp lệ của positive targets trong `vidoseek.json` và sinh splits 799/171/172:
```powershell
.venv/Scripts/python.exe scripts/audit_primary_corpus.py `
  --annotations data/raw/vidoseek-e91a92b/vidoseek.json `
  --corpus-zip data/raw/vidoseek-e91a92b/vidoseek_pdf_document.zip `
  --output evidence/revisions/m1.3-001/audit_report.json `
  --splits-dir evidence/revisions/m1.3-001/splits `
  --generate-splits
```

---

### 5. Chạy xác thực Splits chỉ đọc (Read-only Split Verification - M1.3)
Xác minh độc lập không ghi đè: đối chiếu 3 file split (`train_ids.txt`, `val_ids.txt`, `test_ids.txt`) với annotations và PDF corpus thực tế:
```powershell
.venv/Scripts/python.exe scripts/audit_primary_corpus.py `
  --annotations data/raw/vidoseek-e91a92b/vidoseek.json `
  --corpus-zip data/raw/vidoseek-e91a92b/vidoseek_pdf_document.zip `
  --splits-dir evidence/revisions/m1.3-001/splits `
  --verify-splits --dry-run
```

---

### 6. Rà soát Trùng lặp (Collision), Rò rỉ (Leakage) trên 5.385 trang thật (M1.6)
Render 5.385 trang PDF thật ở 72 DPI RGB, băm SHA-256 pixel payload, kiểm tra alias, trùng lặp nội dung, đo đạc rò rỉ split và kiểm tra qrels:
```powershell
.venv/Scripts/python.exe scripts/audit_collisions.py `
  --annotations data/raw/vidoseek-e91a92b/vidoseek.json `
  --corpus-dir data/raw/vidoseek-e91a92b/pdfs/pdf `
  --splits-dir evidence/revisions/m1.3-001/splits `
  --output-dir evidence/revisions/m1.6-002
```
*(Tùy chọn: Chạy nhanh trên fixture mô phỏng 5 tài liệu/20 trang để kiểm tra công cụ:)*
```powershell
.venv/Scripts/python.exe scripts/audit_collisions.py --fixture --output-dir temp_fixture_audit
```

---

### 7. Kiểm kê & Xác thực mã băm toàn bộ Repository (M1.4)
Kiểm tra tính toàn vẹn của tất cả 631 file trong snapshot `m1.4-004` (295 data assets, 28 source files, loại trừ `.tmp`):
```powershell
# Xác thực mã băm 631 file:
.venv/Scripts/python.exe scripts/audit_repository.py --verify evidence/revisions/m1.4-004/hash_manifest.csv

# Tạo snapshot kiểm kê mới:
.venv/Scripts/python.exe scripts/audit_repository.py --output evidence/revisions/m1.4-new-snapshot
```

---

### 8. Tái lập kiểm chứng toán học & bộ tối ưu lõi 13 Features (M1.2)
Chạy kiểm tra gradient sai phân hữu hạn (finite-difference check) và các bước cập nhật trọng số SGD của Gating Network:
```powershell
.venv/Scripts/python.exe scripts/verify_m12.py
```

---

### 9. Kiểm tra chính sách chất lượng OCR & định dạng Run ID (M1.8)
Chạy kiểm thử các trường hợp chuỗi văn bản sạch, văn bản lỗi mã hóa (mojibake), văn bản ngắn và quy chuẩn đặt tên Run ID M1.7:
```powershell
.venv/Scripts/python.exe scripts/audit_ocr_policy.py
```

---

### 10. Chạy thử nghiệm Pipeline mô phỏng M1.1 (Software Fixture)
Chạy kiểm thử luồng trích xuất BM25, Dense, Visual và giải bài toán Oracle trên tập dữ liệu mẫu nhỏ:
```powershell
# Thực thi pipeline trên fixture mẫu:
.venv/Scripts/python.exe scripts/run_m11_modal.py --config configs/m1.1/software_fixture.toml

# Đánh giá per-query metrics trên kết quả vừa chạy:
.venv/Scripts/python.exe scripts/evaluate_m11.py --run-dir results/m1.1/software_fixture/runs/software-fixture/oracle/latest
```

---

### 11. Các lệnh chạy từng module kiểm thử riêng biệt
Khi cần gỡ lỗi hoặc phát triển sâu từng thành phần:
```powershell
# Kiểm thử pipeline M1.1 & artifacts:
.venv/Scripts/python.exe -m unittest tests/test_m11_artifacts.py

# Kiểm thử bộ tối ưu & gradient M1.2:
.venv/Scripts/python.exe -m unittest tests/test_m12_fusion.py tests/test_m12_gating.py tests/test_m12_loss.py tests/test_m12_training.py

# Kiểm thử splits & corpus M1.3:
.venv/Scripts/python.exe -m unittest tests/test_m13_splits.py tests/test_m13_corpus.py tests/test_m13_cli.py tests/test_m13_vidoseek.py

# Kiểm thử kiểm kê M1.4:
.venv/Scripts/python.exe -m unittest tests/test_audit.py

# Kiểm thử collision M1.6:
.venv/Scripts/python.exe -m unittest tests/test_m16_collision.py tests/test_m16_real_audit.py

# Kiểm thử registry M1.7:
.venv/Scripts/python.exe -m unittest tests/test_m17_registry.py

# Kiểm thử OCR & runtime guards M1.8:
.venv/Scripts/python.exe -m unittest tests/test_m18_ocr.py tests/test_m18_runtime.py
```
