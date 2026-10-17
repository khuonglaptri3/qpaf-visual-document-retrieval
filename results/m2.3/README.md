# M2.3 — OCR calibration và human review

Run được thực thi: `RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01`.
Trạng thái: **COMPLETE_BOUNDED_CALIBRATION**, policy vận hành đã FROZEN.
121 native đã chốt (95 PASS/25 HAS_ERRORS/1 NO_TEXT), 18 references giữ nguyên.
Chính sách: giữ native hợp lệ và bổ sung OCR 300 DPI ngoài vùng native,
confidence word từ60. Có21 review amendment của Codex AI; không giả chữ ký nhóm.

**Dùng tiếp:** [HTML cuối, có text theo policy](closure/2026-10-17-closed/index.html#reference),
[decision](closure/2026-10-17-closed/decision.json),
[121 trang sau policy](closure/2026-10-17-closed/resolved_pages.json),
[revision m2.3-002](../../evidence/revisions/m2.3-002/README.md),
[hợp đồng bàn giao](../../docs/superpowers/reports/2026-10-17-m23-downstream-handoff.md).
Các gói trong reviews/ và closure trước bản closed là lịch sử; gói closed
đã sửa parser TSV và kiểm hash byte config trên Windows. Không cần review lại.

Tái tạo package local vào thư mục mới, không gọi OCR/cloud:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/finalize_m23_calibration.py `
  --output results/m2.3/closure/<id-moi>
```

Các lệnh tạo/run calibration và workflow nhận review bên dưới được giữ làm
runbook lịch sử. Kết luận cuối nằm trong decision của gói closed/revision002;
summarizer nguyên bản chưa có quyết định freeze và vẫn dùng target41 lúc chạy.

## Nơi đọc

- [Đặc tả pipeline](../../docs/superpowers/specs/2026-10-17-m23-ocr-calibration-design.md).
- [Kế hoạch](../../docs/superpowers/plans/2026-10-17-m23-ocr-calibration.md).
- [Nhật ký](../../docs/superpowers/progress/2026-10-17-m23-ocr-calibration.md).
- [Giao diện có 18 bản sửa](reviews/2026-10-17-reference-qa-final/index.html#reference).
- [Giao diện ban đầu](review/index.html), vẫn chứa protocol 41-target và nháp browser cũ.

## Chạy và kiểm tra

Cài dependency CPU-only, không cần import Torch:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements/m23-modal.lock
```

Chuẩn bị mẫu, chưa gọi Modal:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m23_calibration.py --prepare-only
```

Chạy một prepared run với cùng config/source; dùng paid CPU hoặc credit Modal:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m23_calibration.py `
  --execute-prepared results/m2.3/<run-id>
```

Không dùng lại run đã thực thi. Lệnh không có `--prepare-only` cũng tạo mẫu mới
và thực thi ngay. Không tự dùng GPU hoặc retry khi có lỗi.

Xác minh dữ liệu đã tải về, không gọi cloud:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m23_calibration.py `
  --verify results/m2.3/RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01
```

Tạo lại giao diện ổn định mà không chạy OCR:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m23_calibration.py `
  --build-review results/m2.3/RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01
```

## Người dùng cần review

1. Mở `reviews/2026-10-17-reference-qa-final/index.html` bằng Chrome/Edge.
2. Bước 2: còn native STT 37, 49, 50, 67, 93, 104, 109, 112 cần chốt;
   đổi tên reviewer thành tên mình trước khi lưu kết luận mới.
3. Bước 4: đã có đủ 18 bản sửa và xác nhận, gồm một trang không chữ.
4. Có thể so native/OCR 150/OCR 300 trong dropdown. Bản nháp không được chấm;
   sửa nội dung hủy xác nhận. Vùng chọn không tự chấm với output toàn trang.
5. Bấm **Xuất đánh giá**, giữ JSON tải xuống rồi bàn giao để tổng hợp.

Nháp ở localStorage không tự ghi vào repo; chuyển máy cần xuất/nhập JSON.
Prototype M2.2 trước đó có namespace khác, không được nhập thành nhãn M2.3.

## Tổng hợp sau khi review

Bộ 18 hiện tại đã có summary và 54 dòng metrics trong package bản sửa.
Tái tạo bằng `scripts/repair_m23_references.py --output <thu-muc-moi>`.
Summarizer nguyên bản bên dưới vẫn kiểm tra 41-target của run đã khóa;
thiếu references theo lệnh này không phải yêu cầu người dùng làm thêm 23 trang.

```powershell
.venv/Scripts/python.exe -X utf8 scripts/summarize_m23_reviews.py `
  --run results/m2.3/RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01 `
  --reviews <duong-dan-file-JSON-da-xuat> `
  --output results/m2.3/reviews/<summary-id-moi>
```

Mỗi lần tổng hợp dùng thư mục mới. Công cụ kiểm tra đúng IDs/hash/mẫu rồi ghi
review nguồn, page metrics, report, summary và hashes. Thiếu review hoặc bản chữ
thì trả `HUMAN_REVIEW_INCOMPLETE`; đủ review vẫn chưa tự đóng băng threshold.
Dev/holdout/regression được báo riêng, không dùng nhãn test hoặc oracle.

## Artifact layout

```text
<run-id>/
  resolved_config.json, source.json, source_snapshot.zip
  inputs/                  # PDFs, native/probes, sample manifest, hashes
  execution_started.json
  remote/
    images150/, images300/ # ảnh render có hash, ngoài Git
    ocr/150/, ocr/300/      # txt, TSV bbox/confidence, stderr, ngoài Git
    pages.json             # từng đầu ra, command, thời gian, confidence, trạng thái
    environment.json, source.json, resolved_config.json
    errors.json, resources.json, summary.json, hashes.json
  review/index.html, review/workspace.json
  summary.json, verification.json, hashes.json
review/                    # HTML hiện hành, trỏ đến ảnh của run được chọn
reviews/<summary-id>/      # JSON review và tổng hợp, tạo sau người dùng review
verification/              # test/runtime receipts
```

Remote Volume: `qpaf-m23-ocr-artifacts`, `runs/<run-id>/output/` và `inputs/`.
Clone Git không có PDFs/ảnh/raw OCR/HTML; cần payload local/Volume để xác minh
hoặc tạo lại giao diện. Giữ nguyên run đã khóa và bằng chứng M1/M2.2.
