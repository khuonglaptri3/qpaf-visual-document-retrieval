#!/usr/bin/env python3
"""CLI tool for M1.8 OCR Quality Policy, Failure Thresholds & Artifact Namespace Audit."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure src is in python path
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from qpaf.m18.namespace import format_canonical_run_id, parse_canonical_run_id
from qpaf.m18.ocr_policy import evaluate_page_text


def generate_ocr_checklist_content() -> str:
    return """# M1.8 — OCR Calibration & Quality Checklist

**Status:** `READY_FOR_CALIBRATION`
**Owner:** Khương (Data & Technical Owner)
**Target Pipeline:** QPAF Visual Document Retrieval (Dual-Path Extraction)
**Updated:** 2026-09-28

---

## 1. Engine, Tools & Execution Boundary

1. **Native Text Layer Parser:**
   - Primary: PyMuPDF (`fitz` >= 1.23) or `pdfplumber` (CPU-only execution).
   - Task: Direct glyph and character stream extraction from vector PDF text streams.
2. **Visual OCR Fallback Engine:**
   - Primary: Tesseract OCR (v5.3+) or PaddleOCR (CPU mode).
   - Image Preprocessing: 300 DPI page rendering via `pdftoppm` / `pdf2image`, contrast normalization, deskewing.
   - Language pack: `vie` + `eng` for multilingual ViDoSeek documents.
3. **Execution Guard:**
   - In accordance with Gate G1 boundary (`execution_authorized = false`), heavy OCR model execution remains closed.
   - Full OCR corpus processing is designated for **Milestone M2.6**.

---

## 2. Dual-Path Extraction Decision Rules

Mọi trang tài liệu PDF đều đi qua quy trình kiểm tra chất lượng tự động:

```text
[PDF Page] 
    │
    ▼
[Trích xuất Native Text] ──> Đo chất lượng (C_page, R_printable)
    │
    ├──> ĐẠT CHUẨN (C_page >= 50, R_printable >= 85%) ──> [NATIVE_TEXT_QUALIFIED]
    │                                                            │
    └──> KHÔNG ĐẠT (Text thiếu, lỗi font Mojibake)                │
            │                                                    ▼
            ▼                                            [BM25 Indexer / Corpus]
    [OCR Fallback: Render 300 DPI + Tesseract]
            │
            ├──> ĐẠT (Confidence >= 60%) ───────────────> [OCR_FALLBACK_SUCCESS]
            │
            └──> LỖI (Timeout > 15s hoặc rỗng) ──────────> [EXTRACTION_FAILED] 
                                                                 │
                                                                 ▼
                                                         [failures.csv Record]
```

---

## 3. Quy tắc Fail-Closed & Audit Log

1. Mọi trang rơi vào `EXTRACTION_FAILED` đều bắt buộc phải ghi 1 bản ghi vào `failures.csv` với các trường:
   `document_id,page_id,error_type,runtime_seconds,source_hash`.
2. **Tuyệt đối cấm:** Chuyển trang lỗi thành chuỗi rỗng `""` rồi báo cáo là trang thành công.
3. Giữ nguyên mã định danh trang canonical `{document_id}_page_{page_number:04d}` xuyên suốt toàn bộ pipeline để đảm bảo qrels và cache truy hồi khớp 100%.
"""


def generate_ocr_failure_threshold_content() -> str:
    return """# M1.8 — OCR Failure Thresholds & Metric Definitions

**Status:** `PROVISIONAL — BENCHMARK HEURISTIC (AWAITING M2.3 SAMPLE CALIBRATION)`
**Owner:** Khương (Data & Technical Owner)
**Evaluator:** QPAF Quality Policy Engine v1.0
**Updated:** 2026-09-28

---

## 1. Cơ sở Khoa học & Cam kết Không Bịa đặt Số liệu

Theo đúng Nghị định thư bàn giao tại `docs/m1-restart-handoff.md` (mục 4) và kế hoạch Superpowers:
- **Ranh giới:** M1.8 xây dựng khung công thức toán học và thiết lập các giá trị tham chiếu dự kiến (**Provisional Benchmark Heuristics**) lấy từ thực hành tiêu chuẩn công nghiệp (Unstructured.io, PDFMiner, Tesseract Guidelines).
- **Điều kiện Freeze chính thức:** Các giá trị số học chỉ được chốt chính thức (Frozen) sau đợt đo đạc mẫu thực nghiệm (Calibration Run) trên tập PDF thật của ViDoSeek tại **Milestone M2.3**.

---

## 2. Định nghĩa Toán học của các Chỉ số Đo lường

