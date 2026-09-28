# M1.8 — OCR Failure Thresholds & Metric Definitions

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
| **Độ tin cậy OCR** | $S_{conf}$ | $\frac{1}{|W|} \sum_{w \in W} \text{conf}(w)$ | $S_{conf} \ge 60.0\%$ | Đánh dấu cảnh báo chất lượng thấp |
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
