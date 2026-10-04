# M1.3 Primary-Corpus Audit Package & Closed Boundary — Design Spec (ViDoSeek)

**Feature Name:** `m13-primary-corpus`  
**Target Dataset:** `https://huggingface.co/datasets/Qiuchen-Wang/ViDoSeek`  
**Status:** DRAFT (Updated for ViDoSeek)  
**Author:** Khương (Technical / Data Owner)  
**Date:** 2026-09-28  

---

## 1. Mục tiêu và Bối cảnh (Context & Scope)

Theo kế hoạch tổng thể ([`POAI_Milestone_Group01_Hoan_Chinh.xlsx`](file:///home/intern-tdkhuong/Desktop/qpaf-visual-document-retrieval/docs/GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx)), cấu hình thực tế tại [`configs/m1.1/vidoseek.toml`](file:///home/intern-tdkhuong/Desktop/qpaf-visual-document-retrieval/configs/m1.1/vidoseek.toml) và [`docs/06_handover/m1-restart-handoff.md`](file:///home/intern-tdkhuong/Desktop/qpaf-visual-document-retrieval/docs/m1-restart-handoff.md):
* **Tập dữ liệu chính xác:** **`Qiuchen-Wang/ViDoSeek`** tại `https://huggingface.co/datasets/Qiuchen-Wang/ViDoSeek`.
* **M1.3 giải quyết triệt để:** Bất đồng bộ giữa protocol cũ của Tấn Phát (vốn chép nhầm ViMDoc từ máy cá nhân cũ) với repo mới (đang chuẩn hóa hoàn toàn theo **ViDoSeek**).
* **Đầu ra của M1.3:**
  1. Gói công cụ kiểm toán dữ liệu chạy thuần túy trên **CPU** (`CPU-only audit package`), không tiêu tốn GPU, không đòi hỏi tải full tệp nặng khi chạy test.
  2. Cơ chế phân tích và lập manifest chuẩn hóa cho **ViDoSeek**:
     - Phân tích `vidoseek.json` (1.142 queries/examples).
     - Phân tích cấu trúc tài liệu PDF từ `vidoseek_pdf_document.zip`.
     - Ánh xạ rõ ràng: mỗi file PDF là 1 tài liệu (`document_id`), các trang là số thứ tự 1-based (`{document_id}_page_{num}`).
     - Đối chiếu và kiểm tra tính hợp lệ của `qrels` (`reference_page` nằm trong phạm vi số trang thực tế của tài liệu).
  3. Cơ chế phân tách tập Train / Val / Test tất định bằng băm `SHA256(seed:query_id)` hoàn toàn không dùng nhãn (label-free).
  4. Khóa chặt ranh giới thực thi (**Closed Boundary**): Đảm bảo `execution_authorized = false`, cấm mọi hành vi tự ý chạy mô hình khi chưa thông qua Gate G1.

---

## 2. Đặc tả dữ liệu ViDoSeek (`Qiuchen-Wang/ViDoSeek`)

### 2.1 Định danh và Cấu trúc
* **Hugging Face Hub:** `https://huggingface.co/datasets/Qiuchen-Wang/ViDoSeek`
* **Pinned Revision:** `e91a92ba5f38690696c7e66be5c5474b54c6e791`
* **Tệp thành phần chính:**
  1. `vidoseek.json`: Chứa mảng `examples` với 1.142 query items.
     * Mỗi item gồm: `uid` (query ID), `query` (nội dung câu hỏi), `meta_info` (chứa `file_name` của file PDF và `reference_page` danh sách các trang liên quan).
  2. `vidoseek_pdf_document.zip`: Chứa toàn bộ các tài liệu PDF gốc.

### 2.2 Quy tắc Ánh xạ & Toàn vẹn (Integrity & Mapping Invariants)
* **Document ID:** Tên gốc của tệp PDF (ví dụ `doc_01.pdf`).
* **Page ID:** Định dạng chuẩn tắc `{file_name_stem}_page_{page_num:04d}` (1-based index).
* **Kiểm tra Qrels:**
  * Mọi `reference_page` phải là số nguyên $\ge 1$ và $\le$ tổng số trang của file PDF tương ứng.
  * Không chứa query ID rỗng, không chứa query ID trùng lặp.
* **Phân chia Splits chuẩn tắc (Label-free Deterministic Splits):**
  * Hỗ trợ chia tập có thể tái lập dựa trên băm `SHA256(f"{namespace}:{seed}:{query_id}")`.
  * Đảm bảo không rò rỉ (leakage): $\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$.

---

## 3. Kiến trúc Phân hệ M1.3 (`src/qpaf/m13/`)

```text
src/qpaf/m13/
├── __init__.py           # Package exports
├── vidoseek.py           # Phân tích cú pháp vidoseek.json, map PDF pages, kiểm tra qrels
├── splits.py             # Sinh và kiểm tra splits tất định cho ViDoSeek
├── corpus.py             # Quét thư mục PDF/ZIP, tính mã băm SHA256, sinh fixture giả lập
└── boundary.py           # Kiểm soát Closed Boundary (chặn tự ý chạy training khi chưa có G1)

scripts/
└── audit_primary_corpus.py  # CLI kiểm toán ViDoSeek và xuất báo cáo JSON/CSV

tests/
├── test_m13_vidoseek.py  # Unit tests phân tích annotations và qrels của ViDoSeek
├── test_m13_splits.py    # Unit tests thuật toán chia split ViDoSeek, kiểm tra zero-overlap
├── test_m13_corpus.py    # Unit tests kiểm kê file ZIP/PDF, kiểm tra hash trên CPU
└── test_m13_boundary.py  # Unit tests cơ chế Closed Boundary Guard

docs/
└── m1.3-primary-corpus.md # Tài liệu đặc tả và hướng dẫn nghiệm thu M1.3
```

### 3.1 Chi tiết các chức năng module

* **`vidoseek.py`:**
  * `parse_vidoseek_annotations(json_path_or_dict, doc_page_counts=None) -> ViDoSeekDataset`:
    * Đọc dữ liệu `examples`, trích xuất queries, document references, và qrels.
    * Kiểm tra lỗi: query trùng, query rỗng, trang tham chiếu vượt quá số trang của tài liệu.
* **`splits.py`:**
  * `create_deterministic_splits(query_ids, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15, seed=2026, namespace="vidoseek_v1") -> dict[str, list[str]]`:
    * Chia 1.142 queries thành Train / Val / Test hoàn toàn dựa trên băm SHA-256 không nhãn.
  * `verify_split_disjointness(splits_dict) -> bool`:
    * Kiểm tra triệt để không có query nào nằm ở 2 tập khác nhau.
* **`corpus.py`:**
  * `inspect_pdf_archive(zip_path) -> dict[str, int]`:
    * Kiểm kê danh sách file PDF và kiểm tra tính toàn vẹn của archive mà không cần bung toàn bộ ra đĩa nếu không cần thiết.
  * `generate_synthetic_vidoseek_fixture(target_dir)`:
    * Tạo bộ fixture nhỏ gồm 5 queries và 3 tài liệu PDF mẫu để test unit cục bộ siêu nhanh trên mọi máy.
* **`boundary.py`:**
  * `enforce_closed_boundary()`:
    * Kiểm tra cờ `execution_authorized`. Mặc định luôn là `False`.
    * Ngăn chặn việc chạy các script nặng ở M2/M3 trước khi Gate G1 thông qua.
* **`scripts/audit_primary_corpus.py`:**
  * CLI kiểm toán:
    ```bash
    python scripts/audit_primary_corpus.py --config configs/m1.1/vidoseek.toml --output results/m1.3/audit_report.json
    ```

---

## 4. Kế hoạch kiểm thử & Tiêu chí nghiệm thu (Acceptance Criteria)

1. **Khả năng tái lập 100% trên CPU:**
   * Chạy toàn bộ test `python -m unittest discover -s tests -p "test_m13_*.py"` pass 100% không cần GPU và không phụ thuộc vào kết nối mạng ngoài.
2. **Khớp nối với M1.1:**
   * Đọc và tương thích hoàn toàn với schema của [`configs/m1.1/vidoseek.toml`](file:///home/intern-tdkhuong/Desktop/qpaf-visual-document-retrieval/configs/m1.1/vidoseek.toml) và [`src/qpaf/m11/dataset.py`](file:///home/intern-tdkhuong/Desktop/qpaf-visual-document-retrieval/src/qpaf/m11/dataset.py).
3. **Tài liệu đầy đủ:**
   * Viết tài liệu [`docs/04_data_protocol/m1.3-primary-corpus.md`](file:///home/intern-tdkhuong/Desktop/qpaf-visual-document-retrieval/docs/m1.3-primary-corpus.md) ghi nhận hướng dẫn kiểm toán ViDoSeek, các lệnh chạy, và bảng đối chiếu nghiệm thu.