| Chỉ số | Ký hiệu | Công thức toán học | Ngưỡng dự kiến (Provisional) | Hành động khi vi phạm |
| :--- | :--- | :--- | :--- | :--- |
| **Độ dài ký tự trang** | $C_{page}$ | $C_{page} = \text{len}(\text{raw\_text})$ | $C_{page} \ge 50$ ký tự | Kích hoạt OCR Fallback |
| **Tỷ lệ ký tự in được** | $R_{printable}$ | $\frac{\sum_{c \in \text{text}} \mathbb{I}[c \text{ is printable}]}{C_{page}}$ | $R_{printable} \ge 0.85$ ($85\%$) | Kích hoạt OCR Fallback (lỗi font) |
| **Độ tin cậy OCR** | $S_{conf}$ | $\frac{1}{\|W\|} \sum_{w \in W} \text{conf}(w)$ | $S_{conf} \ge 60.0\%$ | Đánh dấu cảnh báo chất lượng thấp |
| **Trần thời gian trang** | $T_{page}$ | Thời gian xử lý CPU / trang | $T_{page} \le 15.0$ giây | Ngắt timeout, ghi vào `failures.csv` |
| **Tỷ lệ lỗi toàn corpus** | $E_{corpus}$ | $\frac{N_{failed}}{N_{total}}$ | $E_{corpus} \le 1.0\%$ | Dừng đợt chạy (Fail-Closed) nếu vượt |

---

## 3. Bảng Theo dõi Hiệu chuẩn (Calibration Tracking)

| Hạng mục kiểm tra | Căn cứ chọn ngưỡng | Trạng thái hiện tại | Lộ trình nghiệm thu |
| :--- | :--- | :--- | :--- |
| **Chất lượng Native Text** | Phân tích phân bố ký tự trên mẫu ViDoSeek | `PROVISIONAL (50 ký tự, 85% printable)` | Đo đạc chính thức tại M2.3 |
| **Chất lượng OCR Fallback** | Đánh giá độ tin cậy từ ngữ Tesseract | `PROVISIONAL (60% confidence)` | Đo đạc chính thức tại M2.3 |
| **Tài nguyên & Timeout** | Bounded CPU profiling trên mẫu PDF | `PROVISIONAL (15s timeout / 512MB RAM)`| Đo đạc chính thức tại M2.3 |
| **Dung sai lỗi hệ thống** | Tỷ lệ trang scan hỏng hoặc ảnh thuần | `PROVISIONAL (1.0% max fail)` | Freeze tại Gate G1 / M2.3 |
"""


def generate_artifact_namespace_content() -> str:
    return """# M1.8 — Canonical Artifact Namespace Specification

**Status:** `ACTIVE — ALIGNED WITH M1.7 EXPERIMENT REGISTRY`
**Owner:** Khương (Data & Technical Owner)
**Reviewed by:** Đồng bộ với `evidence/M1_FINAL/04_experiment_registry/experiment_naming_rules.md` của Thanh
**Updated:** 2026-09-28

---

## 1. Cấu trúc Không gian tên Bất biến (Immutable Layout)

Mọi lần chạy thực nghiệm hợp lệ trong tương lai (sau khi Gate G1 cấp phép) đều bắt buộc tuân thủ cấu trúc lưu trữ:

```text
artifacts/<experiment_id>/<run_id>/
├── metadata.json       # Metadata: Git commit, UTC start/end, hardware, config_hash, split_hash
├── config.json         # Cấu hình TOML/JSON đầy đủ đã resolve
├── command.txt         # Lệnh thực thi chính xác (CLI command)
├── environment.txt     # Python version, pip freeze, OS environment
├── outputs/            # Toàn bộ tệp kết quả (manifests, embeddings, BM25 scores)
├── failures.csv        # Nhật ký chi tiết các mẫu/trang lỗi (fail-closed)
└── hashes.csv          # Mã băm SHA-256 của từng tệp đầu ra trong thư mục
```

---

## 2. Quy tắc Đặt tên Run ID

Run ID tuân theo cú pháp nghiêm ngặt của M1.7:

```text
RUN-<experiment_id>-<YYYYMMDDTHHMMSSZ>-A<NN>
```

- `<experiment_id>`: Theo đăng ký registry, ví dụ `QPAF-M1_8-OCR-001`, `QPAF-M2_3-CAL-001`.
- `<YYYYMMDDTHHMMSSZ>`: Dấu thời gian bắt đầu theo chuẩn UTC (ví dụ `20260928T164500Z`).
- `A<NN>`: Số thứ tự lần thực thi được cấp phép (`A01` cho lần đầu; `A02` cho lần thử lại và phải có `retry_of`).

---

## 3. Nguyên tắc Create-Once & Chuỗi Thẩm định

1. **Bảo vệ Create-Once:** Thư mục `artifacts/<experiment_id>/<run_id>/` chỉ được tạo mới một lần. Nếu thư mục đã tồn tại trên ổ đĩa, chương trình lập tức ném ngoại lệ `FileExistsError` và từ chối ghi đè.
2. **Chuỗi thẩm định nguồn gốc (Review Chain):**
   $$\text{Run} \longrightarrow \text{Config} \longrightarrow \text{Commit} \longrightarrow \text{Data} \longrightarrow \text{Hash} \longrightarrow \text{Output}$$
"""


def generate_calibration_methodology_content() -> str:
    return """# M1.8 — Calibration Methodology for Milestone M2.3

