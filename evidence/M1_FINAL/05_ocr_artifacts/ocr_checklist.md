# M1.8 — OCR calibration checklist

**Status: DRAFT. Owner: Khương. Planned freeze: 25/09/2026.**

Đây là quy tắc chuẩn bị; chưa có OCR engine/version, mẫu calibration hoặc kết
quả chất lượng/thời gian thực tế. Full OCR là công việc M2.6 theo Milestones.

## Chuẩn bị

- [ ] Nhận corpus/split policy và page/alias manifest đã được review.
- [ ] Ghi engine/parser/rendering version, language, DPI, preprocessing,
      hardware và config hash; không tự đổi phiên bản giữa các run.
- [ ] Chọn mẫu giới hạn có nguồn gốc, đại diện PDF text/scan/image theo corpus
      thật; không dùng confirmation/external labels để chọn ngưỡng.
- [ ] Chốt cách đánh giá chất lượng và nguồn tham chiếu với protocol owner.

## Quy tắc trích xuất đề xuất

1. Thử native text với PDF có text layer; ghi phương pháp và chất lượng quan sát.
2. Chỉ dùng OCR khi trang là scan/image hoặc native text không đạt tiêu chí đã
   calibration. Không dùng một số ký tự tùy ý làm ngưỡng đã được chứng minh.
3. Lưu page ID, phương pháp chọn, lý do fallback, engine/config và source hash.
4. Ghi rõ trang lỗi/timeout/không có text; không bỏ trang âm thầm hoặc chuyển lỗi
   thành chuỗi rỗng rồi tính như thành công.
5. Giữ page/alias identity ổn định để qrels và retrieval cache dùng cùng dữ liệu.

## Đầu ra calibration

- [ ] Số trang thử, số trang đạt/lỗi, các loại lỗi và mẫu cụ thể.
- [ ] Thời gian theo trang, bộ nhớ và giới hạn tài nguyên quan sát.
- [ ] Chất lượng native text/OCR theo cách đo đã chọn, kèm per-page record.
- [ ] Ngưỡng thất bại được giải thích bằng kết quả thực nghiệm.
- [ ] Hash output, lệnh chạy, config, commit và review trước khi freeze.
