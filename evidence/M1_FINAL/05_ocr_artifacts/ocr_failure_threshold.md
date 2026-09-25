# OCR failure thresholds

**Status: DRAFT — thresholds not calibrated or approved.**

| Đại lượng | Bằng chứng để chọn ngưỡng | Trạng thái |
| --- | --- | --- |
| Native text đủ chất lượng để bỏ OCR | Mẫu PDF có text layer và kiểm tra chất lượng | Chưa có mẫu |
| OCR đạt chất lượng nội dung | Tiêu chí và tham chiếu được protocol chấp nhận | Chưa có protocol/calibration |
| Timeout và tài nguyên từng trang | Runtime/memory từ bounded calibration | Chưa đo |
| Tỉ lệ trang lỗi cho phép trong full run | Phân bố lỗi, ảnh hưởng coverage và quy tắc retry | Chưa chốt |

Không có giá trị số được freeze trong file này. M1.8 chưa hoàn tất chỉ vì file
đã tồn tại. Cần cập nhật kết quả calibration, căn cứ, ngày và người review.

Quy tắc xử lý đề xuất: lỗi đọc, timeout và output không hợp lệ phải có failure
record; source/hash/ID không nhất quán phải dừng bước sử dụng đầu ra đó để
kiểm tra. Retry dùng run ID mới, giữ lần lỗi cũ và liên kết lý do retry.

Sau Protocol Freeze, thay đổi ngưỡng phải ghi nội dung, lý do, ngày và người
approve. Không chỉnh ngưỡng theo kết quả confirmation/external evaluation.
