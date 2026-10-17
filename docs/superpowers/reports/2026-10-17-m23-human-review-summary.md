# M2.3 — Tổng hợp JSON review của Khuong

**Cập nhật phạm vi sau báo cáo:** người dùng đã chọn giữ 18 bản chữ đã làm ở
bước 4, thay yêu cầu 41. Đã tự nhận bản mới và có
[nhận xét 18 trang](2026-10-17-m23-18-page-review.md). Số đếm và các mục
còn thiếu bên dưới thuộc export `11-07-38-920Z` theo protocol 41 trang cũ; xem
[điều chỉnh phạm vi](../specs/2026-10-17-m23-ocr-calibration-design.md).

**Kết luận: M2.3 chưa hoàn tất; trạng thái `HUMAN_REVIEW_INCOMPLETE`.**
Phần triển khai và lấy dữ liệu đã có bằng chứng kỹ thuật. File người dùng bàn
giao có 113/121 kết luận native đã chốt, còn 8 trang cần xử lý và 41/41 bản chữ
toàn trang bắt buộc chưa xác nhận. Chưa có CER/WER để chọn DPI hoặc freeze ngưỡng.

## Nguồn và xác minh

- File nhận: `C:/Users/lanph/Downloads/m23-review-2026-10-17T11-07-38-920Z.json`.
- Reviewer: `Khuong`; thời điểm export: `2026-10-17T11:07:38.919Z`.
- Run: `RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01`.
- SHA-256 file nhận: `e7b25eb72884392175ba7426121655a19914539519697cfd39b4c63b5ffc7b53`.
- Dataset SHA-256: `dd5423699964e723daeca36d6a1309ff7ef343bd4c75087d4d63b6bacbd25c94`.
- Summarizer đã xác minh remote manifest, ảnh, dataset/run, 121 page IDs và
  các trường ký xác nhận; chạy thành công với exit code 0.
- [Summary máy đọc](../../../results/m2.3/reviews/2026-10-17T110738920Z-khuong/summary.json),
  [bản review lưu lại](../../../results/m2.3/reviews/2026-10-17T110738920Z-khuong/human_reviews.json),
  [manifest kết quả](../../../results/m2.3/reviews/2026-10-17T110738920Z-khuong/hashes.json).
  Bản lưu JSON được serializer định dạng lại; hash file nguồn nằm trong summary.

## Đã làm được

- Khóa mẫu 30 PDF /120 trang chính và 1 trang regression; tách development,
  holdout theo PDF; có IDs/hashes, native text và ảnh review.
- Chạy đủ 242 OCR attempts ở 150/300 DPI, 0 lỗi kỹ thuật ở run chọn; có raw
  text/TSV, số đo thời gian/RSS và bằng chứng runtime. Xem
  [báo cáo kỹ thuật](2026-10-17-m23-ocr-calibration.md).
- Bàn giao JSON review thật, được backend chấp nhận đúng namespace; 114 trang
  có đánh giá đã lưu, gồm 1 `UNSURE`. Có 113 trang đã chốt Đạt/Có lỗi (93.39%).

| Split | Tổng trang | PASS | HAS_ERRORS | PENDING | UNSURE | Reference bắt buộc đã xác nhận |
|---|---:|---:|---:|---:|---:|---:|
| Development | 80 | 70 | 5 | 5 | 0 | 0/30 |
| Holdout | 40 | 37 | 1 | 2 | 0 | 0/10 |
| Regression | 1 | 0 | 0 | 0 | 1 | 0/1 |
| Tổng | 121 | 107 | 6 | 7 | 1 | 0/41 |

Sáu đánh giá `HAS_ERRORS` đều ghi loại lỗi `missing` (thiếu nội dung). Đây là
lỗi của native text do người review ghi nhận; chưa có tham chiếu để xác định
OCR150/OCR300 khắc phục được bao nhiêu. Không suy rộng tỷ lệ lỗi mẫu thành tỷ lệ
lỗi toàn corpus vì mẫu được chọn có chủ đích.

## Tám trang cần chốt ở bước 2

STT là vị trí trong danh sách 121 trang của JSON, tính từ 1, khi không lọc.
`page_XXXX` là số trang trong PDF tương ứng.

| STT | Page ID | Trạng thái |
|---|---|---|
| 37 | `011e012b28d60278c243b200eaf19952a725370c_page_0001` | PENDING |
| 49 | `01ada48daaf576de7e173f212b032ab06b742e24_page_0001` | PENDING |
| 50 | `01ada48daaf576de7e173f212b032ab06b742e24_page_0002` | PENDING |
| 67 | `0295f1ca960d29e2327e90a848235693d965d308_page_0013` | PENDING |
| 93 | `03e90a945dafd353e9d86b46ca2774a29149048d_page_0001` | PENDING |
| 104 | `0454efb78bc1e03ae39f9552cb4c165495b11e4b_page_0012` | PENDING |
| 109 | `048ce9cbabf9b58c9764e8be143b7196b5478ac1_page_0007` | UNSURE, regression |
| 112 | `04d14102144bfa97bf1f2e41bda7986bd3f712c1_page_0013` | PENDING |

Năm trong bảy trang PENDING đã đánh dấu xem ảnh nhưng chưa có reviewer/thời
điểm lưu; hai trang STT 93/104 chưa đánh dấu xem ảnh. Các trang 93/104/112 có
nháp issue `missing`, chưa phải kết luận `HAS_ERRORS` đã ký.

Sáu trang Có lỗi đã lưu nằm ở STT 33, 90, 99, 110, 111, 113. Không cần đổi
những kết luận này thành PASS để hoàn tất review; cần giữ đúng lỗi quan sát được.

## Phần còn thiếu để hoàn tất M2.3

1. Trong [HTML review](../../../results/m2.3/review/index.html), nhập lại JSON
   nếu cần, chốt/lưu 7 trang PENDING và xử lý 1 trang UNSURE ở bước 2.
2. Vào **04 — Bản chữ đối chiếu**, chọn **Cần bản chữ đối chiếu**. Kiểm tra/sửa
   theo ảnh và xác nhận đủ 41 bản toàn trang: 30 development, 10 holdout,
   1 regression. Cả 121 reference trong file hiện đều DRAFT và text rỗng;
   chỉ 41 trang thuộc tập bắt buộc. Bước 2 PASS không thay thế bước xác nhận này.
   Trang thực sự không chữ cần xác nhận riêng theo ảnh.
3. Xuất JSON mới, tổng hợp CER/WER native/OCR150/OCR300 riêng cho từng split,
   phân tích lỗi và đề xuất ngưỡng trên development, đánh giá holdout độc lập.
4. Review quyết định và tạo revision ngưỡng khi đủ điều kiện. Hiện
   `thresholds_frozen=false`, `aggregates=[]`; không có chỉ số chất lượng để
   kết luận DPI tốt hơn hoặc nghiệm thu calibration.

Chỉ đọc và tổng hợp payload local trong lần này; giữ nguyên run và revision
`m2.3-001`. Báo cáo này ghi nhận tiến độ review, chưa phải revision nghiệm thu.