**Status:** `PLANNED PROTOCOL`
**Owner:** Khương (Data & Technical Owner)
**Target Milestone:** M2.3 (Sample Calibration Run)

---

## 1. Mục đích Đo đạc Mẫu (Purpose of Calibration)

Nhằm chuyển đổi các ngưỡng dự kiến (**Provisional**) ở M1.8 thành các giá trị đóng băng chính thức (**Frozen Thresholds**), đợt chạy Calibration M2.3 sẽ thực hiện đo đạc thực nghiệm trên một tập mẫu đại diện của kho tài liệu ViDoSeek.

## 2. Kế hoạch Lấy mẫu Đại diện (Stratified Sampling)
1. Lấy mẫu ngẫu nhiên tất định 30 tài liệu PDF từ ViDoSeek (bao gồm cả tài liệu văn bản sinh học, kỹ thuật, báo cáo nhiều cột, và tài liệu chứa bảng biểu/hình ảnh).
2. Kiểm tra tổng cộng khoảng 100–150 trang.

## 3. Các Phép Đo Cần Thu thập
1. **Phân bố độ dài ký tự Native Text:** Vẽ biểu đồ histogram độ dài ký tự của các trang có text layer thật so với trang scan.
2. **Đo đạc tỷ lệ Mojibake:** Kiểm tra tỷ lệ lỗi font encoding trên tập PDF thực tế.
3. **Đo đạc thời gian CPU:** Tính thời gian xử lý trung bình và phân vị 99th ($P_{99}$) của Tesseract OCR trên CPU máy trạm.
4. **Báo cáo kết quả:** Lập biên bản đo đạc, trình Tấn Phát và Thanh ký duyệt đóng băng ngưỡng tại M2.3 trước khi chạy Full OCR M2.6.
"""


def compute_hash_manifest(directory: Path) -> Path:
    manifest_path = directory / "hash_manifest.csv"
    files = sorted([f for f in directory.iterdir() if f.is_file() and f.name != "hash_manifest.csv"])
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "size_bytes", "sha256"])
        for file_path in files:
            data = file_path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            writer.writerow([file_path.name, len(data), sha])
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M1.8 OCR Quality Policy & Artifact Namespace Tool.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "evidence" / "revisions" / "m1.8-001",
        help="Target output directory for M1.8 revision artifacts.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Run simulated text quality evaluation probe.",
    )
    parser.add_argument(
        "--verify-namespace",
        type=str,
        help="Verify a canonical Run ID string against M1.7 naming specification.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print("QPAF Milestone 1.8 — OCR Quality Policy & Artifact Namespace Audit")
    print("================================================================================")

    if args.verify_namespace:
        try:
            parsed = parse_canonical_run_id(args.verify_namespace)
            print(f"[OK] Valid canonical Run ID: {parsed}")
            return 0
        except ValueError as err:
            print(f"[FAIL] Invalid Run ID: {err}")
            return 1

    if args.probe:
        print("[INFO] Running simulated OCR quality evaluation probe on representative mockups...")
        samples = [
            ("Clean academic body text with full late interaction details.", None, "Expected: NATIVE_TEXT_QUALIFIED"),
            ("Short title", None, "Expected: OCR_FALLBACK_TRIGGERED"),
            ("Corrupted" + ("\x00\x01\x02\x03\x04" * 15), None, "Expected: OCR_FALLBACK_TRIGGERED (Mojibake)"),
            ("", 35.0, "Expected: EXTRACTION_FAILED"),
        ]
        for idx, (txt, conf, desc) in enumerate(samples, 1):
            dec = evaluate_page_text(txt, confidence=conf)
            print(f"  [Sample {idx}] Route: {dec.route:<24} | Reason: {dec.reason:<36} ({desc})")

    # Generate calibrated policy revision package
    (output_dir / "ocr_checklist.md").write_text(generate_ocr_checklist_content(), encoding="utf-8")
    (output_dir / "ocr_failure_threshold.md").write_text(generate_ocr_failure_threshold_content(), encoding="utf-8")
    (output_dir / "artifact_namespace.md").write_text(generate_artifact_namespace_content(), encoding="utf-8")
    (output_dir / "calibration_methodology.md").write_text(generate_calibration_methodology_content(), encoding="utf-8")

    manifest_file = compute_hash_manifest(output_dir)

    print("--------------------------------------------------------------------------------")
    print(f"[EXPORT] OCR Checklist:          {output_dir / 'ocr_checklist.md'}")
    print(f"[EXPORT] OCR Failure Threshold:  {output_dir / 'ocr_failure_threshold.md'}")
    print(f"[EXPORT] Artifact Namespace:     {output_dir / 'artifact_namespace.md'}")
    print(f"[EXPORT] Calibration Method:     {output_dir / 'calibration_methodology.md'}")
    print(f"[EXPORT] Hash Manifest:          {manifest_file}")
    print("[STATUS] Milestone 1.8 Revision m1.8-001 Generated Successfully.")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
