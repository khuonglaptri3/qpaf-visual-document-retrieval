# M2.3 — Thiết kế hai màn hình review thủ công

Trạng thái: **PROTOTYPE — chờ người dùng review thiết kế**.
Đây là giao diện hoạt động trên dữ liệu M2.2 đã có, không phải run hiệu chuẩn
M2.3 hoặc bản chữ tham chiếu đã được nghiệm thu.

**Cập nhật sau triển khai:** pipeline đã có dữ liệu M2.3 thật. Link HTML cũ bên
dưới chuyển đến [workspace review hiện hành](../../../results/m2.3/review/index.html).
Phần mô tả prototype 16 trang được giữ làm lịch sử thiết kế; xem
[đặc tả pipeline thật](2026-10-17-m23-ocr-calibration-design.md). Có thể tái tạo
prototype bằng builder với `--output` riêng, không ghi đè workspace đang review.

## Mở bản thiết kế

Mở bằng Chrome/Edge:
[`results/m2.3/review-demo-2026-10-17/index.html`](../../../results/m2.3/review-demo-2026-10-17/index.html).
Trang HTML tự chứa ảnh và dữ liệu, không cần server hay kết nối mạng.

Hai mục ở thanh trái:

1. **02 — Kiểm tra native text:** xem ảnh cạnh chữ lấy trực tiếp từ PDF; chọn
   Đạt / Có lỗi / Trang không có chữ / Chưa chắc; ghi loại lỗi và ghi chú.
2. **04 — Bản chữ đối chiếu:** chép hoặc sửa bản chữ theo ảnh, chọn toàn trang
   hay vùng được mô tả, rồi xác nhận trước khi tính CER/WER.

Ảnh xem trước do trình duyệt chụp:
[bước 2](../../../results/m2.3/review-demo-2026-10-17/previews/native-review.png),
[bước 4](../../../results/m2.3/review-demo-2026-10-17/previews/reference-review.png).
Ảnh bước 4 hiển thị native làm **bản nháp**, không phải nhãn đúng đã duyệt.

## Dữ liệu dùng để thiết kế

- 16 trang thật của run `RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01`.
- Native lấy từ `inputs/pages.json`, trước khi OCR thay text trong prepare.
- Ảnh render 150 DPI từ mẫu M2.2, kiểm tra SHA-256 trước khi nhúng vào HTML.
- OCR 150 DPI chỉ có ở 3 trang đã chạy OCR trong M2.2, gồm một đầu ra rỗng.
- OCR 300 DPI luôn ghi **chưa chạy**. Không tạo hoặc giả lập số đo cho phần này.
- Chưa chọn mẫu M2.3 30 PDF / 100–150 trang, chưa chạy OCR mới hoặc gọi Modal.

## Cách người dùng review

### Bước 2: kiểm tra chữ gốc

1. Điền tên người review ở góc trên.
2. Chọn trang bên trái hoặc dùng Trang trước / Trang tiếp. `Alt+←/→` cũng chuyển trang.
3. Phóng to ảnh để xem đủ chữ; đối chiếu nội dung, số, thứ tự đọc, vùng bị thiếu.
4. Chọn kết luận. Với Có lỗi, cần ít nhất một loại lỗi hoặc ghi chú.
5. Đánh dấu đã xem ảnh đủ rõ rồi bấm **Lưu đánh giá**.

Đã review không đồng nghĩa đã đạt: Có lỗi và Chưa chắc vẫn được giữ riêng để
lọc kiểm tra tiếp. Chỉnh một đánh giá đã lưu đưa trang về trạng thái chưa review
cho đến khi người dùng lưu lại. Ghi chú nháp được giữ trong trình duyệt.

### Bước 4: tạo bản chữ đối chiếu

1. Đọc ảnh, nhập bản chữ đúng; có thể dùng native làm nháp để giảm công gõ.
2. Kiểm tra toàn bộ phần định xác nhận, nhất là số, dấu và thứ tự đọc.
3. Nếu chỉ chép một vùng, chọn Vùng chọn và mô tả vùng đó. Không dùng bản chữ
   này để chấm với text toàn trang.
4. Nếu toàn trang không có nội dung chữ, dùng xác nhận riêng và để text rỗng.
5. Đánh dấu đã đối chiếu toàn bộ rồi bấm **Xác nhận bản chữ đúng**.

