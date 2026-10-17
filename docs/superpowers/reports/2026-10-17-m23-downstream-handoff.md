# M2.3 — Đầu vào cụ thể cho M2.4, M2.6 và M2.8

M2.3 đã hoàn tất hiệu chuẩn có giới hạn. Điểm vào duy nhất:
[handover.json của m2.3-002](../../../evidence/revisions/m2.3-002/handover.json).
Manifest này khóa policy hash và identity của bộ text mẫu sau xử lý.

## M2.4 đọc gì?

- Config: `configs/m2.3/ocr_policy_frozen.toml`; kiểm hash từ handover trước khi nạp.
- Dữ liệu mẫu: `evidence/revisions/m2.3-002/resolved_pages.json`, đúng121 page IDs
  của run cũ. Đây là bộ thử loader/feature/quality states, không phải toàn corpus.
- Các trường cần giữ:

| Trường | Ý nghĩa |
|---|---|
| `page_id`, `document_id`, `page_number` | Khóa trang để nối với corpus/qrels đúng namespace |
| `text`, `text_sha256` | Văn bản sau policy; dùng thống nhất cho các đặc trưng text |
| `text_source` | `native`, `native+ocr` hoặc `ocr` |
| `extraction_status` | `NATIVE_TEXT_USED`, `NATIVE_PLUS_OCR`, `OCR_TEXT_USED`, `NO_TEXT_DETECTED`; trạng thái lỗi được lưu riêng khi phát sinh |
| `technical_failure`, `reason` | Lỗi engine/render/parse/timeout không được biến thành thành công rỗng |
| `warnings` | Cảnh báo confidence/encoding/no-text, không đồng nghĩa lỗi kỹ thuật |
| `policy_sha256` | Cấu hình tiền xử lý gắn với từng trang |
| `pdf_sha256`, `image_sha256`, `native_text_sha256`, `raw_ocr_text_sha256` | Truy vết nguồn và đầu ra gốc |

Ví dụ nạp và kiểm dữ liệu mẫu:

```python
import json
from pathlib import Path
from qpaf.m23.policy import load_frozen_policy

root = Path('.')
handover = json.loads((root / 'evidence/revisions/m2.3-002/handover.json').read_text(encoding='utf-8'))
policy = load_frozen_policy(root / handover['policy']['path'], handover['policy']['sha256'])
pages = json.loads((root / handover['sample_pages']['path']).read_text(encoding='utf-8'))
assert all(page['policy_sha256'] == handover['policy']['sha256'] for page in pages)
```

M2.4 vẫn lấy query/split/qrels từ M2.1 và điểm retriever từ cache tương ứng.
18 bản chép tay không phải relevance labels. Trang `NO_TEXT_DETECTED` có thể
có nội dung hình/scene text; giữ page ID và visual input, xử lý text rỗng
theo quy ước feature hiện có, không bỏ trang khỏi candidate namespace.

## M2.6 thực thi gì?

1. Kiểm parser 4.30.0, engine 5.3.0 và traineddata SHA đã chốt.
2. Render/OCR 300 DPI, OEM 3/PSM 3/eng, 1 thread/subprocess, 2 workers,
   cap **15 giây/OCR subprocess**. Lượt calibration cũ dùng 120s làm
   giới hạn thăm dò; max đo được7.329s. Render không bị gọi nhầm là cùng deadline.
3. Dùng `extract_native_geometry(pdf, page_number, native_sha256)` để lấy
   rectangles đúng crop origin. `rectangles_to_pixels` hỗ trợ rotation 0/90/180/270.
4. Đọc raw TSV bằng `QUOTE_NONE` qua `tsv_words` và `parse_tsv`; gọi
   `resolve_page(native, ocr, words, geometry, image_size, policy['routing'])`.
5. Giữ raw outputs và một record cho mọi trang. `enforce_failure_cap` áp dụng
   ngưỡng lỗi kỹ thuật1% trên tất cả trang đã lên lịch; lỗi render không được
   biến mất khỏi mẫu số. Full-corpus renderer/scheduler phải đưa lỗi render
   vào records trước bước kiểm cap này.

Không sửa config/run của M1.1/M2.2 để giả chúng đã dùng policy mới. Legacy
config validator vẫn yêu cầu PROVISIONAL; code mới nạp policy qua loader M2.3.

## M2.8 khóa gì?

Khóa `policy_sha256` và hash text trong cache metadata. Text đã thay đổi so
với smoke M2.2 nên cần cache text mới. Hai cấu hình QARF/QPAF phải dùng chung
text/page IDs/features/cache; không dùng hai phiên bản tiền xử lý khác nhau.

Giới hạn: 121 trang mẫu chỉ hỗ trợ tích hợp ban đầu. Hiệu quả retrieval thật,
cache toàn corpus và learned training thuộc các milestone sau.
