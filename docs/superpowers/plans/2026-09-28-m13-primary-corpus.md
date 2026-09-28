# M1.3 Primary-Corpus Audit Package & Closed Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng gói công cụ kiểm toán dữ liệu ViDoSeek (`CPU-only audit package`), sinh/kiểm tra phân chia split tất định không nhãn, và cơ chế bảo vệ ranh giới an toàn (`Closed Boundary Guard`) phục vụ Milestone M1.3.

**Architecture:** Tạo phân hệ `src/qpaf/m13/` gồm 4 module độc lập: `boundary.py` (khóa thực thi), `vidoseek.py` (phân tích annotations và qrels), `splits.py` (chia tập train/val/test tất định bằng SHA256), `corpus.py` (kiểm kê tệp và fixture giả lập), cùng công cụ dòng lệnh `scripts/audit_primary_corpus.py` và tài liệu chuẩn `docs/m1.3-primary-corpus.md`.

**Tech Stack:** Python 3.11, standard library (`hashlib`, `json`, `pathlib`, `zipfile`, `unittest`), không đòi hỏi thư viện GPU hay tài nguyên nặng.

**Spec:** [`docs/superpowers/specs/2026-09-28-m13-primary-corpus-design.md`](file:///home/intern-tdkhuong/Desktop/qpaf-visual-document-retrieval/docs/superpowers/specs/2026-09-28-m13-primary-corpus-design.md)

## Global Constraints

- Chạy thuần túy trên CPU (`CPU-only`), không import torch/cuda/modal trong mã kiểm toán cốt lõi.
- Không hardcode đường dẫn tuyệt đối hoặc thông tin cá nhân.
- Ranh giới thực thi mặc định luôn đóng: `execution_authorized = false`.
- Thuật toán phân tách tập dữ liệu là hoàn toàn không nhãn (`label-free`), dựa trên băm SHA-256 tất định.
- Mã nguồn tuân thủ PEP 8 và tương thích hoàn toàn với cấu trúc existing repo.

## Review Focus

1. **Query validation:** Phát hiện và chặn query trùng lặp, query rỗng, hoặc query thiếu trường bắt buộc.
2. **Qrels bounds:** Bắt lỗi nếu `reference_page` nhỏ hơn 1 hoặc vượt quá số trang thực tế của file PDF.
3. **Split disjointness:** Đảm bảo toán học $A \cap B = \emptyset$ giữa mọi cặp tập dữ liệu (zero leakage).
4. **Closed boundary enforcement:** Chặn đứng mọi lời gọi thực thi model training trái phép khi chưa có chứng nhận G1.
5. **Offline capability:** Khả năng chạy kiểm thử pass 100% bằng mock fixture mà không cần tải file zip 20GB về máy.

---

### Task 1: Module Ranh giới an toàn (Closed Boundary Guard)

**Files:**
- Create: `tests/test_m13_boundary.py`
- Create: `src/qpaf/m13/__init__.py`
- Create: `src/qpaf/m13/boundary.py`

- [x] **Step 1:** Viết failing unit tests trong `tests/test_m13_boundary.py` kiểm tra `ExecutionBoundary`: mặc định bị khóa (`is_authorized() == False`), bắn `PermissionError` khi gọi `assert_execution_authorized()`, và hỗ trợ ghi nhận trạng thái kiểm toán.
- [x] **Step 2:** Chạy test để đảm bảo fail: `python3 -m unittest tests/test_m13_boundary.py`.
- [x] **Step 3:** Triển khai `src/qpaf/m13/boundary.py` và export trong `src/qpaf/m13/__init__.py`.
- [x] **Step 4:** Chạy lại test để đảm bảo pass 100%: `python3 -m unittest tests/test_m13_boundary.py`.
- [x] **Step 5:** Commit thay đổi: `git commit -m "feat(m1.3): add execution boundary guard and tests"`.

---

### Task 2: Module Phân tích ViDoSeek Annotations & Qrels

**Files:**
- Create: `tests/test_m13_vidoseek.py`
- Create: `src/qpaf/m13/vidoseek.py`

- [x] **Step 1:** Viết failing unit tests trong `tests/test_m13_vidoseek.py` kiểm tra:
  - Phân tích cú pháp hợp lệ của `vidoseek.json` (`examples` chứa `uid`, `query`, `meta_info`).
  - Ánh xạ `document_id` và định dạng `page_id` chuẩn `{doc}_page_{num:04d}`.
  - Xử lý lỗi: trùng query ID, query rỗng, trang tham chiếu vượt biên (`out-of-bounds page`).
- [x] **Step 2:** Chạy test để đảm bảo fail: `python3 -m unittest tests/test_m13_vidoseek.py`.
- [x] **Step 3:** Triển khai `src/qpaf/m13/vidoseek.py`.
- [x] **Step 4:** Chạy lại test để đảm bảo pass 100%: `python3 -m unittest tests/test_m13_vidoseek.py`.
- [x] **Step 5:** Commit thay đổi: `git commit -m "feat(m1.3): add ViDoSeek annotation parser and qrels validator"`.

---

### Task 3: Module Phân chia Split Tất định (Deterministic Splits)

**Files:**
- Create: `tests/test_m13_splits.py`
- Create: `src/qpaf/m13/splits.py`

- [x] **Step 1:** Viết failing unit tests trong `tests/test_m13_splits.py` kiểm tra:
  - Thuật toán băm SHA256 cho phân chia Train / Val / Test.
  - Tính tất định (cùng seed/query_ids luôn ra cùng kết quả).
  - Kiểm tra tính rời rạc tuyệt đối (zero overlap giữa các tập).
  - Serialization ra định dạng text mỗi dòng một ID có kèm hash SHA256.
- [x] **Step 2:** Chạy test để đảm bảo fail: `python3 -m unittest tests/test_m13_splits.py`.
- [x] **Step 3:** Triển khai `src/qpaf/m13/splits.py`.
- [x] **Step 4:** Chạy lại test để đảm bảo pass 100%: `python3 -m unittest tests/test_m13_splits.py`.
- [x] **Step 5:** Commit thay đổi: `git commit -m "feat(m1.3): add deterministic split derivation and verification"`.

---

### Task 4: Module Kiểm kê Corpus & Fixture Giả lập (Corpus Scanner)

**Files:**
- Create: `tests/test_m13_corpus.py`
- Create: `src/qpaf/m13/corpus.py`

- [x] **Step 1:** Viết failing unit tests trong `tests/test_m13_corpus.py` kiểm tra:
  - Kiểm tra và đếm tài liệu trong file ZIP mà không cần giải nén đĩa đầy đủ.
  - Quét thư mục PDF thật trên máy.
  - Tạo bộ fixture giả lập nhỏ (synthetic dataset) phục vụ kiểm thử cô lập.
- [x] **Step 2:** Chạy test để đảm bảo fail: `python3 -m unittest tests/test_m13_corpus.py`.
- [x] **Step 3:** Triển khai `src/qpaf/m13/corpus.py`.
- [x] **Step 4:** Chạy lại test để đảm bảo pass 100%: `python3 -m unittest tests/test_m13_corpus.py`.
- [x] **Step 5:** Commit thay đổi: `git commit -m "feat(m1.3): add CPU corpus inspector and fixture generator"`.

---

### Task 5: Công cụ Dòng lệnh Kiểm toán CLI

**Files:**
- Create: `tests/test_m13_cli.py`
- Create: `scripts/audit_primary_corpus.py`

- [x] **Step 1:** Viết failing unit tests trong `tests/test_m13_cli.py` kiểm tra gọi CLI:
  - Chạy với `--dry-run` hoặc `--generate-splits`.
  - Xuất báo cáo JSON kiểm toán với đầy đủ thông tin metadata, counts, và cờ boundary.
- [x] **Step 2:** Chạy test để đảm bảo fail: `python3 -m unittest tests/test_m13_cli.py`.
- [x] **Step 3:** Triển khai `scripts/audit_primary_corpus.py`.
- [x] **Step 4:** Chạy lại test để đảm bảo pass 100%: `python3 -m unittest tests/test_m13_cli.py`.
- [x] **Step 5:** Commit thay đổi: `git commit -m "feat(m1.3): add CLI primary corpus audit tool"`.

---

### Task 6: Tài liệu Hướng dẫn & Báo cáo Nghiệm thu M1.3

**Files:**
- Create: `docs/m1.3-primary-corpus.md`
- Modify: `docs/m1.1-m1.2-status.md` (hoặc bổ sung phần M1.3)

- [x] **Step 1:** Viết tài liệu `docs/m1.3-primary-corpus.md` trình bày chi tiết mục đích, cách cấu hình, cách chạy CLI, các tiêu chí nghiệm thu và ranh giới nghiên cứu (tương tự như `docs/m1.1-modal-oracle.md` và `docs/m1.2-method-core.md`).
- [x] **Step 2:** Chạy toàn bộ test suite của dự án (`python3 -m unittest discover -s tests -v`) để đảm bảo không có bất kỳ regression nào.
- [x] **Step 3:** Commit tài liệu: `git commit -m "docs(m1.3): add M1.3 primary corpus audit documentation"`.
