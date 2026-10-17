# M1.8 OCR Policy, Failure Thresholds & Artifact Namespace — Design Spec

**Feature Name:** `m18-ocr-artifact`  
**Status:** DRAFT (Ready for Implementation)  
**Author:** Khương (Data & Technical Owner)  
**Date:** 2026-09-28  

---

## 1. Mục tiêu và Bối cảnh (Context & Scope)

Theo tiến độ `TIMELINE_fixed.md` và các hướng dẫn tại `docs/06_handover/m1-restart-handoff.md`:
* **Ranh giới công việc:**
  - **M1.8** là giai đoạn chuẩn bị khung chính sách kiểm tra chất lượng trích xuất (OCR Checklist), định nghĩa toán học các biến đo lường và thiết lập ngưỡng dự kiến (Failure Thresholds), cùng với việc chuẩn hóa không gian tên lưu trữ hiện vật (Artifact Namespace).
  - **M2.3** sẽ thực hiện chạy thực nghiệm đo đạc mẫu (Sample Calibration Run) trên tập PDF thật của ViDoSeek để chính thức đóng băng (Freeze) các giá trị số học.
  - **M2.6** mới chạy toàn bộ OCR trên toàn bộ kho tài liệu (Full OCR Run).
* **Mục tiêu đáp ứng Gate G1:**
  - `G1-OCR-01`: Quy tắc phân biệt Native Text vs OCR Fallback có cơ chế đo lường và ghi log rõ ràng.
  - `G1-OCR-02`: Ngưỡng thất bại phải là đại lượng số học, đo đạc được, tuân thủ nguyên tắc fail-closed (ngắt lỗi có ghi nhận, không nuốt lỗi âm thầm). Các giá trị số học được ghi nhận ở trạng thái **PROVISIONAL (DỰ KIẾN)** từ tiêu chuẩn ngành (Industry Heuristic), chờ freeze tại M2.3.
  - `G1-OCR-03`: Không gian tên hiện vật khớp 100% với đặc tả của Thanh tại `evidence/M1_FINAL/04_experiment_registry/experiment_naming_rules.md`.

---

## 2. Đặc tả Kỹ thuật OCR Policy (`ocr_checklist.md` & `ocr_failure_threshold.md`)

### 2.1 Quy trình Phân định Đường dẫn Kép (Dual-Path Extraction Routing)
1. **Kiểm tra lớp văn bản gốc (PDF Native Text Layer):**
   - Thử trích xuất văn bản trực tiếp từ PDF bằng PyMuPDF (fitz) hoặc pdfplumber.
   - Tính toán các chỉ số chất lượng: độ dài văn bản ($C_{page}$) và tỷ lệ ký tự in được ($R_{printable}$).
2. **Điều kiện kích hoạt OCR Fallback:**
   - Trang không có text layer hoặc $C_{page} < C_{min}$ (dự kiến $50$ ký tự).
   - Tỷ lệ ký tự lỗi/rác font $R_{printable} < R_{min}$ (dự kiến $85\%$).
   - Khi kích hoạt Fallback: chuyển sang OCR engine (Tesseract OCR v5.x) ở độ phân giải chuẩn 300 DPI, ngôn ngữ cấu hình theo dataset (VIE/ENG).
3. **Chính sách Fail-Closed & Ghi nhận thất bại:**
   - Mọi trang bị lỗi đọc, timeout hoặc không trích xuất được chữ đều phải xuất bản ghi vào `failures.csv`.
   - Tuyệt đối cấm hành vi chuyển lỗi thành chuỗi rỗng `""` rồi báo cáo là trang thành công.

### 2.2 Định nghĩa Toán học của các Chỉ số Chất lượng (Metric Definitions)

1. **Độ dài ký tự trang ($C_{page}$):**
   $$C_{page} = \text{len}(\text{raw\_text})$$
   - *Ngưỡng dự kiến (Provisional):* $C_{min} = 50$ ký tự.
2. **Tỷ lệ ký tự in được hợp lệ ($R_{printable}$):**
   $$R_{printable} = \frac{\sum_{c \in \text{text}} \mathbb{I}[c \text{ is printable and not control char}]}{C_{page}}$$
   - *Ngưỡng dự kiến (Provisional):* $R_{min} = 0.85$ ($85\%$).
