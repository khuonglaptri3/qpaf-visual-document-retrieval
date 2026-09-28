# M1.8 — Calibration Methodology for Milestone M2.3

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