Bản nháp không có chỉ số chất lượng. Sửa nội dung/phạm vi/xác nhận không chữ
đưa bản đã xác nhận về nháp, xóa hiệu lực xác nhận cũ. Chỉ bản full-page đã xác
nhận và có đầu ra máy mới được chấm tự động trong prototype.

## Lưu và bàn giao

- Trình duyệt giữ nháp theo hash mẫu bằng localStorage, không sửa file nguồn.
- Bấm **Xuất đánh giá** để tải JSON xuống, giữ bản sao và bàn giao. Đây là thao
  tác cần làm trước khi chuyển máy hoặc xóa dữ liệu trình duyệt.
- **Nhập đánh giá** kiểm tra schema, dataset hash, source run, page IDs, hash ảnh
  và các trường xác nhận. File không thuộc đúng mẫu bị từ chối.
- JSON chứa reviewer, thời gian, kết luận native, lỗi/ghi chú, reference text,
  phạm vi và trạng thái xác nhận; không nhúng ảnh.
- Nếu localStorage bị chặn hoặc đầy, giao diện báo lỗi; xuất JSON vẫn là cách
  lưu độc lập. Prototype không tự ghi JSON vào một thư mục trên máy.

## Chỉ số trong prototype

`CER = Levenshtein(ký tự máy, ký tự tham chiếu) / số ký tự tham chiếu`.
WER tương tự trên token tách theo khoảng trắng. Chuẩn hóa NFC, trim/collapse
khoảng trắng; giữ chữ hoa/thường, số, dấu câu và dấu tiếng Việt. Giá trị có thể
vượt 100% khi đầu ra có nhiều ký tự/từ thừa.

Với tham chiếu không chữ, CER/WER không áp dụng; thay bằng số ký tự máy nhận
thừa. Với vùng chọn, chưa có đầu ra vùng tương ứng nên không tự tính chỉ số.
Để giữ trình duyệt phản hồi, bản mẫu giới hạn phép tính edit-distance còn lại
ở 4 triệu ô sau khi bỏ prefix/suffix giống nhau; vượt giới hạn hiển thị rõ,
không thay bằng một số đo giả.

Đây là công cụ hỗ trợ nhập/review, không tự xác minh người review đã chép đúng.
Calibration thật còn cần protocol, mẫu độc lập, kiểm tra bản tham chiếu và review
ngưỡng như đề xuất M2.3.

## Code và tái tạo

| Thành phần | File |
|---|---|
| HTML/CSS/JavaScript của hai màn hình | [`src/qpaf/m23/review_template.html`](../../../src/qpaf/m23/review_template.html) |
| Builder offline, không import Torch/Modal | [`scripts/build_m23_review_demo.py`](../../../scripts/build_m23_review_demo.py) |
| Kiểm tra hành vi bằng browser | [`tests/browser/m23_review_demo.cjs`](../../../tests/browser/m23_review_demo.cjs) |
| Nguồn và hash HTML đã sinh | [`demo_manifest.json`](../../../results/m2.3/review-demo-2026-10-17/demo_manifest.json) |

Từ gốc repo, dùng payload M2.2 đã có ở local:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/build_m23_review_demo.py
```

HTML nhúng ảnh khoảng 14 MB và screenshots không đưa vào Git; template, builder,
spec và manifest được quản lý bằng Git. Không sửa run M2.2 hoặc revision đã khóa.

Kiểm thử browser dùng Playwright cài tạm ngoài dependencies dự án và Edge có
sẵn trên máy:

```powershell
npm.cmd install --prefix .superpowers/m23-review-browser --no-save --package-lock=false playwright
$env:PLAYWRIGHT_MODULE = (Resolve-Path '.superpowers/m23-review-browser/node_modules/playwright').Path
node tests/browser/m23_review_demo.cjs
```

Đã kiểm thử: mở bằng file URL, ảnh thật, lưu và khôi phục native review, kiểm tra
điều kiện xác nhận, bản nháp không được chấm, chỉnh bản chuẩn hủy xác nhận,
vùng chọn và trang không chữ, OCR chưa có, JSON export/import, từ chối hash khác,
Unicode/edit distance, desktop/mobile. Không có lỗi JavaScript hoặc HTTP ngoài.

Các điểm để người dùng góp ý: cách bố trí ảnh/chữ, mức phóng to, danh sách lỗi,
thao tác chép chữ đúng, phạm vi vùng chọn và cách xuất/bàn giao đánh giá.