3. **Điểm tin cậy OCR trung bình ($S_{conf}$):**
   $$S_{conf} = \frac{1}{|W|} \sum_{w \in W} \text{confidence}(w)$$
   - *Ngưỡng dự kiến (Provisional):* $S_{min} = 60.0\%$.
4. **Trần thời gian xử lý mỗi trang ($T_{page}$):**
   $$T_{page} \le 15.0 \text{ giây}$$
   - *Cơ chế:* Ngắt timeout cưỡng bức nếu vượt 15 giây, ghi bản ghi lỗi (`failure_record`) vào `failures.csv`.
5. **Dung sai tỷ lệ lỗi toàn kho tài liệu ($E_{corpus}$):**
   $$E_{corpus} = \frac{N_{failed\_pages}}{N_{total\_pages}} \le 1.0\%$$

> **Cam kết tính bất biến & Chống số liệu bịa đặt:**  
> Mọi con số trên được dán nhãn `PROVISIONAL — BENCHMARK HEURISTIC`. Gói M1.8 ghi rõ điều kiện chuyển sang `FROZEN` là sau khi có báo cáo calibration chính thức tại M2.3.

---

## 3. Đặc tả Không gian tên Hiện vật (`artifact_namespace.md`)

Đồng bộ 100% với Thanh (`experiment_naming_rules.md`):

### 3.1 Cấu trúc Thư mục Lưu trữ
```text
artifacts/<experiment_id>/<run_id>/
├── metadata.json       # Git commit, UTC window, owner, hardware, config_hash, split_hash
├── config.json         # Cấu hình TOML/JSON đã resolve
├── command.txt         # Lệnh thực thi chính xác
├── environment.txt     # Python, packages, pip freeze, hardware platform
├── outputs/            # Kết quả tính toán, manifests, caches
├── failures.csv        # Ghi nhận chi tiết từng trang/mẫu lỗi (fail-closed)
└── hashes.csv          # Bảng băm SHA-256 của từng file đầu ra
```

### 3.2 Quy tắc Đặt tên Run ID
- **Định dạng:** `RUN-<experiment_id>-<YYYYMMDDTHHMMSSZ>-A<NN>`
  - Ví dụ: `RUN-QPAF-M1_8-OCR-001-20260928T164000Z-A01`
  - Thử lần đầu là `A01`, lần thử lại hợp lệ ghi `A02` và phải liên kết trường `retry_of` trỏ tới exact prior run ID.
- **Nguyên tắc Create-Once:** Thư mục chỉ được tạo mới. Nếu thư mục đã tồn tại trên đĩa, chương trình lập tức từ chối thực thi và dừng khẩn cấp.

---

## 4. Kiến trúc Phân hệ M1.8 (`src/qpaf/m18/`)

```text
src/qpaf/m18/
├── __init__.py           # Package exports
├── ocr_policy.py         # Lớp OCRQualityAuditor, tính C_page, R_printable, phân loại routing
└── namespace.py          # Lớp ArtifactNamespaceManager, tạo thư mục create-once, kiểm tra schema Run ID

scripts/
└── audit_ocr_policy.py   # CLI tool hiệu chuẩn và kiểm tra chính sách OCR & Namespace

tests/
└── test_m18_ocr.py       # Bộ kiểm thử đơn vị tự động kiểm tra toàn bộ luồng logic

evidence/revisions/m1.8-001/
├── ocr_checklist.md           # Hướng dẫn kiểm tra OCR chi tiết
├── ocr_failure_threshold.md   # Bảng ngưỡng định lượng và công thức toán học
├── artifact_namespace.md      # Quy chuẩn không gian tên hiện vật khớp M1.7
├── calibration_methodology.md # Đặc tả phương pháp đo đạc mẫu M2.3
└── hash_manifest.csv          # Bảng băm bảo vệ tính bất biến của revision
```

---

## 5. Kế hoạch Nghiệm thu (Verification Criteria)

1. `tests/test_m18_ocr.py` đạt 100% Pass (toàn bộ 97+ tests của dự án đều Green).
2. Không sửa đè các file gốc tại `evidence/M1_FINAL/05_ocr_artifacts/` để bảo vệ mã băm của `test_m17_registry.py`.
3. Gói `evidence/revisions/m1.8-001/` được xuất bản đầy đủ và băm SHA-256 bảo vệ.
