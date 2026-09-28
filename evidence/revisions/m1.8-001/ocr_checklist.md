# M1.8 — OCR Calibration & Quality Checklist

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
