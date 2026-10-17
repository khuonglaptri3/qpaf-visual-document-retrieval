# M2.3 — Nhật ký thiết kế review thủ công

## 2026-10-17 — Prototype bước 2 và bước 4

- Người dùng yêu cầu thiết kế hai màn hình để xem và góp ý trước.
- Tạo prototype HTML offline từ 16 trang thật của mẫu M2.2. Không chạy OCR mới,
  không chọn mẫu calibration M2.3, không gọi Modal hoặc encoder GPU.
- Bước 2: ảnh/native song song, zoom, kết luận, loại lỗi, ghi chú, người review.
- Bước 4: bản chữ nháp/xác nhận, phạm vi toàn trang/vùng chọn, so đầu ra máy;
  CER/WER chỉ có khi reference được xác nhận và có đầu ra cùng phạm vi.
- Thêm localStorage và JSON export/import với kiểm tra IDs/hashes; ảnh được
  nhúng để mở file HTML trực tiếp không cần server.
- Native gốc được giữ riêng với text sau OCR. Chỉ 3 trang có OCR 150 DPI đã đo;
  OCR 300 DPI hiển thị chưa chạy. Không tạo dữ liệu hoặc nhãn giả.
- Builder: `.venv/Scripts/python.exe -X utf8 scripts/build_m23_review_demo.py`.
- Kiểm thử bằng Edge headless qua Playwright: 9 nhóm kiểm tra hành vi PASS,
  gồm trạng thái xác nhận, round-trip export/import, metric và mobile.
- Đã xem hai ảnh chụp desktop để kiểm tra bố cục. Output:
  `results/m2.3/review-demo-2026-10-17/index.html`, ảnh dưới `previews/`.
- Spec: [thiết kế hai màn hình](../specs/2026-10-17-m23-manual-review-design.md).
- Trạng thái: **chờ người dùng review thiết kế**, chưa nghiệm thu M2.3.
