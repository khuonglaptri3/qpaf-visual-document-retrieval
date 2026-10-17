# ViMDoc OCR và page identity — specification v1

Ngày đóng băng specification: 2026-09-10. Phạm vi: chuẩn bị local; chưa audit archive thật, chưa OCR, không Modal/GPU và không training.

## Quyết định

`configs/vimdoc_ocr_page_identity_v1.json` là specification dùng cho extraction package tương lai. Nó giải quyết hai câu hỏi thiết kế: văn bản nào đi vào BM25/BGE-M3, và một ảnh ViMDoc được nhận diện như thế nào khi nhiều file có cùng stem. Specification đã chốt; bằng chứng thực thi trên archive 17,5 GB vẫn chưa có nên M3 execution vẫn `BLOCKED`.

Official HEAVEN revision `3eea5ca61f492d3fa18594d455ee10024932f851` gọi `pytesseract.image_to_string` cho từng ảnh, xuất plain text, rồi dùng OCR cho textual encoders gồm BGE-M3. Vì vậy protocol này dùng Tesseract plain text, **không gọi là Markdown**. Reference source `indexing/encode/ocr.py` có 2.864 bytes và SHA-256 `eabe9cffc6d82f2634ec07d8b579c26dfd96acab4565fba5a5c9c618cac7922b` tại revision trên.

Các default ngầm của reference được viết thành tham số rõ: Debian 12 Bookworm; `tesseract-ocr=5.3.0-2`; English traineddata `1:4.1.0-2`; `pytesseract=0.3.13`; Pillow `11.3.0`; `lang=eng`; `--oem 3 --psm 3`; load ảnh bằng Pillow và convert RGB. Thay đổi engine, language, PSM, OCR model/data hoặc image conversion tạo protocol version mới. Worker count và per-page timeout chỉ ảnh hưởng vận hành nhưng phải được đóng băng sau calibration; hiện để `null`, do đó chưa có quyền chạy.

Reference HEAVEN trả chuỗi rỗng khi OCR exception. Protocol này không chấp nhận cách đó: exception/timeout/decode failure là `ERROR`, tạo failure evidence và không được tạo success marker. Một lần OCR thành công nhưng thật sự không có text là `SUCCESS_EMPTY`; giữ lại và báo riêng. Chỉ chuẩn hóa CRLF/CR thành LF, không `strip`, không Unicode normalization. Mọi row chứa `text_sha256` trên UTF-8 bytes. BM25 và BGE-M3 phải trỏ tới cùng một OCR JSONL hash; ColQwen2.5 trỏ tới cùng canonical asset manifest hash.

## Page identity

Archive member hợp lệ có dạng chính xác `pages/<filename>` và extension `.jpg`, `.jpeg` hoặc `.png` (case-insensitive). Không cho absolute path, nested path, backslash, NUL, `.`/`..`, symbolic/hard link hoặc duplicate member path. Không normalize tên Unicode/path.

- `asset_path`: nguyên tar member name; sort bằng UTF-8 bytes.
- `asset_sha256`: SHA-256 của uncompressed image bytes; `asset_id` chính là digest này.
- `page_id`: filename bỏ đúng một extension cuối; giữ nguyên các dấu chấm khác.
- `page_number`: suffix sau `_` cuối, bắt buộc ASCII decimal; parse thành integer chỉ để audit.
- `document_id`: bỏ đúng suffix `_page_number`, phù hợp HEAVEN mapping.
- Ranking/gradient tie vẫn dùng `page_id` theo UTF-8-byte ascending, không dùng numeric page order.

Nếu nhiều assets có cùng `page_id` và cùng content hash, chúng là aliases của một page. Canonical asset là `asset_path` nhỏ nhất theo UTF-8 bytes; mọi alias vẫn được ghi trong manifest. Nếu cùng `page_id` nhưng content hash khác nhau, audit `BLOCK`: không ưu tiên `.png`/`.jpg`, không thêm suffix, không average và không bỏ file. Nếu cùng content nhưng khác `page_id`, giữ tất cả page identities và báo duplicate-content group; không gộp vì identity chính thức khác nhau.

## Evidence contract

Future page audit phải kiểm tra live archive hash và tái tạo đúng 76.347 assets, 70.080 pre-audit stems, 6.267 extra assets và 1.247 document IDs. Quan trọng nhất là `different_content_collision_count=0`; con số này hiện chưa biết từ metadata cũ. Output canonical rows gồm page/document/number, canonical path, content hash, bytes và aliases; không nhận qrels.

Future OCR phải có đúng một `SUCCESS_*` row cho mỗi canonical page, đúng thứ tự page ID; không duplicate/missing/extra/ERROR. Runtime manifest phải ghi image digest, package versions, `tesseract --version`, `eng.traineddata` hash, resource parameters và output hashes. Validation lần hai phải tái tạo canonical asset/OCR JSONL hashes.

`scripts/validate_vimdoc_ocr_page_identity.py` chỉ đọc: nó có thể inspect một tar được cung cấp hoặc validate identity/OCR manifests và in JSON ra stdout. Nó không import Pillow, pytesseract, Torch, Modal hay network client; không chạy OCR và không ghi file.

```powershell
C:\Python313\python.exe scripts\validate_vimdoc_ocr_page_identity.py --inspect-tar <PATH_TO_ViMDoc_pages.tar.gz>
C:\Python313\python.exe scripts\validate_vimdoc_ocr_page_identity.py --validate-ocr <OCR_JSONL> --identity <IDENTITY_JSON>
$env:PYTHONPATH = 'src'
C:\Python313\python.exe -m pytest tests/test_vimdoc_ocr_page_identity.py -q
```

Exit `0` là validation pass, `2` là malformed/input drift, `3` là collision khác content. Đây không phải execution approval. Bước tiếp theo sau specification này là chạy **content audit** ở nơi archive đã tồn tại, nhưng việc đó phải thuộc một execution/resource package riêng nếu dùng Modal.
